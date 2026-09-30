from __future__ import annotations

import argparse
import asyncio
import gc
import json
import socket
import sys
import time
from contextlib import suppress
from pathlib import Path
from typing import Any, Awaitable, Callable

from .config import DeviceConfig
from .connection import open_rsd
from .ddi import mount_ddi
from .operations import (
    capture_bytes,
    difference_score,
    launch,
    orientation,
    paste,
    press,
    rotate,
    save_capture,
    swipe,
    tap,
    type_ascii,
)
from .pairing import convert_pairing, validate_pairing
from .semantic import collect_elements, press_text


def emit(payload: dict[str, Any]) -> None:
    # ASCII escapes survive both UTF-8 and legacy cp932 Windows consoles.
    print(json.dumps(payload, ensure_ascii=True, default=str, separators=(",", ":")), flush=True)


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(
        prog="ipad-control",
        description="Control an iPad through shared CoreDevice transport with vision or accessibility observation.",
    )
    result.add_argument("--config", type=Path, default=Path("config.toml"))
    result.add_argument("--udid")
    result.add_argument("--host")
    result.add_argument("--port", type=int)
    result.add_argument("--debug", action="store_true")
    sub = result.add_subparsers(dest="command", required=True)

    sub.add_parser("doctor", help="validate configuration, pairing record, and TCP reachability")
    sub.add_parser("status", help="connect and report orientation and screenshot dimensions")
    sub.add_parser("orient", help="report the current SpringBoard orientation")
    sub.add_parser("mount-ddi", help="mount the personalized developer image")

    pair = sub.add_parser("convert-pairing", help="convert a StikPair plist for pymobiledevice3")
    pair.add_argument("source", type=Path)
    pair.add_argument("--device-udid", help="override the UDID in config.toml")
    pair.add_argument("--output", type=Path)

    observe = sub.add_parser("observe", aliases=["look"], help="save the current screen for visual analysis")
    observe.add_argument("--out", type=Path)
    observe.add_argument("--thumbnail", type=Path)

    elements = sub.add_parser("elements", help="read foreground accessibility captions without a vision model")
    elements.add_argument("--filter")
    elements.add_argument("--limit", type=int, default=0)
    elements.add_argument("--max-chars", type=int, default=80)
    elements.add_argument("--passes", type=int, default=2)

    launch_parser = sub.add_parser("launch", help="launch an application by bundle identifier")
    launch_parser.add_argument("bundle_id")

    rotate_parser = sub.add_parser("rotate", help="rotate the device by 90 degrees")
    rotate_parser.add_argument("direction", choices=("left", "right"))

    tap_parser = sub.add_parser("tap", help="tap a pixel coordinate from the latest screenshot")
    tap_parser.add_argument("x", type=int)
    tap_parser.add_argument("y", type=int)

    swipe_parser = sub.add_parser("swipe", help="swipe between screenshot pixel coordinates")
    swipe_parser.add_argument("x1", type=int)
    swipe_parser.add_argument("y1", type=int)
    swipe_parser.add_argument("x2", type=int)
    swipe_parser.add_argument("y2", type=int)
    swipe_parser.add_argument("--duration", type=int, default=300)
    swipe_parser.add_argument("--steps", type=int, default=16)

    press_parser = sub.add_parser("press", help="press home, lock, volume-up, volume-down, mute, or siri")
    press_parser.add_argument("name")

    type_parser = sub.add_parser("type", help="type printable US-layout ASCII into the focused field")
    type_parser.add_argument("text")
    type_parser.add_argument("--key-delay", type=int, default=0)

    paste_parser = sub.add_parser("paste", help="paste Unicode text into the focused field")
    paste_parser.add_argument("text")

    tap_text_parser = sub.add_parser(
        "tap-text",
        help="best-effort AX Activate by caption; use coordinate HID when UIKit does not activate",
    )
    tap_text_parser.add_argument("text")
    tap_text_parser.add_argument("--index", type=int, default=0)
    tap_text_parser.add_argument("--limit", type=int, default=0)
    tap_text_parser.add_argument("--max-chars", type=int, default=80)
    tap_text_parser.add_argument("--include-headers", action="store_true")

    for action_parser in (
        launch_parser, tap_parser, swipe_parser, press_parser, type_parser, paste_parser, tap_text_parser
    ):
        action_parser.add_argument("--after", type=Path, help="path for the post-action screenshot")
        action_parser.add_argument("--settle", type=float, default=0.8)
        action_parser.add_argument(
            "--measure-change",
            action="store_true",
            help="report a numeric before/after screen change without interpreting the image",
        )
    return result


def load_config(args: argparse.Namespace) -> DeviceConfig:
    return DeviceConfig.load(args.config, udid=args.udid, host=args.host, port=args.port)


