//  Tesla Lab BALAM 2026
//  Rol: recibe comandos del PC por USB Serial,
//       los reenvía al slave por UART2,
//       mide el resultado en pines de loopback,
//       reporta al PC: [STATUS] CMD | ESPERADO | SLAVE | MEDIDO | PASS/FAIL
//
//  ── Conexiones loopback (master ← slave) ──────────────────
//  GPIO35 - GPIO15  (M1 PWM)      input-only ADC1_7
//  GPIO34 - GPIO2   (M2 PWM)      input-only ADC1_6
//  GPIO36 - GPIO5   (M1 AIN1)     input-only S_VP
//  GPIO39 - GPIO18  (M1 AIN2)     input-only S_VN
//  GPIO32 - GPIO27  (M2 BIN1)     ADC1_4
//  GPIO33 - GPIO14  (M2 BIN2)     ADC1_5
//  GPIO25 - GPIO4   (SERVO)       DAC1 / ADC2_8  (con filtro RC)
//  GPIO26 - GPIO23  (NEOPIXEL)    DAC2
//
//  ── UART2 al slave ────────────────────────────────────────
//  GPIO17 (TX) → RX del slave
//  GPIO16 (RX) ← TX del slave

// ── UART al slave ────────────────────────────────────────────
#define SLAVE_TX    17
#define SLAVE_RX    16
#define SLAVE_BAUD  9600

// ── Pines de loopback en el master ───────────────────────────
#define LB_M1_PWM   35   // mide duty PWM motor 1 (input-only)
#define LB_M2_PWM   34   // mide duty PWM motor 2 (input-only)
#define LB_M1_AIN1  36   // mide digital M1 AIN1  (input-only)
#define LB_M1_AIN2  39   // mide digital M1 AIN2  (input-only)
#define LB_M2_BIN1  32   // mide digital M2 BIN1
#define LB_M2_BIN2  33   // mide digital M2 BIN2
#define LB_SERVO    25   // mide posicion servo aprox. via ADC + filtro RC
#define LB_NEO      26   // detecta actividad NeoPixel

// ── Comandos (mismo enum que slave) ──────────────────────────
#define CMD_PWM      0x01
#define CMD_DIGITAL  0x02
#define CMD_SERVO    0x03
#define CMD_NEOPIXEL 0x04
#define CMD_ADC      0x05
#define CMD_PING     0xF0
#define CMD_RESET    0xFF

#define ACK_OK   0xAA
#define ACK_ERR  0xEE

// ── Tolerancias DAQ ──────────────────────────────────────────
#define TOL_PWM_PCT   5    // ±5% en duty cycle
#define TOL_SERVO_DEG 10   // ±10° en lectura servo
#define PWM_WINDOW_US 20000UL  // ventana de medicion PWM: 20 ms

// ── Estructura de respuesta del slave ────────────────────────
struct SlaveResp {
    bool    ok;
    uint8_t ack;
    uint8_t cmd;
    uint8_t val;
};

// ── Prototipos ───────────────────────────────────────────────
void handleCommand(String cmd);
void cmdPWM(int motor, uint8_t duty);
void cmdDigital(uint8_t pinId, uint8_t val);
void cmdServo(uint8_t angle);
void cmdNeopixel(uint8_t color);
void cmdADC(uint8_t pin);
void sendToSlave(uint8_t cmd, uint8_t pinId, uint8_t value);
SlaveResp waitSlaveResp(uint32_t timeout_ms);
float measureDuty(int pin);
int   loopbackForDigital(uint8_t pinId);

// ─────────────────────────────────────────────────────────────
void setup() {
    Serial.begin(9600);
    Serial2.begin(SLAVE_BAUD, SERIAL_8N1, SLAVE_RX, SLAVE_TX);

    // Pines de loopback como entrada
    pinMode(LB_M1_PWM,  INPUT);
    pinMode(LB_M2_PWM,  INPUT);
    pinMode(LB_M1_AIN1, INPUT);
    pinMode(LB_M1_AIN2, INPUT);
    pinMode(LB_M2_BIN1, INPUT);
    pinMode(LB_M2_BIN2, INPUT);
    pinMode(LB_SERVO,   INPUT);
    pinMode(LB_NEO,     INPUT);

    Serial.println("=== MASTER DAQ — Tesla Lab BALAM 2026 ===");
    Serial.println("Comandos disponibles:");
    Serial.println("  ping");
    Serial.println("  pwm <1-4> <0-255>        — controla motor y mide loopback");
    Serial.println("  servo <0-180>            — mueve servo y mide loopback");
    Serial.println("  neo <0|1|2|3|ff>         — off/rojo/verde/azul/blanco");
    Serial.println("  digital <pinId> <0|1>    — ej: digital 11 1 (M1 AIN1)");
    Serial.println("  adc <pin>                — lee ADC del slave");
    Serial.println("  reset");
    Serial.println();
    Serial.println("Formato respuesta: [STATUS] CMD | ESPERADO | SLAVE | MEDIDO | RESULT");
    Serial.println();
}

