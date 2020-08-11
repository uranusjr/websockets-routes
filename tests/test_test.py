import contextlib

import pytest
import websockets


def _get_url(server):
    sockname = server.sockets[0].getsockname()
    return f"ws://{sockname[0]}:{sockname[1]}"


@pytest.fixture(scope="session")
def start_server():
    # Monkeypatch to add a property to access the serving URL.
    websockets.WebSocketServer.url = property(_get_url)

    host = "127.0.0.1"  # Don't use localhost because we don't want IPv6.

    @contextlib.asynccontextmanager
    async def manager(handler):
        server = await websockets.serve(handler, host, None)
        yield server
        server.close()
        await server.wait_closed()

    return manager


@pytest.mark.asyncio
async def test_server(start_server):
    sent = None

    async def handler(ws, path):
        nonlocal sent
        sent = await ws.recv()
        await ws.send("OK!")

    async with start_server(handler) as server:
        async with websockets.connect(server.url) as ws:
            await ws.send("Go")
            received = await ws.recv()

    assert sent == "Go"
    assert received == "OK!"
