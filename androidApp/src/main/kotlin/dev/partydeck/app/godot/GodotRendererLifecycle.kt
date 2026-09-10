package dev.partydeck.app.godot

/** One child Activity lifetime; generation increases for every published snapshot. */
data class GodotRendererLifecycle(
    val started: Boolean,
    val resumed: Boolean,
    val focused: Boolean,
    val generation: Long,
) {
    val interactive: Boolean get() = started && resumed && focused
}
