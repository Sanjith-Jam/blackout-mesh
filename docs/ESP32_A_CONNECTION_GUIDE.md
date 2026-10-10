# Board A (ESP32 A) — connection guide

Board A is the **input station**: it reads the RFID cards and five buttons, sends what happened to the laptop over USB, and passes the laptop's LED commands to board B by radio. Board A has no classroom LEDs; board B has those.

```
 cards ─► RFID reader ─► ESP32 A ──USB──► laptop (backend + website)
 buttons ─────────────►     │                     │
                            └──── ESP-NOW radio ──┴──► ESP32 B ─► room LEDs A/B/C + link LED
```

## 1. Parts

- 1 × ESP32 dev board (classic ESP32, not S2/S3/C3) and a USB **data** cable
- 1 × RC522 RFID reader (3.3 V) and 3 RFID cards
- 5 × push buttons
- 1 breadboard and jumper wires (male–female for the reader if its pins are headers)

No resistors are needed for the buttons: the firmware turns on the ESP32's internal pull-ups.

## 2. Unplug USB before wiring

Always wire with USB unplugged. Never connect the reader or buttons to 5 V or VIN.

## 3. RFID reader (RC522)

| RC522 pin | ESP32 pin | What it does |
|---|---|---|
| 3.3V | **3V3** | Power (**not 5V**) |
| GND | **GND** | Ground |
| SDA (also called SS) | **GPIO 21** | Chip select |
| SCK | **GPIO 18** | Clock |
| MOSI | **GPIO 23** | Data ESP32 → reader |
| MISO | **GPIO 19** | Data reader → ESP32 |
| RST | **GPIO 22** | Reset |
| IRQ | leave empty | Not used |

The ESP32 pins may be printed as `D21`, `G21` or just `21`.

## 4. Five buttons

Each button has **one side to its GPIO pin and the other side to GND**. That's all.

| Button label | ESP32 pin | What it does in the demo |
|---|---|---|
| **DEPRIVED (kW shortage)** | GPIO 26 | Drops the classroom supply to the 3,400 W shortage level |
| **NORMAL** | GPIO 27 | Restores the full 8,000 W supply |
| **ROOM A** | GPIO 33 | Starts room A's session exactly as card A would; press again to end it |
| **ROOM B** | GPIO 13 | Same for room B |
| **ROOM C** | GPIO 14 | Same for room C |

There are no END or RESET buttons: press a room button again to end that room, and reset from the website.

How to wire one button on a breadboard:
1. Put the button across the breadboard's centre gap so its legs are in two different row groups.
2. Jumper from the ESP32 pin (e.g. GPIO 33) to the row of **one** leg.
3. Jumper from the row of the **diagonally opposite** leg to the breadboard's blue (−) rail.
4. Run **one** jumper from an ESP32 **GND** pin to that blue (−) rail. All buttons and the reader share it.

Not sure which legs are connected? Four-leg buttons join their legs in pairs. Using diagonally opposite legs always gives you "open when released, closed when pressed". A multimeter on continuity mode confirms it.

## 5. Install the tools (laptop, once)

From the repository folder:

```
python -m venv .venv
.venv\Scripts\python -m pip install platformio pyserial -r backend\requirements.txt -r backend\requirements-ml.txt
```

## 6. Pair board A and board B (once)

The two boards only talk to each other, encrypted. They need each other's address and a shared secret key. Flash both boards once first (steps 7–8) just to read their MACs, then fill in `secrets.h` and flash them again.

1. **Make the keys.** Run this twice; the first result is the PMK and the second the LMK:
   ```
   python -c "import secrets; print(', '.join(f'0x{b:02x}' for b in secrets.token_bytes(16)))"
   ```
2. **Find each board's MAC.** Every upload prints it: look for the line `MAC: xx:xx:xx:xx:xx:xx` in the upload log (PlatformIO or Arduino IDE). Board B also prints it on its boot line in the serial monitor.
3. **Board A:** copy `firmware/include/secrets.example.h` to `firmware/include/secrets.h`. Put **board B's** MAC in `PEER_MAC`, and the PMK and LMK.
4. **Board B:** copy `hardware/firmware/BoardB_Output/secrets.example.h` to `secrets.h` in the same folder. Put **board A's** MAC in `PEER_MAC`, and the **same** PMK and LMK.

`secrets.h` files are git-ignored. Never commit them.

## 7. Register the three cards (once)

1. Plug board A in. Find its port in Device Manager (e.g. `COM4`).
2. Flash enrollment mode: `.venv\Scripts\pio run -d firmware -e esp32-a-enroll -t upload --upload-port COM4`
3. Record the cards: `.venv\Scripts\python tools\enroll_cards.py --port COM4` and tap card A, then B, then C when asked. This writes the git-ignored `firmware/include/cards.local.h`.

## 8. Flash the normal firmware

- **Board A:** `.venv\Scripts\pio run -d firmware -e esp32-a -t upload --upload-port COM4`
- **Board B:** open `hardware/firmware/BoardB_Output` in the Arduino IDE (board "ESP32 Dev Module", **Upload Speed 115200**) and upload. Optional USB check of board B on its own: `.venv\Scripts\python hardware\tools\check_board_b.py COM3`

## 9. Run the demo

1. Board A on the laptop's USB; board B on any USB power (laptop or charger).
2. Start the backend with board A's port:
   ```
   set BLACKOUT_GATEWAY_PORT=COM4
   .venv\Scripts\python -m uvicorn app.main:app --app-dir backend --port 8000
   ```
   or start it normally and use **Connect** in the "Physical boards" box on the Classrooms page.
3. Start the website: `cd frontend` then `npm run dev`, and open `http://127.0.0.1:5173/classrooms`.
4. The "Physical boards" box shows **Connected**, board B **Online, bound**, and board B's link LED goes solid.

## 10. Test cases

| Do this | You should see |
|---|---|
| Tap card A | Room A scanned on the page; board B's LED A turns on; panel shows A **ON** confirmed |
| Tap card B | Rooms A and B on |
| Press **DEPRIVED** | Supply drops to 3,400 W; only room A stays fully powered, so LED B goes off |
| Press **NORMAL** | Supply back to 8,000 W; LED B comes back about 5–7 s later (staged restoration) |
| Press a room button again | That room ends; its LED goes off |
| Press **Reset demo** on the website | All rooms cleared, all LEDs off |
| **RFID failure:** unplug the reader's SDA wire (USB unplugged first), then power up | Panel shows "Card reader: FAULT" |
| Press **ROOM A**, **ROOM B** or **ROOM C** | That room starts exactly as if its card had been tapped; its LED turns on |
| Unplug board B | Link shows stale; board A reports board B not heard; LEDs keep their last state until B is back |

## 11. Troubleshooting

- **Panel stays "Waiting for board A…"**: wrong port, or the Arduino Serial Monitor holds the port. Close it.
- **Board B "Not heard"**: check both `secrets.h` files (each has the *other* board's MAC, and the same keys) and that both are flashed.
- **Card does nothing**: re-run card registration (step 7), then re-flash normal firmware.
- **A button does nothing**: one leg must reach GND through the blue rail, and the ESP32 GND must be wired to that rail.

The firmware details are in `contracts/serial_protocol.md` (USB and radio contract) and `docs/ESP32_A_INTEGRATION.md`.
