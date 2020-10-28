from __future__ import annotations

import asyncio
import http
import typing

import routes
import websockets


def _match_route_cls(params):
    if params is None:
        return None
    try:
        route_cls = params.pop("__route_cls")
    except KeyError:
        return None
    return route_cls()


class RoutedPath(str):
    """A string subclass that holds extra routing context.

    * ``route`` is an instance of the matched route class.
    * ``params`` is a mapping that holds the routed parameters.
    * ``context`` is a mapping for the user to pass connection context.
    """

    route: typing.Any
    params: typing.Mapping[str, str]
    context: typing.MutableMapping[typing.Any, typing.Any]

    @classmethod
    def create(cls, raw_path, route, params) -> RoutedPath:
        path = cls(raw_path)
        path.route = route
        path.params = params
        path.context = {}
        return path


class Protocol(websockets.WebSocketServerProtocol):
    """Server protocol to hook in routing.

    This hacks the handshaking phase to inject the matched route instance into
    the ``path`` value, so hooks in the matched route can be called in various
    phases.
    """

    def __init__(self, router, *args, **kwargs):
        super().__init__(router, *args, **kwargs)
        self._router = router

    async def read_http_request(self):
        raw_path, headers = await super().read_http_request()
        return self._router.match(raw_path), headers

    async def process_request(self, path, headers):
        if path.params is None:
            return (http.HTTPStatus.NOT_FOUND, [], b"not found\n")
        process_request = getattr(path.route, "process_request", None)
        if process_request is None:
            return None
        response = await process_request(path, headers)
        if response and not isinstance(response[0], http.HTTPStatus):
            # Do users a favor since the websockets throws cryptic exception
            # if the hook implementation uses a plain integer.
            response = (http.HTTPStatus(response[0]), *response[1:])
        return response


class Router:
    """Routing support for views.

    This instance both provides the routing decorator, and is a callable that
    serves as the server protocol's websocket handler.
    """

    def __init__(self, *args, **kwargs):
        self._mapper = routes.Mapper()

    async def __call__(self, ws, path):
        if not isinstance(path, RoutedPath):
            path = self.match(path)
        if path.params is None:
            await ws.close(4040)
        handle = getattr(path.route, "handle", None)
        await handle(ws, path)

    def route(self, path: str, *, name: typing.Optional[str] = None):
        """Decorator to route a coroutine to ``path``."""

        def decorator(endpoint: typing.Callable[[], typing.Any]):
            if not asyncio.iscoroutinefunction(endpoint):
                # A decorated class can be used directly.
                route_cls = endpoint
            else:
                # Create a stub class to hold the "async def" function.
                handle = staticmethod(endpoint)
                route_cls = type(endpoint.__name__, (), {"handle": handle})
            self._mapper.connect(name, path, __route_cls=route_cls)
            return endpoint

        return decorator

    def match(self, path: str) -> RoutedPath:
        params = self._mapper.match(path)
        route = _match_route_cls(params)
        return RoutedPath.create(path, route, params)

    async def serve(self, *args, **kwargs):
        return await websockets.serve(
            self,
            *args,
            create_protocol=Protocol,
            **kwargs,
        )
