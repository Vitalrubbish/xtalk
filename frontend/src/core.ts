import { createWebSocket } from "./websocket";
import type { InputAudioSessionConfig, OutputAudioSessionConfig } from "./bases/audio-session";
import { HTTPRequestError } from "./bases/http";
import type { ResolvableURL, SessionServiceURLConfig, SessionServiceURLs } from "./bases/http";
import { createInputAudioSession, createOutputAudioSession } from "./audio-session";
import { buildAuthenticatedWebSocketURL, createHTTPClient, resolvePlatformServiceURLs } from "./http";
import { Conversation } from "./conversation";
import type { ConversationMessage, ConversationUser } from "./conversation";
import { ActionHandler } from "./action-handler";

export { createSession };
export type {
    Session,
    SessionConfig,
    SessionServiceURLs,
    SessionServiceURLConfig,
    SessionSummary,
    SessionDetail,
};

type SessionState = Conversation["state"];
type AudioChunkCallback = (pcmChunkInt16: ArrayBuffer, sampleRate: number) => void;

type SessionSummary = {
    session_id: string;
    title: string | null;
};

type SessionDetail = {
    session_id: string;
    title: string | null;
    messages: Array<{
        role: "user" | "assistant" | "info";
        content: string;
        turn_id?: number | null;
    }>;
};

type PersistedConversationSnapshot = {
    accessToken: string | null;
    user: ConversationUser | null;
    sessionId: string | null;
    messages: ConversationMessage[];
};

interface SessionConfig {
    inputConfig?: Partial<InputAudioSessionConfig>;
    outputConfig?: Partial<OutputAudioSessionConfig>;
    serviceURLs?: SessionServiceURLConfig;
}

interface Session {
    open(): Promise<void>;
    close(): Promise<void>;
    onStateChange(callback: (state: Conversation["state"]) => void): void;
    readonly state: Conversation["state"];
    onInputAudioChunk(callback: (pcmChunkInt16: ArrayBuffer, sampleRate: number) => void): void;
    onOutputAudioChunk(callback: (pcmChunkInt16: ArrayBuffer, sampleRate: number) => void): void;
    onFullAudioChunk(callback: (pcmChunkInt16: ArrayBuffer, sampleRate: number) => void): void;
    muted: boolean;
    changeVoice(voiceName: string): Promise<void>;
    uploadFile(file: Blob, endpoint?: string | URL): Promise<void>;
    getSessions(): Promise<SessionSummary[]>;
    switchSession(sessionId: string | null): Promise<void>;
}

function mapSessionMessages(messages: SessionDetail["messages"]): ConversationMessage[] {
    return messages.map((message) => {
        const mapped: ConversationMessage = {
            role: message.role,
            content: message.content,
        };
        if (typeof message.turn_id === "number") {
            mapped.turnId = message.turn_id;
        }
        return mapped;
    });
}

function resolvePersistenceKey(websocketURL: ResolvableURL): string | null {
    if (typeof window === "undefined" || typeof window.localStorage === "undefined") {
        return null;
    }
    const resolvedURL = new URL(websocketURL.toString(), window.location.href);
    return `xtalk:session:${resolvedURL.toString()}`;
}

function normalizePersistedMessageRole(
    value: unknown,
): ConversationMessage["role"] | null {
    return value === "user" || value === "assistant" || value === "info"
        ? value
        : null;
}

function normalizePersistedMessages(value: unknown): ConversationMessage[] {
    if (!Array.isArray(value)) {
        return [];
    }
    const messages: ConversationMessage[] = [];
    for (const item of value) {
        if (!item || typeof item !== "object") {
            continue;
        }
        const role = normalizePersistedMessageRole((item as { role?: unknown }).role);
        const content = (item as { content?: unknown }).content;
        const turnId = (item as { turnId?: unknown }).turnId;
        if (!role || typeof content !== "string") {
            continue;
        }
        const message: ConversationMessage = { role, content };
        if (typeof turnId === "number" && Number.isFinite(turnId)) {
            message.turnId = turnId;
        }
        messages.push(message);
    }
    return messages;
}

