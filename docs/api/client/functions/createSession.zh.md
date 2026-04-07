[**xtalk-client**](../globals.zh.md)

***

[xtalk-client](../globals.zh.md) / createSession

# 函数: createSession()

> **createSession**(`websocketURL`, `config?`): [`Session`](../interfaces/Session.zh.md)

定义于: [core.ts:221](https://github.com/xcc-zach/xtalk/blob/1ab4d6236f175a0f8859ae9c1357c84b771261e6/frontend/src/core.ts#L221)

创建一个浏览器会话，将音频流式传输到 X-Talk 服务端，并暴露会话生命周期、状态以及音频事件钩子。

## 参数

### websocketURL

`string` \| `URL`

用于连接 X-Talk 服务端的 websocket 端点。

### config?

[`SessionConfig`](../interfaces/SessionConfig.zh.md) = `{}`

用于输入和输出处理的可选音频会话覆盖配置。

## 返回

[`Session`](../interfaces/Session.zh.md)

用于管理连接并订阅客户端事件的会话控制器。

## 备注

`createSession` 会准备客户端侧的连接逻辑，包括 websocket 传输、麦克风采集、音频播放以及会话状态管理。
除非通过 [SessionConfig](../interfaces/SessionConfig.zh.md) 覆盖，否则输入音频默认采样率为 `16000` Hz，输出音频默认采样率为 `48000` Hz。

在与会话交互前，请先调用 [Session.open](../interfaces/Session.zh.md#open)。会话打开后，你可以观察状态变化、查看最新状态快照、切换麦克风静音、切换语音或上传文件。

## 示例

```ts
import { createSession } from "xtalk-client";

const session = createSession("ws://localhost:8000/ws", {
  inputConfig: { sampleRate: 16000 },
  outputConfig: { sampleRate: 48000 },
});

session.onStateChange((state) => {
  console.log(state.streamState, state.messages);
});

await session.open();
```
