import { getPlatform, Platform } from "./utils";
import { BaseInputAudioSession, BaseOutputAudioSession } from "./bases/audio-session";
import { WebInputAudioSession, WebOutputAudioSession } from "./platforms/web";
export { createInputAudioSession, createOutputAudioSession };

function createInputAudioSession(sampleRate: number = 16000): BaseInputAudioSession {
    switch (getPlatform()) {
        case Platform.Web:
            return new WebInputAudioSession(sampleRate);
        default:
            throw new Error("Unknown platform");
    }
}

function createOutputAudioSession(sampleRate: number = 48000): BaseOutputAudioSession {
    switch (getPlatform()) {
        case Platform.Web:
            return new WebOutputAudioSession(sampleRate);
        default:
            throw new Error("Unknown platform");
    }
}