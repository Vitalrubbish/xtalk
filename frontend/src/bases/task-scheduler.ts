export { BaseDeferredTaskScheduler };

/**
 * Schedules deferred tasks without exposing platform-specific timing primitives.
 */
abstract class BaseDeferredTaskScheduler {
    /**
     * Enqueues a task to run asynchronously after the current hot path completes.
     *
     * @param task Task to run in a later task turn.
     */
    abstract schedule(task: () => void): void;

    /**
     * Stops the scheduler and clears any queued tasks that have not run yet.
     */
    abstract dispose(): void;
}
