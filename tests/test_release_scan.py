import importlib.util
import subprocess
import tempfile
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "tools" / "check_release.py"
SPEC = importlib.util.spec_from_file_location("check_release", MODULE_PATH)
check_release = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(check_release)


class ReleaseScanTests(unittest.TestCase):
    def test_ignored_local_config_is_not_a_candidate(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            subprocess.run(["git", "init", "-q", str(root)], check=True)
            (root / ".gitignore").write_text("config.toml\n", encoding="utf-8")
            (root / "safe.txt").write_text("safe", encoding="utf-8")
            (root / "config.toml").write_text('udid = "local-device-id"', encoding="utf-8")
            subprocess.run(["git", "-C", str(root), "add", ".gitignore", "safe.txt"], check=True)
            candidates = {path.relative_to(root).as_posix() for path in check_release.release_candidates(root)}
            self.assertNotIn("config.toml", candidates)
            self.assertIn("safe.txt", candidates)

    def test_rejects_pairing_record_by_filename(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            record = root / "remote-pairing.plist"
            record.write_bytes(b"binary plist payload")
            self.assertEqual(
                check_release.file_findings([record], root),
                ["remote-pairing.plist: forbidden release file"],
            )

    def test_rejects_tracked_runtime_config(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            config = root / "config.toml"
            config.write_text("[device]", encoding="utf-8")
            self.assertEqual(
                check_release.file_findings([config], root),
                ["config.toml: forbidden release file"],
            )

    def test_rejects_top_level_generated_artifact_directory(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            image = root / "artifacts" / "screen.txt"
            image.parent.mkdir()
            image.write_text("captured screen", encoding="utf-8")
            self.assertEqual(
                check_release.file_findings([image], root),
                ["artifacts/screen.txt: forbidden release file"],
            )

    def test_allows_same_directory_name_below_docs(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            text = root / "docs" / "build" / "notes.txt"
            text.parent.mkdir(parents=True)
            text.write_text("documentation", encoding="utf-8")
            self.assertEqual(check_release.file_findings([text], root), [])

    def test_allows_documentation_image_outside_runtime_paths(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            image = root / "docs" / "screen.png"
            image.parent.mkdir()
            image.write_bytes(b"not-a-real-image")
            self.assertEqual(check_release.file_findings([image], root), [])

    def test_allows_non_runtime_log_and_plist(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            log = root / "docs" / "example.log"
            plist = root / "tests" / "fixture.plist"
            log.parent.mkdir()
            plist.parent.mkdir()
            log.write_text("sanitized example", encoding="utf-8")
            plist.write_text("<plist><dict/></plist>", encoding="utf-8")
            self.assertEqual(check_release.file_findings([log, plist], root), [])

    def test_rejects_pem_private_key_text(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            text = root / "notes.txt"
            marker = "-----BEGIN " + "PRIVATE KEY-----"
            text.write_text(marker + "\nsynthetic\n", encoding="utf-8")
            self.assertEqual(
                check_release.file_findings([text], root),
                ["notes.txt: PEM private key"],
            )


if __name__ == "__main__":
    unittest.main()
