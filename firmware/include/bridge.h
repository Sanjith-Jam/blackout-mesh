#pragma once
#include "protocol.h"
namespace mesh {
enum class RadioResult { NONE, CONFIRMED, SYNCED, TIMEOUT, REJECTED, BAD_ACK, REBOOT, STALE };
struct Bridge {
  uint32_t session = 0, boot = 0, highest = 0, started = 0, seen = 0;
  bool online = false, ready = false, active = false, queued = false, completed = false;
  uint8_t attempts = 0;
  Packet current, pending, last;
  void disconnect() { session = 0; ready = active = queued = completed = false; highest = 0; }
  void bind(uint32_t value) { disconnect(); session = value; }
  bool submit(Kind kind, uint32_t seq, uint16_t mask, uint32_t target, uint32_t now) {
    if (!session || !seq || !online || uint32_t(now - seen) >= 1500 || target != boot ||
        (mask & ~VALID_MASK) || (kind != SYNC && kind != SET_LOADS) ||
        (kind == SYNC && mask) || (kind == SET_LOADS && !ready)) return false;
    Packet p; p.kind = kind; p.session = session; p.seq = seq; p.boot = boot; p.mask = mask;
    if (seq <= highest) {
      return (active && sameCommand(p, current)) || (queued && sameCommand(p, pending)) ||
             (completed && sameCommand(p, last));
    }
    if (kind == SYNC && active) return false;
    highest = seq;
    if (active) { pending = p; queued = true; }
    else { current = p; active = true; attempts = 0; started = now; }
    return true;
  }
  // Returns a packet for transmission; retries preserve the complete identity.
  bool next(uint32_t now, Packet& out) {
    if (!active || uint32_t(now - started) >= 600 ||
        (attempts && uint32_t(now - started) < uint32_t(attempts) * 200)) return false;
    out = current; ++attempts; return true;
  }
  RadioResult tick(uint32_t now) {
    if (online && uint32_t(now - seen) >= 1500) {
      online = ready = false; active = queued = false;
      return RadioResult::STALE;
    }
    if (active && uint32_t(now - started) >= 600) {
      active = queued = ready = false;
      return RadioResult::TIMEOUT;
    }
    return RadioResult::NONE;
  }
  RadioResult receive(const Packet& p, uint32_t now) {
    if (p.kind == HELLO || p.kind == HEARTBEAT) {
      if (p.mask & ~CLASSROOM_MASK) return RadioResult::BAD_ACK;
      const bool reboot = boot != p.boot;
      boot = p.boot; seen = now; online = true;
      if (reboot) { ready = active = queued = completed = false; return RadioResult::REBOOT; }
      return RadioResult::NONE;
    }
    if (p.kind != ACK || !active || p.session != session || p.boot != boot ||
        p.ack != current.seq || uint32_t(now - started) >= 600) return RadioResult::NONE;
    const bool syncing = current.kind == SYNC;
    if (p.status || (p.mask & ~CLASSROOM_MASK) ||
        (!syncing && p.mask != (current.mask & CLASSROOM_MASK))) {
      active = queued = ready = false;
      return p.status ? RadioResult::REJECTED : RadioResult::BAD_ACK;
    }
    seen = now; online = true; ready = true; active = false;
    last = current; completed = true;
    if (queued) { current = pending; queued = false; active = true; attempts = 0; started = now; }
    return syncing ? RadioResult::SYNCED : RadioResult::CONFIRMED;
  }
};
}