// ─────────────────────────────────────────────────────────────
void loop() {
    if (Serial.available()) {
        String line = Serial.readStringUntil('\n');
        line.trim();
        if (line.length() > 0) handleCommand(line);
    }

    // Mostrar respuestas espontaneas del slave (ej: boot 0xAA 0xF0 0x00)
    if (Serial2.available() >= 3) {
        uint8_t a = Serial2.read();
        uint8_t c = Serial2.read();
        uint8_t v = Serial2.read();
        Serial.printf("[SLAVE] ACK=0x%02X CMD=0x%02X VAL=%d\n", a, c, v);
    }
}

// ─────────────────────────────────────────────────────────────
void handleCommand(String line) {
    String l = line;
    l.toLowerCase();

    if (l == "ping") {
        sendToSlave(CMD_PING, 0x00, 0x00);
        SlaveResp r = waitSlaveResp(500);
        Serial.println(r.ok ? "[OK]  PING — slave vivo" : "[ERR] PING — timeout");

    } else if (l == "reset") {
        sendToSlave(CMD_RESET, 0x00, 0x00);
        SlaveResp r = waitSlaveResp(500);
        Serial.println(r.ok ? "[OK]  RESET enviado" : "[ERR] RESET — timeout");

    } else if (l.startsWith("pwm ")) {
        int sp1   = l.indexOf(' ', 4);
        int motor = l.substring(4, sp1).toInt();
        int duty  = l.substring(sp1 + 1).toInt();
        cmdPWM(motor, (uint8_t)constrain(duty, 0, 255));

    } else if (l.startsWith("servo ")) {
        int angle = l.substring(6).toInt();
        cmdServo((uint8_t)constrain(angle, 0, 180));

    } else if (l.startsWith("neo ")) {
        String color = l.substring(4);
        color.trim();
        uint8_t val = (color == "ff") ? 0xFF : (uint8_t)color.toInt();
        cmdNeopixel(val);

    } else if (l.startsWith("digital ")) {
        int sp1   = l.indexOf(' ', 8);
        int pinId = l.substring(8, sp1).toInt();
        int val   = l.substring(sp1 + 1).toInt();
        cmdDigital((uint8_t)pinId, (uint8_t)val);

    } else if (l.startsWith("adc ")) {
        int pin = l.substring(4).toInt();
        cmdADC((uint8_t)pin);

    } else {
        Serial.println("[ERR] Comando no reconocido");
    }
}

// ─────────────────────────────────────────────────────────────
//  COMANDOS DAQ
// ─────────────────────────────────────────────────────────────

void cmdPWM(int motor, uint8_t duty) {
    if (motor < 1 || motor > 4) {
        Serial.println("[ERR] Motor invalido (1-4)");
        return;
    }

    sendToSlave(CMD_PWM, (uint8_t)motor, duty);
    SlaveResp r = waitSlaveResp(500);

    if (!r.ok) {
        Serial.printf("[ERR] PWM M%d — timeout\n", motor);
        return;
    }

    // Medir duty en loopback (solo M1 y M2 tienen loopback)
    float expected_pct = (duty / 255.0f) * 100.0f;
    float slave_pct    = (r.val / 255.0f) * 100.0f;
    float meas_pct     = -1;

    if (motor == 1) meas_pct = measureDuty(LB_M1_PWM);
    else if (motor == 2) meas_pct = measureDuty(LB_M2_PWM);

    if (meas_pct >= 0) {
        bool pass = fabs(meas_pct - expected_pct) <= TOL_PWM_PCT;
        Serial.printf("[%s] PWM M%d | ESP=%.0f%% | SLAVE=%.0f%% | MEAS=%.1f%% | %s\n",
            r.ack == ACK_OK ? "OK" : "ERR",
            motor, expected_pct, slave_pct, meas_pct,
            pass ? "PASS" : "FAIL");
    } else {
        Serial.printf("[%s] PWM M%d | ESP=%.0f%% | SLAVE=%.0f%% | MEAS=N/A (sin loopback)\n",
            r.ack == ACK_OK ? "OK" : "ERR",
            motor, expected_pct, slave_pct);
    }
}

