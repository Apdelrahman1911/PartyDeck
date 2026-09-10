package dev.partydeck.app.godot

/** Post-cleanup notification only. Never delays covering the surface or native teardown. */
internal class GodotCloseHandshake {
    private var nativeClosed = false
    private var parentClosed = false
    private var connectionLost = false
    private var completed = false

    fun nativeClosed(): Boolean {
        nativeClosed = true
        return completeIfReady()
    }

    fun parentClosed(): Boolean {
        parentClosed = true
        return completeIfReady()
    }

    fun connectionLost(): Boolean {
        connectionLost = true
        return completeIfReady()
    }

    fun expired(): Boolean {
        connectionLost = true
        return completeIfReady()
    }

    /** True once: native cleanup is complete and confirmation or bounded failure is known. */
    private fun completeIfReady(): Boolean {
        if (completed || !nativeClosed || !parentClosed && !connectionLost) return false
        completed = true
        return true
    }
}
