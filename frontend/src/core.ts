import { createWebSocket } from "./websocket";
import type { InputAudioSessionConfig, OutputAudioSessionConfig } from "./bases/audio-session";
import { createInputAudioSession, createOutputAudioSession } from "./audio-session";
import { Conversation } from "./conversation";
import { ActionHandler } from "./action-handler";

export { createSession };

/**
 * Runtime state exposed by an active X-Talk client session.
 */
type SessionState = Conversation["state"];

/**
 * Receives a PCM audio chunk and the sample rate used for that chunk.
 */
type AudioChunkCallback = (pcmChunkInt16: ArrayBuffer, sampleRate: number) => void;

/**
 * Configures how a session captures microphone input and plays synthesized output.
 */
export interface SessionConfig {
    /**
     * Overrides for the input audio session.
     *
     * @remarks
     * The default input sample rate is `16000`.
     */
    inputConfig?: Partial<InputAudioSessionConfig>,
    /**
     * Overrides for the output audio session.
     *
     * @remarks
     * The default output sample rate is `48000`.
     */
    outputConfig?: Partial<OutputAudioSessionConfig>
}

/**
 * Public API returned by {@link createSession}.
 */
export interface Session {
    /**
     * Opens the websocket connection and prepares audio input/output resources.
     *
     * @remarks
     * Call this before reading live state updates, toggling mute, switching voices,
     * or uploading files through the session.
     *
     * @returns A promise that resolves once the local audio sessions are ready.
     *
     * @example
     * ```ts
     * const session = createSession("ws://localhost:8000/ws");
     * await session.open();
     * ```
     */
    open(): Promise<void>;
    /**
     * Closes the audio sessions and websocket connection.
     *
     * @remarks
     * After closing, the current session instance should be treated as inactive.
     *
     * @returns A promise that resolves after the session is fully shut down.
     *
     * @example
     * ```ts
     * await session.close();
     * ```
     */
    close(): Promise<void>;
    /**
     * Subscribes to conversation state updates.
     *
     * @remarks
     * The callback is invoked whenever the internal conversation state changes.
     *
     * @param callback - Receives the full session state whenever it changes.
     *
     * @returns Nothing.
     *
     * @example
     * ```ts
     * session.onStateChange((state) => {
     *   console.log(state.streamState, state.messages);
     * });
     * ```
     */
    onStateChange(callback: (state: Conversation["state"]) => void): void;
    /**
     * The latest conversation state snapshot.
     */
    readonly state: Conversation["state"];
    /**
     * Subscribes to microphone PCM frames before they are sent to the server.
     *
     * @remarks
     * Use this to inspect or duplicate outgoing audio captured from the local input device.
     *
     * @param callback - Receives each outbound audio chunk and its sample rate.
     *
     * @returns Nothing.
     *
     * @example
     * ```ts
     * session.onInputAudioChunk((chunk, sampleRate) => {
     *   console.log(chunk.byteLength, sampleRate);
     * });
     * ```
     */
    onInputAudioChunk(callback: (pcmChunkInt16: ArrayBuffer, sampleRate: number) => void): void;
    /**
     * Subscribes to synthesized PCM frames before playback.
     *
     * @remarks
     * Use this to inspect audio returned by the server before it is played locally.
     *
     * @param callback - Receives each inbound audio chunk and its sample rate.
     *
     * @returns Nothing.
     *
     * @example
     * ```ts
     * session.onOutputAudioChunk((chunk, sampleRate) => {
     *   console.log(chunk.byteLength, sampleRate);
     * });
     * ```
     */
    onOutputAudioChunk(callback: (pcmChunkInt16: ArrayBuffer, sampleRate: number) => void): void;
    /**
     * Subscribes to merged assistant audio chunks after playback assembly.
     *
     * @remarks
     * This callback receives the reconstructed full audio chunk emitted by the conversation layer.
     *
     * @param callback - Receives each completed audio chunk and its sample rate.
     *
     * @returns Nothing.
     *
     * @example
     * ```ts
     * session.onFullAudioChunk((chunk, sampleRate) => {
     *   console.log(chunk.byteLength, sampleRate);
     * });
     * ```
     */
    onFullAudioChunk(callback: (pcmChunkInt16: ArrayBuffer, sampleRate: number) => void): void;
    /**
     * Whether the microphone capture path is muted.
     */
    muted: boolean;
    /**
     * Requests that the server switch to another voice.
     *
     * @remarks
     * The provided voice name must match a voice supported by the connected server.
     *
     * @param voiceName - The server-side voice identifier to activate.
     * @returns A promise that resolves after the request has been dispatched.
     *
     * @example
     * ```ts
     * await session.changeVoice("alloy");
     * ```
     */
    changeVoice(voiceName: string): Promise<void>;
    /**
     * Uploads a file for use by the session.
     *
     * @remarks
     * This forwards the file and endpoint to the server-side upload action.
     *
     * @param file - The file blob to upload.
     * @param endpoint - The upload endpoint. Defaults to `./api/upload`.
     * @returns A promise that resolves after the upload action has been dispatched.
     *
     * @example
     * ```ts
     * const file = new Blob(["hello"], { type: "text/plain" });
     * await session.uploadFile(file);
     * ```
     */
    uploadFile(file: Blob, endpoint?: string | URL): Promise<void>;
}

