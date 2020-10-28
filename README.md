# `websockets-routes`

`websockets` [does not do routing](https://github.com/aaugustin/websockets/issues/311), and I don't like Sanic, so I rolled my own.

Routing backed by [`Routes`](https://routes.readthedocs.io/en/latest/).


## Usage

Decorate your handlers by path, and serve the router.

```python
import asyncio

import websockets
import websockets_routes

router = websockets_routes.Router()

@router.route("/thing/")
async def thing_list(ws, path):
    ...

start_server = websockets.serve(router.handle, ...)

loop = asyncio.get_event_loop()
loop.run_until_complete(start_server)
loop.run_forever()
```

By default, connections are closed immediately with 4040 if the URL does not match any of the registered routes.


### Block connections during handshake

The router has its own `serve()` method that overrides the `process_request()`
hook, making the server return an HTTP 404 during the handshake phase instead:

```python
start_server = router.serve(...)
```

This way, a non-matching client never connects to the websocket handler at all.

The override is implemented via a custom [WebSocket protocol], so you can
subclass that if you need further customisation:

```python
class MyProtocol(websockets_routes.Protocol):
    ...

start_server = websockets.serve(
    router,
    ...,
    create_protocol=MyProtocol,
    ...,
)
```

[WebSocket protocol]: https://websockets.readthedocs.io/en/stable/cheatsheet.html?highlight=protocol#server


### Access route parameters

The handler's second parameter is a `RoutedPath` instead of a plain `str`. This is a `str` subclass, so you can do anything you could as in `websockets`. There is one additional attribute, `params`, that allows you to access the matched route parameters.

```python
@router.route("/thing/{id}")
async def thing_detail(ws, path):
    # Asumming this is accessed with "/thing/123".
    await ws.send(path)  # This sends a text frame "/thing/123".
    await ws.send(path.params["id"])  # Text frame "123".
```


### Per-view handshake hooks

Decorate a class to provide per-view validation and additional processing:

```python
import http

@router.route("/thing/{id}")
class ThingDetail:
    async def process_request(self, path, headers):
        thing_id = path.params["id"]
        thing = get_thing_or_none(thing_id)
        if thing is not None:
            # Pass additional context to handle().
            path.context["thing"] = thing
            return None
        message = f"thing {thing_id!r} not found\n"
        return (http.HTTPStatus.NOT_FOUND, [], message.encode("utf-8"))

    async def handle(self, ws, path):
        """Now this is only called if thing is found.
        """
        thing = path.context["thing"]  # Retrieve the context to use.
```
