// ═══════════════════════════════════════════════════════════
//  SLAVE BLE TEST — Tesla Lab BALAM 2026
//  Protocolo: [CMD, 0x00, 0x00] → [ACK, CMD, VAL]
//
//  0x20  BLE_SCAN  — escanea 5s, VAL = cantidad de dispositivos
//  0x21  BLE_ADV   — inicia advertising como "TeslaLab-ESP32"
//  0x22  BLE_STOP  — detiene advertising
//  0xF0  PING      — alive check
//  0xFF  RESET
// ═══════════════════════════════════════════════════════════

#include <BLEDevice.h>
#include <BLEScan.h>
#include <BLEAdvertising.h>

#define DEVICE_NAME  "TeslaLab-ESP32"
#define SCAN_SECS    5

#define CMD_PING     0xF0
#define CMD_RESET    0xFF
#define CMD_BLE_SCAN 0x20
#define CMD_BLE_ADV  0x21
#define CMD_BLE_STOP 0x22

#define ACK_OK  0xAA
#define ACK_ERR 0xEE

BLEScan*        pScan = nullptr;
BLEAdvertising* pAdv  = nullptr;
bool            advOn = false;

void sendResponse(uint8_t ack, uint8_t cmd, uint8_t val) {
    uint8_t buf[3] = {ack, cmd, val};
    Serial.write(buf, 3);
}

void setup() {
    Serial.begin(9600);
    // Libera RAM de BT Classic — no se usa
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

        case CMD_PING:
            sendResponse(ACK_OK, CMD_PING, 0x00);
            break;

        case CMD_RESET:
            sendResponse(ACK_OK, CMD_RESET, 0x00);
            delay(100);
            ESP.restart();
            break;

        case CMD_BLE_SCAN: {
            // Si estaba advertiseando, detener antes de escanear
            if (advOn && pAdv) { pAdv->stop(); advOn = false; }

            if (!pScan) {
                pScan = BLEDevice::getScan();
                pScan->setActiveScan(false);
                pScan->setInterval(100);
                pScan->setWindow(80);
            }
            BLEScanResults* results = pScan->start(SCAN_SECS, false);
            uint8_t count = results ? (uint8_t)min(results->getCount(), 254) : 0;
            pScan->clearResults();
            sendResponse(ACK_OK, CMD_BLE_SCAN, count);
            break;
        }

        case CMD_BLE_ADV: {
            if (!pAdv) {
                pAdv = BLEDevice::getAdvertising();
                // Generic Access service — visible en cualquier scanner BLE
                pAdv->addServiceUUID("0000180A-0000-1000-8000-00805F9B34FB");
                pAdv->setScanResponse(true);
                pAdv->setMinPreferred(0x06);
            }
            if (!advOn) {
                pAdv->start();
                advOn = true;
            }
            sendResponse(ACK_OK, CMD_BLE_ADV, 1);
            break;
        }

        case CMD_BLE_STOP: {
            if (pAdv && advOn) {
                pAdv->stop();
                advOn = false;
            }
            sendResponse(ACK_OK, CMD_BLE_STOP, 0);
            break;
        }

        default:
            sendResponse(ACK_ERR, cmd, 0x00);
            break;
    }
}
