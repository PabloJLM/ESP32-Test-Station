// ═══════════════════════════════════════════════════════════
//  SLAVE CONECTIVIDAD — Tesla Lab BALAM 2026
//  WiFi + BLE en un solo firmware.
//  Comunicación con maestro por Serial0 (GPIO1/GPIO3)
//
//  WiFi:  0x10 SCAN | 0x11 AP | 0x12 STA | 0x13 PING | 0x14 DISC
//  BLE:   0x20 SCAN | 0x21 ADV | 0x22 STOP
//  Com:   0xF0 PING | 0xFF RESET
// ═══════════════════════════════════════════════════════════

#include <WiFi.h>
#include <WiFiUdp.h>
#include <BLEDevice.h>
#include <BLEScan.h>
#include <BLEAdvertising.h>

#define DEVICE_NAME      "TeslaLab-ESP32"
#define WIFI_SSID        "Balam_Test"
#define WIFI_PASS        "Reze_123"
#define WIFI_TIMEOUT_MS   8000
#define AP_SSID          "TeslaLab-Test"
#define AP_PASS          ""
#define SCAN_SECS        5

// ── Comandos WiFi ─────────────────────────────────────────
#define CMD_WIFI_SCAN    0x10
#define CMD_WIFI_AP      0x11
#define CMD_WIFI_CONNECT 0x12
#define CMD_WIFI_PING    0x13
#define CMD_WIFI_DISC    0x14

// ── Comandos BLE ──────────────────────────────────────────
#define CMD_BLE_SCAN     0x20
#define CMD_BLE_ADV      0x21
#define CMD_BLE_STOP     0x22

// ── Comunes ───────────────────────────────────────────────
#define CMD_PING         0xF0
#define CMD_RESET        0xFF
#define ACK_OK           0xAA
#define ACK_ERR          0xEE

WiFiUDP         udp;
BLEScan*        pScan = nullptr;
BLEAdvertising* pAdv  = nullptr;
bool            advOn = false;

void sendResponse(uint8_t ack, uint8_t cmd, uint8_t val) {
    uint8_t buf[3] = {ack, cmd, val};
    Serial.write(buf, 3);
}

void setup() {
    Serial.begin(9600);

    // WiFi apagado por default
    WiFi.mode(WIFI_OFF);
    delay(100);

    // BLE: liberar Classic BT (no se usa), iniciar BLE
    esp_bt_controller_mem_release(ESP_BT_MODE_CLASSIC_BT);
    BLEDevice::init(DEVICE_NAME);

    sendResponse(ACK_OK, CMD_PING, 0x00);
}

void loop() {
    if (Serial.available() < 3) return;
    uint8_t cmd   = Serial.read();
    uint8_t pinId = Serial.read();
    uint8_t value = Serial.read();

    switch (cmd) {

        // ── Comunes ───────────────────────────────────────
        case CMD_PING:
            sendResponse(ACK_OK, CMD_PING, 0x00);
            break;

        case CMD_RESET:
            sendResponse(ACK_OK, CMD_RESET, 0x00);
            delay(100);
            ESP.restart();
            break;

        // ── WiFi ──────────────────────────────────────────
        case CMD_WIFI_SCAN: {
            if (advOn && pAdv) { pAdv->stop(); advOn = false; }
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
            if (advOn && pAdv) { pAdv->stop(); advOn = false; }
            WiFi.mode(WIFI_AP);
            bool ok = WiFi.softAP(AP_SSID, AP_PASS);
            delay(200);
            sendResponse(ok ? ACK_OK : ACK_ERR, CMD_WIFI_AP, ok ? 1 : 0);
            break;
        }

        case CMD_WIFI_CONNECT: {
            if (advOn && pAdv) { pAdv->stop(); advOn = false; }
            WiFi.mode(WIFI_STA);
            WiFi.disconnect(true);
            delay(100);
            WiFi.begin(WIFI_SSID, WIFI_PASS);
            uint32_t t0 = millis();
            while (!WiFi.isConnected() && millis() - t0 < WIFI_TIMEOUT_MS)
                delay(100);
            bool ok = WiFi.isConnected();
            sendResponse(ok ? ACK_OK : ACK_ERR, CMD_WIFI_CONNECT, ok ? 1 : 0);
            break;
        }

        case CMD_WIFI_PING: {
            if (!WiFi.isConnected()) {
                sendResponse(ACK_ERR, CMD_WIFI_PING, 255);
                break;
            }
            udp.begin(12345);
            uint8_t dummy[1] = {0x00};
            uint32_t t0 = millis();
            udp.beginPacket("192.168.1.1", 53);
            udp.write(dummy, 1);
            udp.endPacket();
            bool ok = false;
            uint32_t rtt = 255;
            while (millis() - t0 < 3000) {
                if (udp.parsePacket() > 0) {
                    rtt = millis() - t0; ok = true; break;
                }
                delay(10);
            }
            udp.stop();
            sendResponse(ok ? ACK_OK : ACK_ERR, CMD_WIFI_PING,
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

        // ── BLE ───────────────────────────────────────────
        case CMD_BLE_SCAN: {
            if (advOn && pAdv) { pAdv->stop(); advOn = false; }
            if (!pScan) {
                pScan = BLEDevice::getScan();
                pScan->setActiveScan(false);
                pScan->setInterval(100);
                pScan->setWindow(80);
            }
            BLEScanResults* res = pScan->start(SCAN_SECS, false);
            uint8_t count = res ? (uint8_t)min((int)res->getCount(), 254) : 0;
            pScan->clearResults();
            sendResponse(ACK_OK, CMD_BLE_SCAN, count);
            break;
        }

        case CMD_BLE_ADV: {
            WiFi.mode(WIFI_OFF);
            delay(50);
            if (!pAdv) {
                pAdv = BLEDevice::getAdvertising();
                pAdv->addServiceUUID("0000180A-0000-1000-8000-00805F9B34FB");
                pAdv->setScanResponse(true);
                pAdv->setMinPreferred(0x06);
            }
            if (!advOn) { pAdv->start(); advOn = true; }
            sendResponse(ACK_OK, CMD_BLE_ADV, 1);
            break;
        }

        case CMD_BLE_STOP:
            if (pAdv && advOn) { pAdv->stop(); advOn = false; }
            sendResponse(ACK_OK, CMD_BLE_STOP, 0);
            break;

        default:
            sendResponse(ACK_ERR, cmd, 0x00);
            break;
    }
}