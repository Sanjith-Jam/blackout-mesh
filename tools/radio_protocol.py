"""26-byte v2 codec for contract fixtures and future host integration; no I/O."""
from dataclasses import dataclass
import struct

KINDS = {"HELLO": 1, "SYNC": 2, "SET_LOADS": 3, "ACK": 4, "HEARTBEAT": 5, "BUTTON": 6}
VALID_MASK = 0x01FF
CLASSROOM_MASK = 0x0038
HEADER = struct.Struct("<BBBBIIIIHBB")


def crc16(data):
    crc = 0xFFFF
    for byte in data:
        crc ^= byte << 8
        for _ in range(8):
            crc = ((crc << 1) ^ (0x1021 if crc & 0x8000 else 0)) & 0xFFFF
    return crc


@dataclass(frozen=True)
class Packet:
    kind: int
    session: int
    seq: int
    boot: int
    ack: int = 0
    mask: int = 0
    status: int = 0
    flags: int = 0

    def encode(self):
        values = (self.kind, self.session, self.seq, self.boot, self.ack, self.mask, self.status, self.flags)
        if any(type(value) is not int for value in values):
            raise ValueError("integer fields required")
        if self.kind not in KINDS.values() or not 1 <= self.boot <= 0xFFFFFFFF:
            raise ValueError("invalid kind/boot")
        if any(not 0 <= value <= 0xFFFFFFFF for value in (self.session, self.seq, self.ack)):
            raise ValueError("invalid counter")
        if not 0 <= self.mask <= VALID_MASK or self.status not in (0, 1) or self.flags:
            raise ValueError("invalid mask/status/flags")
        body = HEADER.pack(0xA5, 2, self.kind, 2, self.session, self.seq, self.boot,
                           self.ack, self.mask, self.status, self.flags)
        return body + struct.pack("<H", crc16(body))

    @classmethod
    def decode(cls, data):
        if len(data) != 26 or crc16(data[:24]) != struct.unpack("<H", data[24:])[0]:
            raise ValueError("length/CRC")
        magic, version, kind, node, *fields = HEADER.unpack(data[:24])
        if (magic, version, node) != (0xA5, 2, 2):
            raise ValueError("header")
        packet = cls(kind, *fields)
        packet.encode()
        return packet
