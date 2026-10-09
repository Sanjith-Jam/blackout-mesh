// Blackout Mesh, board B (output station).
//
// Receives SYNC / SET_MASK / HEARTBEAT frames (protocol v2, fixed 26 bytes, see PROTOCOL.md)
// either over ESP-NOW from board A or as "F <hex>" lines on USB serial (bench mode).
// Validates session / boot / sequence / mask, drives the three classroom LEDs from
// commanded_mask & 0x0038, and answers every command with an ACK carrying the mask it
// actually applied. The radio callback only enqueues; all logic runs in loop().

#include <WiFi.h>
#include <esp_now.h>
#include <esp_wifi.h>

// ---- Pins (proposed for an ESP32 DevKit; confirm before wiring) ----
const uint8_t PIN_ROOM_A = 25;  // catalog bit 3
const uint8_t PIN_ROOM_B = 26;  // catalog bit 4
const uint8_t PIN_ROOM_C = 27;  // catalog bit 5
const uint8_t PIN_LINK = 33;    // solid = synced and fresh, 1 Hz = unsynced, 4 Hz = stale

// ---- Board A's MAC (fill in from Person A; all zero = radio frames rejected) ----
uint8_t PEER_A_MAC[6] = {0, 0, 0, 0, 0, 0};
const uint8_t WIFI_CHANNEL = 1;

// ---- Protocol v2 ----
const uint8_t MAGIC = 0xA7, VERSION = 2, FRAME_LEN = 26;
const uint8_t NODE_HOST = 0, NODE_B = 2;
enum : uint8_t { T_HELLO = 1, T_SYNC = 2, T_SET_MASK = 3, T_ACK = 4, T_HEARTBEAT = 5 };
enum : uint8_t { S_APPLIED = 0, S_DUP_REPLAY = 1, S_REJ_SESSION = 2, S_REJ_BOOT = 3,
                 S_REJ_STALE_REV = 4, S_REJ_BAD = 5 };
enum : uint8_t { FW_BOOT = 0, FW_UNSYNCED = 1, FW_ONLINE = 2, FW_LINK_STALE = 3 };
const uint16_t FULL_MASK = 0x01FF, ROOM_MASK = 0x0038;
const uint16_t FW_VER = 0x0200;
const uint32_t HOST_STALE_MS = 3000;

enum Src : uint8_t { SRC_SERIAL = 0, SRC_RADIO = 1 };
struct RxItem { uint8_t src; uint8_t len; uint8_t data[32]; };
QueueHandle_t rxQueue;

// ---- State ----
uint32_t bootId, mySeq = 0;
uint32_t session = 0;          // 0 = unsynced
uint32_t lastRev = 0;
uint16_t appliedMask = 0;      // classroom bits actually driven
uint32_t lastHostMs = 0;
bool haveCachedAck = false;
uint32_t cachedCmdId = 0;
uint8_t cachedAck[FRAME_LEN];
uint32_t rxOk = 0, rxBad = 0;
bool radioReady = false;

// ---- Little-endian helpers ----
static void put16(uint8_t *p, uint16_t v) { p[0] = v; p[1] = v >> 8; }
static void put32(uint8_t *p, uint32_t v) { for (int i = 0; i < 4; i++) p[i] = v >> (8 * i); }
static uint16_t get16(const uint8_t *p) { return p[0] | (p[1] << 8); }
static uint32_t get32(const uint8_t *p) { return p[0] | (p[1] << 8) | (p[2] << 16) | ((uint32_t)p[3] << 24); }

// CRC-16/CCITT-FALSE, check("123456789") = 0x29B1
static uint16_t crc16(const uint8_t *d, size_t n) {
  uint16_t c = 0xFFFF;
  for (size_t i = 0; i < n; i++) {
    c ^= (uint16_t)d[i] << 8;
    for (int b = 0; b < 8; b++) c = (c & 0x8000) ? (c << 1) ^ 0x1021 : c << 1;
  }
  return c;
}

uint8_t fwState() {
  if (session == 0) return FW_UNSYNCED;
  if (millis() - lastHostMs > HOST_STALE_MS) return FW_LINK_STALE;
  return FW_ONLINE;
}

void buildHeader(uint8_t *f, uint8_t type) {
  memset(f, 0, FRAME_LEN);
  f[0] = MAGIC; f[1] = VERSION; f[2] = NODE_B; f[3] = type;
  put32(f + 4, session); put32(f + 8, bootId); put32(f + 12, ++mySeq);
}

