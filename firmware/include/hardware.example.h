#pragma once
// Copy to hardware.local.h after verifying the exact board and button wiring.
// RC522 pins already match the user's wiring. Button guide uses 25/26/27/32; verify exposed labels before wiring.
// For each verified GPIO use #undef then #define, e.g.:
// #undef BUTTON_END
// #define BUTTON_END <verified GPIO>
// #undef BUTTON_FALLBACK_A
// #define BUTTON_FALLBACK_A <verified GPIO>   (RFID-fail fallback, starts room A)
// Button defaults: INPUT_PULLUP, active LOW, switch between GPIO and GND.
