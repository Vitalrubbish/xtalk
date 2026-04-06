[**xtalk-client**](../globals.md)

***

[xtalk-client](../globals.md) / createSession

# Function: createSession()

> **createSession**(`websocketURL`, `config?`): [`Session`](../interfaces/Session.md)

Defined in: [core.ts:221](https://github.com/xcc-zach/xtalk/blob/b1e0a878b5a746db0f30624d4b54208177abedd7/frontend/src/core.ts#L221)

Creates a browser session that streams audio to an X-Talk server and exposes
session lifecycle, state, and audio event hooks.

## Parameters

### websocketURL

`string` \| `URL`

The websocket endpoint used to connect to the X-Talk server.

### config?

[`SessionConfig`](../interfaces/SessionConfig.md) = `{}`

Optional audio session overrides for input and output handling.

## Returns

[`Session`](../interfaces/Session.md)

A session controller for managing the connection and subscribing to client events.

## Remarks

`createSession` prepares the client-side wiring between websocket transport,
microphone capture, audio playback, and conversation state management.
Input audio defaults to `16000` Hz and output audio defaults to `48000` Hz
unless overridden through [SessionConfig](../interfaces/SessionConfig.md).

Call [Session.open](../interfaces/Session.md#open) before interacting with the session. Once opened,
you can observe state changes, inspect the latest state snapshot, toggle
microphone muting, switch voices, or upload files.

## Example

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
