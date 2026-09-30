from __future__ import annotations

import asyncio
import io
from pathlib import Path
from typing import Any

from PIL import Image, ImageChops, ImageStat


RPC_TIMEOUT = 30.0
ORIENTATION_NAMES = {
    "PORTRAIT": "portrait",
    "PORTRAIT_UPSIDE_DOWN": "portraitUpsideDown",
    "LANDSCAPE": "landscapeLeft",
    "LANDSCAPE_HOME_TO_LEFT": "landscapeRight",
}


async def orientation(rsd: Any) -> tuple[int, str]:
    from pymobiledevice3.services.springboard import SpringBoardServicesService

    async with SpringBoardServicesService(rsd) as springboard:
        value = await asyncio.wait_for(springboard.get_interface_orientation(), RPC_TIMEOUT)
    return int(value), ORIENTATION_NAMES[str(getattr(value, "name", value))]


async def capture_bytes(rsd: Any) -> tuple[bytes, str | None]:
    from pymobiledevice3.remote.core_device.screen_capture_service import ScreenCaptureService

    service = ScreenCaptureService(rsd)
    await asyncio.wait_for(service.connect(), RPC_TIMEOUT)
    capture = await asyncio.wait_for(service.capture_screenshot(), RPC_TIMEOUT)
    return bytes(capture["image"]), capture.get("imageFormat")


def image_size(data: bytes) -> tuple[int, int]:
    with Image.open(io.BytesIO(data)) as image:
        return image.size


def difference_score(before: bytes, after: bytes) -> float:
    """Return a small grayscale change score without interpreting the UI."""
    with Image.open(io.BytesIO(before)) as first, Image.open(io.BytesIO(after)) as second:
        left = first.convert("L").resize((96, 64))
        right = second.convert("L").resize((96, 64))
        statistic = ImageStat.Stat(ImageChops.difference(left, right))
    return round(statistic.mean[0] / 255.0, 4)


async def save_capture(
    rsd: Any,
    output: Path,
    *,
    thumbnail: Path | None = None,
    thumbnail_width: int = 768,
) -> dict[str, Any]:
    data, image_format = await capture_bytes(rsd)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(data)
    width, height = image_size(data)
    result: dict[str, Any] = {
        "image": str(output.resolve()),
        "size": [width, height],
        "bytes": len(data),
        "format": image_format,
    }
    if thumbnail is not None:
        thumbnail.parent.mkdir(parents=True, exist_ok=True)
        with Image.open(io.BytesIO(data)) as source:
            preview = source.convert("RGB")
            preview.thumbnail((thumbnail_width, thumbnail_width))
            preview.save(thumbnail, "JPEG", quality=72, optimize=True)
        result["thumbnail"] = str(thumbnail.resolve())
    return result


def hid_point(orientation_name: str, x: int, y: int, width: int, height: int) -> tuple[int, int]:
    if width < 2 or height < 2:
        raise ValueError(f"invalid screenshot dimensions: {width} x {height}")
    max_x, max_y = width - 1, height - 1
    if not (0 <= x <= max_x and 0 <= y <= max_y):
        raise ValueError(f"({x}, {y}) is outside screenshot bounds 0..{max_x} x 0..{max_y}")
    if orientation_name == "portrait":
        rx, ry = x / max_x, y / max_y
    elif orientation_name == "portraitUpsideDown":
        rx, ry = 1 - x / max_x, 1 - y / max_y
    elif orientation_name == "landscapeLeft":
        rx, ry = 1 - y / max_y, x / max_x
    elif orientation_name == "landscapeRight":
        rx, ry = y / max_y, 1 - x / max_x
    else:
        raise ValueError(f"unsupported orientation: {orientation_name}")

    def scale(value: float) -> int:
        return min(65535, max(0, round(value * 65535)))

    return scale(rx), scale(ry)


async def current_geometry(rsd: Any) -> tuple[int, str, int, int]:
    code, name = await orientation(rsd)
    data, _format = await capture_bytes(rsd)
    width, height = image_size(data)
    return code, name, width, height


async def tap(rsd: Any, x: int, y: int) -> dict[str, Any]:
    from pymobiledevice3.remote.core_device.hid_service import (
        TOUCHSCREEN_STATE_CONTACT,
        TOUCHSCREEN_STATE_RELEASE,
        touch_session,
    )

    code, name, width, height = await current_geometry(rsd)
    hid_x, hid_y = hid_point(name, x, y, width, height)
    async with touch_session(rsd) as hid:
        await hid.send_touchscreen(TOUCHSCREEN_STATE_CONTACT, hid_x, hid_y)
        await asyncio.sleep(0.05)
        await hid.send_touchscreen(TOUCHSCREEN_STATE_RELEASE, hid_x, hid_y)
    return {
        "action": "tap",
        "orientation": name,
        "orientationCode": code,
        "pixel": [x, y],
        "screen": [width, height],
        "hid": [hid_x, hid_y],
    }