void seal(uint8_t *f) { put16(f + 24, crc16(f, 24)); }

void transmit(const uint8_t *f, uint8_t src) {
  if (src == SRC_SERIAL) {
    Serial.print("F ");
    for (int i = 0; i < FRAME_LEN; i++) Serial.printf("%02x", f[i]);
    Serial.println();
  } else if (radioReady) {
    esp_now_send(PEER_A_MAC, f, FRAME_LEN);
  }
}

void broadcast(const uint8_t *f) {  // status frames go to both paths
  transmit(f, SRC_SERIAL);
  transmit(f, SRC_RADIO);
}

void applyOutputs(uint16_t commanded) {
  appliedMask = commanded & ROOM_MASK;
  digitalWrite(PIN_ROOM_A, (appliedMask >> 3) & 1);
  digitalWrite(PIN_ROOM_B, (appliedMask >> 4) & 1);
  digitalWrite(PIN_ROOM_C, (appliedMask >> 5) & 1);
}

void sendAck(uint32_t cmdId, uint8_t status, uint8_t src, bool cache) {
  uint8_t f[FRAME_LEN];
  buildHeader(f, T_ACK);
  put32(f + 16, cmdId); put16(f + 20, appliedMask); f[22] = status; f[23] = fwState();
  seal(f);
  if (cache) { memcpy(cachedAck, f, FRAME_LEN); cachedCmdId = cmdId; haveCachedAck = true; }
  transmit(f, src);
}

void sendHello() {
  uint8_t f[FRAME_LEN];
  buildHeader(f, T_HELLO);
  put16(f + 16, FW_VER); f[18] = NODE_B; f[19] = fwState(); put16(f + 20, appliedMask);
  seal(f);
  broadcast(f);
}

void sendHeartbeat() {
  uint8_t f[FRAME_LEN];
  buildHeader(f, T_HEARTBEAT);
  put32(f + 16, millis()); put16(f + 20, appliedMask); f[22] = fwState(); f[23] = 0;
  seal(f);
  broadcast(f);
}

void handleFrame(const uint8_t *f, uint8_t len, uint8_t src) {
  if (len != FRAME_LEN || f[0] != MAGIC || f[1] != VERSION || crc16(f, 24) != get16(f + 24)) {
    rxBad++;
    Serial.println("# drop: bad length/magic/version/CRC");
    return;
  }
  if (f[2] != NODE_HOST) { rxBad++; return; }
  rxOk++;
  uint8_t type = f[3];
  uint32_t fSession = get32(f + 4), fBoot = get32(f + 8), fSeq = get32(f + 12);

  if (type == T_SYNC) {
    uint32_t expectedBoot = get32(f + 16);
    if (expectedBoot != bootId) { Serial.println("# SYNC rejected: boot mismatch"); return; }
    if (fSession == 0 || (session != 0 && fSession < session)) {
      Serial.println("# SYNC rejected: older session");
      return;
    }
    if (fSession != session) { lastRev = 0; haveCachedAck = false; }
    session = fSession;
    lastHostMs = millis();
    Serial.printf("# synced: session %lu\n", (unsigned long)session);
    sendHello();  // report current state after sync
    return;
  }

  // All other host frames must carry the current session and this boot.
  if (session == 0 || fSession != session) {
    if (type == T_SET_MASK) sendAck(get32(f + 12), S_REJ_SESSION, src, false);
    return;
  }
  if (fBoot != bootId) {
    if (type == T_SET_MASK) sendAck(fSeq, S_REJ_BOOT, src, false);
    return;
  }
  lastHostMs = millis();

  if (type == T_HEARTBEAT) return;

  if (type == T_SET_MASK) {
    uint32_t cmdId = fSeq, rev = get32(f + 16);
    uint16_t req = get16(f + 20);
    if (haveCachedAck && cmdId == cachedCmdId) {  // duplicate delivery: replay, no side effect
      uint8_t dup[FRAME_LEN];
      memcpy(dup, cachedAck, FRAME_LEN);
      dup[22] = S_DUP_REPLAY;
      put32(dup + 12, ++mySeq);
      seal(dup);
      transmit(dup, src);
      return;
    }
    if (req & ~FULL_MASK) { sendAck(cmdId, S_REJ_BAD, src, false); return; }
    if (rev < lastRev) { sendAck(cmdId, S_REJ_STALE_REV, src, false); return; }
    lastRev = rev;
    applyOutputs(req);
    Serial.printf("# applied cmd %lu rev %lu: commanded 0x%03x -> classrooms 0x%03x\n",
                  (unsigned long)cmdId, (unsigned long)rev, req, appliedMask);
    sendAck(cmdId, S_APPLIED, src, true);
  }
}

