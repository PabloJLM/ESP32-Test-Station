// ═══════════════════════════════════════════════════════════
//  SLAVE — Tesla Lab BALAM 2026
//  Placa: Tesla Lab ESP32-WROVER-IE
//  Core:  ESP32 Arduino Core 3.x
//
//  Protocolo entrada:  [CMD, PIN_ID, VALUE]       3 bytes
//
//  Protocolo salida estándar:  [ACK, CMD, VALOR]  3 bytes
//  Protocolo salida I2C scan:  [ACK, CMD, COUNT] + COUNT bytes (direcciones)
//
//  Comandos:
//    0x01  CMD_PWM       — pinId=motor(1-4), value=duty(0-255)
//    0x02  CMD_DIGITAL   — pinId=AIN/BIN id, value=0/1
//    0x03  CMD_SERVO     — value=ángulo(0-180)
//    0x04  CMD_NEOPIXEL  — value: 0x00 OFF, 0x01 R, 0x02 G, 0x03 B, 0xFF W
//    0x05  CMD_ADC       — pinId=pin GPIO a leer
//    0x06  CMD_I2C_SCAN  — escanea bus I2C, responde [ACK, 0x06, COUNT] + addrs
//    0xF0  CMD_PING
//    0xFF  CMD_RESET
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
// SDA/SCL por defecto del ESP32: GPIO21 / GPIO22
#define I2C_SDA       21
#define I2C_SCL       22
#define I2C_FREQ      100000UL   // 100 kHz estándar
#define I2C_TIMEOUT   10         // ms por dirección

// ── Comandos ─────────────────────────────────────────────────
#define CMD_PWM       0x01
#define CMD_DIGITAL   0x02
#define CMD_SERVO     0x03
#define CMD_NEOPIXEL  0x04
#define CMD_ADC       0x05
#define CMD_I2C_SCAN  0x06
#define CMD_PING      0xF0
#define CMD_RESET     0xFF

// ── ACK ──────────────────────────────────────────────────────
#define ACK_OK   0xAA
#define ACK_ERR  0xEE

// ── NeoPixel ─────────────────────────────────────────────────
Adafruit_NeoPixel pixel(1, PIN_NEOPIXEL, NEO_GRB + NEO_KHZ800);

// ── Prototipos ───────────────────────────────────────────────
void processCommand(uint8_t cmd, uint8_t pinId, uint8_t value);
int  pinIdToGpio(uint8_t pinId);
void sendResponse(uint8_t ack, uint8_t cmd, uint8_t val);
void cmdI2CScan();

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

    // I2C
    Wire.begin(I2C_SDA, I2C_SCL, I2C_FREQ);

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

        // CMD_SERVO — value: ángulo 0-180
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

        // CMD_I2C_SCAN — escanea 0x08–0x77, responde lista de dispositivos
        case CMD_I2C_SCAN:
            cmdI2CScan();
            break;

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
//  I2C SCAN
//  Respuesta: [ACK_OK, CMD_I2C_SCAN, COUNT] + COUNT bytes de direcciones
//  Si el bus está vacío: [ACK_OK, CMD_I2C_SCAN, 0x00]
//  Si hay error de bus:  [ACK_ERR, CMD_I2C_SCAN, 0x00]
// ─────────────────────────────────────────────────────────────
void cmdI2CScan() {
    uint8_t found[112];   // máximo 112 direcciones válidas (0x08–0x77)
    uint8_t count = 0;

    for (uint8_t addr = 0x08; addr <= 0x77; addr++) {
        Wire.beginTransmission(addr);
        uint8_t err = Wire.endTransmission();
        if (err == 0) {
            found[count++] = addr;
        }
        // err==4 indica error de bus — abortamos
        if (err == 4) {
            sendResponse(ACK_ERR, CMD_I2C_SCAN, 0x00);
            return;
        }
    }

    // Enviar respuesta extendida
    // Primero el header de 3 bytes estándar
    Serial.write(ACK_OK);
    Serial.write(CMD_I2C_SCAN);
    Serial.write(count);

    // Luego las direcciones (0 bytes si count==0)
    if (count > 0) {
        Serial.write(found, count);
    }
}

// ─────────────────────────────────────────────────────────────
//  Tabla PIN_ID → GPIO físico
//  Nibble alto = motor (1-4), nibble bajo = AIN1(1)/AIN2(2)
// ─────────────────────────────────────────────────────────────
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
//  Respuesta estándar: 3 bytes [ACK, CMD, VALOR]
// ─────────────────────────────────────────────────────────────
void sendResponse(uint8_t ack, uint8_t cmd, uint8_t val) {
    uint8_t buf[3] = {ack, cmd, val};
    Serial.write(buf, 3);
}
