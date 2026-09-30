import os
import subprocess
import tempfile
import unittest
from pathlib import Path

from tools.check_release import commit_metadata_findings


class ReleaseMetadataTests(unittest.TestCase):
    def test_checks_both_roles_and_ancestors_without_printing_addresses(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            def git(*args, author="user@users.noreply.github.com", committer="123+user@users.noreply.github.com"):
                env = dict(os.environ, GIT_AUTHOR_NAME="Test", GIT_COMMITTER_NAME="Test",
                           GIT_AUTHOR_EMAIL=author, GIT_COMMITTER_EMAIL=committer)
                return subprocess.check_output(["git", "-C", str(root), *args], env=env, stderr=subprocess.PIPE)
            git("init")
            git("-c", "commit.gpgsign=false", "commit", "--allow-empty", "-m", "private metadata",
                author="private@example.org", committer="private@example.org")
            git("-c", "commit.gpgsign=false", "commit", "--allow-empty", "-m", "safe metadata")
            findings = commit_metadata_findings(root)
            self.assertEqual(len(findings), 2)
            self.assertIn("author email", findings[0])
            self.assertIn("committer email", findings[1])
            self.assertNotIn("private@example.org", str(findings))
            git("checkout", "--orphan", "clean")
            git("-c", "commit.gpgsign=false", "commit", "--allow-empty", "-m", "clean root")
            self.assertEqual(commit_metadata_findings(root), [])

    def test_missing_repository_fails_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            self.assertTrue(commit_metadata_findings(Path(directory)))
