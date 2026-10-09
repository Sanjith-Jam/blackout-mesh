#pragma once
#include <Arduino.h>
#include <ArduinoJson.h>
#include "session.h"
namespace mesh {
class SerialBridge {
  struct Line { char bytes[513]; size_t size = 0, sent = 0; };
  Line lines[8];
  uint8_t head = 0, count = 0;
 public:
  Framer framer;
  bool failed = false;
  bool emit(const JsonDocument& doc) {
    if (count == 8 || measureJson(doc) > 511) { failed = true; return false; }
    auto& line = lines[(head + count) % 8];
    line.size = serializeJson(doc, line.bytes, sizeof(line.bytes));
    line.bytes[line.size++] = '\n'; line.sent = 0; ++count; return true;
  }
  void clear() { count = 0; head = 0; framer.clear(); }
  void flush() {
    if (!count) return;
    auto& line = lines[head];
    size_t size = min(size_t(Serial.availableForWrite()), line.size - line.sent);
    if (size) line.sent += Serial.write(reinterpret_cast<uint8_t*>(line.bytes + line.sent), size);
    if (line.sent == line.size) { head = (head + 1) % 8; --count; }
  }
};
}
