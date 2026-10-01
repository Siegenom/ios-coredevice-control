from __future__ import annotations

import os
import plistlib
import tempfile
from pathlib import Path


SOURCE_KEYS = {"public_key", "private_key", "identifier", "alt_irk"}
RECORD_KEYS = {
    "public_key",
    "private_key",
    "host_identifier",
    "host_alt_irk",
    "peer_udid",
    "remote_unlock_host_key",
}


def convert_pairing(source: Path, udid: str, destination: Path | None = None) -> Path:
    raw = plistlib.loads(source.read_bytes())
    missing = SOURCE_KEYS.difference(raw)
    if missing:
        raise ValueError(f"StikPair plist is missing keys: {', '.join(sorted(missing))}")

    record = {
        "public_key": raw["public_key"],
        "private_key": raw["private_key"],
        "host_identifier": raw["identifier"],
        "host_alt_irk": raw["alt_irk"],
        "peer_udid": udid,
        "remote_unlock_host_key": "",
    }
    target = destination or source.with_name("remote-pairing.plist")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(plistlib.dumps(record))
    return target


def validate_pairing(path: Path, udid: str, *, debug: bool = False) -> list[str]:
    problems: list[str] = []
    if not path.is_file():
        return [f"pairing record not found: {path}" if debug else "pairing record not found"]
    try:
        record = plistlib.loads(path.read_bytes())
    except Exception as exc:  # plist parse error should be reported, not hidden
        return [f"cannot parse pairing record: {exc}" if debug else "cannot parse pairing record"]
    missing = RECORD_KEYS.difference(record)
    if missing:
        problems.append(f"missing keys: {', '.join(sorted(missing))}")
    if record.get("peer_udid") != udid:
        problems.append("peer_udid does not match the configured UDID")
    return problems


def stage_pairing_record(source: Path, destination: Path, udid: str) -> None:
    """Atomically stage the configured record where pymobiledevice3 loads it."""
    problems = validate_pairing(source, udid, debug=False)
    if problems:
        raise ValueError("invalid configured pairing record: " + "; ".join(problems))

    payload = source.read_bytes()
    destination.parent.mkdir(parents=True, exist_ok=True)

    # Write in the destination directory so os.replace() stays on the same
    # filesystem and is atomic.  Avoid exposing the configured source path in
    # normal exception messages.
    fd, temporary = tempfile.mkstemp(
        prefix=f".{destination.name}.",
        suffix=".tmp",
        dir=destination.parent,
    )
    temporary_path = Path(temporary)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_path, destination)
    finally:
        if temporary_path.exists():
            temporary_path.unlink()
