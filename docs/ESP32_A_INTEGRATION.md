# A → laptop → B integration

Person A owns reader/buttons and transport. Person B owns output firmware and the
laptop's authoritative registration/allocation adapter. No B firmware, classifier
or allocator was replaced or implemented by this change. Start with the
[wiring guide](ESP32_A_WIRING.md) and [shared v2 contract](../contracts/serial_protocol.md).

## Pairing

1. Person B records B's STA MAC locally, exact board and GPIO wiring, and uses
   the contract's numeric kinds, monotonic boot IDs and classroom projection.
2. Copy `firmware/include/secrets.example.h` to ignored `secrets.h`. Fill B's MAC
   and matching random 16-byte PMK/LMK locally. Never use the zero template values
   or publish the keys/MAC. Provision matching credentials on B by its own method.
3. Match RADIO_CHANNEL (default 1), provision encrypted unicast in both directions,
   and rebuild. A refuses to send if configuration is missing/zero/invalid.
4. B sends encrypted HELLO/heartbeat. Laptop reads A's `radio_state` boot report,
   sends `radio_sync`, waits for result SYNCED, then sends current `set_loads`.

The Radio adapter was written against the callbacks in the locally installed
Arduino ESP32 2.0.17 examples, not newer IDF callback signatures. Installed package
versions are pinned in `firmware/platformio.ini` after successful builds.

## Host ownership

- Keep registered rooms, current selection, current budget and desired logical
  mask in one existing laptop authority. Do not infer registration from LEDs.
- Map START to observed room session evidence and registration; preserve other
  rooms. END removes eligibility immediately and recomputes desired outputs.
- Map SIMULATE_SHORTAGE/RESTORE to configured host budgets; restore through fresh
  evidence/stable capacity/staged policy. RESET starts a new persisted session,
  clears registrations/selection and desired outputs, then resynchronizes.
- Host `event_ack` means input accepted, not power delivered. Deduplicate using
  boot/event/context. Invalid actions get accepted=false and a fresh sync.
- Apply registration eligibility before allocation. For full-campus operation,
  fixed critical tiers/feeder/capacity constraints remain binding. Card identity
  is never a classifier feature, a forced ACTIVE label or priority override.
- Use the existing exact allocator and classifier entrypoints when implemented.
  Input-only console is solely a transport test. BENCH/RULES mode must be labeled;
  it does not satisfy trained ML or held-out evaluation gates.
- Keep full logical desired mask, simulated applied state and physical ACK state
  separate. Only matching SET ACK with the projection confirms B's classroom LEDs.
- Use host monotonic timestamps for event→allocation→ACK latency. Device `ms`
  cannot by itself measure host latency. Log actual errors/abstentions/denominators.

## Recovery

An A boot change starts a fresh host run: clear registrations/selection and reconcile desired outputs OFF.
On same-boot host reconnect, HELLO clears obsolete pending serial/radio work. SYNC restores
host-selected room; it does not replay taps. Read B's current boot/state, radio
SYNC, then send the newest desired mask. With a newer session, continue monotonic
command numbering within that session. Device reboot invalidates old ACKs and
requires fresh radio SYNC; B's initial report must precede commands. Lower boot
reports and stale context/ACKs cannot confirm the new run.

One in-flight command plus one coalesced unsent mask is bounded. Timeouts at 600
ms do not fabricate success or apply a different local allocation. Reconcile on
reconnect from current authority state. END/reset while B is unreachable stays
visibly unconfirmed; B may still show its last acknowledged state and stale LED.

## Physical acceptance with Person B

Record the hardware plan's matrix, including 8/16/32/24/56 and 511→56; no
unregistered room ON; A then B retains both registrations; unknown card and held
card; shortage/restore; END/reset offline; B power cycle; stale session/boot/seq;
bad CRC/version/mask; duplicate payload versus conflicting duplicate; wrong-mask
ACK; host reconnect without stale tap replay. Observe each actual LED and capture
command/ACK identities. Record 60 seconds of stability and three final rehearsals.
Do not call this integration complete based on the simulated contract tests.
