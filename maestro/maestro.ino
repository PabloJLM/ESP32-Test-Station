// ═══════════════════════════════════════════════════════════
//  MAESTRO DAQ — Tesla Lab BALAM 2026
//  Rol: recibe comandos del PC por USB Serial,
//       los reenvía al slave por UART2,
//       mide el resultado en pines de loopback,
//       reporta al PC: [STATUS] CMD | ESPERADO | SLAVE | MEDIDO | PASS/FAIL
//
//  ── Loopback disponible (maestro ← slave) ─────────────────
//    GPIO35 ← GPIO15   M1 PWM   (input-only ADC1_7)
//    GPIO34 ← GPIO2    M2 PWM   (input-only ADC1_6)
//    GPIO36 ← GPIO5    M1 AIN1  (input-only S_VP)
//    GPIO39 ← GPIO18   M1 AIN2  (input-only S_VN)
//    GPIO32 ← GPIO27   M2 BIN1  (ADC1_4)
//    GPIO33 ← GPIO14   M2 BIN2  (ADC1_5)
//    GPIO25 ← GPIO4    SERVO    (ADC2_8 + filtro RC)
//    GPIO26 ← GPIO23   NEOPIXEL (detección pulso DATA)
//
//  ── Sin loopback (slave confirma por ACK) ─────────────────
//    M3 PWM, M3 AIN1/AIN2, M4 PWM, M4 BIN1/BIN2
//
//  ── UART2 al slave ────────────────────────────────────────
//    GPIO17 (TX) → RX slave
//    GPIO16 (RX) ← TX slave
//
//  ── WiFi / BT ─────────────────────────────────────────────
//    No se prueban aquí — el slave los gestiona de forma
//    autónoma y se validan desde tab_wifi / tab_ble en la PC.
// ═══════════════════════════════════════════════════════════

// ── UART al slave ─────────────────────────────────────────────
#define SLAVE_TX    19   // GPIO19 → RX del slave
#define SLAVE_RX    21   // GPIO21 ← TX del slave
#define SLAVE_BAUD  9600

// ── Pines de loopback en el maestro ──────────────────────────
#define LB_M1_PWM   35
#define LB_M2_PWM   34
#define LB_M1_AIN1  36
#define LB_M1_AIN2  39
#define LB_M2_BIN1  32
#define LB_M2_BIN2  33
#define LB_SERVO    25
#define LB_NEO      26

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

// ── Tolerancias DAQ ──────────────────────────────────────────
#define TOL_PWM_PCT    5     // ±5 % en duty cycle
#define TOL_SERVO_DEG  10    // ±10° en lectura servo
#define PWM_WINDOW_US  20000UL   // ventana de medición: 20 ms

// ── Estructura de respuesta estándar del slave ───────────────
struct SlaveResp {
    bool    ok;
    uint8_t ack;
    uint8_t cmd;
    uint8_t val;
};

// ── Prototipos ───────────────────────────────────────────────
void handleCommand(String cmd);
void cmdPing();
void cmdReset();
void cmdPWM(int motor, uint8_t duty);
void cmdDigital(uint8_t pinId, uint8_t val);
void cmdServo(uint8_t angle);
void cmdNeopixel(uint8_t color);
void cmdADC(uint8_t pin);
void cmdI2CScan();
void sendToSlave(uint8_t cmd, uint8_t pinId, uint8_t value);
SlaveResp waitSlaveResp(uint32_t timeout_ms);
float measureDuty(int pin);
int   loopbackForDigital(uint8_t pinId);

