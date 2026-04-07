[**xtalk-client**](../globals.zh.md)

***

[xtalk-client](../globals.zh.md) / SessionConfig

# 接口: SessionConfig

定义于: [core.ts:22](https://github.com/xcc-zach/xtalk/blob/1ab4d6236f175a0f8859ae9c1357c84b771261e6/frontend/src/core.ts#L22)

用于配置会话如何采集麦克风输入并播放合成输出。

## 属性

### inputConfig?

> `optional` **inputConfig?**: `Partial`&lt;`InputAudioSessionConfig`&gt;

定义于: [core.ts:29](https://github.com/xcc-zach/xtalk/blob/1ab4d6236f175a0f8859ae9c1357c84b771261e6/frontend/src/core.ts#L29)

输入音频会话的覆盖配置。

#### 备注

默认输入采样率为 `16000`。

***

### outputConfig?

> `optional` **outputConfig?**: `Partial`&lt;`OutputAudioSessionConfig`&gt;

定义于: [core.ts:36](https://github.com/xcc-zach/xtalk/blob/1ab4d6236f175a0f8859ae9c1357c84b771261e6/frontend/src/core.ts#L36)

输出音频会话的覆盖配置。

#### 备注

默认输出采样率为 `48000`。
