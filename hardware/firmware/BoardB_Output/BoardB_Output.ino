// Blackout Mesh, board B (output station), on board A's contract v2 (contracts/serial_protocol.md).
//
// Receives SYNC / SET_LOADS / HEARTBEAT from board A over encrypted ESP-NOW (or as "F <hex>" lines on
// USB for bench tests), drives the three classroom LEDs from mask & 0x0038, and ACKs the mask it
// actually applied. protocol.h is a byte-identical copy of firmware/include/protocol.h.
//
// LEDs: room A GPIO25, room B GPIO26, room C GPIO27, link GPIO33.
// Link LED: solid = synced and A heard within 1.5 s; fast blink = synced but stale; slow blink = waiting for SYNC.

#include <Preferences.h>
#include <WiFi.h>
#include <esp_now.h>
#include <esp_wifi.h>
#include "protocol.h"

#if __has_include("secrets.h")
#include "secrets.h"
#else
constexpr uint8_t PEER_MAC[6] = {};
constexpr uint8_t PMK[16] = {}, LMK[16] = {};
#define PEER_CONFIGURED false
#endif

using namespace mesh;

const uint8_t PIN_ROOM_A = 25, PIN_ROOM_B = 26, PIN_ROOM_C = 27, PIN_LINK = 33;
const uint8_t RADIO_CHANNEL = 1;
const uint32_t STALE_MS = 1500, HEARTBEAT_MS = 400;

enum Source : uint8_t { FROM_RADIO, FROM_SERIAL };
struct Frame { uint8_t source; uint8_t data[PACKET_SIZE]; };
QueueHandle_t rxQueue;

Preferences prefs;
uint32_t bootId = 0, session = 0, lastSeq = 0, mySeq = 0, lastSeen = 0, lastBeat = 0;
uint16_t applied = 0;
bool radioReady = false;
bool haveCached = false;
uint32_t cachedSeq = 0;
uint16_t cachedMask = 0;
uint32_t rxBad = 0;

void sendPacket(const Packet& p, uint8_t to) {
  uint8_t bytes[PACKET_SIZE];
  encode(p, bytes);
  if (to == FROM_SERIAL) {
    Serial.print("F ");
    for (size_t i = 0; i < PACKET_SIZE; ++i) Serial.printf("%02x", bytes[i]);
    Serial.println();
  } else if (radioReady) {
    esp_now_send(PEER_MAC, bytes, PACKET_SIZE);
  }
}

Packet outgoing(Kind kind) {
  Packet p;
  p.kind = kind; p.session = session; p.seq = ++mySeq; p.boot = bootId; p.mask = applied;
  return p;
}

void ack(uint32_t commandSeq, uint8_t status, uint8_t to) {
  Packet p = outgoing(ACK);
  p.ack = commandSeq; p.status = status;
  sendPacket(p, to);
}

void applyOutputs(uint16_t mask) {
  applied = mask & CLASSROOM_MASK;
  digitalWrite(PIN_ROOM_A, (applied >> 3) & 1);
  digitalWrite(PIN_ROOM_B, (applied >> 4) & 1);
  digitalWrite(PIN_ROOM_C, (applied >> 5) & 1);
}

void handle(const Frame& frame) {
  Packet p;
  if (!decode(frame.data, PACKET_SIZE, p)) { ++rxBad; Serial.println("# drop: invalid frame"); return; }
  if (p.boot != bootId) return;  // addressed to another boot of B: ignore
  const uint8_t reply = frame.source;
  if (p.kind == HEARTBEAT) {
    if (session && p.session == session) lastSeen = millis();
    return;
  }
  if (p.kind == SYNC) {
    if (p.mask || (session && p.session < session)) { ack(p.seq, 1, reply); return; }  // never downgrade
    if (p.session != session) haveCached = false;
    session = p.session; lastSeq = p.seq; lastSeen = millis();
    Serial.printf("# synced session %lu\n", (unsigned long)session);
    ack(p.seq, 0, reply);
    return;
  }
  if (p.kind == SET_LOADS) {
    if (!session || p.session != session) { ack(p.seq, 1, reply); return; }
    lastSeen = millis();
    if (haveCached && p.seq == cachedSeq) {  // duplicate identity: same payload re-ACKs, different is rejected
      ack(p.seq, p.mask == cachedMask ? 0 : 1, reply);
      return;
    }
    if (p.seq <= lastSeq) { ack(p.seq, 1, reply); return; }
    lastSeq = p.seq;
    applyOutputs(p.mask);
    haveCached = true; cachedSeq = p.seq; cachedMask = p.mask;
    Serial.printf("# applied seq %lu: commanded 0x%03x -> classrooms 0x%03x\n", (unsigned long)p.seq, p.mask, applied);
    ack(p.seq, 0, reply);
  }
}

