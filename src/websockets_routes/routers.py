import routes


class RequestedPath(str):
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
        def decorator(f):
            self._mapper.connect(name, path, __handler=f)
            return f

        return decorator

    async def handle(self, ws, path):
        """Handler coroutine to serve in the server.
        """
        params = self._mapper.match(path)
        if params is None:
            # This should not happen because we blocked all unmatched URLs
            # during handshake, so it's a server error if we end up here.
            await ws.close(1008)
        handler = params.pop("__handler")
        return await handler(ws, RequestedPath.create(path, params))
