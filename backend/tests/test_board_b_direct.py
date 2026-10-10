"""Board B alone on USB: the software stand-in for board A drives B's bench interface (#40 contract v2)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
from radio_protocol import KINDS, Packet  # noqa: E402

from app.hardware.board_b_direct import BoardBDirectTransport  # noqa: E402
from app.hardware.gateway import GatewayBridge  # noqa: E402


class FakeBoardBSerial:
    """Board B's USB bench mode: 'F <hex>' frames in, ACK/HEARTBEAT frames out."""

    def __init__(self, boot=5, answer=True):
        self.boot, self.answer = boot, answer
        self.session = self.last_seq = self.applied = self.seq = 0
        self.pending = b""
        self.heartbeat()

    def _frame(self, kind, **fields):
        self.seq += 1
        p = Packet(KINDS[kind], self.session, self.seq, self.boot, mask=self.applied, **fields)
        self.pending += ("F " + p.encode().hex() + "\n").encode()

    def heartbeat(self):
        self._frame("HEARTBEAT")

    def write(self, data):
        line = data.decode().strip()
        p = Packet.decode(bytes.fromhex(line[2:]))
        if not self.answer or p.boot != self.boot:
            return
        if p.kind == KINDS["SYNC"]:
            self.session, self.last_seq = p.session, p.seq
            self._frame("ACK", ack=p.seq)
        elif p.kind == KINDS["SET_LOADS"]:
            ok = p.session == self.session and p.seq > self.last_seq
            if ok:
                self.last_seq, self.applied = p.seq, p.mask & 0x38
            self._frame("ACK", ack=p.seq, status=0 if ok else 1)

    def read(self, _n):
        out, self.pending = self.pending, b""
        return out


def rig(board, mask):
    now = [0.0]
    transport = BoardBDirectTransport("COM-test", clock=lambda: now[0], serial_port=board)
    bridge = GatewayBridge(transport, lambda action, room: False, lambda: mask[0], clock=lambda: now[0],
                           session_seed=lambda: 1000)

    def run(seconds):
        end = now[0] + seconds
        while now[0] < end:
            now[0] += 0.05
            if int(now[0] * 20) % 8 == 0:
                board.heartbeat()
            bridge.step()
    return bridge, run


def test_website_mask_reaches_board_b_and_only_its_ack_confirms():
    board, mask = FakeBoardBSerial(), [0b011000]
    bridge, run = rig(board, mask)
    run(1.0)
    status = bridge.status()
    assert status["link"] == "CONNECTED" and status["board_b"] == {"online": True, "boot": 5, "radio_ready": True}
    assert board.applied == 0b011000 and status["confirmed_mask"] == 0b011000 and status["led_confirmed"]
    mask[0] = 0
    run(0.5)
    assert board.applied == 0 and bridge.status()["confirmed_mask"] == 0


def test_silent_board_b_is_never_reported_confirmed():
    board, mask = FakeBoardBSerial(answer=False), [0b001000]
    bridge, run = rig(board, mask)
    run(3.0)
    assert bridge.status()["confirmed_mask"] is None and not bridge.status()["led_confirmed"]


def test_board_b_reboot_rebinds_and_reapplies():
    board, mask = FakeBoardBSerial(), [0b100000]
    bridge, run = rig(board, mask)
    run(1.0)
    board.boot, board.session, board.last_seq, board.applied = 6, 0, 0, 0  # power-cycled: outputs off
    run(1.0)
    assert bridge.status()["board_b"]["boot"] == 6 and board.applied == 0b100000
    assert bridge.status()["confirmed_mask"] == 0b100000
