// ============================================================
//  SLAVE - ESP32 Custom Board (la que se testea)
//  Serial (GPIO1/GPIO3) recibe comandos de la estación
//  Librerías requeridas (instalar en Arduino IDE):
//    - ESP32Servo  (por Kevin Harrington)
//    - Adafruit NeoPixel
// ============================================================

#include <ESP32Servo.h>
#include <Adafruit_NeoPixel.h>

// ── Definición de pines ──────────────────────────────────────
#define PIN_M1_PWM    15
#define PIN_M1_AIN1    5
#define PIN_M1_AIN2   18
#define PIN_M2_PWM     2
#define PIN_M2_AIN1   27
#define PIN_M2_AIN2   14
#define PIN_M3_PWM    12
#define PIN_M3_AIN1   32
#define PIN_M3_AIN2   33
#define PIN_M4_PWM    13
#define PIN_M4_AIN1   25
#define PIN_M4_AIN2   26
#define PIN_SERVO1     4
#define PIN_NEOPIXEL  23
#define PIN_N_MOT     36
#define PIN_N_ESP     39
#define PIN_FUNCTION  34

// ── Comandos del protocolo ───────────────────────────────────
#define CMD_PWM      0x01
#define CMD_DIGITAL  0x02
#define CMD_SERVO    0x03
#define CMD_NEOPIXEL 0x04
#define CMD_PING     0xF0
#define CMD_RESET    0xFF

// ── Canales LEDC (PWM) ───────────────────────────────────────
#define CH_M1   0
#define CH_M2   1
#define CH_M3   2
#define CH_M4   3
#define CH_SRV  4

Adafruit_NeoPixel pixel(1, PIN_NEOPIXEL, NEO_GRB + NEO_KHZ800);

// ── Prototipos ───────────────────────────────────────────────
void processCommand(uint8_t cmd, uint8_t pinId, uint8_t value);
int  pinIdToGpio(uint8_t pinId);
void sendResponse(uint8_t resp);

// ─────────────────────────────────────────────────────────────
void setup() {
  // Serial de control: USB en DevKitC, GPIO1/3 en la custom board
  Serial.begin(9600);

  // Salidas digitales motores
  pinMode(PIN_M1_AIN1, OUTPUT);
  pinMode(PIN_M1_AIN2, OUTPUT);
  pinMode(PIN_M2_AIN1, OUTPUT);
  pinMode(PIN_M2_AIN2, OUTPUT);
  pinMode(PIN_M3_AIN1, OUTPUT);
  pinMode(PIN_M3_AIN2, OUTPUT);
  pinMode(PIN_M4_AIN1, OUTPUT);
  pinMode(PIN_M4_AIN2, OUTPUT);

  // Entradas digitales
  pinMode(PIN_N_MOT,    INPUT);
  pinMode(PIN_N_ESP,    INPUT);
  pinMode(PIN_FUNCTION, INPUT);

  // ─── NUEVA API LEDC PARA ESP32 CORE 3.x ───────────────────
  // PWM Motores - 5 kHz, 10 bits (0-1023)
  ledcAttach(PIN_M1_PWM, 5000, 10);  // channel asignado automáticamente
  ledcAttach(PIN_M2_PWM, 5000, 10);
  ledcAttach(PIN_M3_PWM, 5000, 10);
  ledcAttach(PIN_M4_PWM, 5000, 10);
  
  // Servo - 50 Hz, 16 bits
  ledcAttach(PIN_SERVO1, 50, 16);

  // NeoPixel
  pixel.begin();
  pixel.clear();
  pixel.show();

  // Señal de listo
  sendResponse(0xAA);
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

    // ── SET PWM (0-255 → 0-1023) ─────────────────────────────
    case CMD_PWM: {
      uint16_t pwmVal = map(value, 0, 255, 0, 1023);
      switch (pinId) {
        case 0x01: ledcWrite(PIN_M1_PWM, pwmVal); break;  // Usamos el pin directamente
        case 0x02: ledcWrite(PIN_M2_PWM, pwmVal); break;
        case 0x03: ledcWrite(PIN_M3_PWM, pwmVal); break;
        case 0x04: ledcWrite(PIN_M4_PWM, pwmVal); break;
        default:   sendResponse(0xEE); return;
      }
      sendResponse(0x01);
      break;
    }

    // ── SET DIGITAL ──────────────────────────────────────────
    case CMD_DIGITAL: {
      int gpio = pinIdToGpio(pinId);
      if (gpio >= 0) {
        digitalWrite(gpio, value ? HIGH : LOW);
        sendResponse(0x02);
      } else {
        sendResponse(0xEE);
      }
      break;
    }

    // ── SET SERVO (0-180 grados) ─────────────────────────────
    // 16 bits a 50Hz: 1ms=3277 counts, 2ms=6554 counts
    case CMD_SERVO: {
      uint32_t duty = map(value, 0, 180, 1638, 8192);
      ledcWrite(PIN_SERVO1, duty);  // Usamos el pin directamente
      sendResponse(0x03);
      break;
    }

    // ── SET NEOPIXEL ─────────────────────────────────────────
    case CMD_NEOPIXEL: {
      switch (value) {
        case 0x00: pixel.setPixelColor(0, 0,   0,   0  ); break; // OFF
        case 0x01: pixel.setPixelColor(0, 255, 0,   0  ); break; // RED
        case 0x02: pixel.setPixelColor(0, 0,   255, 0  ); break; // GREEN
        case 0x03: pixel.setPixelColor(0, 0,   0,   255); break; // BLUE
        case 0xFF: pixel.setPixelColor(0, 255, 255, 255); break; // WHITE
        default:   sendResponse(0xEE); return;
      }
      pixel.show();
      sendResponse(0x04);
      break;
    }

    // ── PING ─────────────────────────────────────────────────
    case CMD_PING:
      sendResponse(0xAA);
      break;

    // ── RESET ────────────────────────────────────────────────
    case CMD_RESET:
      sendResponse(0xBB);
      delay(100);
      ESP.restart();
      break;

    default:
      sendResponse(0xEE); // Comando desconocido
      break;
  }
}

// ─────────────────────────────────────────────────────────────
// Convierte PIN_ID del protocolo al GPIO real
int pinIdToGpio(uint8_t pinId) {
  switch (pinId) {
    case 0x11: return PIN_M1_AIN1;
    case 0x12: return PIN_M1_AIN2;
    case 0x21: return PIN_M2_AIN1;
    case 0x22: return PIN_M2_AIN2;
    case 0x31: return PIN_M3_AIN1;
    case 0x32: return PIN_M3_AIN2;
    case 0x41: return PIN_M4_AIN1;
    case 0x42: return PIN_M4_AIN2;
    default:   return -1;
  }
}

// ─────────────────────────────────────────────────────────────
void sendResponse(uint8_t resp) {
  Serial.write(resp);
}