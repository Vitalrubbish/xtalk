[**xtalk-client**](../globals.zh.md)

***

[xtalk-client](../globals.zh.md) / Session

# 接口: Session

定义于: [core.ts:42](https://github.com/xcc-zach/xtalk/blob/1ab4d6236f175a0f8859ae9c1357c84b771261e6/frontend/src/core.ts#L42)

由 [createSession](../functions/createSession.zh.md) 返回的公开 API。

## 属性

### muted

> **muted**: `boolean`

定义于: [core.ts:152](https://github.com/xcc-zach/xtalk/blob/1ab4d6236f175a0f8859ae9c1357c84b771261e6/frontend/src/core.ts#L152)

麦克风采集链路当前是否静音。

***

### state

> `readonly` **state**: `object`

定义于: [core.ts:94](https://github.com/xcc-zach/xtalk/blob/1ab4d6236f175a0f8859ae9c1357c84b771261e6/frontend/src/core.ts#L94)

最新的会话状态快照。

#### caption

> **caption**: `string`

#### latency

> **latency**: `object`

##### latency.asr?

> `optional` **asr?**: `number`

##### latency.llmFirstToken?

> `optional` **llmFirstToken?**: `number`

##### latency.llmSentence?

> `optional` **llmSentence?**: `number`

##### latency.network?

> `optional` **network?**: `number`

##### latency.ttsFirstChunk?

> `optional` **ttsFirstChunk?**: `number`

#### messages

> **messages**: `Message`[]

#### retrieval

> **retrieval**: `string`

#### sessionId

> **sessionId**: `string` \| `null`

#### streamState

> **streamState**: `"idle"` \| `"listening"` \| `"processing"` \| `"speaking"`

#### thought

> **thought**: `string`

## 方法

### changeVoice()

> **changeVoice**(`voiceName`): `Promise`&lt;`void`&gt;

定义于: [core.ts:167](https://github.com/xcc-zach/xtalk/blob/1ab4d6236f175a0f8859ae9c1357c84b771261e6/frontend/src/core.ts#L167)

请求服务端切换到另一种语音。

#### 参数

##### voiceName

`string`

要激活的服务端语音标识符。

#### 返回

`Promise`&lt;`void`&gt;

请求发出后解析的 Promise。

#### 备注

提供的语音名称必须与当前连接服务端支持的语音一致。

#### 示例

```ts
await session.changeVoice("alloy");
```

***

### close()

> **close**(): `Promise`&lt;`void`&gt;

定义于: [core.ts:72](https://github.com/xcc-zach/xtalk/blob/1ab4d6236f175a0f8859ae9c1357c84b771261e6/frontend/src/core.ts#L72)

关闭音频会话和 websocket 连接。

#### 返回

`Promise`&lt;`void`&gt;

会话完全关闭后解析的 Promise。

#### 备注

关闭后，当前会话实例应视为不再可用。

#### 示例

```ts
await session.close();
```

***

### onFullAudioChunk()

> **onFullAudioChunk**(`callback`): `void`

定义于: [core.ts:148](https://github.com/xcc-zach/xtalk/blob/1ab4d6236f175a0f8859ae9c1357c84b771261e6/frontend/src/core.ts#L148)

订阅播放拼装完成后的合并助手音频块。

#### 参数

##### callback

(`pcmChunkInt16`, `sampleRate`) => `void`

接收每个完整音频块及其采样率。

#### 返回

`void`

无返回值。

#### 备注

该回调会收到由会话层输出的重建后的完整音频块。

#### 示例

```ts
session.onFullAudioChunk((chunk, sampleRate) => {
  console.log(chunk.byteLength, sampleRate);
});
```

***

### onInputAudioChunk()

> **onInputAudioChunk**(`callback`): `void`

定义于: [core.ts:112](https://github.com/xcc-zach/xtalk/blob/1ab4d6236f175a0f8859ae9c1357c84b771261e6/frontend/src/core.ts#L112)

订阅发送到服务端之前的麦克风 PCM 帧。

#### 参数

##### callback

(`pcmChunkInt16`, `sampleRate`) => `void`

接收每个外发音频块及其采样率。

#### 返回

`void`

无返回值。

#### 备注

可用于检查或复制从本地输入设备采集的外发音频。

#### 示例

```ts
session.onInputAudioChunk((chunk, sampleRate) => {
  console.log(chunk.byteLength, sampleRate);
});
```

***

### onOutputAudioChunk()

> **onOutputAudioChunk**(`callback`): `void`

定义于: [core.ts:130](https://github.com/xcc-zach/xtalk/blob/1ab4d6236f175a0f8859ae9c1357c84b771261e6/frontend/src/core.ts#L130)

订阅播放前的合成 PCM 帧。

#### 参数

##### callback

(`pcmChunkInt16`, `sampleRate`) => `void`

接收每个入站音频块及其采样率。

#### 返回

`void`

无返回值。

#### 备注

可用于在本地播放前检查服务端返回的音频。

#### 示例

```ts
session.onOutputAudioChunk((chunk, sampleRate) => {
  console.log(chunk.byteLength, sampleRate);
});
```

***

### onStateChange()

> **onStateChange**(`callback`): `void`

定义于: [core.ts:90](https://github.com/xcc-zach/xtalk/blob/1ab4d6236f175a0f8859ae9c1357c84b771261e6/frontend/src/core.ts#L90)

订阅会话状态更新。

#### 参数

##### callback

(`state`) => `void`

每当状态变化时接收完整的会话状态。

#### 返回

`void`

无返回值。

#### 备注

每当内部会话状态发生变化时，都会调用该回调。

#### 示例

```ts
session.onStateChange((state) => {
  console.log(state.streamState, state.messages);
});
```

***

### open()

> **open**(): `Promise`&lt;`void`&gt;

定义于: [core.ts:58](https://github.com/xcc-zach/xtalk/blob/1ab4d6236f175a0f8859ae9c1357c84b771261e6/frontend/src/core.ts#L58)

打开 websocket 连接，并准备音频输入/输出资源。

#### 返回

`Promise`&lt;`void`&gt;

本地音频会话准备完成后解析的 Promise。

#### 备注

在读取实时状态更新、切换静音、切换语音或通过会话上传文件之前，应先调用此方法。

#### 示例

```ts
const session = createSession("ws://localhost:8000/ws");
await session.open();
```

***

### uploadFile()

> **uploadFile**(`file`, `endpoint?`): `Promise`&lt;`void`&gt;

定义于: [core.ts:184](https://github.com/xcc-zach/xtalk/blob/1ab4d6236f175a0f8859ae9c1357c84b771261e6/frontend/src/core.ts#L184)

上传供会话使用的文件。

#### 参数

##### file

`Blob`

要上传的文件 Blob。

##### endpoint?

`string` \| `URL`

上传端点，默认为 `./api/upload`。

#### 返回

`Promise`&lt;`void`&gt;

上传动作发出后解析的 Promise。

#### 备注

该方法会将文件和端点转发给服务端上传逻辑。

#### 示例

```ts
const file = new Blob(["hello"], { type: "text/plain" });
await session.uploadFile(file);
```
