import { getPlatform, Platform } from "./utils";
import { BaseInputAudioSession, BaseOutputAudioSession } from "./bases/audio-session";
import type { InputAudioSessionConfig, OutputAudioSessionConfig } from "./bases/audio-session";
import { WebInputAudioSession, WebOutputAudioSession } from "./platforms/web";
export { createInputAudioSession, createOutputAudioSession };

function createInputAudioSession(config: InputAudioSessionConfig): BaseInputAudioSession {
    switch (getPlatform()) {
        case Platform.Web:
            return new WebInputAudioSession(config);
        default:
            throw new Error("Unknown platform");
    }
}

function createOutputAudioSession(config: OutputAudioSessionConfig): BaseOutputAudioSession {
    switch (getPlatform()) {
        case Platform.Web:
            return new WebOutputAudioSession(config);
        default:
            throw new Error("Unknown platform");
    }
}