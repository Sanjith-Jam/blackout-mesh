#pragma once
#include <stdint.h>
// User-reported RC522 wiring, 2026-10-09. Board carrier and operation still unverified.
#define RFID_ENABLED 1
#define RFID_SS 21
#define RFID_RST 22
#define RFID_SCK 18
#define RFID_MISO 19
#define RFID_MOSI 23
#define BUTTON_END 25
#define BUTTON_SHORTAGE 26
#define BUTTON_RESTORE 27
#define BUTTON_RESET 32
#define BUTTON_ACTIVE_LEVEL 0
#define RADIO_CHANNEL 1
#define SERIAL_BAUD 115200
#if __has_include("hardware.local.h")
#include "hardware.local.h"
#endif
namespace config {
constexpr int buttons[] = {BUTTON_END, BUTTON_SHORTAGE, BUTTON_RESTORE, BUTTON_RESET};
constexpr bool safeButton(int pin) {
  return pin == -1 || pin == 4 || pin == 13 || pin == 14 || pin == 25 ||
         pin == 26 || pin == 27 || pin == 32 || pin == 33;
}
static_assert(safeButton(BUTTON_END) && safeButton(BUTTON_SHORTAGE) &&
              safeButton(BUTTON_RESTORE) && safeButton(BUTTON_RESET), "Unsafe button GPIO");
static_assert((BUTTON_END < 0 || BUTTON_SHORTAGE < 0 || BUTTON_END != BUTTON_SHORTAGE) &&
              (BUTTON_END < 0 || BUTTON_RESTORE < 0 || BUTTON_END != BUTTON_RESTORE) &&
              (BUTTON_END < 0 || BUTTON_RESET < 0 || BUTTON_END != BUTTON_RESET) &&
              (BUTTON_SHORTAGE < 0 || BUTTON_RESTORE < 0 || BUTTON_SHORTAGE != BUTTON_RESTORE) &&
              (BUTTON_SHORTAGE < 0 || BUTTON_RESET < 0 || BUTTON_SHORTAGE != BUTTON_RESET) &&
              (BUTTON_RESTORE < 0 || BUTTON_RESET < 0 || BUTTON_RESTORE != BUTTON_RESET), "Duplicate button GPIO");
}
#if __has_include("secrets.h")
#include "secrets.h"
#else
constexpr uint8_t PEER_MAC[6] = {};
constexpr uint8_t PMK[16] = {}, LMK[16] = {};
#define PEER_CONFIGURED false
#endif
#if __has_include("cards.local.h")
#include "cards.local.h"
#else
constexpr const char* CARD_UIDS[3] = {"", "", ""};
#endif
