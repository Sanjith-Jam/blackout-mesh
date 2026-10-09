#pragma once
#include <MFRC522.h>
#include <SPI.h>
#include "config.h"
#include "inputs.h"
namespace mesh {
class Reader {
  MFRC522 device{RFID_SS, RFID_RST};
  uint32_t polled = 0, health = 0;
  bool healthy = false, mappings = true;
 public:
  void begin() {
    for (int i = 0; i < 3; ++i) {
      const size_t size = strlen(CARD_UIDS[i]);
      if (size && size != 8 && size != 14 && size != 20) mappings = false;
      for (size_t j = 0; j < size; ++j)
        if (!strchr("0123456789ABCDEF", CARD_UIDS[i][j])) mappings = false;
      for (int j = 0; j < i; ++j)
        if (size && !strcmp(CARD_UIDS[i], CARD_UIDS[j])) mappings = false;
    }
    if (!RFID_ENABLED) return;
    SPI.begin(RFID_SCK, RFID_MISO, RFID_MOSI, RFID_SS);
    device.PCD_Init();
    const uint8_t version = device.PCD_ReadRegister(MFRC522::VersionReg);
    healthy = version != 0 && version != 0xff;
  }
  bool ok() const { return healthy && mappings; }
  // -2 device fault, -1 no sample, 0 absent, 1 complete UID, 2 read error.
  int poll(uint32_t now, char& room, char* uid) {
    if (!RFID_ENABLED) return -1;
    if (uint32_t(now - polled) < 50) return -1;
    polled = now;
    if (uint32_t(now - health) >= 1000) {
      health = now;
      uint8_t version = device.PCD_ReadRegister(MFRC522::VersionReg);
      healthy = version != 0 && version != 0xff;
    }
    if (!ok()) return -2;
    uint8_t atqa[2], size = 2;
    auto status = device.PICC_WakeupA(atqa, &size);
    if (status == MFRC522::STATUS_TIMEOUT) return 0;
    if (status != MFRC522::STATUS_OK && status != MFRC522::STATUS_COLLISION) return 2;
    room = 0; uid[0] = 0;
    if (!device.PICC_ReadCardSerial()) { device.PICC_HaltA(); return 2; }
    const uint8_t length = device.uid.size;
    if (length != 4 && length != 7 && length != 10) { device.PICC_HaltA(); return 2; }
    const char hex[] = "0123456789ABCDEF";
    for (uint8_t i = 0; i < length; ++i) {
      uid[i * 2] = hex[device.uid.uidByte[i] >> 4];
      uid[i * 2 + 1] = hex[device.uid.uidByte[i] & 15];
    }
    uid[length * 2] = 0;
    for (int i = 0; i < 3; ++i) if (!strcmp(uid, CARD_UIDS[i])) room = char('A' + i);
    device.PICC_HaltA(); device.PCD_StopCrypto1();
    return 1;
  }
};
}
