"""Blackout Mesh radio/serial protocol v2: fixed 26-byte little-endian frames.

Header 16 B: magic u8=0xA7 | ver u8=2 | node u8 | type u8 | session u32 | boot u32 | seq u32
Payload 8 B (per type), trailer CRC-16/CCITT-FALSE over the first 24 bytes.
"""
import struct
from dataclasses import dataclass

MAGIC, VERSION, FRAME_LEN = 0xA7, 2, 26
NODE_HOST, NODE_A, NODE_B = 0, 1, 2
HELLO, SYNC, SET_MASK, ACK, HEARTBEAT = 1, 2, 3, 4, 5
TYPE_NAMES = {HELLO: "HELLO", SYNC: "SYNC", SET_MASK: "SET_MASK", ACK: "ACK", HEARTBEAT: "HEARTBEAT"}

APPLIED, DUP_REPLAY, REJ_SESSION, REJ_BOOT, REJ_STALE_REV, REJ_BAD = range(6)
STATUS_NAMES = ["APPLIED", "DUP_REPLAY", "REJ_SESSION", "REJ_BOOT", "REJ_STALE_REV", "REJ_BAD"]
FW_STATES = ["BOOT", "UNSYNCED", "ONLINE", "LINK_STALE"]

FULL_MASK = 0x01FF
ROOM_MASK = 0x0038
ROOM_BITS = {"A": 3, "B": 4, "C": 5}

_HDR = struct.Struct("<BBBBIII")


def crc16(data: bytes) -> int:
    crc = 0xFFFF
    for byte in data:
        crc ^= byte << 8
        for _ in range(8):
            crc = ((crc << 1) ^ 0x1021) if crc & 0x8000 else (crc << 1)
            crc &= 0xFFFF
    return crc


@dataclass
class Frame:
    node: int
    type: int
    session: int
    boot: int
    seq: int
    payload: bytes  # 8 bytes

    # Typed payload views
    def set_mask(self):  # (state_rev, req_mask)
        rev, mask, _ = struct.unpack("<IHH", self.payload)
        return rev, mask

    def ack(self):  # (cmd_id, applied_mask, status, fw_state)
        return struct.unpack("<IHBB", self.payload)

    def hello(self):  # (fw_ver, role, fw_state, applied_mask)
        ver, role, state, mask, _ = struct.unpack("<HBBHH", self.payload)
        return ver, role, state, mask

    def heartbeat(self):  # (uptime_ms, applied_mask, fw_state)
        up, mask, state, _ = struct.unpack("<IHBB", self.payload)
        return up, mask, state


def encode(node, ftype, session, boot, seq, payload: bytes) -> bytes:
    assert len(payload) == 8
    body = _HDR.pack(MAGIC, VERSION, node, ftype, session, boot, seq) + payload
    return body + struct.pack("<H", crc16(body))


def decode(raw: bytes) -> Frame:
    if len(raw) != FRAME_LEN:
        raise ValueError(f"length {len(raw)} != {FRAME_LEN}")
    magic, ver, node, ftype, session, boot, seq = _HDR.unpack_from(raw)
    if magic != MAGIC or ver != VERSION:
        raise ValueError("bad magic/version")
    if crc16(raw[:24]) != struct.unpack_from("<H", raw, 24)[0]:
        raise ValueError("bad CRC")
    return Frame(node, ftype, session, boot, seq, raw[16:24])


def sync_frame(session, expected_boot, seq) -> bytes:
    return encode(NODE_HOST, SYNC, session, expected_boot, seq, struct.pack("<II", expected_boot, 0))


def set_mask_frame(session, boot, cmd_id, state_rev, req_mask) -> bytes:
    if not 0 <= req_mask <= 0xFFFF:
        raise ValueError("mask out of u16 range")
    return encode(NODE_HOST, SET_MASK, session, boot, cmd_id, struct.pack("<IHH", state_rev, req_mask, 0))


def host_heartbeat_frame(session, boot, seq, uptime_ms) -> bytes:
    return encode(NODE_HOST, HEARTBEAT, session, boot, seq, struct.pack("<IHBB", uptime_ms & 0xFFFFFFFF, 0, 0, 0))


def project(commanded_mask: int) -> int:
    """Physically displayed classroom bits on board B."""
    return commanded_mask & ROOM_MASK


def to_line(frame: bytes) -> str:
    return "F " + frame.hex()


def from_line(line: str):
    """Return frame bytes for an 'F <hex>' line, else None."""
    if not line.startswith("F "):
        return None
    try:
        return bytes.fromhex(line[2:].strip())
    except ValueError:
        return b""
