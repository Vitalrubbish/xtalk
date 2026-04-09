import { BaseInputAudioSession, BaseOutputAudioSession } from "./bases/audio-session";
import type { InputAudioSessionConfig, OutputAudioSessionConfig } from "./bases/audio-session";
import { getPlatformRuntime } from "./platforms/index";
export { createInputAudioSession, createOutputAudioSession };

function createInputAudioSession(config: InputAudioSessionConfig): BaseInputAudioSession {
    return getPlatformRuntime().createInputAudioSession(config);
}

function createOutputAudioSession(config: OutputAudioSessionConfig): BaseOutputAudioSession {
    return getPlatformRuntime().createOutputAudioSession(config);
}
