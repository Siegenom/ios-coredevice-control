import plistlib
import tempfile
import unittest
from pathlib import Path

from ipad_hybrid_control.pairing import convert_pairing, validate_pairing


class PairingTests(unittest.TestCase):
    def test_convert_pairing(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "rp_pairing_file.plist"
            source.write_bytes(
                plistlib.dumps(
                    {
                        "public_key": b"public",
                        "private_key": b"private",
                        "identifier": "host-id",
                        "alt_irk": b"irk",
                    }
                )
            )
            target = root / "remote_device.plist"
            convert_pairing(source, "device-udid", target)
            self.assertEqual(validate_pairing(target, "device-udid"), [])
            record = plistlib.loads(target.read_bytes())
            self.assertEqual(record["host_identifier"], "host-id")
            self.assertEqual(record["peer_udid"], "device-udid")

    def test_default_destination_stays_next_to_source(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "rp_pairing_file.plist"
            source.write_bytes(
                plistlib.dumps(
                    {
                        "public_key": b"public",
                        "private_key": b"private",
                        "identifier": "host-id",
                        "alt_irk": b"irk",
                    }
                )
            )
            target = convert_pairing(source, "device-udid")
            self.assertEqual(target, root / "remote-pairing.plist")
            self.assertEqual(validate_pairing(target, "device-udid"), [])


if __name__ == "__main__":
    unittest.main()
