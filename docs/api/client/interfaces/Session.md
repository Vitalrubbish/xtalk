[**xtalk-client**](../globals.md)

***

[xtalk-client](../globals.md) / Session

# Interface: Session

Defined in: [core.ts:42](https://github.com/xcc-zach/xtalk/blob/1ab4d6236f175a0f8859ae9c1357c84b771261e6/frontend/src/core.ts#L42)

Public API returned by [createSession](../functions/createSession.md).

## Properties

### muted

> **muted**: `boolean`

Defined in: [core.ts:152](https://github.com/xcc-zach/xtalk/blob/1ab4d6236f175a0f8859ae9c1357c84b771261e6/frontend/src/core.ts#L152)

Whether the microphone capture path is muted.

***

### state

> `readonly` **state**: `object`

Defined in: [core.ts:94](https://github.com/xcc-zach/xtalk/blob/1ab4d6236f175a0f8859ae9c1357c84b771261e6/frontend/src/core.ts#L94)

The latest conversation state snapshot.

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

## Methods

### changeVoice()

> **changeVoice**(`voiceName`): `Promise`&lt;`void`&gt;

Defined in: [core.ts:167](https://github.com/xcc-zach/xtalk/blob/1ab4d6236f175a0f8859ae9c1357c84b771261e6/frontend/src/core.ts#L167)

Requests that the server switch to another voice.

#### Parameters

##### voiceName

`string`

The server-side voice identifier to activate.

#### Returns

`Promise`&lt;`void`&gt;

A promise that resolves after the request has been dispatched.

#### Remarks

The provided voice name must match a voice supported by the connected server.

#### Example

```ts
await session.changeVoice("alloy");
```

***

### close()

> **close**(): `Promise`&lt;`void`&gt;

Defined in: [core.ts:72](https://github.com/xcc-zach/xtalk/blob/1ab4d6236f175a0f8859ae9c1357c84b771261e6/frontend/src/core.ts#L72)

Closes the audio sessions and websocket connection.

#### Returns

`Promise`&lt;`void`&gt;

A promise that resolves after the session is fully shut down.

#### Remarks

After closing, the current session instance should be treated as inactive.

#### Example

```ts
await session.close();
```

***

### onFullAudioChunk()

> **onFullAudioChunk**(`callback`): `void`

Defined in: [core.ts:148](https://github.com/xcc-zach/xtalk/blob/1ab4d6236f175a0f8859ae9c1357c84b771261e6/frontend/src/core.ts#L148)

Subscribes to merged assistant audio chunks after playback assembly.

#### Parameters

##### callback

(`pcmChunkInt16`, `sampleRate`) => `void`

Receives each completed audio chunk and its sample rate.

#### Returns

`void`

Nothing.

#### Remarks

This callback receives the reconstructed full audio chunk emitted by the conversation layer.

#### Example

```ts
session.onFullAudioChunk((chunk, sampleRate) => {
  console.log(chunk.byteLength, sampleRate);
});
```

***

### onInputAudioChunk()

> **onInputAudioChunk**(`callback`): `void`

Defined in: [core.ts:112](https://github.com/xcc-zach/xtalk/blob/1ab4d6236f175a0f8859ae9c1357c84b771261e6/frontend/src/core.ts#L112)

Subscribes to microphone PCM frames before they are sent to the server.

#### Parameters

##### callback

(`pcmChunkInt16`, `sampleRate`) => `void`

Receives each outbound audio chunk and its sample rate.

#### Returns

`void`

Nothing.

#### Remarks

Use this to inspect or duplicate outgoing audio captured from the local input device.

#### Example

```ts
session.onInputAudioChunk((chunk, sampleRate) => {
  console.log(chunk.byteLength, sampleRate);
});
```

***

### onOutputAudioChunk()

> **onOutputAudioChunk**(`callback`): `void`

Defined in: [core.ts:130](https://github.com/xcc-zach/xtalk/blob/1ab4d6236f175a0f8859ae9c1357c84b771261e6/frontend/src/core.ts#L130)

Subscribes to synthesized PCM frames before playback.

#### Parameters

##### callback

(`pcmChunkInt16`, `sampleRate`) => `void`

Receives each inbound audio chunk and its sample rate.

#### Returns

`void`

Nothing.

#### Remarks

Use this to inspect audio returned by the server before it is played locally.

#### Example

```ts
session.onOutputAudioChunk((chunk, sampleRate) => {
  console.log(chunk.byteLength, sampleRate);
});
```

***

### onStateChange()

> **onStateChange**(`callback`): `void`

Defined in: [core.ts:90](https://github.com/xcc-zach/xtalk/blob/1ab4d6236f175a0f8859ae9c1357c84b771261e6/frontend/src/core.ts#L90)

Subscribes to conversation state updates.

#### Parameters

##### callback

(`state`) => `void`

Receives the full session state whenever it changes.

#### Returns

`void`

Nothing.

#### Remarks

The callback is invoked whenever the internal conversation state changes.

#### Example

```ts
session.onStateChange((state) => {
  console.log(state.streamState, state.messages);
});
```

***

### open()

> **open**(): `Promise`&lt;`void`&gt;

Defined in: [core.ts:58](https://github.com/xcc-zach/xtalk/blob/1ab4d6236f175a0f8859ae9c1357c84b771261e6/frontend/src/core.ts#L58)

Opens the websocket connection and prepares audio input/output resources.

#### Returns

`Promise`&lt;`void`&gt;

A promise that resolves once the local audio sessions are ready.

#### Remarks

Call this before reading live state updates, toggling mute, switching voices,
or uploading files through the session.

#### Example

```ts
const session = createSession("ws://localhost:8000/ws");
await session.open();
```

***

### uploadFile()

> **uploadFile**(`file`, `endpoint?`): `Promise`&lt;`void`&gt;

Defined in: [core.ts:184](https://github.com/xcc-zach/xtalk/blob/1ab4d6236f175a0f8859ae9c1357c84b771261e6/frontend/src/core.ts#L184)

Uploads a file for use by the session.

#### Parameters

##### file

`Blob`

The file blob to upload.

##### endpoint?

`string` \| `URL`

The upload endpoint. Defaults to `./api/upload`.

#### Returns

`Promise`&lt;`void`&gt;

A promise that resolves after the upload action has been dispatched.

#### Remarks

This forwards the file and endpoint to the server-side upload action.

#### Example

```ts
const file = new Blob(["hello"], { type: "text/plain" });
await session.uploadFile(file);
```
