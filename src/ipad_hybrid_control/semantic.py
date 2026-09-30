from __future__ import annotations

import asyncio
from contextlib import suppress
from typing import Any


RPC_TIMEOUT = 30.0


def caption_of(focus: Any) -> str:
    return (focus.caption or focus.spoken_description or "").strip()


async def collect_elements(
    rsd: Any,
    *,
    text_filter: str | None = None,
    limit: int = 0,
    max_chars: int = 80,
    passes: int = 2,
) -> dict[str, Any]:
    """Read a stable union of the foreground app's accessibility captions.

    One accessibility walk returns only one focus cycle and the starting point
    can move between calls. Each pass therefore rewinds to Direction.First and
    the results are merged by platform identifier.
    """
    from pymobiledevice3.services.accessibilityaudit import AccessibilityAudit, Direction

    captions: dict[str, str] = {}
    order: list[str] = []
    timed_out = False
    for _attempt in range(max(1, passes)):
        try:
            async with AccessibilityAudit(rsd) as audit:
                with suppress(Exception):
                    await asyncio.wait_for(audit.move_focus(Direction.First), RPC_TIMEOUT)
                async for focus in audit.iter_elements():
                    identifier = focus.platform_identifier
                    if identifier not in captions:
                        captions[identifier] = caption_of(focus)
                        order.append(identifier)
                    if limit and len(order) >= limit:
                        break
        except TimeoutError:
            timed_out = True
        if limit and len(order) >= limit:
            break

    all_items = [(captions[identifier], identifier) for identifier in order]
    visible_items = all_items
    if text_filter:
        needle = text_filter.casefold()
        visible_items = [(caption, identifier) for caption, identifier in all_items if needle in caption.casefold()]
    return {
        "action": "elements",
        "scanned": len(all_items),
        "matched": len(visible_items),
        "passes": max(1, passes),
        "timedOut": timed_out,
        "elements": [
            {"index": index, "caption": caption[:max_chars]}
            for index, (caption, _identifier) in enumerate(visible_items)
        ],
    }


async def press_text(
    rsd: Any,
    text: str,
    *,
    index: int = 0,
    limit: int = 0,
    max_chars: int = 80,
    include_headers: bool = False,
) -> dict[str, Any]:
    """Dispatch AX Activate while the matching element handle is live.

    On the verified iPad this can move focus or scroll an element into view,
    but it does not reliably activate UIKit controls. Callers must inspect the
    result and use coordinate HID when actual activation is required.
    """
    from pymobiledevice3.services.accessibilityaudit import AccessibilityAudit, Direction

    seen = 0
    matched = 0
    scanned = 0
    async with AccessibilityAudit(rsd) as audit:
        with suppress(Exception):
            await asyncio.wait_for(audit.move_focus(Direction.First), RPC_TIMEOUT)
        async for focus in audit.iter_elements():
            caption = caption_of(focus)
            scanned += 1
            if text.casefold() in caption.casefold():
                matched += 1
                is_header = "ヘッダ" in caption.casefold() or "header" in caption.casefold()
                if is_header and not include_headers:
                    continue
                if seen < index:
                    seen += 1
                    continue
                await asyncio.wait_for(audit.perform_press(focus.element.identifier), RPC_TIMEOUT)
                return {
                    "action": "tap-text",
                    "query": text,
                    "caption": caption[:max_chars],
                    "matched": matched,
                    "scanned": scanned,
                    "index": index,
                    "bestEffort": True,
                }
            if limit and scanned >= limit:
                break

    details = f"{matched} match(es) in {scanned} scanned elements"
    if matched and not include_headers:
        details += "; matching headers may require --include-headers"
    if scanned == 0:
        details += "; an application must be in the foreground"
    raise ValueError(f"could not press {text!r}: {details}")
