import { BaseInputAudioSession, BaseOutputAudioSession } from "../bases/audio-session";
import type { InputAudioSessionConfig, OutputAudioSessionConfig } from "../bases/audio-session";
import { BaseHTTPClient } from "../bases/http";
import type { ResolvableURL, SessionServiceURLConfig, SessionServiceURLs } from "../bases/http";
import { BaseEncoding } from "../bases/encoding";
import { BasePersistenceStore } from "../bases/persistence";
import { BaseDeferredTaskScheduler } from "../bases/task-scheduler";
import { BaseWebSocket } from "../bases/websocket";
import {
    WebDeferredTaskScheduler,
    WebEncoding,
    WebHTTPClient,
    WebInputAudioSession,
    WebOutputAudioSession,
    WebPersistenceStore,
    WebWebSocket,
    buildWebSocketURLWithAccessToken,
    resolveWebServiceURLs,
} from "./web";

export {
    getPlatformRuntime,
};

type PlatformRuntime = {
    createInputAudioSession(config: InputAudioSessionConfig): BaseInputAudioSession;
    createOutputAudioSession(config: OutputAudioSessionConfig): BaseOutputAudioSession;
    createWebSocket(url: string | URL, protocols?: string | string[]): BaseWebSocket;
    delay(milliseconds: number): Promise<void>;
    createHTTPClient(): BaseHTTPClient;
    createDeferredTaskScheduler(): BaseDeferredTaskScheduler;
    resolveServiceURLs(
        websocketURL: ResolvableURL,
        config?: SessionServiceURLConfig,
    ): SessionServiceURLs;
    buildAuthenticatedWebSocketURL(
        websocketURL: ResolvableURL,
        accessToken: string,
    ): ResolvableURL;
    createEncoding(): BaseEncoding;
    createPersistenceStore(): BasePersistenceStore;
};

enum Platform {
    Web,
}

function detectPlatform(): Platform {
    if (typeof window !== "undefined" && typeof document !== "undefined") {
        return Platform.Web;
    }
    throw new Error("Unknown platform");
}

const WEB_PLATFORM_RUNTIME: PlatformRuntime = {
    createInputAudioSession(config) {
        return new WebInputAudioSession(config);
    },
    createOutputAudioSession(config) {
        return new WebOutputAudioSession(config);
    },
    createWebSocket(url, protocols) {
        return new WebWebSocket(url, protocols);
    },
    delay(milliseconds) {
        return new Promise((resolve) => {
            window.setTimeout(resolve, milliseconds);
        });
    },
    createHTTPClient() {
        return new WebHTTPClient();
    },
    createDeferredTaskScheduler() {
        return new WebDeferredTaskScheduler();
    },
    resolveServiceURLs(websocketURL, config) {
        return resolveWebServiceURLs(websocketURL, config);
    },
    buildAuthenticatedWebSocketURL(websocketURL, accessToken) {
        return buildWebSocketURLWithAccessToken(websocketURL, accessToken);
    },
    createEncoding() {
        return new WebEncoding();
    },
    createPersistenceStore() {
        return new WebPersistenceStore();
    },
};

function getPlatformRuntime(): PlatformRuntime {
    switch (detectPlatform()) {
        case Platform.Web:
            return WEB_PLATFORM_RUNTIME;
        default:
            throw new Error("Unknown platform");
    }
}
