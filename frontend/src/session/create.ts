import { createHTTPClient, resolvePlatformServiceURLs } from "../http";
import { createPersistenceStore } from "../persistence";
import { Conversation } from "../conversation";
import { ActionHandler } from "../action-handler";
import {
    buildPersistedConversationSnapshot,
    clearPersistedConversationSnapshot,
    loadPersistedConversationSnapshot,
    savePersistedConversationSnapshot,
} from "./snapshot";
import { createSessionAuthController } from "./auth";
import { createSessionAPI } from "./api";
import { createSessionRuntimeController } from "./runtime";
import type { Session, SessionConfig } from "./types";

export { createSession };

/**
 * Creates a session client bound to the provided websocket endpoint.
 *
 * The returned session coordinates authentication, runtime audio streaming,
 * message state synchronization, and persisted conversation restoration.
 *
 * @param websocketURL Websocket endpoint used to establish the realtime session.
 * @param config Optional session configuration overrides.
 * @returns A session controller for opening, closing, and interacting with X-Talk.
 */
function createSession(
    websocketURL: string | URL,
    {
        inputConfig = {},
        outputConfig = {},
        serviceURLs: configuredServiceURLs,
    }: SessionConfig = {},
): Session {
    const resolvedInputConfig = {
        sampleRate: 16000,
        ...inputConfig,
    };
    const resolvedOutputConfig = {
        sampleRate: 48000,
        ...outputConfig,
    };
    const httpClient = createHTTPClient();
    const persistenceStore = createPersistenceStore();
    const serviceURLs = resolvePlatformServiceURLs(websocketURL, configuredServiceURLs);
    const persistenceKey = persistenceStore.resolveKey(websocketURL);
    const conversation = new Conversation();
    const actionHandler = new ActionHandler();
    const restoredSnapshot = loadPersistedConversationSnapshot(
        persistenceStore,
        persistenceKey,
    );

    if (restoredSnapshot) {
        conversation.setUser(restoredSnapshot.user);
        conversation.switch(restoredSnapshot.sessionId, restoredSnapshot.messages);
    }

    function clearPersistedSnapshot(): void {
        clearPersistedConversationSnapshot(persistenceStore, persistenceKey);
    }

    const authController = createSessionAuthController({
        clearPersistedSnapshot,
        conversation,
        httpClient,
        initialAccessToken: restoredSnapshot?.accessToken ?? null,
        serviceURLs,
    });
    const runtimeController = createSessionRuntimeController({
        actionHandler,
        conversation,
        getAccessToken: authController.getAccessToken,
        inputConfig: resolvedInputConfig,
        outputConfig: resolvedOutputConfig,
        websocketURL,
    });
    const sessionAPI = createSessionAPI({
        closeRuntime: runtimeController.close,
        conversation,
        ensureLoggedIn: authController.ensureLoggedIn,
        httpClient,
        serviceURLs,
        withAuthorizedToken: authController.withAuthorizedToken,
    });

    conversation.onStateChange((state) => {
        savePersistedConversationSnapshot(
            persistenceStore,
            persistenceKey,
            buildPersistedConversationSnapshot(
                authController.getAccessToken(),
                state.user,
                state.sessionId,
                state.messages,
            ),
        );
    });

    let pendingOpen: Promise<void> | null = null;
    let canRetryRuntimeAfterRestoredAuth = restoredSnapshot?.accessToken != null;

    return {
        async open() {
            if (pendingOpen) {
                return pendingOpen;
            }
            pendingOpen = (async () => {
                await authController.ensureLoggedIn();
                await runtimeController.close();
                try {
                    await runtimeController.initialize();
                    canRetryRuntimeAfterRestoredAuth = false;
                } catch (error) {
                    await runtimeController.close();
                    if (canRetryRuntimeAfterRestoredAuth) {
                        canRetryRuntimeAfterRestoredAuth = false;
                        authController.resetAuthState(true);
                        await authController.ensureLoggedIn();
                        await runtimeController.initialize();
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
        async close() {
            await runtimeController.close();
        },
        onStateChange(callback) {
            conversation.onStateChange(callback);
        },
        get state() {
            return conversation.state;
        },
        onInputAudioChunk(callback) {
            runtimeController.onInputAudioChunk(callback);
        },
        onOutputAudioChunk(callback) {
            runtimeController.onOutputAudioChunk(callback);
        },
        onFullAudioChunk(callback) {
            conversation.onFullAudioChunk(callback);
        },
        get muted() {
            return runtimeController.muted;
        },
        async changeVoice(voiceName: string) {
            const runtime = runtimeController.requireRuntime();
            await actionHandler.handleAction(
                "client_change_voice",
                { voiceName },
                runtime.websocket,
                conversation,
                runtime.outputAudioSession,
            );
        },
        async uploadFile(file: Blob, endpoint?: string | URL) {
            await sessionAPI.uploadFile(file, endpoint);
        },
        async getSessions() {
            return await sessionAPI.getSessions();
        },
        async switchSession(sessionId: string | null) {
            await sessionAPI.switchSession(sessionId);
        },
        set muted(value: boolean) {
            runtimeController.muted = value;
        },
    };
}
