#pragma once
#include <ArduinoJson.h>
#include <string.h>
#include <stdint.h>
namespace mesh {
constexpr size_t LINE_LIMIT = 512;
struct Framer {
  char data[LINE_LIMIT + 1] = {};
  size_t used = 0;
  bool bad = false, carriage = false;
  // 1 = complete frame, -1 = rejected frame, 0 = incomplete.
  int feed(char c) {
    if (c == '\n') {
      data[used] = 0;
      const int result = bad || !used ? -1 : 1;
      used = 0; bad = carriage = false; return result;
    }
    if (c == '\r') { if (carriage) bad = true; carriage = true; return 0; }
    if (carriage) bad = true;
    if (uint8_t(c) < 32 || uint8_t(c) > 126 || used == LINE_LIMIT) bad = true;
    if (!bad) data[used++] = c;
    return 0;
  }
  void clear() { used = 0; bad = carriage = false; }
};
enum class HostKind { HELLO, SYNC, PING, RADIO_SYNC, SET_LOADS, EVENT_ACK };
struct HostMessage {
  HostKind kind = HostKind::HELLO;
  uint32_t boot = 0, epoch = 0, session = 0, seq = 0, target = 0, event = 0;
  uint16_t mask = 0;
  char selected = 0;
  bool accepted = false;
};
inline bool positive(JsonVariantConst value, uint32_t& out) {
  if (!value.is<uint32_t>() || value.is<bool>()) return false;
  out = value.as<uint32_t>(); return out != 0;
}
struct JsonReader {
  const char* cursor;
  int read() { return *cursor ? uint8_t(*cursor++) : -1; }
  size_t readBytes(char* buffer, size_t size) {
    size_t count = 0;
    while (count < size && *cursor) buffer[count++] = *cursor++;
    return count;
  }
};
inline bool parseHost(const char* line, HostMessage& out) {
  JsonDocument doc;
  JsonReader reader{line};
  if (deserializeJson(doc, reader, DeserializationOption::NestingLimit(2)) || !doc.is<JsonObject>()) return false;
  while (*reader.cursor == ' ' || *reader.cursor == '\t' || *reader.cursor == '\r') ++reader.cursor;
  if (*reader.cursor) return false;
  auto object = doc.as<JsonObjectConst>();
  if (!object["v"].is<unsigned>() || object["v"].is<bool>() || object["v"].as<unsigned>() != 2 ||
      !object["type"].is<const char*>()) return false;
  const char* type = object["type"].as<const char*>();
  HostMessage msg;
  if (!strcmp(type, "hello")) {
    if (object.size() != 2) return false;
    out = msg; return true;
  }
  if (!positive(object["boot"], msg.boot) || !positive(object["epoch"], msg.epoch) ||
      !positive(object["session"], msg.session)) return false;
  if (!strcmp(type, "sync")) {
    msg.kind = HostKind::SYNC;
    if (object.size() != 6 || object["selected"].isUnbound()) return false;
    if (!object["selected"].isNull()) {
      if (!object["selected"].is<const char*>()) return false;
      const char* room = object["selected"];
      if (strlen(room) != 1 || room[0] < 'A' || room[0] > 'C') return false;
      msg.selected = room[0];
    }
  } else if (!strcmp(type, "ping")) {
    msg.kind = HostKind::PING;
    if (object.size() != 5) return false;
  } else if (!strcmp(type, "event_ack")) {
    msg.kind = HostKind::EVENT_ACK;
    if (object.size() != 7 || !positive(object["event"], msg.event) ||
        !object["accepted"].is<bool>()) return false;
    msg.accepted = object["accepted"];
  } else if (!strcmp(type, "radio_sync") || !strcmp(type, "set_loads")) {
    msg.kind = !strcmp(type, "radio_sync") ? HostKind::RADIO_SYNC : HostKind::SET_LOADS;
    if (object.size() != 8 || !positive(object["seq"], msg.seq) ||
        !positive(object["target"], msg.target) || !object["mask"].is<uint16_t>() ||
        object["mask"].is<bool>()) return false;
    msg.mask = object["mask"];
    if ((msg.mask & ~uint16_t(0x01ff)) || (msg.kind == HostKind::RADIO_SYNC && msg.mask)) return false;
  } else return false;
  out = msg; return true;
}
}