// ─────────────────────────────────────────────────────────────
void setup() {
    Serial.begin(9600);
    Serial2.begin(SLAVE_BAUD, SERIAL_8N1, SLAVE_RX, SLAVE_TX);

    pinMode(LB_M1_PWM,  INPUT);
    pinMode(LB_M2_PWM,  INPUT);
    pinMode(LB_M1_AIN1, INPUT);
    pinMode(LB_M1_AIN2, INPUT);
    pinMode(LB_M2_BIN1, INPUT);
    pinMode(LB_M2_BIN2, INPUT);
    pinMode(LB_SERVO,   INPUT);
    pinMode(LB_NEO,     INPUT);

    Serial.println("=== MAESTRO DAQ — Tesla Lab BALAM 2026 ===");
    Serial.println("Comandos:");
    Serial.println("  ping");
    Serial.println("  reset");
    Serial.println("  pwm <1-4> <0-255>");
    Serial.println("  servo <0-180>");
    Serial.println("  neo <0|1|2|3|ff>       0=OFF 1=R 2=G 3=B ff=W");
    Serial.println("  digital <pinId> <0|1>  ej: digital 11 1 (M1 AIN1)");
    Serial.println("  adc <pin>              lee ADC del slave");
    Serial.println("  i2c                    escanea bus I2C del slave");
    Serial.println();
    Serial.println("Respuesta: [STATUS] CMD | ESPERADO | SLAVE | MEDIDO | RESULT");
    Serial.println();
}

