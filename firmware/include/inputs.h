#pragma once
#include <stdint.h>
namespace mesh {
enum class Action { NONE, START_SESSION, END_SESSION, SHORTAGE, RESTORE, RESET_SESSION,
                    UNKNOWN_CARD, IGNORED_NO_SELECTION, UNSYNCHRONIZED };
struct Input {
  bool synced = false, presented = false;
  char selected = 0;
  uint32_t absentSince = 0;
  bool absent = false;
  void sync(char room) { selected = room; synced = true; }
  void disconnect() { synced = false; selected = 0; }
  Action card(bool present, char room, uint32_t now) {
    if (!present) {
      if (!absent) { absent = true; absentSince = now; }
      if (uint32_t(now - absentSince) >= 250) presented = false;
      return Action::NONE;
    }
    absent = false;
    if (presented) return Action::NONE;
    presented = true;
    if (!synced) return Action::UNSYNCHRONIZED;
    if (room < 'A' || room > 'C') return Action::UNKNOWN_CARD;
    selected = room;
    return Action::START_SESSION;
  }
  Action button(int index) {
    if (!synced) return Action::UNSYNCHRONIZED;
    if (index == 0) return selected ? Action::END_SESSION : Action::IGNORED_NO_SELECTION;
    if (index == 1) return Action::SHORTAGE;
    if (index == 2) return Action::RESTORE;
    if (index >= 4 && index <= 6) {  // room buttons: the same START_SESSION that room's card would send
      selected = char('A' + index - 4);
      return Action::START_SESSION;
    }
    return Action::RESET_SESSION;
  }
};
}
