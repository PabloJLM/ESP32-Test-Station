// ============================================================
//  MASTER - Estación de Test con comandos por Serial USB
//  Recibe comandos del PC y los envía al SLAVE por UART2
// ============================================================

// ── Configuración de pines ──────────────────────────────────
#define UART_TX_PIN    18  // Conectar al RX del slave (GPIO3)
#define UART_RX_PIN    19  // Conectar al TX del slave (GPIO1)

// ── Comandos del protocolo (igual que en slave) ─────────────
#define CMD_PWM      0x01
#define CMD_DIGITAL  0x02
#define CMD_SERVO    0x03
#define CMD_NEOPIXEL 0x04
#define CMD_PING     0xF0
#define CMD_RESET    0xFF

void setup() {
  // Serial al PC (USB)
  Serial.begin(9600);
  
  // Serial al slave (pines alternativos)
  Serial2.begin(9600, SERIAL_8N1, UART_RX_PIN, UART_TX_PIN);
  
  Serial.println("\n=== MASTER para ESP32 Slave ===");
  Serial.printf("UART a Slave: TX=%d, RX=%d\n", UART_TX_PIN, UART_RX_PIN);
  Serial.println("Comandos disponibles:");
  Serial.println("  ping                    - Enviar PING");
  Serial.println("  pwm <1-4> <0-255>       - Control PWM motor");
  Serial.println("  servo <0-180>           - Control servo");
  Serial.println("  neo <0|1|2|3|ff>        - NeoPixel (0=off,1=red,2=green,3=blue,ff=white)");
  Serial.println("  digital <pin> <0|1>     - Pin digital (ej: digital 11 1)");
  Serial.println("  reset                    - Reset slave");
  Serial.println("  status                   - Ver estado");
  Serial.println();
}

void loop() {
  // Reenviar comandos del PC al slave
  if (Serial.available()) {
    String cmd = Serial.readStringUntil('\n');
    cmd.trim();
    
    if (cmd == "ping") {
      sendCommand(CMD_PING, 0x00, 0x00);
      Serial.println("→ PING enviado");
    }
    else if (cmd == "reset") {
      sendCommand(CMD_RESET, 0x00, 0x00);
      Serial.println("→ RESET enviado");
    }
    else if (cmd == "status") {
      Serial.printf("Estado: Conectado a slave por pines TX:%d RX:%d\n", 
                   UART_TX_PIN, UART_RX_PIN);
    }
    else if (cmd.startsWith("pwm ")) {
      // pwm 1 128
      int motor = cmd.substring(4, cmd.indexOf(' ', 5)).toInt();
      int value = cmd.substring(cmd.lastIndexOf(' ') + 1).toInt();
      sendCommand(CMD_PWM, motor, value);
      Serial.printf("→ PWM M%d = %d\n", motor, value);
    }
    else if (cmd.startsWith("servo ")) {
      int angle = cmd.substring(6).toInt();
      sendCommand(CMD_SERVO, 0x00, angle);
      Serial.printf("→ Servo = %d°\n", angle);
    }
    else if (cmd.startsWith("neo ")) {
      String color = cmd.substring(4);
      int val;
      if (color == "ff") val = 0xFF;
      else val = color.toInt();
      sendCommand(CMD_NEOPIXEL, 0x00, val);
      Serial.printf("→ NeoPixel = 0x%02X\n", val);
    }
    else if (cmd.startsWith("digital ")) {
      // digital 11 1
      int pinId = cmd.substring(8, cmd.indexOf(' ', 9)).toInt();
      int val = cmd.substring(cmd.lastIndexOf(' ') + 1).toInt();
      // Convertir a hexadecimal si viene en decimal
      int pinHex;
      if (pinId == 11) pinHex = 0x11;
      else if (pinId == 12) pinHex = 0x12;
      else if (pinId == 21) pinHex = 0x21;
      else if (pinId == 22) pinHex = 0x22;
      else if (pinId == 31) pinHex = 0x31;
      else if (pinId == 32) pinHex = 0x32;
      else if (pinId == 41) pinHex = 0x41;
      else if (pinId == 42) pinHex = 0x42;
      else pinHex = pinId;
      
      sendCommand(CMD_DIGITAL, pinHex, val);
      Serial.printf("→ Digital pin 0x%02X = %d\n", pinHex, val);
    }
    else if (cmd.length() > 0) {
      Serial.println("Comando no reconocido");
    }
  }
  
  // Leer respuestas del slave y mostrarlas
  if (Serial2.available()) {
    uint8_t resp = Serial2.read();
    Serial.printf("← Slave resp: 0x%02X", resp);
    
    // Decodificar respuesta
    switch(resp) {
      case 0xAA: Serial.println(" (PONG / OK)"); break;
      case 0x01: Serial.println(" (PWM OK)"); break;
      case 0x02: Serial.println(" (DIGITAL OK)"); break;
      case 0x03: Serial.println(" (SERVO OK)"); break;
      case 0x04: Serial.println(" (NEOPIXEL OK)"); break;
      case 0xBB: Serial.println(" (RESET OK)"); break;
      case 0xEE: Serial.println(" (ERROR)"); break;
      default: Serial.println(); break;
    }
  }
}

void sendCommand(uint8_t cmd, uint8_t pinId, uint8_t value) {
  uint8_t buffer[3] = {cmd, pinId, value};
  Serial2.write(buffer, 3);
}