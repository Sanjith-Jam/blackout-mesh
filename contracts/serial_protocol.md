# ESP32 A input gateway contract v2

Scope: firmware-specific serial/radio transport, not a simulator snapshot schema.
There was no implementation of A, B or the laptop controller in the repository.
The existing plans define framing and radio layout; this document freezes the
previously unspecified kind numbers and envelopes. **Person B must adopt these
values or agree a coordinated contract change before real integration.** No
compatibility with an unseen receiver is claimed.

USB: 115200 baud, one ASCII JSON object per newline, optional terminal CR before
LF; maximum 512 payload bytes. All current fields are ASCII. Unknown fields,
wrong types (including boolean-as-integer), nested structures, bad room/mask,
trailing data and unknown versions are rejected. Oversized/control-byte frames
are discarded through the next newline. Queues are bounded. Partial lines never
execute. Errors are JSON `status` records, not interspersed plain-text logs.

## Host handshake

1. Open port, discard old input bytes, send `{"v":2,"type":"hello"}`. A invalidates
   old pending work and returns a new epoch. Classic USB bridges cannot reliably
   indicate every cable/host disconnect: missing host pings expires after 1500 ms.
   Every opener must send HELLO before commands, including brief reconnects.
2. Read A's `hello`: `boot`, `epoch`, `minimum_session`, `target` (B boot, 0 unknown),
   `reader_ok`, `radio_configured`, `radio_online`, `mode`, plus common fields below.
3. Send `sync` with the current context and host's selected room or null:
   `{"v":2,"type":"sync","boot":99,"epoch":1,"session":10,"selected":null}`.
   Host owns registered rooms and selection reconciliation. A stores only selection.
4. Wait for `host_synced`. Send a `ping` every 500 ms. Only pings renew the lease.
   Every non-HELLO host message includes current `boot`, `epoch`, `session`.

Counters are positive unsigned 32-bit integers; never wrap. A's boot counter and
session floor are persisted in NVS, failing closed on write failure. Host persists
its session counter and increases it for reset/new run/backend restart. For a
serial reconnect to the same run, reuse session only with continuing radio
sequence numbers; A accepts no session below its persisted floor. RESET raises
that floor, clears selection and forces fresh synchronization. Do not erase NVS
while retaining old peer/session state: deliberately reprovision both sides.

## Exact host records

Common context = `v:2`, `type`, `boot`, `epoch`, `session`. Add only listed fields:

| type | Additional fields | Result |
|---|---|---|
| sync | selected: "A" / "B" / "C" / null | Host selection restored; no allocation implied |
| ping | none | pong; renews host lease |
| event_ack | event: positive uint32; accepted: boolean | Input accepted/rejected by authority |
| radio_sync | seq: positive uint32; target: B boot; mask: 0 | Bind B to current session |
| set_loads | seq: positive uint32; target: B boot; mask: integer 0..511 | Forward full logical display mask |

A emits common context plus `ms` (device milliseconds, wrapping uint32; not host
latency). `event` additionally has `event` and `action`, with `room` only for START
and END. Identity is `(A boot, event counter)` under current epoch/session.
Actions: `START_SESSION`, `END_SESSION`, `SIMULATE_SHORTAGE`, `RESTORE`,
`RESET_SESSION`. Shortage/restore request host-configured budgets; A never chooses
watts or allocates. Input events are not retransmitted. Host ACK within 1000 ms;
rejection/timeout/backpressure invalidates sync rather than replaying stale input.
RESET is sent once under the old context, then immediately invalidates it; process
RESET and begin a new handshake instead of waiting for an ACK exchange in the old
context. The new run reconciles B separately; offline RESET does not turn LEDs OFF.

