import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from ipad_hybrid_control.cli import doctor, main
from ipad_hybrid_control.config import DeviceConfig


class DoctorTests(unittest.TestCase):
    def test_default_hides_identifiers_in_fields_and_errors(self):
        with tempfile.TemporaryDirectory() as directory:
            record = Path(directory) / "private-record.plist"
            config = DeviceConfig("private-device", "private-host", pairing_record=record)
            with patch("ipad_hybrid_control.cli.socket.create_connection",
                       side_effect=OSError(f"cannot connect {config.host} {record}")):
                result = doctor(config)
            output = json.dumps(result)
            for secret in (config.udid, config.host, str(record), directory):
                self.assertNotIn(secret, output)
            self.assertFalse(result["ok"])
            self.assertEqual(result["pairingRecord"], "[redacted]")

    def test_debug_exposes_details_explicitly(self):
        config = DeviceConfig("private-device", "private-host", pairing_record=Path("missing.plist"))
        with patch("ipad_hybrid_control.cli.socket.create_connection", side_effect=OSError("detail")):
            result = doctor(config, debug=True)
        self.assertEqual(result["udid"], config.udid)
        self.assertEqual(result["host"], config.host)
        self.assertEqual(result["pairingRecord"], str(config.pairing_record))
        self.assertEqual(result["tcpError"], "detail")

    def test_config_failure_does_not_leak_exception_text(self):
        output = io.StringIO()
        with patch("ipad_hybrid_control.cli.load_config", side_effect=ValueError("private-value")):
            with contextlib.redirect_stdout(output):
                self.assertEqual(main(["doctor"]), 1)
        self.assertNotIn("private-value", output.getvalue())

    def test_success_stays_redacted(self):
        config = DeviceConfig("private-device", "private-host")
        with patch("ipad_hybrid_control.cli.validate_pairing", return_value=[]), patch(
            "ipad_hybrid_control.cli.socket.create_connection"
        ):
            result = doctor(config)
        self.assertTrue(result["ok"])
        self.assertEqual(result["host"], "[redacted]")

    def test_parse_error_does_not_leak_parser_details(self):
        from ipad_hybrid_control.pairing import validate_pairing
        with tempfile.TemporaryDirectory() as directory:
            record = Path(directory) / "record.plist"
            record.write_bytes(b"invalid")
            with patch("ipad_hybrid_control.pairing.plistlib.loads", side_effect=ValueError("private-value")):
                self.assertEqual(validate_pairing(record, "device"), ["cannot parse pairing record"])
