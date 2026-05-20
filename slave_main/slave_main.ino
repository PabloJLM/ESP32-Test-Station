// ═══════════════════════════════════════════════════════════
//  SLAVE MAIN — Tesla Lab BALAM 2026  (PCB v2)
//
//  Motor 1:  AIN1=IO33  AIN2=IO32  PWM=IO14
//  Motor 2:  BIN1=IO27  BIN2=IO25  PWM=IO12
//  Servo 1:  IO18 (H1)
//  Servo 2:  IO13 (U13)
//  Servo 3:  IO15 (U13)
//  NeoPixel: IO23 — cadena 4× WS2812B
//  I2C:      SCL=IO22  SDA=IO21
//
//  Protocolo 3 bytes: [CMD, ID, VAL] → [ACK, CMD, VAL]
//    0x01 MOTOR    ID=1|2   VAL=0(stop)/1(fwd)/2(bwd)
//    0x02 PWM      ID=1|2   VAL=0-255 (velocidad, mantiene dir)
//    0x03 SERVO    ID=1|2|3 VAL=0-180°
//    0x04 NEO      ID=0(all)/1-4  VAL=00/01/02/03/FF
//    0x06 I2C_SCAN → [ACK,0x06,COUNT] + COUNT bytes addrs
//    0xF0 PING
//    0xFF RESET
// ═══════════════════════════════════════════════════════════

#include <Adafruit_NeoPixel.h>
#include <Wire.h>
#include "esp32-hal-ledc.h"

// ── Pines ───────────────────────────────────────────────────
#define M1_AIN1     33
#define M1_AIN2     32
#define M1_PWM      14

#define M2_BIN1     27
#define M2_BIN2     25
#define M2_PWM      12

#define SERVO_IO18  18
#define SERVO_IO13  13
#define SERVO_IO15  15

#define NEO_PIN     23
#define NEO_N        4

#define I2C_SCL     22
#define I2C_SDA     21

// ── Protocolo ───────────────────────────────────────────────
#define CMD_MOTOR    0x01
#define CMD_PWM      0x02
#define CMD_SERVO    0x03
#define CMD_NEO      0x04
#define CMD_DIGITAL  0x05   // GPIO raw: ID=pin VAL=0/1
#define CMD_I2C_SCAN 0x06
#define CMD_PING     0xF0
#define CMD_RESET    0xFF
#define ACK_OK       0xAA
#define ACK_ERR      0xEE

// ── Estado ──────────────────────────────────────────────────
Adafruit_NeoPixel neo(NEO_N, NEO_PIN, NEO_GRB + NEO_KHZ800);
uint8_t m_dir[3] = {0, 0, 0};   // dir actual [_, M1, M2]

// ── Helpers ─────────────────────────────────────────────────
inline void respond(uint8_t ack, uint8_t cmd, uint8_t val) {
    uint8_t b[3] = {ack, cmd, val};
    Serial.write(b, 3);
}

void motorSet(uint8_t m, uint8_t dir, uint8_t spd) {
    uint8_t in1 = (m == 1) ? M1_AIN1 : M2_BIN1;
    uint8_t in2 = (m == 1) ? M1_AIN2 : M2_BIN2;
    uint8_t pwm = (m == 1) ? M1_PWM  : M2_PWM;
    uint16_t duty = (uint16_t)map(spd, 0, 255, 0, 1023);
    switch (dir) {
        case 0:  // STOP — freno suave
            digitalWrite(in1, LOW); digitalWrite(in2, LOW);
            ledcWrite(pwm, 0);
            break;
        case 1:  // ADELANTE
            digitalWrite(in1, HIGH); digitalWrite(in2, LOW);
            ledcWrite(pwm, duty);
            break;
        case 2:  // ATRÁS
            digitalWrite(in1, LOW); digitalWrite(in2, HIGH);
            ledcWrite(pwm, duty);
            break;
    }
}

void servoWrite(uint8_t id, uint8_t angle) {
    uint8_t pin;
    switch (id) {
        case 1: pin = SERVO_IO18; break;
        case 2: pin = SERVO_IO13; break;
        case 3: pin = SERVO_IO15; break;
        default: return;
    }
    // 16-bit 50Hz: 0°→1638 | 90°→4915 | 180°→8192
    uint32_t duty = map(angle, 0, 180, 1638, 8192);
    ledcWrite(pin, duty);
}

