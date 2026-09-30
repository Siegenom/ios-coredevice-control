from __future__ import annotations

import asyncio
import hashlib
import plistlib
from typing import Any, Callable


async def mount_ddi(rsd: Any, progress: Callable[[str], None] | None = None) -> str:
    from pymobiledevice3.exceptions import MissingManifestError
    from pymobiledevice3.services.mobile_image_mounter import (
        PersonalizedImageMounter,
        fetch_personalized_ddi,
        request_personalization_manifest,
    )

    report = progress or (lambda _stage: None)
    mounter = PersonalizedImageMounter(rsd)
    report("check-mounted")
    if await asyncio.wait_for(mounter.is_image_mounted("Personalized"), 30):
        return "already-mounted"

    report("fetch-ddi")
    image, build_manifest, trustcache = fetch_personalized_ddi()
    await asyncio.wait_for(mounter.raise_if_cannot_mount(), 30)
    image_bytes = image.read_bytes()
    try:
        report("query-cached-ticket")
        manifest = await asyncio.wait_for(
            mounter.query_personalization_manifest("DeveloperDiskImage", hashlib.sha384(image_bytes).digest()),
            30,
        )
    except MissingManifestError:
        report("request-ticket")
        mounter._service = await asyncio.wait_for(rsd.start_lockdown_service(mounter.service_name), 30)
        identifiers = await asyncio.wait_for(mounter.query_personalization_identifiers(), 30)
        nonce = await asyncio.wait_for(mounter.query_nonce("DeveloperDiskImage"), 30)
        manifest = await asyncio.wait_for(
            request_personalization_manifest(
                plistlib.loads(build_manifest.read_bytes()), identifiers, rsd.ecid, nonce
            ),
            60,
        )

    report("upload-image")
    await asyncio.wait_for(mounter.upload_image("Personalized", image_bytes, manifest), 240)
    report("mount-image")
    await asyncio.wait_for(
        mounter.mount_image("Personalized", manifest, extras={"ImageTrustCache": trustcache.read_bytes()}),
        60,
    )
    return "mounted"