def doctor(config: DeviceConfig, *, debug: bool = False) -> dict[str, Any]:
    problems = validate_pairing(config.pairing_record, config.udid, debug=debug)
    reachable = False
    tcp_error = None
    try:
        with socket.create_connection((config.host, config.port), timeout=5):
            reachable = True
    except OSError as exc:
        tcp_error = str(exc) if debug else type(exc).__name__
        problems.append(
            f"TCP {config.host}:{config.port} is unreachable: {exc}"
            if debug else "TCP endpoint is unreachable"
        )
    return {
        "ok": not problems,
        "udid": config.udid if debug else "[redacted]",
        "host": config.host if debug else "[redacted]",
        "port": config.port,
        "pairingRecord": str(config.pairing_record) if debug else "[redacted]",
        "tcpReachable": reachable,
        "tcpError": tcp_error,
        "problems": problems,
    }


async def after_image(config: DeviceConfig, rsd: Any, path: Path | None) -> dict[str, Any]:
    target = path or config.output_directory / "after.png"
    return await save_capture(
        rsd,
        target,
        thumbnail=config.output_directory / "after-thumb.jpg",
        thumbnail_width=config.thumbnail_width,
    )


async def run_connected(args: argparse.Namespace, config: DeviceConfig) -> dict[str, Any]:
    started = time.monotonic()
    async with open_rsd(config) as rsd:
        if args.command == "status":
            code, name = await orientation(rsd)
            captured = await save_capture(rsd, config.output_directory / "status.png")
            result: dict[str, Any] = {
                "ok": True,
                "orientation": name,
                "orientationCode": code,
                "screen": captured["size"],
            }
        elif args.command == "orient":
            code, name = await orientation(rsd)
            result = {"ok": True, "orientation": name, "orientationCode": code}
        elif args.command == "mount-ddi":
            stages: list[str] = []
            state = await mount_ddi(rsd, stages.append)
            result = {"ok": True, "state": state, "stages": stages}
        elif args.command in ("observe", "look"):
            out = args.out or config.output_directory / "screen.png"
            thumb = args.thumbnail or config.output_directory / "screen-thumb.jpg"
            code, name = await orientation(rsd)
            result = {
                "ok": True,
                "orientation": name,
                "orientationCode": code,
                **await save_capture(rsd, out, thumbnail=thumb, thumbnail_width=config.thumbnail_width),
            }
        elif args.command == "elements":
            result = {
                "ok": True,
                **await collect_elements(
                    rsd,
                    text_filter=args.filter,
                    limit=args.limit,
                    max_chars=args.max_chars,
                    passes=args.passes,
                ),
            }
        elif args.command == "rotate":
            # Do not capture through the same RSD lease after rotation.  The
            # next CLI process reconnects and observes the new orientation.
            result = {"ok": True, **await rotate(rsd, args.direction)}
        else:
            actions: dict[str, Callable[[], Awaitable[dict[str, Any]]]] = {
                "launch": lambda: launch(rsd, args.bundle_id),
                "tap": lambda: tap(rsd, args.x, args.y),
                "swipe": lambda: swipe(
                    rsd, args.x1, args.y1, args.x2, args.y2,
                    duration_ms=args.duration, steps=args.steps,
                ),
                "press": lambda: press(rsd, args.name),
                "type": lambda: type_ascii(rsd, args.text, args.key_delay),
                "paste": lambda: paste(rsd, args.text),
                "tap-text": lambda: press_text(
                    rsd,
                    args.text,
                    index=args.index,
                    limit=args.limit,
                    max_chars=args.max_chars,
                    include_headers=args.include_headers,
                ),
            }
            before = None
            if args.measure_change:
                before, _format = await capture_bytes(rsd)
            result = {"ok": True, **await actions[args.command]()}
            await asyncio.sleep(max(0, args.settle))
            result["after"] = await after_image(config, rsd, args.after)
            if before is not None:
                result["change"] = difference_score(before, Path(result["after"]["image"]).read_bytes())
    result["elapsedMs"] = round((time.monotonic() - started) * 1000)
    return result


def run_sync(awaitable: Awaitable[dict[str, Any]]) -> dict[str, Any]:
    """Finish transport finalizers before closing the Windows event loop."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        result = loop.run_until_complete(awaitable)
        loop.run_until_complete(loop.shutdown_asyncgens())
        gc.collect()
        loop.run_until_complete(asyncio.sleep(0))
        return result
    finally:
        loop.close()
        asyncio.set_event_loop(None)


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        if args.command == "convert-pairing":
            config = load_config(args)
            destination = convert_pairing(
                args.source,
                args.device_udid or config.udid,
                args.output or config.pairing_record,
            )
            emit({"ok": True, "pairingRecord": str(destination.resolve())})
            return 0

        config = load_config(args)
        if args.command == "doctor":
            result = doctor(config, debug=args.debug)
        else:
            result = run_sync(run_connected(args, config))
        emit(result)
        return 0 if result.get("ok") else 1
    except BaseException as exc:
        if args.debug:
            raise
        error = (f"{type(exc).__name__}: doctor failed; use --debug for details"
                 if args.command == "doctor" else f"{type(exc).__name__}: {exc}")
        emit({"ok": False, "error": error})
        return 1


if __name__ == "__main__":
    with suppress(KeyboardInterrupt):
        sys.exit(main())
