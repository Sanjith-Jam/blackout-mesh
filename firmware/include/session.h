#pragma once
#include "inputs.h"
#include "serial_protocol.h"
namespace mesh {
struct Session {
  Input input;
  uint32_t boot, epoch = 1, session = 0, floor, seen = 0, counter = 0;
  uint32_t pending[8] = {}, deadlines[8] = {};
  explicit Session(uint32_t id, uint32_t previous) : boot(id), floor(previous) {}
  void disconnect() {
    input.disconnect(); session = 0;
    for (auto& event : pending) event = 0;
    if (epoch != UINT32_MAX) ++epoch;
  }
  bool context(const HostMessage& msg) const {
    return input.synced && msg.boot == boot && msg.epoch == epoch && msg.session == session;
  }
  bool sync(const HostMessage& msg, uint32_t now) {
    if (input.synced || epoch == UINT32_MAX || msg.boot != boot || msg.epoch != epoch ||
        !msg.session || msg.session < floor) return false;
    session = floor = msg.session; seen = now; input.sync(msg.selected); return true;
  }
  bool stale(uint32_t now) {
    return input.synced && uint32_t(now - seen) >= 1500;
  }
  uint32_t event(uint32_t now) {
    if (!input.synced || counter == UINT32_MAX) return 0;
    for (int i = 0; i < 8; ++i) if (!pending[i]) {
      pending[i] = ++counter; deadlines[i] = now; return counter;
    }
    return 0;
  }
  bool acknowledge(uint32_t event) {
    for (auto& item : pending) if (item == event && event) { item = 0; return true; }
    return false;
  }
  bool eventTimeout(uint32_t now) const {
    for (int i = 0; i < 8; ++i)
      if (pending[i] && uint32_t(now - deadlines[i]) >= 1000) return true;
    return false;
  }
};
}
