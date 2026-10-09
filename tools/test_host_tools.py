"""Tests with a fake serial port: no physical hardware claim."""
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


def load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "tools" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    with patch.dict(sys.modules, {"serial": types.ModuleType("serial"), name: module}):
        spec.loader.exec_module(module)
    return module


class Port:
    def __init__(self, messages):
        self.messages = iter(messages)
        self.sent = []
    def __enter__(self):
        return self
    def __exit__(self, *_):
        pass
    def write(self, data):
        self.sent.append(json.loads(data))
    def read_until(self, *_):
        try:
            return (json.dumps(next(self.messages)) + "\n").encode()
        except StopIteration:
            raise KeyboardInterrupt


class HostTools(unittest.TestCase):
    def test_console_rejects_invalid_input(self):
        module = load("gateway_console")
        for value in (True, -1, 0, 2**32, float("nan")):
            self.assertFalse(module.uint32(value))
        self.assertFalse(module.valid_event({"event": 1, "action": "START_SESSION", "room": "D"}))
        self.assertFalse(module.valid_event({"event": True, "action": "RESET_SESSION"}))
        self.assertFalse(module.valid_context({"boot": 1, "epoch": 1, "session": False}))

    def test_enrollment_private_map(self):
        module = load("enroll_cards")
        port = Port([{"v": 2, "type": "enroll_uid", "uid": value} for value in
                     ["01020304", "01020304", "01020304050607", "0102030405060708090A"]])
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "cards.local.h"
            with patch.object(module.serial, "Serial", return_value=port, create=True), contextlib.redirect_stdout(io.StringIO()):
                module.collect("FAKE", output)
            self.assertEqual(output.stat().st_mode & 0o777, 0o600)
            self.assertEqual(output.read_text().count('"'), 6)

    def test_console_deduplicates_keeps_a_and_b(self):
        module = load("gateway_console")
        context = {"v": 2, "boot": 1, "epoch": 2, "session": 4}
        hello = {"v": 2, "type": "hello", "boot": 1, "epoch": 2, "minimum_session": 3}
        event_a = {**context, "type": "event", "event": 1, "action": "START_SESSION", "room": "A"}
        event_b = {**event_a, "event": 2, "room": "B"}
        port = Port([hello, event_a, event_a, event_b])
        output = io.StringIO()
        with patch.object(module.serial, "Serial", return_value=port, create=True), contextlib.redirect_stdout(output):
            with self.assertRaises(KeyboardInterrupt):
                module.run("FAKE", 1)
        self.assertEqual(output.getvalue().count("START_SESSION"), 2)
        self.assertIn("['A', 'B']", output.getvalue())
        self.assertEqual(sum(m["type"] == "event_ack" for m in port.sent), 3)
        self.assertEqual(port.sent[1]["session"], 4)


if __name__ == "__main__":
    unittest.main()
