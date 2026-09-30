from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TEXT_SUFFIXES = {".py", ".ps1", ".md", ".toml", ".txt", ".yml", ".yaml", ".plist"}
PATTERNS = {
    "Apple Account email": re.compile(r"[A-Za-z0-9._%+-]+@(gmail|icloud|me)\.com", re.I),
    "real iOS UDID": re.compile(r"\b0000[0-9A-F]{4}-[0-9A-F]{16}\b", re.I),
    "Tailscale IPv4": re.compile(r"\b100\.(?:6[4-9]|[7-9]\d|1[01]\d|12[0-7])\.(?:\d{1,3}\.)\d{1,3}\b(?!/\d)"),
    "pairing private key": re.compile("<key>private" + "_key</key>", re.I),
}


def release_candidates() -> list[Path]:
    try:
        result = subprocess.run(
            ["git", "-C", str(ROOT), "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    except (FileNotFoundError, subprocess.CalledProcessError):
        return [path for path in ROOT.rglob("*") if path.is_file()]

    return [ROOT / os.fsdecode(item) for item in result.stdout.split(b"\0") if item]


NOREPLY = re.compile(r"(?:[0-9]+\+)?[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?@users\.noreply\.github\.com", re.I)


def commit_metadata_findings(root: Path = ROOT) -> list[str]:
    # Inspect raw metadata (lowercase %ae/%ce), never mailmap substitutions.
    # HEAD is the publication history; private recovery refs are not published.
    try:
        shallow = subprocess.check_output(
            ["git", "-C", str(root), "rev-parse", "--is-shallow-repository"],
            stderr=subprocess.PIPE, text=True,
        ).strip()
        if shallow != "false":
            return ["commit metadata: full Git history is required (shallow checkout)"]
        log = subprocess.check_output(
            ["git", "-C", str(root), "log", "HEAD", "--format=%H%x00%ae%x00%ce"],
            stderr=subprocess.PIPE, text=True, encoding="utf-8", errors="replace",
        )
    except (OSError, subprocess.CalledProcessError):
        return ["commit metadata: cannot inspect HEAD history"]
    findings = []
    for line in log.splitlines():
        commit, author, committer = line.split("\0")
        for role, email in (("author", author), ("committer", committer)):
            if not NOREPLY.fullmatch(email):
                # Do not repeat the private address in logs.
                findings.append(f"commit {commit[:12]}: non-GitHub-noreply {role} email")
    return findings


def main() -> int:
    findings: list[str] = commit_metadata_findings()
    for path in release_candidates():
        if not path.is_file() or path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        if any(part in {".git", ".venv", "__pycache__"} for part in path.parts):
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        for label, pattern in PATTERNS.items():
            if pattern.search(text):
                findings.append(f"{path.relative_to(ROOT)}: {label}")
    if findings:
        print("Release check failed:")
        print("\n".join(f"- {item}" for item in findings))
        return 1
    print("Release check passed: file scan and HEAD commit email checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
