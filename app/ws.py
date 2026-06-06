"""Tiny WebSocket pub/sub. Used to push live job updates to the UI."""

from __future__ import annotations

import asyncio
import json
from typing import Any, Dict, List, Set

from fastapi import WebSocket


_clients: Set[WebSocket] = set()
_loop: asyncio.AbstractEventLoop | None = None


def set_loop(loop: asyncio.AbstractEventLoop) -> None:
    global _loop
    _loop = loop


async def register(ws: WebSocket) -> None:
    await ws.accept()
    _clients.add(ws)


def unregister(ws: WebSocket) -> None:
    _clients.discard(ws)


def broadcast(msg: Dict[str, Any]) -> None:
    """Fire-and-forget push to every connected client.

    Safe to call from worker threads. If the event loop isn't running yet
    (e.g. broadcast called during startup) the message is dropped.
    """
    if _loop is None or not _clients:
        return
    try:
        data = json.dumps(msg, default=str)
        asyncio.run_coroutine_threadsafe(_send_all(data), _loop)
    except Exception:
        pass


async def _send_all(data: str) -> None:
    dead: List[WebSocket] = []
    for ws in list(_clients):
        try:
            await ws.send_text(data)
        except Exception:
            dead.append(ws)
    for d in dead:
        _clients.discard(d)