function loadPersistedConversationSnapshot(
    persistenceKey: string | null,
): PersistedConversationSnapshot | null {
    if (!persistenceKey) {
        return null;
    }
    try {
        const raw = window.localStorage.getItem(persistenceKey);
        if (!raw) {
            return null;
        }
        const parsed = JSON.parse(raw) as {
            accessToken?: unknown;
            user?: unknown;
            sessionId?: unknown;
            messages?: unknown;
        };
        const userValue = parsed.user;
        const user = userValue
            && typeof userValue === "object"
            && typeof (userValue as { id?: unknown }).id === "string"
            ? { id: (userValue as { id: string }).id }
            : null;
        return {
            accessToken: typeof parsed.accessToken === "string" ? parsed.accessToken : null,
            user,
            sessionId: typeof parsed.sessionId === "string" ? parsed.sessionId : null,
            messages: normalizePersistedMessages(parsed.messages),
        };
    } catch {
        return null;
    }
}

function savePersistedConversationSnapshot(
    persistenceKey: string | null,
    snapshot: PersistedConversationSnapshot,
): void {
    if (!persistenceKey) {
        return;
    }
    try {
        window.localStorage.setItem(persistenceKey, JSON.stringify(snapshot));
    } catch {
        // Ignore storage failures so realtime usage continues normally.
    }
}

function clearPersistedConversationSnapshot(persistenceKey: string | null): void {
    if (!persistenceKey) {
        return;
    }
    try {
        window.localStorage.removeItem(persistenceKey);
    } catch {
        // Ignore storage failures so realtime usage continues normally.
    }
}

