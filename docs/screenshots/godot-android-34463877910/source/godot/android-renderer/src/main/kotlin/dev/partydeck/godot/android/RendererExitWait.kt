package dev.partydeck.godot.android

/**
 * Godot 4.7.2's public timed exit wait can return false after an unrelated GL-monitor
 * notification. Retry against one monotonic budget; only its true result confirms exit.
 * This bounds requested waits, not time spent acquiring Godot's monitor/native cleanup.
 * The caller must be outside the render thread.
 */
fun waitForRendererExit(
    timeoutMillis: Long,
    nowMillis: () -> Long,
    requestExitAndWait: (Long) -> Boolean,
): Boolean {
    require(timeoutMillis > 0)
    val start = nowMillis()
    var remaining = timeoutMillis
    while (remaining > 0 && !Thread.currentThread().isInterrupted) {
        if (requestExitAndWait(remaining)) return true
        remaining = timeoutMillis - (nowMillis() - start)
    }
    return false
}
