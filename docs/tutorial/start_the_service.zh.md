> **Note**
> 详情请参阅 `examples/sample_app/configurable_server.py`、`examples/sample_app/templates` 和 `examples/sample_app/static`。

X-Talk 的大多数模型与执行逻辑都运行在服务端。客户端主要负责访问麦克风、传输音频、收发 WebSocket 消息，以及处理语音活动检测这类轻量逻辑。

客户端 API 已经发布为独立包 [xtalk-client](https://www.npmjs.com/package/xtalk-client)，其公开接口与 `frontend/src` 中的实现保持一致。

客户端最简接入只需要三步：

1. 使用服务端 WebSocket 地址创建一个 session；
2. 按需监听状态变化；
3. 调用 `session.open()`。

如果您使用打包工具，请先安装：

```bash
npm install xtalk-client
```

> 对开发者来说，客户端代码位于 `frontend` 目录下。在该目录中，您可以运行 `npm run watch` 进行开发构建。

然后在前端代码中导入并使用：

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

如果您不想自行打包客户端代码，也可以直接通过 CDN 加载：

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

服务端最简接入方式是：从配置文件创建一个 `Xtalk` 实例，并将其绑定到 FastAPI 的 WebSocket 路由：

```python
from fastapi import FastAPI, WebSocket
from xtalk import Xtalk

app = FastAPI(title="Xtalk Server")
xtalk_instance = Xtalk.from_config("path/to/config.json")


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await xtalk_instance.connect(websocket)
```

这样就能建立最基本的前后端对话闭环。若需要完整示例，包括静态资源、模板、上传接口和音色切换，可以继续参考 `examples/sample_app/configurable_server.py` 与 `examples/sample_app/static/js/index.js`。
