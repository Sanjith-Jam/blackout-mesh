// Board B (output station) Phase 2 indicator test.
// Type a commanded mask on Serial (decimal or 0x hex), e.g. 0, 8, 16, 32, 24, 56.
// Classroom LEDs show only the projected bits: applied = mask & 0x0038.
// Bit 3 = Lab A, bit 4 = Lab B, bit 5 = Lab C (full-catalog positions).
// Pins are a proposal; confirm against your board before wiring.

const uint8_t PIN_A = 25, PIN_B = 26, PIN_C = 27, PIN_LINK = 33;
const uint16_t FULL_MASK = 0x01FF, ROOM_MASK = 0x0038;

uint16_t applied = 0;

void applyMask(uint16_t commanded) {
  applied = commanded & ROOM_MASK;
  digitalWrite(PIN_A, (applied >> 3) & 1);
  digitalWrite(PIN_B, (applied >> 4) & 1);
  digitalWrite(PIN_C, (applied >> 5) & 1);
  Serial.printf("ACK commanded=0x%04x applied=0x%04x  A=%s B=%s C=%s\n", commanded, applied,
                (applied & 0x08) ? "ON" : "off", (applied & 0x10) ? "ON" : "off",
                (applied & 0x20) ? "ON" : "off");
}

void setup() {
  Serial.begin(115200);
  for (uint8_t p : {PIN_A, PIN_B, PIN_C, PIN_LINK}) { pinMode(p, OUTPUT); digitalWrite(p, LOW); }
  delay(300);
  Serial.println("\nBoard B fixture test booted, all classroom outputs OFF");
  Serial.println("Enter mask: 0, 8 (A), 16 (B), 32 (C), 24 (A+B), 56 (all)");
}

void loop() {
  static unsigned long lastBlink = 0;
  if (millis() - lastBlink > 1000) {  // link LED slow blink = alive, test mode
    lastBlink = millis();
    digitalWrite(PIN_LINK, !digitalRead(PIN_LINK));
  }
  if (Serial.available()) {
    String s = Serial.readStringUntil('\n');
    s.trim();
    if (s.length() == 0) return;
    char *end;
    long v = strtol(s.c_str(), &end, 0);
    if (*end != '\0' || v < 0 || v > FULL_MASK) {
      Serial.printf("REJECT '%s' (want 0..0x01ff), outputs unchanged\n", s.c_str());
      return;
    }
    applyMask((uint16_t)v);
  }
}
