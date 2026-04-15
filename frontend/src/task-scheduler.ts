import { BaseDeferredTaskScheduler } from "./bases/task-scheduler";
import { getPlatformRuntime } from "./platforms/index";

export { createDeferredTaskScheduler };

/**
 * Creates a deferred task scheduler backed by the active platform runtime.
 *
 * @returns Scheduler used to enqueue non-blocking observer work.
 */
function createDeferredTaskScheduler(): BaseDeferredTaskScheduler {
    return getPlatformRuntime().createDeferredTaskScheduler();
}
