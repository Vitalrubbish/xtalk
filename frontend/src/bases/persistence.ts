import type { ResolvableURL } from "./http";

export { BasePersistenceStore };

abstract class BasePersistenceStore {
    abstract resolveKey(websocketURL: ResolvableURL): string | null;
    abstract load(key: string | null): string | null;
    abstract save(key: string | null, value: string): void;
    abstract clear(key: string | null): void;
}
