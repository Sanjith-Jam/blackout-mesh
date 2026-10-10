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
// Fallback when the RFID reader fails: starts a session for room A without a card.
#define BUTTON_FALLBACK_A 33
#define BUTTON_ACTIVE_LEVEL 0
#define RADIO_CHANNEL 1
#define SERIAL_BAUD 115200
#if __has_include("hardware.local.h")
#include "hardware.local.h"
#endif
namespace config {
// Index order matters: 0 END, 1 SHORTAGE (deprived of kW), 2 RESTORE (normal), 3 RESET (hold), 4 FALLBACK room A.
constexpr int buttons[] = {BUTTON_END, BUTTON_SHORTAGE, BUTTON_RESTORE, BUTTON_RESET, BUTTON_FALLBACK_A};
constexpr int BUTTON_COUNT = sizeof(buttons) / sizeof(buttons[0]);
constexpr int RESET_BUTTON_INDEX = 3;
constexpr bool safeButton(int pin) {
  return pin == -1 || pin == 4 || pin == 13 || pin == 14 || pin == 25 ||
         pin == 26 || pin == 27 || pin == 32 || pin == 33;
}
constexpr bool allSafe(int i = 0) { return i >= BUTTON_COUNT || (safeButton(buttons[i]) && allSafe(i + 1)); }
constexpr bool distinctFrom(int i, int j) {
  return j >= BUTTON_COUNT || ((buttons[i] < 0 || buttons[j] < 0 || buttons[i] != buttons[j]) && distinctFrom(i, j + 1));
}
constexpr bool allDistinct(int i = 0) { return i >= BUTTON_COUNT || (distinctFrom(i, i + 1) && allDistinct(i + 1)); }
static_assert(allSafe(), "Unsafe button GPIO");
static_assert(allDistinct(), "Duplicate button GPIO");
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