async def swipe(
    rsd: Any,
    x1: int,
    y1: int,
    x2: int,
    y2: int,
    *,
    duration_ms: int = 300,
    steps: int = 16,
) -> dict[str, Any]:
    from pymobiledevice3.remote.core_device.hid_service import (
        TOUCHSCREEN_STATE_CONTACT,
        TOUCHSCREEN_STATE_RELEASE,
        touch_session,
    )

    if steps < 1:
        raise ValueError("steps must be at least 1")
    code, name, width, height = await current_geometry(rsd)
    start_x, start_y = hid_point(name, x1, y1, width, height)
    end_x, end_y = hid_point(name, x2, y2, width, height)
    delay = max(0.001, duration_ms / 1000 / steps)
    async with touch_session(rsd) as hid:
        await hid.send_touchscreen(TOUCHSCREEN_STATE_CONTACT, start_x, start_y)
        for index in range(1, steps + 1):
            await asyncio.sleep(delay)
            await hid.send_touchscreen(
                TOUCHSCREEN_STATE_CONTACT,
                start_x + (end_x - start_x) * index // steps,
                start_y + (end_y - start_y) * index // steps,
            )
        await asyncio.sleep(0.05)
        await hid.send_touchscreen(TOUCHSCREEN_STATE_RELEASE, end_x, end_y)
    return {
        "action": "swipe",
        "orientation": name,
        "orientationCode": code,
        "pixel": [x1, y1, x2, y2],
        "screen": [width, height],
        "hid": [start_x, start_y, end_x, end_y],
        "durationMs": duration_ms,
        "steps": steps,
    }


async def launch(rsd: Any, bundle_id: str) -> dict[str, Any]:
    from pymobiledevice3.remote.core_device.app_service import AppServiceService

    async with AppServiceService(rsd) as apps:
        result = await asyncio.wait_for(apps.launch_application(bundle_id), RPC_TIMEOUT)
    return {"action": "launch", "bundleId": bundle_id, "result": result}


async def rotate(rsd: Any, direction: str) -> dict[str, Any]:
    """Rotate by 90 degrees.

    A successful rotation can invalidate the current RSD channel on the
    verified device.  Callers therefore return immediately and let the next
    CLI invocation establish a fresh tunnel.
    """
    from pymobiledevice3.remote.core_device.orientation_service import OrientationService

    if direction not in {"left", "right"}:
        raise ValueError("direction must be 'left' or 'right'")
    async with OrientationService(rsd) as service:
        result = await asyncio.wait_for(service.rotate(direction), RPC_TIMEOUT)
    return {
        "action": "rotate",
        "direction": direction,
        "result": result,
        "reconnectRequired": True,
    }


async def press(rsd: Any, name: str) -> dict[str, Any]:
    from pymobiledevice3.remote.core_device.hid_service import (
        HID_BUTTON_STATE_DOWN,
        HID_BUTTON_STATE_UP,
        IndigoHIDService,
        touch_session,
    )
    from pymobiledevice3.remote.core_device.screen_stream import _NAMED_BUTTONS

    if name not in _NAMED_BUTTONS:
        raise ValueError(f"unknown button {name!r}; choose from {', '.join(sorted(_NAMED_BUTTONS))}")
    usage_page, usage_code, hold_seconds = _NAMED_BUTTONS[name]
    async with touch_session(rsd):
        async with IndigoHIDService(rsd) as hid:
            await hid.send_button(usage_page, usage_code, HID_BUTTON_STATE_DOWN)
            await asyncio.sleep(hold_seconds)
            await hid.send_button(usage_page, usage_code, HID_BUTTON_STATE_UP)
    return {"action": "press", "button": name}


async def type_ascii(rsd: Any, text: str, key_delay_ms: int = 0) -> dict[str, Any]:
    from pymobiledevice3.remote.core_device.hid_service import ASCII_TO_HID, KEY_LEFT_SHIFT, touch_session

    unsupported = sorted({character for character in text if character not in ASCII_TO_HID})
    if unsupported:
        raise ValueError(f"unsupported characters: {''.join(unsupported)!r}; use paste for non-ASCII text")
    delay = max(0.0, key_delay_ms / 1000)
    async with touch_session(rsd) as hid:
        service_id = await hid.create_keyboard_service()
        for character in text:
            usage, shift = ASCII_TO_HID[character]
            await hid.send_keyboard(service_id, [usage, KEY_LEFT_SHIFT] if shift else [usage])
            await asyncio.sleep(0.01)
            await hid.send_keyboard(service_id, [])
            await asyncio.sleep(0.01 + delay)
    return {"action": "type", "characters": len(text)}


async def paste(rsd: Any, text: str) -> dict[str, Any]:
    from pymobiledevice3.remote.core_device.hid_service import ASCII_TO_HID, KEY_LEFT_GUI, touch_session
    from pymobiledevice3.remote.core_device.pasteboard_service import PasteboardService

    async with PasteboardService(rsd) as pasteboard:
        await pasteboard.set_text(text)
    async with touch_session(rsd) as hid:
        service_id = await hid.create_keyboard_service()
        paste_usage = ASCII_TO_HID["v"][0]
        await hid.send_keyboard(service_id, [KEY_LEFT_GUI, paste_usage])
        await asyncio.sleep(0.08)
        await hid.send_keyboard(service_id, [])
    return {"action": "paste", "characters": len(text)}
