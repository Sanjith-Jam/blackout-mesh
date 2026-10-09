"""python -m unittest test_person_b  (run from host/)"""
import unittest

import allocator as al
import protocol as p
from controller import Controller, RulesActivity
from link import BLink, SimBoardB


class Clock:
    def __init__(self):
        self.t = 100.0

    def __call__(self):
        return self.t


def pump(link, board, clock, seconds=0.0, step=0.05):
    end = clock.t + seconds
    while True:
        link.tick()
        if clock.t >= end:
            link.tick()
            return
        clock.t += step
        if int(clock.t * 20) % 20 == 0:
            board.heartbeat()


def rig(session=7):
    clock, board = Clock(), SimBoardB()
    link = BLink(board, session, clock)
    ctl = Controller(link, RulesActivity(), clock)
    pump(link, board, clock, 0.2)
    return clock, board, link, ctl


def act(ctl, clock, board, *events, settle=0.3):
    for e in events:
        ctl.handle(*e)
    for _ in range(int(settle / 0.05)):
        ctl.recompute()
        pump(ctl.link, board, clock, 0.05)


class ProtocolTests(unittest.TestCase):
    def test_crc_check_value(self):
        self.assertEqual(p.crc16(b"123456789"), 0x29B1)

    def test_roundtrip_and_size(self):
        raw = p.set_mask_frame(12, 0x15A27, 4021, 42, 0x01FF)
        self.assertEqual(len(raw), 26)
        f = p.decode(raw)
        self.assertEqual(f.set_mask(), (42, 0x01FF))
        bad = bytearray(raw)
        bad[20] ^= 1
        with self.assertRaises(ValueError):
            p.decode(bytes(bad))

    def test_projection_fixtures(self):
        for cmd, shown in [(0, 0), (8, 8), (16, 16), (32, 32), (24, 24), (56, 56), (0x1FF, 0x38), (0x7, 0)]:
            self.assertEqual(p.project(cmd), shown)


class AllocatorTests(unittest.TestCase):
    def test_unregistered_never_served(self):
        self.assertEqual(al.allocate([], {}, 16).served, ())
        self.assertEqual(al.allocate(["A"], {}, 6).served, ("A",))

    def test_shortage_fits_one(self):
        self.assertEqual(al.allocate(["A", "B"], {}, 6).served, ("A",))
        self.assertEqual(al.allocate(["A", "B"], {"B": "ACTIVE"}, 6).served, ("B",))
        self.assertEqual(al.allocate(["A", "B"], {"A": "INACTIVE"}, 6).served, ("B",))

    def test_skips_room_that_does_not_fit(self):
        self.assertEqual(al.allocate(["A", "B", "C"], {}, 10).served, ("A", "C"))
        self.assertEqual(al.allocate(["A", "B", "C"], {}, 16).served, ("A", "B", "C"))


