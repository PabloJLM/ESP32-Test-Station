// ═══════════════════════════════════════════════════════════
//  SLAVE WiFi TEST — Tesla Lab BALAM 2026
//  Firmware minimo para prueba de conectividad WiFi.
//  No incluye perifericos — esos se prueban con slave.ino.
//
//  0x10 WIFI_SCAN     — cantidad de redes visibles
//  0x11 WIFI_CONNECT  — conectar al SSID predefinido
//  0x12 WIFI_PING     — RTT TCP al gateway (ms, 255=fallo)
//  0x13 WIFI_RSSI     — señal en % (1-100)
//  0x14 WIFI_HTTP     — HTTP GET (devuelve codigo, 200=OK)
//  0x15 WIFI_DISC     — desconectar
//  0xF0 PING          — alive check
//  0xFF RESET
// ═══════════════════════════════════════════════════════════

#include <WiFi.h>
#include <HTTPClient.h>

#define WIFI_SSID        "galileo"
#define WIFI_PASS        ""
#define WIFI_TIMEOUT_MS   8000
#define HTTP_TEST_URL    "http://httpbin.org/get"

#define CMD_PING         0xF0
#define CMD_RESET        0xFF
#define CMD_WIFI_SCAN    0x10
#define CMD_WIFI_CONNECT 0x11
#define CMD_WIFI_PING    0x12
#define CMD_WIFI_RSSI    0x13
#define CMD_WIFI_HTTP    0x14
#define CMD_WIFI_DISC    0x15

#define ACK_OK  0xAA
#define ACK_ERR 0xEE

void sendResponse(uint8_t ack, uint8_t cmd, uint8_t val) {
    uint8_t buf[3] = {ack, cmd, val};
    Serial.write(buf, 3);
}

void setup() {
    Serial.begin(9600);
    WiFi.mode(WIFI_STA);
    WiFi.disconnect(true);
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
            WiFi.disconnect(true);
            delay(100);
            int n = WiFi.scanNetworks(false, false, false, 300);
            sendResponse(n > 0 ? ACK_OK : ACK_ERR,
                         CMD_WIFI_SCAN,
                         n > 0 ? (uint8_t)min(n, 255) : 0);
            break;
        }

        case CMD_WIFI_CONNECT: {
            if (!WiFi.isConnected()) {
                WiFi.begin(WIFI_SSID, WIFI_PASS);
                uint32_t t0 = millis();
                while (!WiFi.isConnected() && millis() - t0 < WIFI_TIMEOUT_MS)
                    delay(100);
            }
            uint8_t ok = WiFi.isConnected() ? 1 : 0;
            sendResponse(ok ? ACK_OK : ACK_ERR, CMD_WIFI_CONNECT, ok);
            break;
        }

        case CMD_WIFI_PING: {
            if (!WiFi.isConnected()) {
                sendResponse(ACK_ERR, CMD_WIFI_PING, 255);
                break;
            }
            WiFiClient c;
            uint32_t t0  = millis();
            bool ok      = c.connect(WiFi.gatewayIP(), 80, 500);
            uint32_t rtt = millis() - t0;
            c.stop();
            sendResponse(ok ? ACK_OK : ACK_ERR,
                         CMD_WIFI_PING,
                         ok ? (uint8_t)min(rtt, (uint32_t)254) : 255);
            break;
        }

        case CMD_WIFI_RSSI: {
            if (!WiFi.isConnected()) {
                sendResponse(ACK_ERR, CMD_WIFI_RSSI, 0);
                break;
            }
            int32_t rssi = WiFi.RSSI();
            uint8_t pct  = (rssi < -100 || rssi >= 0) ? 1
                         : (uint8_t)map(rssi, -100, 0, 1, 100);
            sendResponse(ACK_OK, CMD_WIFI_RSSI, pct);
            break;
        }

        case CMD_WIFI_HTTP: {
            if (!WiFi.isConnected()) {
                sendResponse(ACK_ERR, CMD_WIFI_HTTP, 0);
                break;
            }
            HTTPClient http;
            http.begin(HTTP_TEST_URL);
            http.setTimeout(5000);
            int code = http.GET();
            http.end();
            uint8_t c2 = code > 0 ? (uint8_t)min(code, 254) : 0;
            sendResponse(c2 > 0 ? ACK_OK : ACK_ERR, CMD_WIFI_HTTP, c2);
            break;
        }

        case CMD_WIFI_DISC:
            WiFi.disconnect(true);
            sendResponse(ACK_OK, CMD_WIFI_DISC, 0x00);
            break;

        default:
            sendResponse(ACK_ERR, cmd, 0x00);
            break;
    }
}
