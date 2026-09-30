import tempfile
import unittest
from pathlib import Path

from ipad_hybrid_control.config import DeviceConfig


class ConfigTests(unittest.TestCase):
    def test_relative_paths_are_based_on_config_file(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            config = root / "config.toml"
            config.write_text(
                "[device]\n"
                'udid = "device-udid"\n'
                'host = "ipad.example"\n'
                'pairing_record = "secrets/remote-pairing.plist"\n'
                "\n[output]\n"
                'directory = "captures"\n',
                encoding="utf-8",
            )
            (root / "secrets").mkdir()
            (root / "secrets" / "remote-pairing.plist").touch()
            (root / "captures").mkdir()
            loaded = DeviceConfig.load(config)
            self.assertTrue(loaded.pairing_record.samefile(root / "secrets" / "remote-pairing.plist"))
            self.assertTrue(loaded.output_directory.samefile(root / "captures"))

    def test_requires_explicit_pairing_record(self):
        with tempfile.TemporaryDirectory() as temporary:
            config = Path(temporary) / "config.toml"
            config.write_text(
                "[device]\n"
                'udid = "device-udid"\n'
                'host = "ipad.example"\n',
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "pairing_record"):
                DeviceConfig.load(config)


if __name__ == "__main__":
    unittest.main()
