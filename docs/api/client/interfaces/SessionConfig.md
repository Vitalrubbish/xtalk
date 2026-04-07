[**xtalk-client**](../globals.md)

***

[xtalk-client](../globals.md) / SessionConfig

# Interface: SessionConfig

Defined in: [core.ts:22](https://github.com/xcc-zach/xtalk/blob/1ab4d6236f175a0f8859ae9c1357c84b771261e6/frontend/src/core.ts#L22)

Configures how a session captures microphone input and plays synthesized output.

## Properties

### inputConfig?

> `optional` **inputConfig?**: `Partial`&lt;`InputAudioSessionConfig`&gt;

Defined in: [core.ts:29](https://github.com/xcc-zach/xtalk/blob/1ab4d6236f175a0f8859ae9c1357c84b771261e6/frontend/src/core.ts#L29)

Overrides for the input audio session.

#### Remarks

The default input sample rate is `16000`.

***

### outputConfig?

> `optional` **outputConfig?**: `Partial`&lt;`OutputAudioSessionConfig`&gt;

Defined in: [core.ts:36](https://github.com/xcc-zach/xtalk/blob/1ab4d6236f175a0f8859ae9c1357c84b771261e6/frontend/src/core.ts#L36)

Overrides for the output audio session.

#### Remarks

The default output sample rate is `48000`.
