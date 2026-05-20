// ═══════════════════════════════════════════════════════════
//  SLAVE MAIN — Tesla Lab BALAM 2026  (PCB v2)
//
//  Motor 1:  IN1=IO33  IN2=IO32  PWM=IO14
//  Motor 2:  IN1=IO27  IN2=IO25  PWM=IO12
//  Servo:    IO18
//  GPIO:     IO13, IO15  (salidas digitales ON/OFF)
//  NeoPixel: IO23 — 4× WS2812B
//  I2C:      SCL=IO22  SDA=IO21
//
//  Protocolo: [CMD, ID, VAL] → [ACK, CMD, VAL]
//    0x01 MOTOR    ID=1|2   VAL=0(stop)/1(fwd)/2(bwd)
//    0x02 PWM      ID=1|2   VAL=0-255
//    0x03 SERVO    ID=1     VAL=0-180
//    0x04 NEO      ID=0(all)/1-4  VAL=00/01/02/03/FF
//    0x05 DIGITAL  ID=13|15 VAL=0/1
//    0x06 I2C_SCAN → [ACK,0x06,COUNT] + COUNT×addr
//    0xF0 PING
//    0xFF RESET
// ═══════════════════════════════════════════════════════════

#include <Adafruit_NeoPixel.h>
#include <Wire.h>

// ── Pines motores ────────────────────────────────────────────
// ⚠ Si M1 va al revés: intercambia M1_IN1 y M1_IN2
// ⚠ Si M2 va al revés: intercambia M2_IN1 y M2_IN2
#define M1_IN1  33
#define M1_IN2  25
#define M1_PWM  32

#define M2_IN1  27
#define M2_IN2  14
#define M2_PWM  12

// ── Resto de pines ────────────────────────────────────────────
#define SERVO_PIN  18
#define IO13       13
#define IO15       15
#define NEO_PIN    23
#define NEO_N       4
#define I2C_SCL    22
#define I2C_SDA    21

// ── Protocolo ────────────────────────────────────────────────
#define CMD_MOTOR    0x01
#define CMD_PWM      0x02
#define CMD_SERVO    0x03
#define CMD_NEO      0x04
#define CMD_DIGITAL  0x05
#define CMD_I2C_SCAN 0x06
#define CMD_PING     0xF0
#define CMD_RESET    0xFF
#define ACK_OK       0xAA
#define ACK_ERR      0xEE

// ── Estado ────────────────────────────────────────────────────
Adafruit_NeoPixel neo(NEO_N, NEO_PIN, NEO_GRB + NEO_KHZ800);
uint8_t m_dir[3] = {0, 0, 0};  // [_, M1dir, M2dir]

// ── Util ──────────────────────────────────────────────────────
inline void respond(uint8_t ack, uint8_t cmd, uint8_t val) {
    uint8_t b[3] = {ack, cmd, val};
    Serial.write(b, 3);
}

// ── Control de motores ────────────────────────────────────────
// Usa PWM en los pines de dirección (compatible TB6612 y DRV8833).
// TB6612: PWMA/PWMB controlan velocidad  → ledcWrite al pin PWM.
// DRV8833: velocidad por PWM en pines IN → ledcWrite a IN activo.
// El código escribe en AMBOS (PWM + IN activo) para cubrir ambos chips.
void motorSet(uint8_t m, uint8_t dir, uint8_t spd) {
    uint8_t in1 = (m == 1) ? M1_IN1 : M2_IN1;
    uint8_t in2 = (m == 1) ? M1_IN2 : M2_IN2;
    uint8_t pwm = (m == 1) ? M1_PWM  : M2_PWM;
    uint16_t duty = (uint16_t)map(spd, 0, 255, 0, 1023);

    switch (dir) {
        case 0:  // STOP / coast
            ledcWrite(in1, 0);
            ledcWrite(in2, 0);
            ledcWrite(pwm, 0);
            break;
        case 1:  // ADELANTE
            ledcWrite(in1, duty);
            ledcWrite(in2, 0);
            ledcWrite(pwm, duty);  // para TB6612
            break;
        case 2:  // ATRÁS
            ledcWrite(in1, 0);
            ledcWrite(in2, duty);
            ledcWrite(pwm, duty);  // para TB6612
            break;
    }
}

// ── Setup ──────────────────────────────────────────────────────
void setup() {
    Serial.begin(9600);

    // ── Motores (LEDC 5kHz 10-bit) ──────────────────────────
    // Canales asignados explícitamente: 0=M1_IN1, 1=M1_IN2,
    //   2=M1_PWM, 3=M2_IN1, 4=M2_IN2, 5=M2_PWM
    ledcAttachChannel(M1_IN1, 5000, 10, 0);
    ledcAttachChannel(M1_IN2, 5000, 10, 1);
    ledcAttachChannel(M1_PWM, 5000, 10, 2);
    ledcAttachChannel(M2_IN1, 5000, 10, 3);
    ledcAttachChannel(M2_IN2, 5000, 10, 4);
    ledcAttachChannel(M2_PWM, 5000, 10, 5);
    // Todo a 0 → motores parados
    for (uint8_t ch = 0; ch < 6; ch++) ledcWriteChannel(ch, 0);

    // ── Servo IO18 (LEDC 50Hz 16-bit, canal 6) ──────────────
    ledcAttachChannel(SERVO_PIN, 50, 16, 6);
    ledcWrite(SERVO_PIN, 4915);  // 90° centro

    // ── GPIO digitales IO13 / IO15 ──────────────────────────
    // NO se les hace ledcAttach — son salidas digitales simples
    pinMode(IO13, OUTPUT); digitalWrite(IO13, LOW);
    pinMode(IO15, OUTPUT); digitalWrite(IO15, LOW);

    // ── NeoPixel ─────────────────────────────────────────────
    neo.begin(); neo.clear(); neo.show();

    // ── I2C ──────────────────────────────────────────────────
    Wire.begin(I2C_SDA, I2C_SCL);

    respond(ACK_OK, CMD_PING, 0x00);
}

// ── Loop ───────────────────────────────────────────────────────
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
            if (id != 1 || val > 180) { respond(ACK_ERR, cmd, 0); break; }
            ledcWrite(SERVO_PIN, map(val, 0, 180, 1638, 8192));
            respond(ACK_OK, CMD_SERVO, val);
            break;

        case CMD_DIGITAL:
            if (id != 13 && id != 15) { respond(ACK_ERR, cmd, 0); break; }
            digitalWrite(id, val ? HIGH : LOW);
            respond(ACK_OK, CMD_DIGITAL, val ? 1 : 0);
            break;

        case CMD_NEO: {
            uint32_t c;
            switch (val) {
                case 0x01: c = neo.Color(255,0,0);     break;
                case 0x02: c = neo.Color(0,255,0);     break;
                case 0x03: c = neo.Color(0,0,255);     break;
                case 0xFF: c = neo.Color(255,255,255); break;
                default:   c = neo.Color(0,0,0);       break;
            }
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