class EndToEndTests(unittest.TestCase):
    def test_sync_then_only_a_on(self):
        clock, board, link, ctl = rig()
        self.assertEqual(link.link_state(), "ONLINE")
        act(ctl, clock, board, ("RESET",), ("SHORTAGE",))
        self.assertEqual(board.applied, 0)
        act(ctl, clock, board, ("SCAN", "A"))
        self.assertEqual(board.applied, 8)
        self.assertTrue(link.confirmed())

    def test_b_only_and_c_only(self):
        for room, mask in (("B", 16), ("C", 32)):
            clock, board, link, ctl = rig()
            act(ctl, clock, board, ("SHORTAGE",), ("SCAN", room))
            self.assertEqual(board.applied, mask)

    def test_constrained_pair_and_end(self):
        clock, board, link, ctl = rig()
        act(ctl, clock, board, ("SCAN", "A"), ("SCAN", "B"))
        self.assertEqual(board.applied, 24)
        act(ctl, clock, board, ("SHORTAGE",))
        self.assertEqual(board.applied, 8)
        act(ctl, clock, board, ("SELECT", "A"), ("END",))
        self.assertEqual(board.applied, 16)  # B reallocated after A ends

    def test_unknown_card_and_end_without_selection(self):
        clock, board, link, ctl = rig()
        act(ctl, clock, board, ("SCAN", "A"))
        act(ctl, clock, board, ("UNKNOWN_CARD",))
        self.assertEqual((ctl.registered, board.applied), (["A"], 8))
        clock2, board2, link2, ctl2 = rig()
        act(ctl2, clock2, board2, ("END",))
        self.assertIn("END ignored", ctl2.log[-1])

    def test_duplicate_event_ids_ignored(self):
        clock, board, link, ctl = rig()
        act(ctl, clock, board, ("SCAN", "A", "e1"), ("END", None, "e2"), ("END", None, "e2"))
        act(ctl, clock, board, ("SCAN", "A", "e1"))
        self.assertEqual(ctl.registered, [])

    def test_staged_restore(self):
        clock, board, link, ctl = rig()
        act(ctl, clock, board, ("SCAN", "A"), ("SCAN", "B"), ("SCAN", "C"), ("SHORTAGE",))
        self.assertEqual(board.applied, 8)
        act(ctl, clock, board, ("RESTORE",), settle=0.3)
        self.assertEqual(board.applied, 8)
        act(ctl, clock, board, settle=1.2)
        self.assertEqual(board.applied, 24)
        act(ctl, clock, board, settle=1.2)
        self.assertEqual(board.applied, 56)

    def test_b_offline_shows_unconfirmed_then_reconciles(self):
        clock, board, link, ctl = rig()
        act(ctl, clock, board, ("SCAN", "A"))
        board.online = False
        act(ctl, clock, board, ("SELECT", "A"), ("END",), settle=1.0)
        self.assertFalse(link.confirmed())
        self.assertEqual(board.applied, 8)  # B holds last acknowledged output
        act(ctl, clock, board, settle=4.0)
        self.assertEqual(link.link_state(), "STALE")
        board.online = True
        act(ctl, clock, board, settle=2.0)
        self.assertEqual(board.applied, 0)
        self.assertTrue(link.confirmed())

    def test_reboot_starts_off_and_resyncs(self):
        clock, board, link, ctl = rig()
        act(ctl, clock, board, ("SCAN", "C"))
        board.reboot(0x1234)
        self.assertEqual(board.applied, 0)
        act(ctl, clock, board, settle=1.0)
        self.assertEqual(link.reboots, 1)
        self.assertEqual(board.applied, 32)

    def test_lost_ack_retry_is_idempotent(self):
        clock, board, link, ctl = rig()
        board.drop_next_acks = 1
        act(ctl, clock, board, ("SCAN", "A"), settle=0.5)
        self.assertTrue(link.confirmed())
        self.assertEqual(board.last_rev, 2)  # initial OFF sync + A; the retry was a DUP_REPLAY, not a new change

    def test_board_rejects_stale_wrong_session_and_bad_mask(self):
        clock, board, link, ctl = rig(session=7)
        act(ctl, clock, board, ("SCAN", "A"))
        sess, boot = link.session, board.boot
        def ack_for(frame):
            board.send_line(p.to_line(frame))
            return p.decode(p.from_line(board.poll_lines()[-1])).ack()
        self.assertEqual(ack_for(p.set_mask_frame(sess - 1, boot, 900, 99, 56))[2], p.REJ_SESSION)
        self.assertEqual(ack_for(p.set_mask_frame(sess, boot + 1, 901, 99, 56))[2], p.REJ_BOOT)
        self.assertEqual(ack_for(p.set_mask_frame(sess, boot, 902, 0, 56))[2], p.REJ_STALE_REV)
        self.assertEqual(ack_for(p.set_mask_frame(sess, boot, 903, 99, 0x200))[2], p.REJ_BAD)
        self.assertEqual(board.applied, 8)


if __name__ == "__main__":
    unittest.main()
