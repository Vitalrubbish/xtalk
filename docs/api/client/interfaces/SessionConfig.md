[**xtalk-client**](../globals.md)

***

[xtalk-client](../globals.md) / SessionConfig

# Interface: SessionConfig

Defined in: [session/types.ts:72](https://github.com/xcc-zach/xtalk/blob/d18912ac9c64b26c4423d8c46cb97496eb709649/frontend/src/session/types.ts#L72)

Configuration overrides used when creating a session.

## Properties

### inputConfig?

> `optional` **inputConfig?**: `Partial`&lt;`InputAudioSessionConfig`&gt;

Defined in: [session/types.ts:76](https://github.com/xcc-zach/xtalk/blob/d18912ac9c64b26c4423d8c46cb97496eb709649/frontend/src/session/types.ts#L76)

Input audio session overrides such as capture sample rate.

***

### outputConfig?

> `optional` **outputConfig?**: `Partial`&lt;`OutputAudioSessionConfig`&gt;

Defined in: [session/types.ts:80](https://github.com/xcc-zach/xtalk/blob/d18912ac9c64b26c4423d8c46cb97496eb709649/frontend/src/session/types.ts#L80)

Output audio session overrides such as playback sample rate.

***

### serviceURLs?

> `optional` **serviceURLs?**: `Partial`&lt;\{ `login`: `ResolvableURL`; `sessionDetail`: `ResolvableURL` \| ((`sessionId`) => `ResolvableURL`); `sessions`: `ResolvableURL`; `upload`: `ResolvableURL`; \}&gt;

Defined in: [session/types.ts:84](https://github.com/xcc-zach/xtalk/blob/d18912ac9c64b26c4423d8c46cb97496eb709649/frontend/src/session/types.ts#L84)

Optional overrides for auxiliary HTTP service endpoints.
