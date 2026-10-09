#include "buttons.h"
#include "bridge.h"
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
  Bridge bridge; bridge.bind(10);
  Packet hello; hello.boot = 20;
  assert(bridge.receive(hello, 0) == RadioResult::REBOOT);
  assert(!bridge.submit(SET_LOADS, 1, 511, 20, 0));
  assert(bridge.submit(SYNC, 1, 0, 20, 0));
  Packet sent;
  assert(bridge.next(0, sent) && sent.kind == SYNC);
  Packet ack; ack.kind = ACK; ack.boot = 20; ack.session = 10; ack.ack = 1;
  assert(bridge.receive(ack, 1) == RadioResult::SYNCED);
  assert(bridge.submit(SET_LOADS, 2, 511, 20, 2));
  assert(bridge.next(2, sent) && sent.mask == 511);
  assert(!bridge.next(100, sent));
  assert(!bridge.submit(SET_LOADS, 2, 8, 20, 3));
  assert(bridge.submit(SET_LOADS, 2, 511, 20, 3));
  assert(!bridge.next(3, sent));
  ack.ack = 2; ack.mask = 56; ack.boot = 19;
  assert(bridge.receive(ack, 4) == RadioResult::NONE);
  ack.boot = 20; ack.session = 9;
  assert(bridge.receive(ack, 4) == RadioResult::NONE);
  ack.session = 10;
  assert(bridge.receive(ack, 4) == RadioResult::CONFIRMED);
  assert(bridge.receive(ack, 5) == RadioResult::NONE);
  assert(bridge.submit(SET_LOADS, 2, 511, 20, 5) && !bridge.active);
  assert(!bridge.submit(SET_LOADS, 3, 512, 20, 6));
  assert(bridge.submit(SET_LOADS, 3, 8, 20, 6));
  assert(bridge.submit(SET_LOADS, 4, 16, 20, 7));
  assert(bridge.submit(SET_LOADS, 5, 32, 20, 8));
  ack.ack = 3; ack.mask = 8;
  assert(bridge.receive(ack, 9) == RadioResult::CONFIRMED);
  assert(bridge.next(9, sent) && sent.seq == 5 && sent.mask == 32);
  assert(bridge.next(209, sent) && sent.seq == 5);
  assert(bridge.next(409, sent) && sent.seq == 5);
  assert(!bridge.next(609, sent));
  assert(bridge.tick(609) == RadioResult::TIMEOUT && !bridge.ready);
  assert(bridge.submit(SYNC, 6, 0, 20, 610));
  assert(bridge.next(610, sent));
  ack.ack = 6; ack.mask = 0;
  assert(bridge.receive(ack, 611) == RadioResult::SYNCED);
  assert(bridge.submit(SET_LOADS, 7, 8, 20, 612));
  ack.ack = 7; ack.mask = 16;
  assert(bridge.receive(ack, 613) == RadioResult::BAD_ACK && !bridge.ready);
  hello.boot = 21;
  assert(bridge.receive(hello, 614) == RadioResult::REBOOT && !bridge.ready);
  assert(!bridge.submit(SYNC, 8, 0, 20, 615));
  assert(bridge.tick(2114) == RadioResult::STALE);
  bridge.disconnect(); assert(!bridge.active && !bridge.session);
  puts("input/buttons/packet/radio assertions passed");
}
