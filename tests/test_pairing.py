import plistlib
import tempfile
import unittest
from pathlib import Path

from ipad_hybrid_control.pairing import convert_pairing, stage_pairing_record, validate_pairing


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

    def test_stages_configured_record_for_transport(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "configured.plist"
            source.write_bytes(
                plistlib.dumps(
                    {
                        "public_key": b"public",
                        "private_key": b"private",
                        "host_identifier": "host-id",
                        "host_alt_irk": b"irk",
                        "peer_udid": "device-udid",
                        "remote_unlock_host_key": "",
                    }
                )
            )
            destination = root / "pymobiledevice3" / "remote_device-udid.plist"
            stage_pairing_record(source, destination, "device-udid")
            self.assertEqual(destination.read_bytes(), source.read_bytes())

    def test_rejects_invalid_record_before_staging_without_leaking_path(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "private-user-name" / "invalid.plist"
            source.parent.mkdir()
            source.write_bytes(plistlib.dumps({}))
            destination = root / "cache" / "record.plist"
            destination.parent.mkdir()
            destination.write_bytes(b"existing-cache")
            with self.assertRaisesRegex(ValueError, "invalid configured pairing record") as raised:
                stage_pairing_record(source, destination, "device-udid")
            self.assertNotIn(str(source), str(raised.exception))
            self.assertEqual(destination.read_bytes(), b"existing-cache")


if __name__ == "__main__":
    unittest.main()
