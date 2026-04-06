[**xtalk-client**](../globals.md)

***

[xtalk-client](../globals.md) / SessionConfig

# Interface: SessionConfig

Defined in: [core.ts:22](https://github.com/xcc-zach/xtalk/blob/b1e0a878b5a746db0f30624d4b54208177abedd7/frontend/src/core.ts#L22)

Configures how a session captures microphone input and plays synthesized output.

## Properties

### inputConfig?

> `optional` **inputConfig?**: `Partial`\<`InputAudioSessionConfig`\>

Defined in: [core.ts:29](https://github.com/xcc-zach/xtalk/blob/b1e0a878b5a746db0f30624d4b54208177abedd7/frontend/src/core.ts#L29)

Overrides for the input audio session.

#### Remarks

The default input sample rate is `16000`.

***

### outputConfig?

> `optional` **outputConfig?**: `Partial`\<`OutputAudioSessionConfig`\>

Defined in: [core.ts:36](https://github.com/xcc-zach/xtalk/blob/b1e0a878b5a746db0f30624d4b54208177abedd7/frontend/src/core.ts#L36)

Overrides for the output audio session.

#### Remarks

The default output sample rate is `48000`.
