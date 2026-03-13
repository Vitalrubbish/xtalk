import { createWebSocket } from "./websocket";
import { createInputAudioSession, createOutputAudioSession } from "./audio-session";
import { Conversation } from "./conversation";
import { ActionHandler } from "./action-handler";

export { createSession };

interface SessionConfig {
    inputSampleRate: number;
    outputSampleRate: number;
}
function createSession(websocketURL: string | URL, {
    inputSampleRate = 16000,
    outputSampleRate = 48000,
}: Partial<SessionConfig> = {
    }) {
    const websocket = createWebSocket(websocketURL);
    const conversation = new Conversation();
    const inputAudioSession = createInputAudioSession(inputSampleRate);
    const outputAudioSession = createOutputAudioSession(outputSampleRate);
    const actionHandler = new ActionHandler();

    // Subscribe actions and audio chunks
    websocket.addEventListener("message", (event: { data: string | ArrayBuffer }) => {
        if (typeof event.data === "string") {
            const message: { action: string, data: any } = JSON.parse(event.data);
            actionHandler.handleAction(message.action, message.data, websocket, conversation, outputAudioSession);

        } else if (event.data instanceof ArrayBuffer) {
            outputAudioSession.pushAudioChunk(event.data);
        }
    });

    // Bind audio input handling
    inputAudioSession.onFrame((audioChunk) => {
        websocket.sendAudioChunk(audioChunk);
    });
    inputAudioSession.onSpeechStart(() => {
        actionHandler.handleAction("client_speech_start", null, websocket, conversation, outputAudioSession);
    });
    inputAudioSession.onSpeechEnd(() => {
        actionHandler.handleAction("client_speech_end", null, websocket, conversation, outputAudioSession);
    });

    // Bind audio output handling
    outputAudioSession.onChunkPlayed(() => {
        actionHandler.handleAction("client_audio_chunk_played", null, websocket, conversation, outputAudioSession);
    })
    outputAudioSession.onAllChunksPlayed(() => {
        actionHandler.handleAction("client_audio_playback_finished", null, websocket, conversation, outputAudioSession);

    })

    const session = {
        open: async () => {
            await inputAudioSession.open();
            await outputAudioSession.open();
        }
    }
}