import asyncio
import http

import routes


class RoutedPath(str):
    """A string subclass that also holds the parsed params.
    """
    @classmethod
    def create(cls, path, params):
        p = cls(path)
        p.params = params
        return p


class Router:
    def __init__(self):
        self._mapper = routes.Mapper()

    def route(self, path, *, name=None):
        """Decorator to route a coroutine to ``path``.
        """
        def decorator(endpoint):
            if asyncio.iscoroutinefunction(endpoint):
                # We are decorating an "async def" function.
                handle = endpoint
                process = None
            else:
                # We are decorating a class.
                instance = endpoint()
                handle = instance.handle
                process = getattr(instance, "process_request", None)
            self._mapper.connect(
                name, path, __handle=handle, __process=process,
            )
            return endpoint

        return decorator

    async def process_request(self, path, headers):
        """A process_request() hook that returns 404 during handshake.
        """
        params = self._mapper.match(path)
        if params is None:
            return (http.HTTPStatus.NOT_FOUND, [], b"not found\n")
        process = params.get("__process")
        if process is None:
            return None
        response = await process(RoutedPath.create(path, params), headers)
        if response and not isinstance(response[0], http.HTTPStatus):
            # Do users a favor since the websockets throws cryptic exception
            # if the hook implementation uses a plain integer.
            response = (http.HTTPStatus(response[0]), *response[1])
        return response

    async def handle(self, ws, path):
        """Handler coroutine to serve in the server.
        """
        params = self._mapper.match(path)
        if params is None:
            # This should not be reached if we throw 404 during handshake.
            await ws.close(4040)  # Invented to act as 404.
        handle = params.pop("__handle")
        return await handle(ws, RoutedPath.create(path, params))
