// ═══════════════════════════════════════════════════════════
//  MAESTRO BRIDGE — Tesla Lab BALAM 2026
//  Rol: Recibe comandos del PC por USB Serial,
//       los reenvía al slave por UART2,
//       reenvía respuestas del slave al PC.
//
//  UART2 al slave: GPIO4 (TX) → RX slave (GPIO3)
//                  GPIO2 (RX) ← TX slave (GPIO1)
// ═══════════════════════════════════════════════════════════

// ── UART2 al slave ─────────────────────────────────────────────
#define SLAVE_TX    4   // GPIO4 → RX del slave (GPIO3)
#define SLAVE_RX    2   // GPIO2 ← TX del slave (GPIO1)
#define SLAVE_BAUD  9600

void setup() {
    // Serial0 para comunicación con PC
    Serial.begin(9600);
    
    // Serial2 para comunicación con slave
    Serial2.begin(SLAVE_BAUD, SERIAL_8N1, SLAVE_RX, SLAVE_TX);
    
    Serial.println("=== MAESTRO BRIDGE ===");
    Serial.println("Reenviando: PC ↔ Slave (UART2 en GPIO2/GPIO4)");
    Serial.println();
}

void loop() {
    // PC → Slave
    if (Serial.available()) {
        uint8_t data = Serial.read();
        Serial2.write(data);
    }
    
    // Slave → PC
    if (Serial2.available()) {
        uint8_t data = Serial2.read();
        Serial.write(data);
    }
}