#include <Arduino.h>
#include <Preferences.h>
#include "buttons.h"
#include "bridge.h"
#include "reader.h"
#include "espnow_link.h"
#include "serial_bridge.h"
using namespace mesh;
QueueHandle_t Radio::queue = nullptr;
std::atomic<uint32_t> Radio::dropped{0};
Preferences preferences;
Session host(1, 0);
Bridge bridge;
Reader reader;
Radio radio;
SerialBridge serial;
Button buttons[config::BUTTON_COUNT];
uint32_t lastHello = 0, lastHeartbeat = 0, lastRadioDrops = 0, lastCardError = 0;
bool radioReady = false, readerWasOk = false;
struct ReaderSample { int state; char room, uid[21]; bool healthy; };
QueueHandle_t readerQueue = nullptr;
std::atomic<bool> readerOverflow{false};
void readCards(void*) {
  for (;;) {
    ReaderSample sample{};
    sample.state = reader.poll(millis(), sample.room, sample.uid);
    sample.healthy = reader.ok();
    if (sample.state != -1 && xQueueSend(readerQueue, &sample, 0) != pdTRUE) readerOverflow = true;
    vTaskDelay(pdMS_TO_TICKS(50));
  }
}

JsonDocument envelope(const char* type) {
  JsonDocument doc;
  doc["v"] = 2; doc["type"] = type; doc["boot"] = host.boot;
  doc["epoch"] = host.epoch; doc["session"] = host.session;
  doc["ms"] = millis(); return doc;
}
void status(const char* code) {
  auto doc = envelope("status"); doc["code"] = code; serial.emit(doc);
}
void disconnect(const char* code) {
  host.disconnect(); bridge.disconnect(); serial.clear();
  status(code);
}
void hello() {
  auto doc = envelope("hello"); doc["reader_ok"] = readerWasOk;
  doc["radio_configured"] = radioReady; doc["target"] = bridge.boot;
  doc["radio_online"] = bridge.online; doc["minimum_session"] = host.floor; doc["mode"] = "INPUT_GATEWAY";
#ifdef ENROLLMENT_MODE
  doc["mode"] = "LOCAL_ENROLLMENT";
#endif
  serial.emit(doc);
}
void action(Action value) {
  if (value == Action::NONE) return;
  if (value == Action::UNKNOWN_CARD) { status("unknown_card"); return; }
  if (value == Action::IGNORED_NO_SELECTION) { status("ignored_no_selection"); return; }
  if (value == Action::UNSYNCHRONIZED) { status("input_ignored_unsynchronized"); return; }
  const char* names[] = {"", "START_SESSION", "END_SESSION", "SIMULATE_SHORTAGE", "RESTORE", "RESET_SESSION"};
  auto doc = envelope("event"); uint32_t event = host.event(millis());
  if (!event) { disconnect("event_backpressure"); return; }
  doc["event"] = event; doc["action"] = names[int(value)];
  if (value == Action::START_SESSION || value == Action::END_SESSION) {
    char room[] = {host.input.selected, 0}; doc["room"] = room;
  }
  if (value == Action::RESET_SESSION) serial.clear();
  serial.emit(doc);
  if (value == Action::RESET_SESSION) {
    // Preserve this outgoing reset frame; invalidate context immediately.
    host.reset(); bridge.disconnect();
    if (preferences.putUInt("session", host.floor) != sizeof(uint32_t)) host.epoch = UINT32_MAX;
    status("reset_requires_sync");
  }
}
void receiveHost(const HostMessage& msg, uint32_t now) {
  if (msg.kind == HostKind::HELLO) { disconnect("host_reconnect"); hello(); return; }
#ifdef ENROLLMENT_MODE
  status("enrollment_only"); return;
#endif
  if (msg.kind == HostKind::SYNC) {
    if (!host.sync(msg, now)) { status("sync_rejected"); return; }
    if (preferences.putUInt("session", host.floor) != sizeof(uint32_t)) {
      disconnect("session_persistence_failed"); return;
    }
    bridge.bind(host.session); status("host_synced"); return;
  }
  if (!host.context(msg)) { status("stale_context"); return; }
  if (msg.kind == HostKind::PING) { host.seen = now; status("pong"); return; }
  if (msg.kind == HostKind::EVENT_ACK) {
    if (!host.acknowledge(msg.event)) { status("unknown_event_ack"); return; }
    if (!msg.accepted) { disconnect("event_rejected_requires_sync"); return; }
    status("event_accepted"); return;
  }
  if (!radioReady || !bridge.submit(msg.kind == HostKind::RADIO_SYNC ? SYNC : SET_LOADS,
                                    msg.seq, msg.mask, msg.target, now)) {
    status("radio_command_rejected"); return;
  }
  auto doc = envelope("queued"); doc["seq"] = msg.seq; serial.emit(doc);
}
void setup() {
  Serial.begin(SERIAL_BAUD);
  bool persisted = preferences.begin("mesh-a", false);
  uint32_t boot = persisted ? preferences.getUInt("boot", 0) : UINT32_MAX;
  if (boot == UINT32_MAX) { host.boot = UINT32_MAX; status("boot_counter_exhausted"); return; }
  ++boot;
  if (preferences.putUInt("boot", boot) != sizeof(uint32_t)) {
    host.boot = UINT32_MAX; status("boot_persistence_failed"); return;
  }
  host = Session(boot, preferences.getUInt("session", 0));
  reader.begin(); readerWasOk = reader.ok();
  readerQueue = xQueueCreate(8, sizeof(ReaderSample));
  if (!readerQueue || xTaskCreate(readCards, "rfid", 4096, nullptr, 1, nullptr) != pdPASS) {
    host.boot = UINT32_MAX; status("reader_task_failed"); return;
  }
  for (int pin : config::buttons) if (pin >= 0)
    pinMode(pin, BUTTON_ACTIVE_LEVEL == LOW ? INPUT_PULLUP : INPUT_PULLDOWN);
#ifndef ENROLLMENT_MODE
  radioReady = radio.begin();
#endif
  hello(); status(readerWasOk ? "reader_initialized_unverified" : "reader_fault");
}
void loop() {
  uint32_t now = millis(); serial.flush();
  if (host.boot == UINT32_MAX) return;
  if (serial.failed) { serial.failed = false; disconnect("serial_backpressure"); }
  if (host.stale(now) || host.eventTimeout(now)) disconnect("host_stale_or_event_timeout");
  for (int i = 0; i < 128 && Serial.available(); ++i) {
    int result = serial.framer.feed(char(Serial.read()));
    if (result) {
      HostMessage msg;
      if (result < 0 || !parseHost(serial.framer.data, msg)) status("malformed_serial");
      else receiveHost(msg, now);
    }
  }
  for (int i = 0; i < config::BUTTON_COUNT; ++i) if (config::buttons[i] >= 0 &&
      buttons[i].poll(digitalRead(config::buttons[i]) == BUTTON_ACTIVE_LEVEL, now, i == config::RESET_BUTTON_INDEX)) {
    if (i == 4 && host.input.synced) status(readerWasOk ? "fallback_room_a" : "fallback_room_a_reader_fault");
    action(host.input.button(i));
  }
  ReaderSample sample;
  if (readerOverflow.exchange(false)) disconnect("reader_queue_overflow");
  for (int i = 0; i < 8 && xQueueReceive(readerQueue, &sample, 0) == pdTRUE; ++i) {
    if (sample.healthy != readerWasOk) {
      readerWasOk = sample.healthy; status(readerWasOk ? "reader_recovered" : "reader_fault");
    }
    if (sample.state == 2 && uint32_t(now - lastCardError) >= 1000) {
      lastCardError = now; status("card_read_failed");
    }
    if (sample.state != 0 && sample.state != 1) continue;
#ifdef ENROLLMENT_MODE
    bool fresh = sample.state == 1 && !host.input.presented;
    host.input.card(sample.state == 1, sample.room, now);
    if (fresh && sample.uid[0]) {
      auto doc = envelope("enroll_uid"); doc["uid"] = sample.uid; serial.emit(doc);
    }
#else
    action(host.input.card(sample.state == 1, sample.room, now));
#endif
  }
  Packet packet; bool invalid = false;
  for (int i = 0; i < 8 && radio.poll(packet, invalid); ++i) {
    if (invalid) { status("invalid_radio_frame"); continue; }
    auto result = bridge.receive(packet, now);
    auto doc = envelope("radio_state"); doc["target"] = packet.boot;
    doc["ack_seq"] = packet.ack; doc["applied_classroom_mask"] = packet.mask;
    doc["confirmed"] = result == RadioResult::CONFIRMED;
    doc["result"] = int(result); serial.emit(doc);
  }
  auto result = bridge.tick(now);
  if (result == RadioResult::TIMEOUT) status("radio_timeout_unconfirmed");
  if (result == RadioResult::STALE) status("radio_stale");
  if (bridge.next(now, packet) && !radio.send(packet)) status("radio_send_failed_unconfirmed");
  if (radio.overflow() != lastRadioDrops) { lastRadioDrops = radio.overflow(); status("radio_rx_overflow"); }
  if (uint32_t(now - lastHeartbeat) >= 500) {
    lastHeartbeat = now;
    if (radioReady && bridge.boot) {
      Packet ping; ping.kind = HEARTBEAT; ping.boot = bridge.boot; ping.session = host.session;
      radio.send(ping);
    }
  }
  if (uint32_t(now - lastHello) >= 1000) { lastHello = now; hello(); }
}
