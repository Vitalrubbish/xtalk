import { getPlatform, Platform } from "./utils";
import { BaseHTTPClient } from "./bases/http";
import type { ResolvableURL, SessionServiceURLConfig, SessionServiceURLs } from "./bases/http";
import { WebHTTPClient, buildWebSocketURLWithAccessToken, resolveWebServiceURLs } from "./platforms/web";

export { createHTTPClient, buildAuthenticatedWebSocketURL, resolvePlatformServiceURLs };

function createHTTPClient(): BaseHTTPClient {
    switch (getPlatform()) {
        case Platform.Web:
            return new WebHTTPClient();
        default:
            throw new Error("Unknown platform");
    }
}

function resolvePlatformServiceURLs(
    websocketURL: ResolvableURL,
    config?: SessionServiceURLConfig,
): SessionServiceURLs {
    switch (getPlatform()) {
        case Platform.Web:
            return resolveWebServiceURLs(websocketURL, config);
        default:
            throw new Error("Unknown platform");
    }
}

function buildAuthenticatedWebSocketURL(
    websocketURL: ResolvableURL,
    accessToken: string,
): ResolvableURL {
    switch (getPlatform()) {
        case Platform.Web:
            return buildWebSocketURLWithAccessToken(websocketURL, accessToken);
        default:
            throw new Error("Unknown platform");
    }
}
