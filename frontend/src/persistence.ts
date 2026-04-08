import { BasePersistenceStore } from "./bases/persistence";
import { getPlatformRuntime } from "./platforms/index";

export { createPersistenceStore };

function createPersistenceStore(): BasePersistenceStore {
    return getPlatformRuntime().createPersistenceStore();
}
