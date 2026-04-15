import { BaseHTTPClient, HTTPRequestError } from "../bases/http";
import type { SessionServiceURLs } from "../bases/http";
import { Conversation } from "../conversation";
import type { ConversationUser } from "../conversation";

export { createSessionAuthController };

type SessionAuthController = ReturnType<typeof createSessionAuthController>;

function createSessionAuthController(
    {
        clearPersistedSnapshot,
        conversation,
        httpClient,
        initialAccessToken,
        initialSupportsSessionRecovery,
        serviceURLs,
    }: {
        clearPersistedSnapshot: () => void;
        conversation: Conversation;
        httpClient: BaseHTTPClient;
        initialAccessToken: string | null;
        initialSupportsSessionRecovery: boolean;
        serviceURLs: SessionServiceURLs;
    },
) {
    let accessToken: string | null = initialAccessToken;
    let supportsSessionRecovery = initialSupportsSessionRecovery;

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

    function resetAuthState(resetConversation: boolean): void {
        accessToken = null;
        supportsSessionRecovery = false;
        conversation.setUser(null);
        if (resetConversation) {
            conversation.switch(null, []);
        }
        clearPersistedSnapshot();
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

    return {
        ensureLoggedIn,
        getAccessToken(): string | null {
            return accessToken;
        },
        getSupportsSessionRecovery(): boolean {
            return supportsSessionRecovery;
        },
        resetAuthState,
        setSupportsSessionRecovery(value: boolean): void {
            supportsSessionRecovery = value;
        },
        withAuthorizedToken,
    };
}

export type { SessionAuthController };
