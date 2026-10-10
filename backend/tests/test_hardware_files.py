"""Board B must use board A's radio codec byte for byte."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_board_b_protocol_header_is_a_copy_of_board_a():
    a = (ROOT / "firmware/include/protocol.h").read_bytes().replace(b"\r\n", b"\n")
    b = (ROOT / "hardware/firmware/BoardB_Output/protocol.h").read_bytes().replace(b"\r\n", b"\n")
    assert a == b


def test_led_mask_needs_a_session_and_full_service():
    import app.main as main
    rooms = [{"id": "CR1", "rfid_active": True, "loads": [{"served": True}, {"served": True}]},
             {"id": "CR2", "rfid_active": True, "loads": [{"served": True}, {"served": False}]},
             {"id": "CR3", "rfid_active": False, "loads": [{"served": True}]}]
    assert main.led_mask({"rooms": rooms}) == 0b001000
