> **Note**
> See `examples/sample_app/configurable_server.py`, `examples/sample_app/templates` and `examples/sample_app/static` for details.
   
X-Talk keeps most models and execution on the server side. The client is mainly responsible for microphone access, audio streaming, WebSocket messaging, and lightweight logic such as voice activity detection.

The client API is published as [xtalk-client](https://www.npmjs.com/package/xtalk-client), and its public interface follows the implementation in `frontend/src`.

For the client side, the minimal setup is:

1. create a session with the server WebSocket URL,
2. optionally subscribe to state changes, and
3. call `session.open()`.

If you use a bundler, install the package first:

```bash
npm install xtalk-client
```

Then import it in your frontend code:

```ts
import { createSession } from "xtalk-client";

const wsUrl =
    location.protocol === "https:"
        ? `wss://${location.host}/ws`
        : `ws://${location.host}/ws`;

const session = createSession(wsUrl);

session.onStateChange((state) => {
    console.log("state:", state);
});

await session.open();
```

If you do not want to bundle the client package yourself, you can load it directly from a CDN:

```html
<script type="module">
    const { createSession } = await import("https://unpkg.com/xtalk-client@latest/dist/index.js");

    const wsUrl =
        location.protocol === "https:"
            ? `wss://${location.host}/ws`
            : `ws://${location.host}/ws`;

    const session = createSession(wsUrl);
    await session.open();
</script>
```

For the server side, the minimal setup is to create an `Xtalk` instance from a config file and connect it to a FastAPI WebSocket route:

```python
from fastapi import FastAPI, WebSocket
from xtalk import Xtalk

app = FastAPI(title="Xtalk Server")
xtalk_instance = Xtalk.from_config("path/to/config.json")


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await xtalk_instance.connect(websocket)
```

This is enough to establish the basic client-server loop. For a fuller example including static files, templates, upload endpoints, and voice selection, see `examples/sample_app/configurable_server.py` and `examples/sample_app/static/js/index.js`.
