from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # Python 3.10
    import tomli as tomllib


@dataclass(frozen=True)
class DeviceConfig:
    udid: str
    host: str
    port: int = 49152
    output_directory: Path = Path("artifacts")
    thumbnail_width: int = 768
    pairing_record: Path = Path("secrets/remote-pairing.plist")

    @classmethod
    def load(
        cls,
        path: Path | None,
        *,
        udid: str | None = None,
        host: str | None = None,
        port: int | None = None,
    ) -> "DeviceConfig":
        data: dict = {}
        if path is not None:
            if not path.is_file():
                raise FileNotFoundError(f"configuration file not found: {path}")
            with path.open("rb") as handle:
                data = tomllib.load(handle)

        device = data.get("device", {})
        output = data.get("output", {})
        resolved_udid = udid or os.getenv("IPAD_UDID") or device.get("udid")
        resolved_host = host or os.getenv("IPAD_HOST") or device.get("host")
        resolved_port = port or int(os.getenv("IPAD_PORT", device.get("port", 49152)))
        pairing_value = os.getenv("IPAD_PAIRING_RECORD") or device.get("pairing_record")

        if not resolved_udid or resolved_udid == "YOUR-IPAD-UDID":
            raise ValueError("set the iPad UDID in config.toml, IPAD_UDID, or --udid")
        if not resolved_host or resolved_host == "YOUR-IPAD-IP-OR-HOSTNAME":
            raise ValueError("set the reachable iPad host in config.toml, IPAD_HOST, or --host")
        if not 1 <= int(resolved_port) <= 65535:
            raise ValueError("device port must be between 1 and 65535")
        if not pairing_value:
            raise ValueError("set device.pairing_record in config.toml or IPAD_PAIRING_RECORD")

        output_dir = Path(output.get("directory", "artifacts"))
        pairing_record = Path(str(pairing_value))
        if path is not None and not output_dir.is_absolute():
            output_dir = path.resolve().parent / output_dir
        if path is not None and not pairing_record.is_absolute():
            pairing_record = path.resolve().parent / pairing_record

        return cls(
            udid=str(resolved_udid),
            host=str(resolved_host),
            port=int(resolved_port),
            output_directory=output_dir,
            thumbnail_width=int(output.get("thumbnail_width", 768)),
            pairing_record=pairing_record,
        )
