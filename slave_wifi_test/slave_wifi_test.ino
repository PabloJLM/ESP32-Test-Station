// ═══════════════════════════════════════════════════════════
//  SLAVE WiFi TEST — Tesla Lab BALAM 2026
//  Protocolo: [CMD, 0x00, 0x00] → [ACK, CMD, VAL]
//
//  0x10  WIFI_SCAN    — cuenta redes visibles (VAL = count)
//  0x11  WIFI_AP      — levanta AP "TeslaLab-Test" (VAL = 1 OK)
//  0x12  WIFI_CONNECT — conecta STA a "galileo" (VAL = 1 OK)
//  0x13  WIFI_PING    — ping UDP 8.8.8.8 (VAL = RTT ms, 255 = fallo)
//  0x14  WIFI_DISC    — desconecta todo (VAL = 0)
//  0xF0  PING         — alive check
//  0xFF  RESET
// ═══════════════════════════════════════════════════════════

#include <WiFi.h>
#include <WiFiUdp.h>

#define WIFI_SSID        "galileo"
#define WIFI_PASS        ""
#define WIFI_TIMEOUT_MS   8000

#define AP_SSID          "TeslaLab-Test"
#define AP_PASS          ""

#define PING_HOST        "8.8.8.8"
#define PING_PORT        53     // DNS — responde rapido

#define CMD_PING         0xF0
#define CMD_RESET        0xFF
#define CMD_WIFI_SCAN    0x10
#define CMD_WIFI_AP      0x11
#define CMD_WIFI_CONNECT 0x12
#define CMD_WIFI_PING    0x13
#define CMD_WIFI_DISC    0x14

#define ACK_OK  0xAA
#define ACK_ERR 0xEE

WiFiUDP udp;

void sendResponse(uint8_t ack, uint8_t cmd, uint8_t val) {
    uint8_t buf[3] = {ack, cmd, val};
    Serial.write(buf, 3);
}

void setup() {
    Serial.begin(9600);
    WiFi.mode(WIFI_OFF);
    delay(100);
    sendResponse(ACK_OK, CMD_PING, 0x00);
}

void loop() {
    if (Serial.available() < 3) return;
    uint8_t cmd   = Serial.read();
    uint8_t pinId = Serial.read();
    uint8_t value = Serial.read();

    switch (cmd) {

        case CMD_PING:
            sendResponse(ACK_OK, CMD_PING, 0x00);
            break;

        case CMD_RESET:
            sendResponse(ACK_OK, CMD_RESET, 0x00);
            delay(100);
            ESP.restart();
            break;

        case CMD_WIFI_SCAN: {
            // Desconectar antes de escanear
            WiFi.mode(WIFI_STA);
            WiFi.disconnect(true);
            delay(100);
            int n = WiFi.scanNetworks(false, false, false, 300);
            if (n < 0) n = 0;
            WiFi.scanDelete();
            uint8_t count = (uint8_t)min(n, 254);
            sendResponse(count > 0 ? ACK_OK : ACK_ERR, CMD_WIFI_SCAN, count);
            break;
        }

        case CMD_WIFI_AP: {
            // Levanta AP propio — no necesita router
            WiFi.mode(WIFI_AP);
            bool ok = WiFi.softAP(AP_SSID, AP_PASS);
            delay(200);
            sendResponse(ok ? ACK_OK : ACK_ERR, CMD_WIFI_AP, ok ? 1 : 0);
            break;
        }

        case CMD_WIFI_CONNECT: {
            WiFi.mode(WIFI_STA);
            WiFi.disconnect(true);
            delay(100);
            WiFi.begin(WIFI_SSID, WIFI_PASS);
            uint32_t t0 = millis();
            while (!WiFi.isConnected() && millis() - t0 < WIFI_TIMEOUT_MS) {
                delay(100);
            }
            bool ok = WiFi.isConnected();
            sendResponse(ok ? ACK_OK : ACK_ERR, CMD_WIFI_CONNECT, ok ? 1 : 0);
            break;
        }

        case CMD_WIFI_PING: {
            if (!WiFi.isConnected()) {
                sendResponse(ACK_ERR, CMD_WIFI_PING, 255);
                break;
            }
            // Ping UDP al puerto 53 de 8.8.8.8 — si responde, hay internet
            udp.begin(12345);
            uint8_t dummy[1] = {0x00};
            uint32_t t0 = millis();
            udp.beginPacket(PING_HOST, PING_PORT);
            udp.write(dummy, 1);
            udp.endPacket();
            // Esperar respuesta hasta 3 segundos
            uint32_t rtt = 0;
            bool ok = false;
            while (millis() - t0 < 3000) {
                if (udp.parsePacket() > 0) {
                    rtt = millis() - t0;
                    ok = true;
                    break;
                }
                delay(10);
            }
            udp.stop();
            // Si no respondio, igual reportar tiempo transcurrido con ERR
            if (!ok) rtt = 255;
            sendResponse(ok ? ACK_OK : ACK_ERR,
                         CMD_WIFI_PING,
                         (uint8_t)min(rtt, (uint32_t)254));
            break;
        }

        case CMD_WIFI_DISC:
            WiFi.softAPdisconnect(true);
            WiFi.disconnect(true);
            WiFi.mode(WIFI_OFF);
            delay(100);
            sendResponse(ACK_OK, CMD_WIFI_DISC, 0x00);
            break;

        default:
            sendResponse(ACK_ERR, cmd, 0x00);
            break;
    }
}
