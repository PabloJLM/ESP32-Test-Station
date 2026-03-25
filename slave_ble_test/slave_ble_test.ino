// ═══════════════════════════════════════════════════════════
//  SLAVE BLE TEST — Tesla Lab BALAM 2026
//  Firmware minimo para prueba de conectividad BLE.
//  No incluye perifericos — esos se prueban con slave.ino.
//
//  0x22 BLE_ADV   — value=1 inicia advertising, value=0 detiene
//  0x23 BLE_SCAN  — escanea y devuelve cantidad de dispositivos
//  0xF0 PING      — alive check
//  0xFF RESET
// ═══════════════════════════════════════════════════════════

#include <BLEDevice.h>
#include <BLEScan.h>
#include <BLEAdvertising.h>

#define BLE_DEVICE_NAME  "TeslaLab-ESP32"
#define BLE_SCAN_SECS    3

#define CMD_PING     0xF0
#define CMD_RESET    0xFF
#define CMD_BLE_ADV  0x22
#define CMD_BLE_SCAN 0x23

#define ACK_OK  0xAA
#define ACK_ERR 0xEE

BLEScan*        pScan = nullptr;
BLEAdvertising* pAdv  = nullptr;

void sendResponse(uint8_t ack, uint8_t cmd, uint8_t val) {
    uint8_t buf[3] = {ack, cmd, val};
    Serial.write(buf, 3);
}

void setup() {
    Serial.begin(9600);
    // Libera RAM de BT Classic — no la necesitamos
    esp_bt_controller_mem_release(ESP_BT_MODE_CLASSIC_BT);
    BLEDevice::init(BLE_DEVICE_NAME);
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

        case CMD_BLE_ADV: {
            if (!pAdv) {
                pAdv = BLEDevice::getAdvertising();
                // Device Information Service — visible en cualquier scanner BLE
                pAdv->addServiceUUID("0000180A-0000-1000-8000-00805F9B34FB");
                pAdv->setScanResponse(true);
            }
            value == 1 ? pAdv->start() : pAdv->stop();
            sendResponse(ACK_OK, CMD_BLE_ADV, value);
            break;
        }

        case CMD_BLE_SCAN: {
            if (!pScan) {
                pScan = BLEDevice::getScan();
                pScan->setActiveScan(false);
                pScan->setInterval(150);
                pScan->setWindow(100);
            }
            BLEScanResults* r = pScan->start(BLE_SCAN_SECS, false);
            uint8_t n = r ? (uint8_t)min(r->getCount(), 254) : 0;
            pScan->clearResults();
            sendResponse(ACK_OK, CMD_BLE_SCAN, n);
            break;
        }

        default:
            sendResponse(ACK_ERR, cmd, 0x00);
            break;
    }
}
