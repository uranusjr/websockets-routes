import contextlib

import pytest
import websockets

import websockets_routes


def _get_url(server):
    sockname = server.sockets[0].getsockname()
    return f"ws://{sockname[0]}:{sockname[1]}"


@pytest.fixture(scope="session")
def start_server():
    # Monkeypatch to add a property to access the serving URL.
    websockets.WebSocketServer.url = property(_get_url)

    host = "127.0.0.1"  # Don't use localhost because we don't want IPv6.

    @contextlib.asynccontextmanager
    async def manager(handler, **kwargs):
        server = await websockets.serve(handler, host, port=None, **kwargs)
        yield server
        server.close()
        await server.wait_closed()

    return manager


@pytest.fixture(scope="session")
def start_server_connection(start_server):
    @contextlib.asynccontextmanager
    async def manager(handler, **kwargs):
        async with start_server(handler, **kwargs) as server:
            async with websockets.connect(server.url) as ws:
                yield server, ws

    return manager


@pytest.mark.asyncio
async def test_routing(start_server):
    router = websockets_routes.Router()

    @router.route("/a")
    async def route_a(ws, path):
        await ws.send("route a")

    @router.route("/b")
    async def route_b(ws, path):
        await ws.send("route b")

    async with start_server(router.handle) as server:
        async with websockets.connect(f"{server.url}/a") as ws:
            received = await ws.recv()
            assert received == "route a"

        async with websockets.connect(f"{server.url}/b") as ws:
            received = await ws.recv()
            assert received == "route b"