/**
 * Creates a browser session that streams audio to an X-Talk server and exposes
 * session lifecycle, state, and audio event hooks.
 *
 * @remarks
 * `createSession` prepares the client-side wiring between websocket transport,
 * microphone capture, audio playback, and conversation state management.
 * Input audio defaults to `16000` Hz and output audio defaults to `48000` Hz
 * unless overridden through {@link SessionConfig}.
 *
 * Call {@link Session.open} before interacting with the session. Once opened,
 * you can observe state changes, inspect the latest state snapshot, toggle
 * microphone muting, switch voices, or upload files.
 *
 * @param websocketURL - The websocket endpoint used to connect to the X-Talk server.
 * @param config - Optional audio session overrides for input and output handling.
 * @returns A session controller for managing the connection and subscribing to client events.
 *
 * @example
 * ```ts
 * import { createSession } from "xtalk-client";
 *
 * const session = createSession("ws://localhost:8000/ws", {
 *   inputConfig: { sampleRate: 16000 },
 *   outputConfig: { sampleRate: 48000 },
 * });
 *
 * session.onStateChange((state) => {
 *   console.log(state.streamState, state.messages);
 * });
 *
 * await session.open();
 * ```
 */
function createSession(
    websocketURL: string | URL,
    {
        inputConfig = {},
        outputConfig = {},
    }: SessionConfig = {},
): Session {
    const resolvedInputConfig: InputAudioSessionConfig = {
        sampleRate: 16000,
        ...inputConfig,
    };
    const resolvedOutputConfig: OutputAudioSessionConfig = {
        sampleRate: 48000,
        ...outputConfig,
    };
    const conversation = new Conversation();
    const actionHandler = new ActionHandler();
    let websocket: ReturnType<typeof createWebSocket>;
    let inputAudioSession: ReturnType<typeof createInputAudioSession>;
    let outputAudioSession: ReturnType<typeof createOutputAudioSession>;

    let inputAudioChunkCallback: AudioChunkCallback = (_chunk, _sr) => { };
    let outputAudioChunkCallback: AudioChunkCallback = (_chunk, _sr) => { };

    function initialize() {
        websocket = createWebSocket(websocketURL);
        inputAudioSession = createInputAudioSession(resolvedInputConfig);
        outputAudioSession = createOutputAudioSession(resolvedOutputConfig);

        // Subscribe actions and audio chunks
        websocket.addEventListener("message", async (event: { data: string | ArrayBuffer }) => {
            if (typeof event.data === "string") {
                const message: { action: string, data: any } = JSON.parse(event.data);
                try {
                    await actionHandler.handleAction(message.action, message.data, websocket, conversation, outputAudioSession);
                } catch (error) {
                    //TODO: Handle unknown action error
                }
            } else if (event.data instanceof ArrayBuffer) {
                await outputAudioSession.pushAudioChunk(event.data);
            }
        });

        // Bind audio input handling
        inputAudioSession.onFrame(async (audioChunk) => {
            inputAudioChunkCallback(audioChunk, resolvedInputConfig.sampleRate);
            websocket.sendAudioChunk(audioChunk);
        });
        inputAudioSession.onSpeechStart(async () => {
            await actionHandler.handleAction("client_speech_start", null, websocket, conversation, outputAudioSession);
        });
        inputAudioSession.onSpeechEnd(async () => {
            await actionHandler.handleAction("client_speech_end", null, websocket, conversation, outputAudioSession);
        });

        // Bind audio output handling
        outputAudioSession.onChunkStarted(async (audioChunk) => {
            outputAudioChunkCallback(audioChunk, resolvedOutputConfig.sampleRate);
            await actionHandler.handleAction("client_audio_chunk_started", null, websocket, conversation, outputAudioSession);
        });
        outputAudioSession.onChunkPlayed(async (_audioChunk) => {
            await actionHandler.handleAction("client_audio_chunk_played", null, websocket, conversation, outputAudioSession);
        });
        outputAudioSession.onAllChunksPlayed(async () => {
            await actionHandler.handleAction("client_audio_playback_finished", null, websocket, conversation, outputAudioSession);
        });
    }


    // Create API for external use
    const session: Session = {
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
        onStateChange: (callback: (state: SessionState) => void) => {
            conversation.onStateChange(callback);
        },
        get state() {
            return conversation.state;
        },
        onInputAudioChunk: (callback: AudioChunkCallback) => {
            inputAudioChunkCallback = callback;
        },
        onOutputAudioChunk: (callback: AudioChunkCallback) => {
            outputAudioChunkCallback = callback;
        },
        onFullAudioChunk: (callback: AudioChunkCallback) => {
            conversation.onFullAudioChunk(callback);
        },
        get muted() {
            return inputAudioSession.muted;
        },
        set muted(value: boolean) {
            inputAudioSession.muted = value;
        },
        async changeVoice(voiceName: string) {
            await actionHandler.handleAction("client_change_voice", { voiceName }, websocket, conversation, outputAudioSession)
        },
        async uploadFile(file: Blob, endpoint: string | URL = "./api/upload") {
            await actionHandler.handleAction("client_upload_file", { file, endpoint }, websocket, conversation, outputAudioSession);
        }
    }

    return session;
}
