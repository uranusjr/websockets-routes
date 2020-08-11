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


@pytest.mark.asyncio
async def test_route(start_server):
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


@pytest.mark.asyncio
async def test_route_not_found(start_server):
    router = websockets_routes.Router()

    @router.route("/")
    async def route_a(ws, path):
        pass

    async with start_server(router.handle) as server:
        async with websockets.connect(f"{server.url}/not-found") as ws:
            with pytest.raises(websockets.ConnectionClosedError) as ctx:
                await ws.recv()
            assert ctx.value.code == 4040


@pytest.mark.asyncio
async def test_handshake_not_found(start_server):
    router = websockets_routes.Router()

    @router.route("/")
    async def route_a(ws, path):
        pass

    async with start_server(
        router.handle, process_request=router.process_request,
    ) as server:
        with pytest.raises(websockets.InvalidStatusCode) as ctx:
            async with websockets.connect(f"{server.url}/not-found"):
                pass
        assert ctx.value.status_code == 404


@pytest.mark.asyncio
async def test_view_process_request(start_server):
    router = websockets_routes.Router()

    @router.route("/test/{id}")
    class Endpoint:
        async def process_request(self, path, headers):
            if path.params["id"] != "error-out":
                return None
            return (406, [], b"rejected by view\n")

        async def handle(self, ws, path):
            await ws.send(path.params["id"])

    async with start_server(
        router.handle, process_request=router.process_request,
    ) as server:
        with pytest.raises(websockets.InvalidStatusCode) as ctx:
            async with websockets.connect(f"{server.url}/test/error-out"):
                pass
        assert ctx.value.status_code == 406

        async with websockets.connect(f"{server.url}/test/this-works") as ws:
            received = await ws.recv()
            assert received == "this-works"
