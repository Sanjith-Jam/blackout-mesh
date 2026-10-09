#pragma once
#include <stdint.h>
namespace mesh {
struct Button {
  bool raw = false, stable = false, fired = false;
  uint32_t changed = 0, pressed = 0;
  bool poll(bool down, uint32_t now, bool reset = false) {
    if (down != raw) { raw = down; changed = now; }
    if (raw != stable && uint32_t(now - changed) >= 30) {
      stable = raw;
      if (stable) { pressed = now; fired = false; }
    }
    if (!stable || !raw || fired || (reset && uint32_t(now - pressed) < 2000)) return false;
    fired = true;
    return true;
  }
};
}
