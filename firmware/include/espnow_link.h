#pragma once
#include <WiFi.h>
#include <atomic>
#include <esp_now.h>
#include <esp_wifi.h>
#include "config.h"
#include "protocol.h"
namespace mesh {
class Radio {
  struct Frame { uint8_t data[PACKET_SIZE]; };
  static QueueHandle_t queue;
  static std::atomic<uint32_t> dropped;
  bool enabled = false;
  static void receive(const uint8_t* mac, const uint8_t* bytes, int size) {
    if (size != PACKET_SIZE || memcmp(mac, PEER_MAC, 6)) return;
    Frame frame; memcpy(frame.data, bytes, PACKET_SIZE);
    if (xQueueSend(queue, &frame, 0) != pdTRUE) ++dropped;
  }
 public:
  bool begin() {
    if (!PEER_CONFIGURED || (PEER_MAC[0] & 1)) return false;
    uint8_t mac = 0, pmk = 0, lmk = 0;
    for (auto b : PEER_MAC) mac |= b;
    for (auto b : PMK) pmk |= b;
    for (auto b : LMK) lmk |= b;
    if (!mac || !pmk || !lmk || RADIO_CHANNEL < 1 || RADIO_CHANNEL > 13) return false;
    WiFi.mode(WIFI_STA); WiFi.disconnect();
    if (esp_wifi_set_channel(RADIO_CHANNEL, WIFI_SECOND_CHAN_NONE) != ESP_OK) return false;
    queue = xQueueCreate(8, sizeof(Frame));
    if (!queue || esp_now_init() != ESP_OK || esp_now_set_pmk(PMK) != ESP_OK) return false;
    esp_now_peer_info_t peer{};
    memcpy(peer.peer_addr, PEER_MAC, 6); memcpy(peer.lmk, LMK, 16);
    peer.channel = RADIO_CHANNEL; peer.ifidx = WIFI_IF_STA; peer.encrypt = true;
    if (esp_now_add_peer(&peer) != ESP_OK || esp_now_register_recv_cb(receive) != ESP_OK) return false;
    enabled = true; return true;
  }
  bool send(const Packet& packet) {
    if (!enabled) return false;
    uint8_t bytes[PACKET_SIZE]; encode(packet, bytes);
    return esp_now_send(PEER_MAC, bytes, sizeof(bytes)) == ESP_OK;
  }
  bool poll(Packet& packet, bool& invalid) {
    Frame frame;
    if (!enabled || xQueueReceive(queue, &frame, 0) != pdTRUE) return false;
    invalid = !decode(frame.data, sizeof(frame.data), packet); return true;
  }
  uint32_t overflow() const { return dropped.load(); }
};
}