function createSession(
    websocketURL: string | URL,
    {
        inputConfig = {},
        outputConfig = {},
        serviceURLs: configuredServiceURLs,
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
    const httpClient = createHTTPClient();
    const serviceURLs = resolvePlatformServiceURLs(websocketURL, configuredServiceURLs);
    const persistenceKey = resolvePersistenceKey(websocketURL);
    const conversation = new Conversation();
    const actionHandler = new ActionHandler();
    const restoredSnapshot = loadPersistedConversationSnapshot(persistenceKey);

    let websocket: ReturnType<typeof createWebSocket> | null = null;
    let inputAudioSession: ReturnType<typeof createInputAudioSession> | null = null;
    let outputAudioSession: ReturnType<typeof createOutputAudioSession> | null = null;
    let accessToken: string | null = restoredSnapshot?.accessToken ?? null;
    let inputAudioChunkCallback: AudioChunkCallback = (_chunk, _sr) => { };
    let outputAudioChunkCallback: AudioChunkCallback = (_chunk, _sr) => { };
    let pendingOpen: Promise<void> | null = null;
    let preferredMuted = false;
    let canRetryRuntimeAfterRestoredAuth = restoredSnapshot?.accessToken != null;

    if (restoredSnapshot) {
        conversation.setUser(restoredSnapshot.user);
        conversation.switch(restoredSnapshot.sessionId, restoredSnapshot.messages);
    }

    function persistSnapshot(): void {
        const state = conversation.state;
        savePersistedConversationSnapshot(persistenceKey, {
            accessToken,
            user: state.user,
            sessionId: state.sessionId,
            messages: state.messages.map((message) => ({
                role: message.role,
                content: message.content,
                ...(typeof message.turnId === "number" ? { turnId: message.turnId } : {}),
            })),
        });
    }

    function clearPersistedSnapshot(): void {
        clearPersistedConversationSnapshot(persistenceKey);
    }

    function resetAuthState(resetConversation: boolean): void {
        accessToken = null;
        conversation.setUser(null);
        if (resetConversation) {
            conversation.switch(null, []);
        }
        clearPersistedSnapshot();
    }

    conversation.onStateChange(() => {
        persistSnapshot();
    });

    async function performLogin(): Promise<void> {
        const payload = await httpClient.postJSON<{
            access_token?: string;
            user?: ConversationUser | null;
        }>(serviceURLs.login, null);
        if (!payload.access_token) {
            throw new Error("Login response did not include access_token");
        }

        accessToken = payload.access_token;
        conversation.setUser(payload.user ?? null);
    }

    async function ensureLoggedIn(): Promise<void> {
        if (accessToken) {
            return;
        }
        await performLogin();
    }

    async function withAuthorizedToken<T>(
        operation: (token: string) => Promise<T>,
    ): Promise<T> {
        await ensureLoggedIn();
        if (!accessToken) {
            throw new Error("Access token missing");
        }
        try {
            return await operation(accessToken);
        } catch (error) {
            if (!(error instanceof HTTPRequestError) || error.status !== 401) {
                throw error;
            }
            resetAuthState(true);
            await ensureLoggedIn();
            if (!accessToken) {
                throw new Error("Access token missing");
            }
            return await operation(accessToken);
        }
    }

    async function authorizedGetJSON<T>(input: ResolvableURL): Promise<T> {
        return await withAuthorizedToken((token) => httpClient.getJSON<T>(input, token));
    }

    function requireRuntime(): {
        websocket: ReturnType<typeof createWebSocket>;
        outputAudioSession: ReturnType<typeof createOutputAudioSession>;
    } {
        if (!websocket || !outputAudioSession) {
            throw new Error("Session is not open");
        }
        return { websocket, outputAudioSession };
    }

    function initializeRuntime(): Promise<void> {
        if (!accessToken) {
            throw new Error("Access token missing");
        }

        const wsURL = buildAuthenticatedWebSocketURL(websocketURL, accessToken);
        websocket = createWebSocket(wsURL);
        inputAudioSession = createInputAudioSession(resolvedInputConfig);
        outputAudioSession = createOutputAudioSession(resolvedOutputConfig);
        const currentWebSocket = websocket;
        const currentInputAudioSession = inputAudioSession;
        const currentOutputAudioSession = outputAudioSession;
        currentInputAudioSession.muted = preferredMuted;

        let resolveAttached: (() => void) | null = null;
        let rejectAttached: ((reason?: unknown) => void) | null = null;
        const attachedPromise = new Promise<void>((resolve, reject) => {
            resolveAttached = resolve;
            rejectAttached = reject;
        });
        const openPromise = new Promise<void>((resolve, reject) => {
            currentWebSocket.addEventListener("open", () => {
                resolve();
            });
            currentWebSocket.addEventListener("error", () => {
                reject(new Error("WebSocket connection failed"));
            });
        });

        currentWebSocket.addEventListener("close", () => {
            conversation.state.streamState = "idle";
            rejectAttached?.(new Error("WebSocket closed before session attachment"));
        });
        currentWebSocket.addEventListener("message", async (event: { data: string | ArrayBuffer }) => {
            if (typeof event.data === "string") {
                const message: { action: string; data: unknown } = JSON.parse(event.data);
                await actionHandler.handleAction(
                    message.action,
                    message.data,
                    currentWebSocket,
                    conversation,
                    currentOutputAudioSession,
                );
                if (message.action === "session_attached") {
                    resolveAttached?.();
                }
            } else if (event.data instanceof ArrayBuffer) {
                await currentOutputAudioSession.pushAudioChunk(event.data);
            }
        });

        currentInputAudioSession.onFrame(async (audioChunk) => {
            inputAudioChunkCallback(audioChunk, resolvedInputConfig.sampleRate);
            if (websocket?.ready()) {
                websocket.sendAudioChunk(audioChunk);
            }
        });
        currentInputAudioSession.onSpeechStart(async () => {
            if (websocket?.ready()) {
                await actionHandler.handleAction(
                    "client_speech_start",
                    null,
                    websocket,
                    conversation,
                    currentOutputAudioSession,
                );
            }
        });
        currentInputAudioSession.onSpeechEnd(async () => {
            if (websocket?.ready()) {
                await actionHandler.handleAction(
                    "client_speech_end",
                    null,
                    websocket,
                    conversation,
                    currentOutputAudioSession,
                );
            }
        });

        currentOutputAudioSession.onChunkStarted(async (audioChunk) => {
            outputAudioChunkCallback(audioChunk, resolvedOutputConfig.sampleRate);
            if (websocket?.ready()) {
                await actionHandler.handleAction(
                    "client_audio_chunk_started",
                    null,
                    websocket,
                    conversation,
                    currentOutputAudioSession,
                );
            }
        });
        currentOutputAudioSession.onChunkPlayed(async () => {
            if (websocket?.ready()) {
                await actionHandler.handleAction(
                    "client_audio_chunk_played",
                    null,
                    websocket,
                    conversation,
                    currentOutputAudioSession,
                );
            }
        });
        currentOutputAudioSession.onAllChunksPlayed(async () => {
            if (websocket?.ready()) {
                await actionHandler.handleAction(
                    "client_audio_playback_finished",
                    null,
                    websocket,
                    conversation,
                    currentOutputAudioSession,
                );
            }
        });

        return (async () => {
            await openPromise;
            currentWebSocket.sendJson({
                action: "attach_session",
                session_id: conversation.state.sessionId,
            });
            await attachedPromise;
            await currentOutputAudioSession.open();
            await currentInputAudioSession.open();
        })();
    }

    async function closeRuntime(): Promise<void> {
        const currentInput = inputAudioSession;
        const currentOutput = outputAudioSession;
        const currentWebSocket = websocket;

        inputAudioSession = null;
        outputAudioSession = null;
        websocket = null;

        if (currentInput) {
            try {
                preferredMuted = currentInput.muted;
                await currentInput.close();
            } catch {
                // Ignore shutdown errors from already-closed audio sessions.
            }
        }
        if (currentOutput) {
            try {
                await currentOutput.close();
            } catch {
                // Ignore shutdown errors from already-closed audio sessions.
            }
        }
        currentWebSocket?.close();
        conversation.state.streamState = "idle";
    }

    const session: Session = {
        open: async () => {
            if (pendingOpen) {
                return pendingOpen;
            }
            pendingOpen = (async () => {
                await ensureLoggedIn();
                await closeRuntime();
                try {
                    await initializeRuntime();
                    canRetryRuntimeAfterRestoredAuth = false;
                } catch (error) {
                    await closeRuntime();
                    if (canRetryRuntimeAfterRestoredAuth) {
                        canRetryRuntimeAfterRestoredAuth = false;
                        resetAuthState(true);
                        await ensureLoggedIn();
                        await initializeRuntime();
                        canRetryRuntimeAfterRestoredAuth = false;
                        return;
                    }
                    throw error;
                }
            })();
            try {
                await pendingOpen;
            } finally {
                pendingOpen = null;
            }
        },
        close: async () => {
            await closeRuntime();
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
            return inputAudioSession ? inputAudioSession.muted : preferredMuted;
        },
        async changeVoice(voiceName: string) {
            const runtime = requireRuntime();
            await actionHandler.handleAction(
                "client_change_voice",
                { voiceName },
                runtime.websocket,
                conversation,
                runtime.outputAudioSession,
            );
        },
        async uploadFile(file: Blob, endpoint?: string | URL) {
            const sessionId = conversation.state.sessionId;
            if (!sessionId) {
                throw new Error("No session selected");
            }

            conversation.state.streamState = "processing";
            try {
                await withAuthorizedToken((token) =>
                    httpClient.postFile(endpoint ?? serviceURLs.upload, token, sessionId, file),
                );
            } finally {
                conversation.state.streamState = "idle";
            }
        },
        async getSessions() {
            const payload = await authorizedGetJSON<{ sessions?: SessionSummary[] }>(serviceURLs.sessions);
            return payload.sessions ?? [];
        },
        async switchSession(sessionId: string | null) {
            await ensureLoggedIn();
            await closeRuntime();
            if (!sessionId) {
                conversation.switch(null, []);
                return;
            }

            const payload = await authorizedGetJSON<SessionDetail>(serviceURLs.sessionDetail(sessionId));
            conversation.switch(payload.session_id, mapSessionMessages(payload.messages));
        },
        set muted(value: boolean) {
            preferredMuted = value;
            if (inputAudioSession) {
                inputAudioSession.muted = value;
            }
        },
    };

    return session;
}
