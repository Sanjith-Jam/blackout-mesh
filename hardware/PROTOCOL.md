# Board A ↔ laptop ↔ board B contract (protocol v2)

Written by Person B. **Person A needs to implement the board A side of this.** Change it only after agreeing together.

## 1. USB serial lines (115200 baud, newline-terminated)

| Line | Direction | Meaning |
|---|---|---|
| `F <52 hex chars>` | laptop ↔ A ↔ B | One 26-byte radio frame. A forwards laptop→B frames over ESP-NOW unchanged, and forwards B→laptop frames to USB unchanged. **A does not parse or alter them.** |
| `EV <event_id> SCAN <A\|B\|C>` | A → laptop | A known card was presented (one event per presentation, not while held) |
| `EV <event_id> UNKNOWN_CARD` | A → laptop | An unknown card was presented |
| `EV <event_id> END` | A → laptop | END SELECTED pressed |
| `EV <event_id> SHORTAGE` | A → laptop | SIMULATE SHORTAGE pressed |
| `EV <event_id> RESTORE` | A → laptop | RESTORE pressed |
| `EV <event_id> RESET` | A → laptop | RESET held for 2 s |
| `EV <event_id> READER_FAULT` / `READER_OK` | A → laptop | Reader stopped / started answering |
| `# anything` | any | Human-readable log, ignored by the laptop |

- `event_id` is unique per event, for example `<A boot id hex>-<counter>`. The laptop ignores repeats.
- A must **not** buffer or replay events after a USB reconnect.
- A maps card UIDs to A/B/C locally. Raw UIDs never leave A.

## 2. Radio frame: 26 bytes, little-endian, field by field (never memcpy a struct)

```
off size field
0   1    magic = 0xA7
1   1    version = 2
2   1    node: 0 = laptop/host, 1 = board A, 2 = board B
3   1    type
4   4    session  (laptop's current run; changes on RESET)
8   4    boot_id  (board B's random id for this boot)
12  4    seq      (sender counter; for SET_MASK this is the command id)
16  8    payload (per type, below)
24  2    CRC-16/CCITT-FALSE over bytes 0..23 (poly 0x1021, init 0xFFFF; "123456789" -> 0x29B1)
```

| Type | From | Payload (8 bytes) |
|---|---|---|
| 1 HELLO | B | fw_ver u16, role u8, fw_state u8, applied_mask u16, reserved u16 |
| 2 SYNC | host | expected_boot u32, reserved u32 (the session in the header is the new session) |
| 3 SET_MASK | host | state_rev u32, req_mask u16 (full nine-load catalog, ≤ 0x01FF), reserved u16 |
| 4 ACK | B | cmd_id u32, applied_mask u16, status u8, fw_state u8 |
| 5 HEARTBEAT | host and B | uptime_ms u32, applied_mask u16, fw_state u8, flags u8 |

- **ACK status:** 0 APPLIED, 1 DUP_REPLAY, 2 REJ_SESSION, 3 REJ_BOOT, 4 REJ_STALE_REV, 5 REJ_BAD.
- **fw_state:** 1 UNSYNCED, 2 ONLINE, 3 LINK_STALE.
- **Projection:** B drives only the classroom bits. `applied_mask = req_mask & 0x0038` (bit 3 = room A, bit 4 = room B, bit 5 = room C). The laptop confirms a command only when `applied_mask == project(req_mask)`.

## 3. Radio settings

- ESP-NOW, Wi-Fi STA mode, channel 1, no encryption (CRC detects corruption, it is not authentication).
- Each board allows only the other board's MAC. **Board B's MAC is `<board B MAC, shared privately>`.**
- Put A's MAC in `PEER_A_MAC` in `BoardB_Output.ino`. Until then, B ignores radio frames and works over its own USB in bench mode.
- One command in flight. The laptop retries after 200 ms, up to 2 times, and gives up at 600 ms ("UNCONFIRMED").
- Heartbeat: 1 Hz each way. B shows stale after 3 s without the laptop.
