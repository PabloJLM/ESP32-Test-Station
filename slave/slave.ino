// ═══════════════════════════════════════════════════════════
//  SLAVE — Tesla Lab BALAM 2026
//  Placa: Tesla Lab ESP32-WROVER-IE
//  Core:  ESP32 Arduino Core 3.x
//
//  Protocolo entrada:  [CMD, PIN_ID, VALUE]       3 bytes
//  Protocolo salida:   [ACK, CMD, VALOR_MEDIDO]   3 bytes
// ═══════════════════════════════════════════════════════════

#include <Adafruit_NeoPixel.h>
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

// ── Comandos ─────────────────────────────────────────────────
#define CMD_PWM      0x01
#define CMD_DIGITAL  0x02
#define CMD_SERVO    0x03
#define CMD_NEOPIXEL 0x04
#define CMD_ADC      0x05
#define CMD_PING     0xF0
#define CMD_RESET    0xFF

// ── ACK / NACK ───────────────────────────────────────────────
#define ACK_OK   0xAA
#define ACK_ERR  0xEE

// ── NeoPixel ─────────────────────────────────────────────────
Adafruit_NeoPixel pixel(1, PIN_NEOPIXEL, NEO_GRB + NEO_KHZ800);

// ── Prototipos ───────────────────────────────────────────────
void processCommand(uint8_t cmd, uint8_t pinId, uint8_t value);
int  pinIdToGpio(uint8_t pinId);
void sendResponse(uint8_t ack, uint8_t cmd, uint8_t val);

// ─────────────────────────────────────────────────────────────
void setup() {
    Serial.begin(9600);

    // Salidas digitales motores
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

    // PWM motores — Core 3.x: ledcAttach(pin, freq, resolution_bits)
    ledcAttach(PIN_M1_PWM, 5000, 10);
    ledcAttach(PIN_M2_PWM, 5000, 10);
    ledcAttach(PIN_M3_PWM, 5000, 10);
    ledcAttach(PIN_M4_PWM, 5000, 10);

    // Servo — 50 Hz, 16 bits
    ledcAttach(PIN_SERVO1, 50, 16);

    // NeoPixel
    pixel.begin();
    pixel.clear();
    pixel.show();

    // Señal de listo
    sendResponse(ACK_OK, CMD_PING, 0x00);
}

// ─────────────────────────────────────────────────────────────
void loop() {
    if (Serial.available() >= 3) {
        uint8_t cmd   = Serial.read();
        uint8_t pinId = Serial.read();
        uint8_t value = Serial.read();
        processCommand(cmd, pinId, value);
    }
}

// ─────────────────────────────────────────────────────────────
void processCommand(uint8_t cmd, uint8_t pinId, uint8_t value) {
    switch (cmd) {

        // CMD_PWM — pinId: 0x01-0x04 = motor 1-4, value: 0-255
        case CMD_PWM: {
            uint16_t pwmVal = map(value, 0, 255, 0, 1023);
            switch (pinId) {
                case 0x01: ledcWrite(PIN_M1_PWM, pwmVal); break;
                case 0x02: ledcWrite(PIN_M2_PWM, pwmVal); break;
                case 0x03: ledcWrite(PIN_M3_PWM, pwmVal); break;
                case 0x04: ledcWrite(PIN_M4_PWM, pwmVal); break;
                default:   sendResponse(ACK_ERR, cmd, 0x00); return;
            }
            // Reporta el duty configurado (0-255) para que el master compare
            sendResponse(ACK_OK, CMD_PWM, value);
            break;
        }

        // CMD_DIGITAL — pinId: ver tabla, value: 0/1
        case CMD_DIGITAL: {
            int gpio = pinIdToGpio(pinId);
            if (gpio < 0) {
                sendResponse(ACK_ERR, cmd, 0x00);
                return;
            }
            digitalWrite(gpio, value ? HIGH : LOW);
            // Readback inmediato para confirmar estado real del pin
            uint8_t readback = (uint8_t)digitalRead(gpio);
            sendResponse(ACK_OK, CMD_DIGITAL, readback);
            break;
        }

        // CMD_SERVO — value: angulo 0-180
        case CMD_SERVO: {
            // 16 bits a 50 Hz: 1 ms = 3277, 2 ms = 6554
            uint32_t duty = map(value, 0, 180, 1638, 8192);
            ledcWrite(PIN_SERVO1, duty);
            sendResponse(ACK_OK, CMD_SERVO, value);
            break;
        }

        // CMD_NEOPIXEL — value: 0x00 OFF, 0x01 R, 0x02 G, 0x03 B, 0xFF W
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

        // CMD_ADC — pinId: pin ADC a leer, devuelve 8-bit (0-255)
        case CMD_ADC: {
            uint16_t raw  = analogRead(pinId);
            uint8_t  val8 = (uint8_t)map(raw, 0, 4095, 0, 255);
            sendResponse(ACK_OK, CMD_ADC, val8);
            break;
        }

        // CMD_PING
        case CMD_PING:
            sendResponse(ACK_OK, CMD_PING, 0x00);
            break;

        // CMD_RESET
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

// ─────────────────────────────────────────────────────────────
// Tabla PIN_ID → GPIO fisico
// Nibble alto = motor (1-4), nibble bajo = AIN1(1)/AIN2(2)
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

// ─────────────────────────────────────────────────────────────
// Respuesta DAQ: 3 bytes [ACK, CMD, VALOR_MEDIDO]
void sendResponse(uint8_t ack, uint8_t cmd, uint8_t val) {
    uint8_t buf[3] = {ack, cmd, val};
    Serial.write(buf, 3);
}
