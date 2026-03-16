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
    let conversation: Conversation;
    let websocket: ReturnType<typeof createWebSocket>;
    let inputAudioSession: ReturnType<typeof createInputAudioSession>;
    let outputAudioSession: ReturnType<typeof createOutputAudioSession>;

    function initialize() {
        conversation = new Conversation();
        websocket = createWebSocket(websocketURL);
        inputAudioSession = createInputAudioSession(inputSampleRate);
        outputAudioSession = createOutputAudioSession(outputSampleRate);
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
        outputAudioSession.onChunkStarted(() => {
            actionHandler.handleAction("client_audio_chunk_started", null, websocket, conversation, outputAudioSession);
        });
        outputAudioSession.onChunkPlayed(() => {
            actionHandler.handleAction("client_audio_chunk_played", null, websocket, conversation, outputAudioSession);
        });
        outputAudioSession.onAllChunksPlayed(() => {
            actionHandler.handleAction("client_audio_playback_finished", null, websocket, conversation, outputAudioSession);
        });
    }


    // Create API for external use
    const session = {
        open: async () => {
            initialize();
            await inputAudioSession.open();
            await outputAudioSession.open();
        },
        close: async () => {
            await inputAudioSession.close();
            await outputAudioSession.close();
            websocket.close();
        },
        onStateChange: (callback: (state: Conversation["state"]) => void) => {
            conversation.onStateChange(callback);
        },
        get muted() {
            return inputAudioSession.muted;
        },
        set muted(value: boolean) {
            inputAudioSession.muted = value;
        }
    }

    return session;
}