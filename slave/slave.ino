// ═══════════════════════════════════════════════════════════
//  SLAVE — Tesla Lab BALAM 2026
//  Comunicación con maestro por Serial0 (GPIO1/GPIO3)
//  ¡No usar monitor serial en el slave durante pruebas!
// ═══════════════════════════════════════════════════════════

#include <Adafruit_NeoPixel.h>
#include <Wire.h>
#include "esp32-hal-ledc.h"

// ── Pines placa Tesla Lab ────────────────────────────────────
#define PIN_M1_PWM    15
#define PIN_M1_AIN1    5
#define PIN_M1_AIN2   18
#define PIN_M2_PWM     2
#define PIN_M2_BIN1   27
#define PIN_M2_BIN2   14
#define PIN_M3_PWM    12
#define PIN_M3_AIN1   32
#define PIN_M3_AIN2   33
#define PIN_M4_PWM    13
#define PIN_M4_BIN1   25
#define PIN_M4_BIN2   26
#define PIN_SERVO1     4
#define PIN_NEOPIXEL  23
#define PIN_N_MOT     36
#define PIN_N_ESP     39
#define PIN_FUNCTION  34

// ── I2C ──────────────────────────────────────────────────────
#define I2C_SDA       21
#define I2C_SCL       22
#define I2C_FREQ      100000UL

// ── Comandos ─────────────────────────────────────────────────
#define CMD_PWM       0x01
#define CMD_DIGITAL   0x02
#define CMD_SERVO     0x03
#define CMD_NEOPIXEL  0x04
#define CMD_ADC       0x05
#define CMD_I2C_SCAN  0x06
#define CMD_PING      0xF0
#define CMD_RESET     0xFF

#define ACK_OK   0xAA
#define ACK_ERR  0xEE

Adafruit_NeoPixel pixel(1, PIN_NEOPIXEL, NEO_GRB + NEO_KHZ800);

void processCommand(uint8_t cmd, uint8_t pinId, uint8_t value);
int  pinIdToGpio(uint8_t pinId);
void sendResponse(uint8_t ack, uint8_t cmd, uint8_t val);
void cmdI2CScan();

void setup() {
    // Usar Serial0 (USB) para comunicación con el maestro
    // ¡NO abrir monitor serial en el slave durante pruebas!
    Serial.begin(9600);

    // Salidas digitales motores (TODOS disponibles)
    pinMode(PIN_M1_AIN1, OUTPUT);
    pinMode(PIN_M1_AIN2, OUTPUT);
    pinMode(PIN_M2_BIN1, OUTPUT);
    pinMode(PIN_M2_BIN2, OUTPUT);
    pinMode(PIN_M3_AIN1, OUTPUT);
    pinMode(PIN_M3_AIN2, OUTPUT);
    pinMode(PIN_M4_BIN1, OUTPUT);
    pinMode(PIN_M4_BIN2, OUTPUT);

    // Entradas digitales
    pinMode(PIN_N_MOT,    INPUT);
    pinMode(PIN_N_ESP,    INPUT);
    pinMode(PIN_FUNCTION, INPUT);

    // PWM motores
    ledcAttach(PIN_M1_PWM, 5000, 10);
    ledcAttach(PIN_M2_PWM, 5000, 10);
    ledcAttach(PIN_M3_PWM, 5000, 10);
    ledcAttach(PIN_M4_PWM, 5000, 10);

    // Servo
    ledcAttach(PIN_SERVO1, 50, 16);

    // NeoPixel
    pixel.begin();
    pixel.clear();
    pixel.show();

    // I2C
    Wire.begin(I2C_SDA, I2C_SCL, I2C_FREQ);

    // Enviar ACK de inicio por Serial
    sendResponse(ACK_OK, CMD_PING, 0x00);
}

void loop() {
    if (Serial.available() >= 3) {
        uint8_t cmd   = Serial.read();
        uint8_t pinId = Serial.read();
        uint8_t value = Serial.read();
        processCommand(cmd, pinId, value);
    }
}

