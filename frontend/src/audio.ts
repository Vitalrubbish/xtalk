import { getPlatform, Platform } from "./utils";
import { IInputAudioSession, IOutputAudioSession } from "./interfaces/audio";
import { WebInputAudioSession, WebOutputAudioSession } from "./platforms/web";
export { createInputAudioSession, createOutputAudioSession };

function createInputAudioSession(sampleRate: number = 16000): IInputAudioSession {
    switch (getPlatform()) {
        case Platform.Web:
            return new WebInputAudioSession(sampleRate);
        default:
            throw new Error("Unknown platform");
    }
}

function createOutputAudioSession(sampleRate: number = 48000): IOutputAudioSession {
    switch (getPlatform()) {
        case Platform.Web:
            return new WebOutputAudioSession(sampleRate);
        default:
            throw new Error("Unknown platform");
    }
}