`status` has `code`. `queued` has `seq` and proves only acceptance into A's bridge.
`radio_state` has `target`, `ack_seq`, `applied_classroom_mask`, `confirmed`, `result`.
Result numbers: 0 NONE, 1 CONFIRMED, 2 SYNCED, 3 TIMEOUT, 4 REJECTED, 5 BAD_ACK,
6 REBOOT, 7 STALE. Only result 1 has `confirmed:true`; mask in any other record is
unverified/reported state. Neither heartbeat nor SYNC ACK is a retroactive SET ACK.
A matching application SET ACK is the sole confirmation source. Retain the host's
full commanded mask separately from the acknowledged physical projection.

In `LOCAL_ENROLLMENT` mode, only `enroll_uid` includes a full raw `uid`. This mode
rejects host synchronization and has no radio. Never use it during the demo.

## Radio: existing 26-byte shape, application version 2

All multi-byte values little endian. Node ID always 2 identifies output station B
in either direction. CRC16/CCITT-FALSE: polynomial 0x1021, initial 0xffff, no
reflection, xor-out 0; CRC over bytes 0..23. CRC bytes at offsets 24..25.

| Offset | Size | Value |
|---|---|---|
| 0 | 1 | magic 0xa5 |
| 1 | 1 | application version 2 |
| 2 | 1 | HELLO=1, SYNC=2, SET_LOADS=3, ACK=4, HEARTBEAT=5, BUTTON=6 |
| 3 | 1 | node 2 |
| 4 | 4 | session |
| 8 | 4 | message sequence |
| 12 | 4 | B boot ID, **persisted monotonic counter**, positive, no wrapping |
| 16 | 4 | acknowledged command sequence (ACK only) |
| 20 | 2 | mask (SET: full nine-load mask; B reports/ACK: physical classroom mask) |
| 22 | 1 | status 0=OK, 1=REJECTED |
| 23 | 1 | flags 0; reject unsupported flags |
| 24 | 2 | CRC |

Fixtures: [esp32_a_v2.json](schema_examples/esp32_a_v2.json). Python codec:
`tools/radio_protocol.py`; production C++ codec: `firmware/include/protocol.h`.
Logical valid mask 0x01ff; classroom mask 0x0038. Lab A/B/C = bits 3/4/5.
Command 511 projects to 56, not 255. Single-room fixtures: 8, 16, 32; A+B=24.

B must boot outputs OFF, report HELLO/state with its new boot, and wait for SYNC.
A ignores lower boot IDs and invalidates in-flight work on a higher boot. SYNC
must match B's boot and never downgrade its active session. SYNC does not apply
outputs; its ACK reports actual classroom mask. SET requires bound session and
increasing sequence, validates the full mask, applies only `mask & 56` outside
the callback, then ACKs actual state. Same identity/same payload returns cached
ACK without reapplying. Same identity/different payload and older sequences are
rejected. A heartbeat reports state and boot every <=500 ms, even before sync;
A sends a heartbeat request every 500 ms once B's boot is known.

A keeps one command in flight and one latest unsent command; a newer unsent mask
supersedes the previous unsent mask. `queued` is not a delivery promise. Sends
occur at t=0/200/400 ms, expire at 600 ms, using identical identity. A failed/wrong
ACK clears pending work and requires fresh radio SYNC. Duplicate current/queued
commands do not reset deadlines or cause immediate extra sends. Exact duplicate
completed commands are ignored; host must retain its previous ACK record.
B stale threshold is 1500 ms. B retains last output during link loss and shows a
separate stale LED. Host END/reset remains pending/unconfirmed until delivery.

Encrypted unicast only: allowlisted peer MAC, locally provisioned 16-byte PMK and
LMK, common channel. Missing/zero keys or missing peer disables radio. Callbacks
only copy bounded frames; parsing, ACK checks and USB output happen in the loop.
ESP-NOW send return/callback is never an application ACK. See the pinned core's
ESPNow examples and [Espressif ESP-NOW documentation](https://docs.espressif.com/projects/esp-idf/en/v4.4/esp32/api-reference/network/esp_now.html).
