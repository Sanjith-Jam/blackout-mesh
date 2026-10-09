#include "buttons.h"
#include "inputs.h"
#include "protocol.h"
#include <assert.h>
#include <stdio.h>
#include <initializer_list>
using namespace mesh;
int main() {
  Input input;
  assert(!input.synced && !input.selected);
  input.sync(0);
  assert(input.card(true, 'A', 0) == Action::START_SESSION);
  assert(input.card(true, 'A', 1000) == Action::NONE);
  input.card(false, 0, 1001); input.card(false, 0, 1251);
  assert(input.card(true, 'A', 1252) == Action::START_SESSION);
  input.card(false, 0, 1300); input.card(false, 0, 1550);
  assert(input.card(true, 'B', 1551) == Action::START_SESSION);
  assert(input.button(0) == Action::END_SESSION && input.selected == 'B');
  input.card(false, 0, 1600); input.card(false, 0, 1850);
  assert(input.card(true, 0, 1851) == Action::UNKNOWN_CARD && input.selected == 'B');
  input.sync(0);
  assert(input.button(0) == Action::IGNORED_NO_SELECTION);
  assert(input.button(1) == Action::SHORTAGE && input.button(2) == Action::RESTORE);
  input.disconnect(); assert(input.button(1) == Action::UNSYNCHRONIZED);
  Button button;
  assert(!button.poll(true, 0)); assert(!button.poll(false, 5));
  assert(!button.poll(true, 10)); assert(button.poll(true, 40));
  assert(!button.poll(true, 100));
  Button reset;
  assert(!reset.poll(true, 0, true)); assert(!reset.poll(true, 30, true));
  assert(!reset.poll(false, 1000, true)); assert(!reset.poll(false, 1030, true));
  assert(!reset.poll(true, 1100, true)); assert(!reset.poll(true, 1130, true));
  assert(!reset.poll(true, 3129, true)); assert(reset.poll(true, 3130, true));
  assert(!reset.poll(true, 5000, true));
  assert(crc16(reinterpret_cast<const uint8_t*>("123456789"), 9) == 0x29b1);
  for (uint16_t mask : {uint16_t(8), uint16_t(16), uint16_t(32), uint16_t(24), uint16_t(56), uint16_t(511)}) {
    Packet p; p.kind = SET_LOADS; p.session = 4; p.seq = 7; p.boot = 8; p.mask = mask;
    uint8_t bytes[26]; encode(p, bytes); Packet decoded;
    assert(decode(bytes, 26, decoded) && sameCommand(p, decoded));
    assert(!decode(bytes, 25, decoded));
    bytes[20] ^= 1; assert(!decode(bytes, 26, decoded));
  }
  puts("input/buttons/packet assertions passed");
}
