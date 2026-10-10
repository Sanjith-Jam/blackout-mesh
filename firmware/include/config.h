#pragma once
#include <stdint.h>
// User-reported RC522 wiring, 2026-10-09. Board carrier and operation still unverified.
#define RFID_ENABLED 1
#define RFID_SS 21
#define RFID_RST 22
#define RFID_SCK 18
#define RFID_MISO 19
#define RFID_MOSI 23
#define BUTTON_END -1  // not fitted: press a room button again to end it
#define BUTTON_SHORTAGE -1  // not fitted: deprived (shortage) from the website
#define BUTTON_RESTORE -1  // not fitted: normal supply from the website
#define BUTTON_RESET -1  // not fitted: reset from the website
// Room buttons: start a session for that room without a card (RFID fallback / card-free demo).
#define BUTTON_FALLBACK_A 33
#define BUTTON_FALLBACK_B 13
#define BUTTON_FALLBACK_C 14
#define BUTTON_ACTIVE_LEVEL 0
#define RADIO_CHANNEL 1
#define SERIAL_BAUD 115200
#if __has_include("hardware.local.h")
#include "hardware.local.h"
#endif
namespace config {
// Index order matters: 0 END, 1 SHORTAGE (deprived of kW), 2 RESTORE (normal), 3 RESET (hold),
// 4/5/6 room A/B/C buttons.
constexpr int buttons[] = {BUTTON_END, BUTTON_SHORTAGE, BUTTON_RESTORE, BUTTON_RESET,
                           BUTTON_FALLBACK_A, BUTTON_FALLBACK_B, BUTTON_FALLBACK_C};
constexpr int BUTTON_COUNT = sizeof(buttons) / sizeof(buttons[0]);
constexpr int RESET_BUTTON_INDEX = 3;
constexpr int FIRST_ROOM_BUTTON_INDEX = 4;  // room A; B and C follow
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
