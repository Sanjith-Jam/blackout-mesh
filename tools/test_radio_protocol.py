"""Synthetic wire fixtures and exhaustive mask round trips."""
import json
from pathlib import Path
import unittest
import radio_protocol
ROOT = Path(__file__).resolve().parents[1]

class RadioContract(unittest.TestCase):
    def test_radio_fixtures_and_all_masks(self):
        module = radio_protocol
        fixture = json.loads((ROOT / "contracts/schema_examples/esp32_a_v2.json").read_text())
        for row in fixture["radio"]:
            packet = module.Packet.decode(bytes.fromhex(row["wire_hex"]))
            self.assertEqual(packet.mask, row["mask"])
            self.assertEqual(packet.mask & 56, row["applied_classroom_mask"])
        for mask in range(512):
            packet = module.Packet(3, 10, 2, 20, mask=mask)
            self.assertEqual(module.Packet.decode(packet.encode()), packet)
        with self.assertRaises(ValueError):
            module.Packet(3, 10, 2, 20, mask=True).encode()
        with self.assertRaises(ValueError):
            module.Packet(3, 10, 2, 20, mask=512).encode()


if __name__ == "__main__":
    unittest.main()
