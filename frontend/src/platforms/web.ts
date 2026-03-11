import type { IInputAudioSession, IOutputAudioSession } from "../interfaces/audio";

class WebInputAudioSession implements IInputAudioSession {
    constructor(sampleRate: number = 16000) {

    }
    async start(): Promise<void> {

    }
    async stop(): Promise<void> {

    }

    get muted(): boolean {
        return false
    }
    set muted(value: boolean) {
    }
}