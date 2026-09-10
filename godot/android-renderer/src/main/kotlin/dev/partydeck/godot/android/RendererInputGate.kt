package dev.partydeck.godot.android

/** Tags renderer input at ingress, before it can wait in the native callback queue. */
internal class RendererInputGate(initiallyEnabled: Boolean = true) {
    private var enabled = initiallyEnabled
    private var generation = 0L

    @Synchronized
    fun capture(): Long? = generation.takeIf { enabled }

    @Synchronized
    fun accepts(captured: Long): Boolean = enabled && captured == generation

    @Synchronized
    fun setEnabled(value: Boolean) {
        if (enabled == value) return
        // Exhaustion must never make an obsolete input generation current again.
        if (generation == Long.MAX_VALUE) {
            enabled = false
            return
        }
        generation += 1
        enabled = value
    }
}