void cmdDigital(uint8_t pinId, uint8_t val) {
    sendToSlave(CMD_DIGITAL, pinId, val);
    SlaveResp r = waitSlaveResp(500);

    if (!r.ok) {
        Serial.printf("[ERR] DIG 0x%02X — timeout\n", pinId);
        return;
    }

    int lb   = loopbackForDigital(pinId);
    int meas = -1;
    if (lb >= 0) {
        delayMicroseconds(200);
        meas = digitalRead(lb);
    }

    if (meas >= 0) {
        bool pass = (meas == (int)val) && (r.val == val);
        Serial.printf("[%s] DIG 0x%02X | CMD=%d | SLAVE=%d | MEAS=%d | %s\n",
            r.ack == ACK_OK ? "OK" : "ERR",
            pinId, val, r.val, meas,
            pass ? "PASS" : "FAIL");
    } else {
        Serial.printf("[%s] DIG 0x%02X | CMD=%d | SLAVE=%d | MEAS=N/A (sin loopback)\n",
            r.ack == ACK_OK ? "OK" : "ERR",
            pinId, val, r.val);
    }
}

void cmdServo(uint8_t angle) {
    sendToSlave(CMD_SERVO, 0x00, angle);
    SlaveResp r = waitSlaveResp(1000);

    if (!r.ok) {
        Serial.println("[ERR] SERVO — timeout");
        return;
    }

    // Esperar que el servo llegue a la posicion y leer ADC
    delay(400);
    int raw  = analogRead(LB_SERVO);
    int meas = map(raw, 0, 4095, 0, 180);
    bool pass = abs(meas - (int)angle) <= TOL_SERVO_DEG;

    Serial.printf("[%s] SERVO | CMD=%d° | SLAVE=%d° | MEAS=%d° | %s\n",
        r.ack == ACK_OK ? "OK" : "ERR",
        angle, r.val, meas,
        pass ? "PASS" : "FAIL");
}

void cmdNeopixel(uint8_t color) {
    sendToSlave(CMD_NEOPIXEL, 0x00, color);
    SlaveResp r = waitSlaveResp(500);

    if (!r.ok) {
        Serial.println("[ERR] NEOPIXEL — timeout");
        return;
    }

    // Detectar pulso en pin data del NeoPixel
    delay(5);
    int neo = digitalRead(LB_NEO);

    const char* names[] = {"OFF","ROJO","VERDE","AZUL"};
    const char* name = (color == 0xFF) ? "BLANCO"
                     : (color < 4)     ? names[color]
                     :                   "?";

    Serial.printf("[%s] NEO | COLOR=%s(0x%02X) | SLAVE=0x%02X | DATA=%s\n",
        r.ack == ACK_OK ? "OK" : "ERR",
        name, color, r.val,
        neo ? "HIGH" : "LOW");
}

void cmdADC(uint8_t pin) {
    sendToSlave(CMD_ADC, pin, 0x00);
    SlaveResp r = waitSlaveResp(500);

    if (!r.ok) {
        Serial.printf("[ERR] ADC pin %d — timeout\n", pin);
        return;
    }

    float voltage = (r.val / 255.0f) * 3.3f;
    Serial.printf("[OK]  ADC pin %d | RAW8=%d | ~%.2f V\n", pin, r.val, voltage);
}

// ─────────────────────────────────────────────────────────────
//  HELPERS
// ─────────────────────────────────────────────────────────────

void sendToSlave(uint8_t cmd, uint8_t pinId, uint8_t value) {
    uint8_t buf[3] = {cmd, pinId, value};
    Serial2.write(buf, 3);
}

SlaveResp waitSlaveResp(uint32_t timeout_ms) {
    SlaveResp r = {false, 0, 0, 0};
    uint32_t t0 = millis();
    while (millis() - t0 < timeout_ms) {
        if (Serial2.available() >= 3) {
            r.ack = Serial2.read();
            r.cmd = Serial2.read();
            r.val = Serial2.read();
            r.ok  = true;
            return r;
        }
    }
    return r;
}

// Mapea pinId de AIN/BIN al pin de loopback del master
// Solo M1 y M2 tienen loopback fisico asignado
int loopbackForDigital(uint8_t pinId) {
    switch (pinId) {
        case 0x11: return LB_M1_AIN1;  // M1 AIN1 → GPIO36
        case 0x12: return LB_M1_AIN2;  // M1 AIN2 → GPIO39
        case 0x21: return LB_M2_BIN1;  // M2 BIN1 → GPIO32
        case 0x22: return LB_M2_BIN2;  // M2 BIN2 → GPIO33
        default:   return -1;           // M3/M4 sin loopback
    }
}

// Mide duty cycle por tiempo HIGH / tiempo total en ventana PWM_WINDOW_US
// Funciona con cualquier pin de entrada, sin necesidad de PCNT
float measureDuty(int pin) {
    uint32_t high_us  = 0;
    uint32_t t0       = micros();
    uint32_t deadline = t0 + PWM_WINDOW_US;

    while (micros() < deadline) {
        if (digitalRead(pin)) {
            uint32_t rise = micros();
            while (digitalRead(pin) && micros() < deadline);
            high_us += micros() - rise;
        }
    }

    uint32_t elapsed = micros() - t0;
    if (elapsed == 0) return 0.0f;
    return (high_us / (float)elapsed) * 100.0f;
}
