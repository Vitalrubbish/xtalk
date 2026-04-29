[**xtalk-client**](../globals.md)

***

[xtalk-client](../globals.md) / Session

# Interface: Session

Defined in: [session/types.ts:90](https://github.com/xcc-zach/xtalk/blob/d18912ac9c64b26c4423d8c46cb97496eb709649/frontend/src/session/types.ts#L90)

Public session controller exposed by the frontend entrypoint.

## Properties

### muted

> **muted**: `boolean`

Defined in: [session/types.ts:130](https://github.com/xcc-zach/xtalk/blob/d18912ac9c64b26c4423d8c46cb97496eb709649/frontend/src/session/types.ts#L130)

Whether microphone capture is currently muted.

***

### state

> `readonly` **state**: `object`

Defined in: [session/types.ts:108](https://github.com/xcc-zach/xtalk/blob/d18912ac9c64b26c4423d8c46cb97496eb709649/frontend/src/session/types.ts#L108)

Current conversation state snapshot.

#### caption

> **caption**: `string`

#### connectionState

> **connectionState**: `"connected"` \| `"reconnecting"` \| `"disconnected"`

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

> **messages**: `ConversationMessage`[]

#### retrieval

> **retrieval**: `string`

#### sessionId

> **sessionId**: `string` \| `null`

#### streamState

> **streamState**: `"idle"` \| `"listening"` \| `"processing"` \| `"speaking"`

#### thought

> **thought**: `string`

#### user

> **user**: `ConversationUser` \| `null`

## Methods

### changeVoice()

> **changeVoice**(`voiceName`): `Promise`&lt;`void`&gt;

Defined in: [session/types.ts:136](https://github.com/xcc-zach/xtalk/blob/d18912ac9c64b26c4423d8c46cb97496eb709649/frontend/src/session/types.ts#L136)

Requests a voice change for subsequent assistant synthesis.

#### Parameters

##### voiceName

`string`

Target voice identifier.

#### Returns

`Promise`&lt;`void`&gt;

***

### close()

> **close**(): `Promise`&lt;`void`&gt;

Defined in: [session/types.ts:98](https://github.com/xcc-zach/xtalk/blob/d18912ac9c64b26c4423d8c46cb97496eb709649/frontend/src/session/types.ts#L98)

Closes the active runtime connection and audio resources.

#### Returns

`Promise`&lt;`void`&gt;

***

### getSessions()

> **getSessions**(): `Promise`&lt;`SessionSummary`[]&gt;

Defined in: [session/types.ts:147](https://github.com/xcc-zach/xtalk/blob/d18912ac9c64b26c4423d8c46cb97496eb709649/frontend/src/session/types.ts#L147)

Fetches available persisted sessions for the current user.

#### Returns

`Promise`&lt;`SessionSummary`[]&gt;

***

### onFullAudioChunk()

> **onFullAudioChunk**(`callback`): `void`

Defined in: [session/types.ts:126](https://github.com/xcc-zach/xtalk/blob/d18912ac9c64b26c4423d8c46cb97496eb709649/frontend/src/session/types.ts#L126)

Registers a callback for merged full-duplex PCM chunks.

#### Parameters

##### callback

`AudioChunkCallback`

Full audio listener.

#### Returns

`void`

***

### onInputAudioChunk()

> **onInputAudioChunk**(`callback`): `void`

Defined in: [session/types.ts:114](https://github.com/xcc-zach/xtalk/blob/d18912ac9c64b26c4423d8c46cb97496eb709649/frontend/src/session/types.ts#L114)

Registers a callback for microphone input PCM chunks.

#### Parameters

##### callback

`AudioChunkCallback`

Input audio listener.

#### Returns

`void`

***

### onOutputAudioChunk()

> **onOutputAudioChunk**(`callback`): `void`

Defined in: [session/types.ts:120](https://github.com/xcc-zach/xtalk/blob/d18912ac9c64b26c4423d8c46cb97496eb709649/frontend/src/session/types.ts#L120)

Registers a callback for speaker output PCM chunks.

#### Parameters

##### callback

`AudioChunkCallback`

Output audio listener.

#### Returns

`void`

***

### onStateChange()

> **onStateChange**(`callback`): `void`

Defined in: [session/types.ts:104](https://github.com/xcc-zach/xtalk/blob/d18912ac9c64b26c4423d8c46cb97496eb709649/frontend/src/session/types.ts#L104)

Registers a callback that runs whenever the conversation state changes.

#### Parameters

##### callback

(`state`) => `void`

State change listener.

#### Returns

`void`

***

### open()

> **open**(): `Promise`&lt;`void`&gt;

Defined in: [session/types.ts:94](https://github.com/xcc-zach/xtalk/blob/d18912ac9c64b26c4423d8c46cb97496eb709649/frontend/src/session/types.ts#L94)

Opens the session runtime and performs authentication if needed.

#### Returns

`Promise`&lt;`void`&gt;

***

### switchSession()

> **switchSession**(`sessionId`): `Promise`&lt;`void`&gt;

Defined in: [session/types.ts:153](https://github.com/xcc-zach/xtalk/blob/d18912ac9c64b26c4423d8c46cb97496eb709649/frontend/src/session/types.ts#L153)

Switches the active conversation to a persisted session or starts a new one.

#### Parameters

##### sessionId

`string` \| `null`

Target session identifier, or `null` to start a new session.

#### Returns

`Promise`&lt;`void`&gt;

***

### uploadFile()

> **uploadFile**(`file`, `endpoint?`): `Promise`&lt;`void`&gt;

Defined in: [session/types.ts:143](https://github.com/xcc-zach/xtalk/blob/d18912ac9c64b26c4423d8c46cb97496eb709649/frontend/src/session/types.ts#L143)

Uploads a file into the current session context.

#### Parameters

##### file

`Blob`

File blob to upload.

##### endpoint?

`string` \| `URL`

Optional upload endpoint override.

#### Returns

`Promise`&lt;`void`&gt;
