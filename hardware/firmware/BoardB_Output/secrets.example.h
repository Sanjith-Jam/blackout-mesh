#pragma once
// Copy to secrets.h (git-ignored) in this folder and fill in real values.
// PEER_MAC is board A's Wi-Fi STA MAC. PMK and LMK must be byte-for-byte the same
// 16 random bytes as board A's firmware/include/secrets.h.
#define PEER_CONFIGURED true
constexpr uint8_t PEER_MAC[6] = {};
constexpr uint8_t PMK[16] = {}, LMK[16] = {};