// ESP-NOW receive callback (Arduino core 3.x): copy and enqueue only.
void onRecv(const esp_now_recv_info_t* info, const uint8_t* data, int len) {
  if (len != PACKET_SIZE || memcmp(info->src_addr, PEER_MAC, 6)) return;
  Frame f; f.source = FROM_RADIO; memcpy(f.data, data, PACKET_SIZE);
  xQueueSend(rxQueue, &f, 0);
}

bool setupRadio() {
  uint8_t any = 0;
  for (auto b : PEER_MAC) any |= b;
  uint8_t keys = 0;
  for (auto b : PMK) keys |= b;
  for (auto b : LMK) keys |= b;
  if (!PEER_CONFIGURED || !any || !keys || (PEER_MAC[0] & 1)) {
    Serial.println("# radio disabled: fill in secrets.h (board A MAC, PMK, LMK); USB bench mode only");
    return false;
  }
  WiFi.mode(WIFI_STA); WiFi.disconnect();
  if (esp_wifi_set_channel(RADIO_CHANNEL, WIFI_SECOND_CHAN_NONE) != ESP_OK) return false;
  if (esp_now_init() != ESP_OK || esp_now_set_pmk(PMK) != ESP_OK) return false;
  esp_now_peer_info_t peer{};
  memcpy(peer.peer_addr, PEER_MAC, 6); memcpy(peer.lmk, LMK, 16);
  peer.channel = RADIO_CHANNEL; peer.ifidx = WIFI_IF_STA; peer.encrypt = true;
  if (esp_now_add_peer(&peer) != ESP_OK || esp_now_register_recv_cb(onRecv) != ESP_OK) return false;
  return true;
}

void pollSerial() {
  static char line[80];
  static uint8_t n = 0;
  while (Serial.available()) {
    char c = Serial.read();
    if (c == '\r') continue;
    if (c != '\n') { if (n < sizeof(line) - 1) line[n++] = c; continue; }
    line[n] = 0; n = 0;
    if (line[0] == 'F' && line[1] == ' ' && strlen(line) == 2 + 2 * PACKET_SIZE) {
      Frame f; f.source = FROM_SERIAL;
      for (size_t i = 0; i < PACKET_SIZE; ++i) {
        char hex[3] = {line[2 + 2 * i], line[3 + 2 * i], 0};
        f.data[i] = (uint8_t)strtoul(hex, nullptr, 16);
      }
      handle(f);
    } else if (strcmp(line, "?") == 0) {
      Serial.printf("# B boot=%lu session=%lu applied=0x%03x radio=%s bad=%lu MAC=%s\n", (unsigned long)bootId,
                    (unsigned long)session, applied, radioReady ? "on" : "off", (unsigned long)rxBad,
                    WiFi.macAddress().c_str());
    }
  }
}

void updateLinkLed(uint32_t now) {
  if (!session) digitalWrite(PIN_LINK, (now / 500) & 1);                        // waiting for SYNC
  else if (now - lastSeen > STALE_MS) digitalWrite(PIN_LINK, (now / 125) & 1);  // stale: keep last outputs
  else digitalWrite(PIN_LINK, HIGH);
}

void setup() {
  for (uint8_t p : {PIN_ROOM_A, PIN_ROOM_B, PIN_ROOM_C, PIN_LINK}) { pinMode(p, OUTPUT); digitalWrite(p, LOW); }
  Serial.begin(115200);
  rxQueue = xQueueCreate(8, sizeof(Frame));
  // Persisted monotonic boot counter (contract: A ignores lower boot IDs).
  prefs.begin("mesh-b", false);
  bootId = prefs.getUInt("boot", 0) + 1;
  prefs.putUInt("boot", bootId);
  delay(200);
  WiFi.mode(WIFI_STA);
  radioReady = setupRadio();
  Serial.printf("\n# Blackout Mesh board B, contract v2, boot %lu, MAC %s, outputs OFF\n", (unsigned long)bootId,
                WiFi.macAddress().c_str());
  Packet hello = outgoing(HELLO);
  sendPacket(hello, FROM_SERIAL);
  sendPacket(hello, FROM_RADIO);
}

void loop() {
  pollSerial();
  Frame f;
  while (xQueueReceive(rxQueue, &f, 0) == pdTRUE) handle(f);
  uint32_t now = millis();
  if (now - lastBeat >= HEARTBEAT_MS) {
    lastBeat = now;
    Packet beat = outgoing(HEARTBEAT);
    sendPacket(beat, FROM_RADIO);
    sendPacket(beat, FROM_SERIAL);
  }
  updateLinkLed(now);
}