void processCommand(uint8_t cmd, uint8_t pinId, uint8_t value) {
    switch (cmd) {
        case CMD_PWM: {
            uint16_t pwmVal = map(value, 0, 255, 0, 1023);
            switch (pinId) {
                case 0x01: ledcWrite(PIN_M1_PWM, pwmVal); break;
                case 0x02: ledcWrite(PIN_M2_PWM, pwmVal); break;
                case 0x03: ledcWrite(PIN_M3_PWM, pwmVal); break;
                case 0x04: ledcWrite(PIN_M4_PWM, pwmVal); break;
                default:   sendResponse(ACK_ERR, cmd, 0x00); return;
            }
            sendResponse(ACK_OK, CMD_PWM, value);
            break;
        }

        case CMD_DIGITAL: {
            int gpio = pinIdToGpio(pinId);
            if (gpio < 0) {
                sendResponse(ACK_ERR, cmd, 0x00);
                return;
            }
            digitalWrite(gpio, value ? HIGH : LOW);
            uint8_t readback = (uint8_t)digitalRead(gpio);
            sendResponse(ACK_OK, CMD_DIGITAL, readback);
            break;
        }

        case CMD_SERVO: {
            uint32_t duty = map(value, 0, 180, 1638, 8192);
            ledcWrite(PIN_SERVO1, duty);
            sendResponse(ACK_OK, CMD_SERVO, value);
            break;
        }

        case CMD_NEOPIXEL: {
            switch (value) {
                case 0x00: pixel.setPixelColor(0,   0,   0,   0); break;
                case 0x01: pixel.setPixelColor(0, 255,   0,   0); break;
                case 0x02: pixel.setPixelColor(0,   0, 255,   0); break;
                case 0x03: pixel.setPixelColor(0,   0,   0, 255); break;
                case 0xFF: pixel.setPixelColor(0, 255, 255, 255); break;
                default:   sendResponse(ACK_ERR, cmd, 0x00); return;
            }
            pixel.show();
            sendResponse(ACK_OK, CMD_NEOPIXEL, value);
            break;
        }

        case CMD_ADC: {
            uint16_t raw  = analogRead(pinId);
            uint8_t  val8 = (uint8_t)map(raw, 0, 4095, 0, 255);
            sendResponse(ACK_OK, CMD_ADC, val8);
            break;
        }

        case CMD_I2C_SCAN:
            cmdI2CScan();
            break;

        case CMD_PING:
            sendResponse(ACK_OK, CMD_PING, 0x00);
            break;

        case CMD_RESET:
            sendResponse(ACK_OK, CMD_RESET, 0x00);
            delay(100);
            ESP.restart();
            break;

        default:
            sendResponse(ACK_ERR, cmd, 0x00);
            break;
    }
}

void cmdI2CScan() {
    uint8_t found[112];
    uint8_t count = 0;

    for (uint8_t addr = 0x08; addr <= 0x77; addr++) {
        Wire.beginTransmission(addr);
        uint8_t err = Wire.endTransmission();
        if (err == 0) {
            found[count++] = addr;
        }
        if (err == 4) {
            sendResponse(ACK_ERR, CMD_I2C_SCAN, 0x00);
            return;
        }
    }

    Serial.write(ACK_OK);
    Serial.write(CMD_I2C_SCAN);
    Serial.write(count);
    if (count > 0) {
        Serial.write(found, count);
    }
}

int pinIdToGpio(uint8_t pinId) {
    switch (pinId) {
        case 0x11: return PIN_M1_AIN1;
        case 0x12: return PIN_M1_AIN2;
        case 0x21: return PIN_M2_BIN1;
        case 0x22: return PIN_M2_BIN2;
        case 0x31: return PIN_M3_AIN1;
        case 0x32: return PIN_M3_AIN2;
        case 0x41: return PIN_M4_BIN1;
        case 0x42: return PIN_M4_BIN2;
        default:   return -1;
    }
}

void sendResponse(uint8_t ack, uint8_t cmd, uint8_t val) {
    uint8_t buf[3] = {ack, cmd, val};
    Serial.write(buf, 3);
}