// Radio callback: copy and enqueue only.
void onRecv(const esp_now_recv_info_t *info, const uint8_t *data, int len) {
  if (memcmp(info->src_addr, PEER_A_MAC, 6) != 0 || len > 32) return;
  RxItem it;
  it.src = SRC_RADIO; it.len = len;
  memcpy(it.data, data, len);
  xQueueSend(rxQueue, &it, 0);
}

bool peerConfigured() {
  for (int i = 0; i < 6; i++) if (PEER_A_MAC[i]) return true;
  return false;
}

void setupRadio() {
  WiFi.mode(WIFI_STA);
  esp_wifi_set_channel(WIFI_CHANNEL, WIFI_SECOND_CHAN_NONE);
  if (esp_now_init() != ESP_OK) { Serial.println("# ESP-NOW init failed"); return; }
  esp_now_register_recv_cb(onRecv);
  if (!peerConfigured()) { Serial.println("# PEER_A_MAC not set: radio receive disabled, serial bench mode only"); return; }
  esp_now_peer_info_t peer = {};
  memcpy(peer.peer_addr, PEER_A_MAC, 6);
  peer.channel = WIFI_CHANNEL;
  peer.encrypt = false;
  if (esp_now_add_peer(&peer) != ESP_OK) { Serial.println("# add peer failed"); return; }
  radioReady = true;
}

void pollSerial() {
  static char line[96];
  static uint8_t n = 0;
  while (Serial.available()) {
    char c = Serial.read();
    if (c == '\r') continue;
    if (c != '\n') { if (n < sizeof(line) - 1) line[n++] = c; continue; }
    line[n] = 0; n = 0;
    if (line[0] == 'F' && line[1] == ' ') {
      RxItem it; it.src = SRC_SERIAL; it.len = 0;
      const char *h = line + 2;
      while (h[0] && h[1] && it.len < sizeof(it.data)) {
        char b[3] = {h[0], h[1], 0};
        it.data[it.len++] = strtoul(b, nullptr, 16);
        h += 2;
      }
      handleFrame(it.data, it.len, SRC_SERIAL);
    } else if (strcmp(line, "?") == 0) {
      Serial.printf("# B state=%u session=%lu boot=%08lx applied=0x%03x rx_ok=%lu rx_bad=%lu radio=%s\n",
                    fwState(), (unsigned long)session, (unsigned long)bootId, appliedMask,
                    (unsigned long)rxOk, (unsigned long)rxBad, radioReady ? "on" : "off");
    }
  }
}

void updateLinkLed() {
  uint32_t now = millis();
  switch (fwState()) {
    case FW_ONLINE: digitalWrite(PIN_LINK, HIGH); break;
    case FW_LINK_STALE: digitalWrite(PIN_LINK, (now / 125) & 1); break;  // 4 Hz
    default: digitalWrite(PIN_LINK, (now / 500) & 1); break;             // 1 Hz
  }
}

void setup() {
  for (uint8_t p : {PIN_ROOM_A, PIN_ROOM_B, PIN_ROOM_C, PIN_LINK}) { pinMode(p, OUTPUT); digitalWrite(p, LOW); }
  Serial.begin(115200);
  rxQueue = xQueueCreate(8, sizeof(RxItem));
  bootId = esp_random();
  if (bootId == 0) bootId = 1;
  delay(200);
  setupRadio();
  Serial.printf("\n# Blackout Mesh board B fw %04x boot %08lx MAC %s, outputs OFF, waiting for SYNC\n",
                FW_VER, (unsigned long)bootId, WiFi.macAddress().c_str());
}

void loop() {
  pollSerial();
  RxItem it;
  while (xQueueReceive(rxQueue, &it, 0) == pdTRUE) handleFrame(it.data, it.len, it.src);

  static uint32_t lastBeat = 0;
  if (millis() - lastBeat >= 1000) {
    lastBeat = millis();
    if (session == 0) sendHello(); else sendHeartbeat();
  }
  updateLinkLed();
}
