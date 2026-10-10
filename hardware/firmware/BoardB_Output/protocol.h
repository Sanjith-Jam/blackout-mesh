#pragma once
#include <stddef.h>
#include <stdint.h>

namespace mesh {
constexpr uint16_t VALID_MASK = 0x01ff, CLASSROOM_MASK = 0x0038;
constexpr size_t PACKET_SIZE = 26;
enum Kind : uint8_t { HELLO = 1, SYNC, SET_LOADS, ACK, HEARTBEAT, BUTTON };
struct Packet {
  Kind kind = HELLO;
  uint32_t session = 0, seq = 0, boot = 0, ack = 0;
  uint16_t mask = 0;
  uint8_t status = 0, flags = 0;
};
inline uint16_t crc16(const uint8_t* data, size_t size) {
  uint16_t crc = 0xffff;
  for (size_t i = 0; i < size; ++i) {
    crc ^= uint16_t(data[i]) << 8;
    for (int b = 0; b < 8; ++b)
      crc = (crc & 0x8000) ? uint16_t((crc << 1) ^ 0x1021) : uint16_t(crc << 1);
  }
  return crc;
}
inline void put32(uint8_t* out, uint32_t value) {
  for (int i = 0; i < 4; ++i) out[i] = uint8_t(value >> (8 * i));
}
inline uint32_t get32(const uint8_t* in) {
  uint32_t value = 0;
  for (int i = 0; i < 4; ++i) value |= uint32_t(in[i]) << (8 * i);
  return value;
}
inline void encode(const Packet& p, uint8_t* out) {
  out[0] = 0xa5; out[1] = 2; out[2] = p.kind; out[3] = 2;
  put32(out + 4, p.session); put32(out + 8, p.seq);
  put32(out + 12, p.boot); put32(out + 16, p.ack);
  out[20] = uint8_t(p.mask); out[21] = uint8_t(p.mask >> 8);
  out[22] = p.status; out[23] = p.flags;
  const uint16_t crc = crc16(out, 24);
  out[24] = uint8_t(crc); out[25] = uint8_t(crc >> 8);
}
inline bool decode(const uint8_t* in, size_t size, Packet& p) {
  if (size != PACKET_SIZE || in[0] != 0xa5 || in[1] != 2 || in[3] != 2 ||
      in[2] < HELLO || in[2] > BUTTON || in[22] > 1 || in[23] != 0 ||
      crc16(in, 24) != (uint16_t(in[24]) | uint16_t(in[25]) << 8)) return false;
  p.kind = Kind(in[2]); p.session = get32(in + 4); p.seq = get32(in + 8);
  p.boot = get32(in + 12); p.ack = get32(in + 16);
  p.mask = uint16_t(in[20]) | uint16_t(in[21]) << 8;
  p.status = in[22]; p.flags = in[23];
  return p.boot && !(p.mask & ~VALID_MASK);
}
inline bool sameCommand(const Packet& a, const Packet& b) {
  return a.kind == b.kind && a.session == b.session && a.seq == b.seq &&
         a.boot == b.boot && a.mask == b.mask;
}
}
