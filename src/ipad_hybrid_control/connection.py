from __future__ import annotations

import asyncio
from contextlib import AsyncExitStack, asynccontextmanager, suppress
from types import SimpleNamespace
from typing import Any, AsyncIterator

from .config import DeviceConfig
from .pairing import stage_pairing_record


CONNECT_TIMEOUT = 30.0


@asynccontextmanager
async def open_rsd(config: DeviceConfig) -> AsyncIterator[Any]:
    from pymobiledevice3.remote import tunnel_service, userspace_tunnel
    from pymobiledevice3.remote.remote_service_discovery import RemoteServiceDiscoveryService
    from pymobiledevice3.remote.tunnel_service import RemotePairingTunnelService
    from pymobiledevice3.remote.userspace_tunnel import UserspaceDialPlane

    tunnel_service.USE_USERSPACE_TUNNEL = True
    pairing = RemotePairingTunnelService(config.udid, config.host, config.port)
    stage_pairing_record(config.pairing_record, pairing.pair_record_path, config.udid)
    stack = AsyncExitStack()
    previous = None
    try:
        await asyncio.wait_for(pairing.connect(autopair=False), CONNECT_TIMEOUT)
        stack.push_async_callback(pairing.close)
        tunnel = await stack.enter_async_context(pairing.start_tcp_tunnel())
        tunnel.client.tun.set_peer(tunnel.address)
        dial = await stack.enter_async_context(UserspaceDialPlane(tunnel.client.tun, tunnel.address))
        rsd = RemoteServiceDiscoveryService(
            (tunnel.address, tunnel.port),
            open_connection=dial.dial,
            auxiliary_metadata=tunnel.auxiliary_metadata,
        )
        stack.push_async_callback(rsd.close)
        await asyncio.wait_for(rsd.connect(), CONNECT_TIMEOUT)

        # Route the device-originated RTP used by HID authentication back through the same userspace tunnel.
        previous = userspace_tunnel._active_tunnel
        userspace_tunnel._active_tunnel = SimpleNamespace(tun=tunnel.client.tun)
        userspace_tunnel.USERSPACE_ACTIVE = True
        yield rsd
    finally:
        userspace_tunnel = None
        with suppress(Exception):
            from pymobiledevice3.remote import userspace_tunnel as userspace_module

            userspace_module._active_tunnel = previous
            userspace_module.USERSPACE_ACTIVE = previous is not None
        with suppress(Exception):
            await stack.aclose()
        tunnel_service.USE_USERSPACE_TUNNEL = False