uint32_t neoColor(uint8_t idx) {
    switch (idx) {
        case 0x01: return neo.Color(255, 0,   0);
        case 0x02: return neo.Color(0,   255, 0);
        case 0x03: return neo.Color(0,   0,   255);
        case 0xFF: return neo.Color(255, 255, 255);
        default:   return neo.Color(0,   0,   0);
    }
}

// ── Setup ───────────────────────────────────────────────────
void setup() {
    Serial.begin(9600);

    // Motores — dirección
    pinMode(M1_AIN1, OUTPUT); pinMode(M1_AIN2, OUTPUT);
    pinMode(M2_BIN1, OUTPUT); pinMode(M2_BIN2, OUTPUT);
    digitalWrite(M1_AIN1, LOW); digitalWrite(M1_AIN2, LOW);
    digitalWrite(M2_BIN1, LOW); digitalWrite(M2_BIN2, LOW);

    // Motores — PWM 5kHz 10-bit
    ledcAttach(M1_PWM, 5000, 10);
    ledcAttach(M2_PWM, 5000, 10);

    // Servos — 50Hz 16-bit
    ledcAttach(SERVO_IO18, 50, 16);
    ledcAttach(SERVO_IO13, 50, 16);
    ledcAttach(SERVO_IO15, 50, 16);
    servoWrite(1, 90); servoWrite(2, 90); servoWrite(3, 90);

    // IO13 / IO15 — salidas digitales
    pinMode(SERVO_IO13, OUTPUT); digitalWrite(SERVO_IO13, LOW);
    pinMode(SERVO_IO15, OUTPUT); digitalWrite(SERVO_IO15, LOW);

    // NeoPixel
    neo.begin(); neo.clear(); neo.show();

    // I2C
    Wire.begin(I2C_SDA, I2C_SCL);

    respond(ACK_OK, CMD_PING, 0x00);
}

// ── Loop ────────────────────────────────────────────────────
void loop() {
    if (Serial.available() < 3) return;
    uint8_t cmd = Serial.read();
    uint8_t id  = Serial.read();
    uint8_t val = Serial.read();

    switch (cmd) {

        case CMD_MOTOR:
            if (id < 1 || id > 2 || val > 2) { respond(ACK_ERR, cmd, 0); break; }
            m_dir[id] = val;
            motorSet(id, val, 255);
            respond(ACK_OK, CMD_MOTOR, val);
            break;

        case CMD_PWM:
            if (id < 1 || id > 2) { respond(ACK_ERR, cmd, 0); break; }
            motorSet(id, m_dir[id], val);
            respond(ACK_OK, CMD_PWM, val);
            break;

        case CMD_SERVO:
            if (id < 1 || id > 1 || val > 180) { respond(ACK_ERR, cmd, 0); break; }
            servoWrite(id, val);
            respond(ACK_OK, CMD_SERVO, val);
            break;

        case CMD_DIGITAL: {
            // Solo IO13 y IO15 permitidos
            if (id != 13 && id != 15) { respond(ACK_ERR, cmd, 0); break; }
            digitalWrite(id, val ? HIGH : LOW);
            respond(ACK_OK, CMD_DIGITAL, val ? 1 : 0);
            break;
        }

        case CMD_NEO: {
            uint32_t c = neoColor(val);
            if (id == 0) {
                neo.fill(c, 0, NEO_N);
            } else if (id >= 1 && id <= NEO_N) {
                neo.setPixelColor(id - 1, c);
            } else {
                respond(ACK_ERR, cmd, 0); break;
            }
            neo.show();
            respond(ACK_OK, CMD_NEO, val);
            break;
        }

        case CMD_I2C_SCAN: {
            uint8_t found[112]; uint8_t n = 0;
            for (uint8_t a = 0x08; a <= 0x77; a++) {
                Wire.beginTransmission(a);
                if (Wire.endTransmission() == 0) found[n++] = a;
            }
            Serial.write(ACK_OK);
            Serial.write((uint8_t)CMD_I2C_SCAN);
            Serial.write(n);
            if (n) Serial.write(found, n);
            break;
        }

        case CMD_PING:
            respond(ACK_OK, CMD_PING, 0x00);
            break;

        case CMD_RESET:
            respond(ACK_OK, CMD_RESET, 0x00);
            delay(100); ESP.restart();
            break;

        default:
            respond(ACK_ERR, cmd, 0x00);
            break;
    }
}