// ─────────────────────────────────────────────────────────────
void loop() {
    if (Serial.available()) {
        String line = Serial.readStringUntil('\n');
        line.trim();
        if (line.length() > 0) handleCommand(line);
    }

    // Reenviar mensajes espontáneos del slave (boot, etc.)
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
        cmdPing();
    } else if (l == "reset") {
        cmdReset();
    } else if (l == "i2c") {
        cmdI2CScan();
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
//  PING
// ─────────────────────────────────────────────────────────────
void cmdPing() {
    sendToSlave(CMD_PING, 0x00, 0x00);
    SlaveResp r = waitSlaveResp(500);
    Serial.println(r.ok
        ? "[OK]  PING | — | 0xAA | — | PASS"
        : "[ERR] PING | — | TIMEOUT | — | FAIL");
}

// ─────────────────────────────────────────────────────────────
//  RESET
// ─────────────────────────────────────────────────────────────
void cmdReset() {
    sendToSlave(CMD_RESET, 0x00, 0x00);
    SlaveResp r = waitSlaveResp(500);
    Serial.println(r.ok
        ? "[OK]  RESET | — | ACK | — | PASS"
        : "[ERR] RESET | — | TIMEOUT | — | FAIL");
}

// ─────────────────────────────────────────────────────────────
//  PWM
//  Loopback disponible: M1 (GPIO35), M2 (GPIO34)
//  M3/M4: sin loopback físico, se reporta N/A en MEDIDO
// ─────────────────────────────────────────────────────────────
void cmdPWM(int motor, uint8_t duty) {
    if (motor < 1 || motor > 4) {
        Serial.println("[ERR] Motor inválido (1-4)");
        return;
    }

    sendToSlave(CMD_PWM, (uint8_t)motor, duty);
    SlaveResp r = waitSlaveResp(500);

    if (!r.ok) {
        Serial.printf("[ERR] PWM M%d | %d%% | TIMEOUT | N/A | FAIL\n",
                      motor, (int)(duty / 255.0f * 100));
        return;
    }

    float exp_pct   = (duty   / 255.0f) * 100.0f;
    float slave_pct = (r.val  / 255.0f) * 100.0f;

    // Loopback solo M1 y M2
    if (motor == 1 || motor == 2) {
        int lb_pin  = (motor == 1) ? LB_M1_PWM : LB_M2_PWM;
        float meas  = measureDuty(lb_pin);
        bool  pass  = (fabs(meas - exp_pct) <= TOL_PWM_PCT)
                       && (r.ack == ACK_OK);
        Serial.printf("[%s] PWM M%d | ESP=%.0f%% | SLAVE=%.0f%% | MEAS=%.1f%% | %s\n",
                      r.ack == ACK_OK ? "OK" : "ERR",
                      motor, exp_pct, slave_pct, meas,
                      pass ? "PASS" : "FAIL");
    } else {
        // M3/M4 — sin loopback, confiar en ACK del slave
        bool pass = (r.ack == ACK_OK) && (r.val == duty);
        Serial.printf("[%s] PWM M%d | ESP=%.0f%% | SLAVE=%.0f%% | MEAS=N/A | %s\n",
                      r.ack == ACK_OK ? "OK" : "ERR",
                      motor, exp_pct, slave_pct,
                      pass ? "PASS" : "FAIL");
    }
}

// ─────────────────────────────────────────────────────────────
//  DIGITAL
//  Loopback: M1 AIN1/AIN2 (GPIO36/39), M2 BIN1/BIN2 (GPIO32/33)
//  M3/M4: solo readback del slave
// ─────────────────────────────────────────────────────────────
void cmdDigital(uint8_t pinId, uint8_t val) {
    sendToSlave(CMD_DIGITAL, pinId, val);
    SlaveResp r = waitSlaveResp(500);

    if (!r.ok) {
        Serial.printf("[ERR] DIG 0x%02X | %d | TIMEOUT | N/A | FAIL\n", pinId, val);
        return;
    }

    int lb = loopbackForDigital(pinId);

    if (lb >= 0) {
        // Loopback físico disponible (M1/M2)
        delayMicroseconds(200);
        int meas = digitalRead(lb);
        bool pass = (meas == (int)val) && (r.val == val) && (r.ack == ACK_OK);
        Serial.printf("[%s] DIG 0x%02X | CMD=%d | SLAVE=%d | MEAS=%d | %s\n",
                      r.ack == ACK_OK ? "OK" : "ERR",
                      pinId, val, r.val, meas,
                      pass ? "PASS" : "FAIL");
    } else {
        // Sin loopback (M3/M4) — readback del slave es la única confirmación
        bool pass = (r.ack == ACK_OK) && (r.val == val);
        Serial.printf("[%s] DIG 0x%02X | CMD=%d | SLAVE=%d | MEAS=N/A | %s\n",
                      r.ack == ACK_OK ? "OK" : "ERR",
                      pinId, val, r.val,
                      pass ? "PASS" : "FAIL");
    }
}

// ─────────────────────────────────────────────────────────────
//  SERVO
// ─────────────────────────────────────────────────────────────
void cmdServo(uint8_t angle) {
    sendToSlave(CMD_SERVO, 0x00, angle);
    SlaveResp r = waitSlaveResp(1000);

    if (!r.ok) {
        Serial.printf("[ERR] SERVO | %d° | TIMEOUT | N/A | FAIL\n", angle);
        return;
    }

    delay(400);   // esperar que el servo llegue a la posición
    int raw  = analogRead(LB_SERVO);
    int meas = map(raw, 0, 4095, 0, 180);
    bool pass = (abs(meas - (int)angle) <= TOL_SERVO_DEG) && (r.ack == ACK_OK);

    Serial.printf("[%s] SERVO | ESP=%d° | SLAVE=%d° | MEAS=%d° | %s\n",
                  r.ack == ACK_OK ? "OK" : "ERR",
                  angle, r.val, meas,
                  pass ? "PASS" : "FAIL");
}

// ─────────────────────────────────────────────────────────────
//  NEOPIXEL
//  Loopback: detección de pulso en línea DATA (GPIO26)
//  Nota: solo verifica actividad (HIGH al momento del show),
//        no el color real — el color se valida por ACK del slave.
// ─────────────────────────────────────────────────────────────
void cmdNeopixel(uint8_t color) {
    sendToSlave(CMD_NEOPIXEL, 0x00, color);
    SlaveResp r = waitSlaveResp(500);

    if (!r.ok) {
        Serial.printf("[ERR] NEO | 0x%02X | TIMEOUT | N/A | FAIL\n", color);
        return;
    }

    // Detectar pulso en la línea DATA durante el show()
    // El NeoPixel genera una ráfaga de ~30 µs por LED tras el show
    delay(2);
    bool data_active = false;
    uint32_t t0 = micros();
    while (micros() - t0 < 500) {         // ventana de 500 µs
        if (digitalRead(LB_NEO)) { data_active = true; break; }
    }

    const char* names[] = {"OFF", "ROJO", "VERDE", "AZUL"};
    const char* name = (color == 0xFF) ? "BLANCO"
                     : (color < 4)     ? names[color]
                     :                   "?";

    bool pass = (r.ack == ACK_OK) && (r.val == color);
    Serial.printf("[%s] NEO | COLOR=%s(0x%02X) | SLAVE=0x%02X | DATA=%s | %s\n",
                  r.ack == ACK_OK ? "OK" : "ERR",
                  name, color, r.val,
                  data_active ? "PULSE" : "NONE",
                  pass ? "PASS" : "FAIL");
}

// ─────────────────────────────────────────────────────────────
//  ADC
// ─────────────────────────────────────────────────────────────
void cmdADC(uint8_t pin) {
    sendToSlave(CMD_ADC, pin, 0x00);
    SlaveResp r = waitSlaveResp(500);

    if (!r.ok) {
        Serial.printf("[ERR] ADC pin %d | — | TIMEOUT | — | FAIL\n", pin);
        return;
    }

    float voltage = (r.val / 255.0f) * 3.3f;
    Serial.printf("[OK]  ADC pin %d | RAW8=%d | ~%.2fV | — | PASS\n",
                  pin, r.val, voltage);
}

// ─────────────────────────────────────────────────────────────
//  I2C SCAN
//  Envía CMD_I2C_SCAN al slave.
//  Respuesta extendida: [ACK, 0x06, COUNT] + COUNT bytes de direcciones
//
//  Formato de salida:
//    [OK]  I2C | — | COUNT=N | ADDRS=0x3C,0x68,... | PASS
//    [OK]  I2C | — | COUNT=0 | ADDRS=none | PASS
//    [ERR] I2C | — | BUS_ERROR | — | FAIL
// ─────────────────────────────────────────────────────────────
void cmdI2CScan() {
    sendToSlave(CMD_I2C_SCAN, 0x00, 0x00);

    // Esperar los 3 bytes del header
    uint32_t t0 = millis();
    while (Serial2.available() < 3 && millis() - t0 < 2000);

    if (Serial2.available() < 3) {
        Serial.println("[ERR] I2C | — | TIMEOUT | — | FAIL");
        return;
    }

    uint8_t ack   = Serial2.read();
    uint8_t cmd_r = Serial2.read();
    uint8_t count = Serial2.read();

    if (ack != ACK_OK) {
        Serial.println("[ERR] I2C | — | BUS_ERROR | — | FAIL");
        return;
    }

    // Leer las direcciones adicionales (count bytes)
    // El slave tarda ~1 ms por dirección escaneada → máx ~112 ms total
    // Damos 500 ms de margen
    uint8_t addrs[112];
    uint8_t received = 0;
    t0 = millis();
    while (received < count && millis() - t0 < 500) {
        if (Serial2.available()) {
            addrs[received++] = Serial2.read();
        }
    }

    // Construir string de direcciones
    if (count == 0) {
        Serial.printf("[OK]  I2C | — | COUNT=0 | ADDRS=none | PASS\n");
    } else {
        char addr_str[128] = "";
        for (uint8_t i = 0; i < received; i++) {
            char tmp[8];
            snprintf(tmp, sizeof(tmp), "0x%02X", addrs[i]);
            strncat(addr_str, tmp, sizeof(addr_str) - strlen(addr_str) - 1);
            if (i < received - 1)
                strncat(addr_str, ",", sizeof(addr_str) - strlen(addr_str) - 1);
        }
        Serial.printf("[OK]  I2C | — | COUNT=%d | ADDRS=%s | PASS\n",
                      count, addr_str);
    }
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

// Mapea pinId de AIN/BIN al pin de loopback del maestro
// Solo M1 y M2 tienen loopback físico
int loopbackForDigital(uint8_t pinId) {
    switch (pinId) {
        case 0x11: return LB_M1_AIN1;   // M1 AIN1 → GPIO36
        case 0x12: return LB_M1_AIN2;   // M1 AIN2 → GPIO39
        case 0x21: return LB_M2_BIN1;   // M2 BIN1 → GPIO32
        case 0x22: return LB_M2_BIN2;   // M2 BIN2 → GPIO33
        default:   return -1;            // M3/M4 sin loopback
    }
}

// Mide duty cycle en ventana PWM_WINDOW_US
// Funciona con cualquier pin GPIO de entrada digital
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
