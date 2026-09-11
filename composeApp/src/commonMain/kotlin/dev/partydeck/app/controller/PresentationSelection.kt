package dev.partydeck.app.controller

/**
 * A picker-owned acknowledgement, with no session data or authority. Commit only after the picker
 * is disposed. Cancellation also remains valid after commit while the choice is waiting for focus.
 */
internal class PresentationSelection(
    private val onCommit: (PresentationSelection) -> Unit,
    private val onCancel: (PresentationSelection) -> Unit,
) {
    var committed = false
        private set
    private var cancelled = false

    fun commit() {
        if (committed || cancelled) return
        committed = true
        onCommit(this)
    }

    fun cancel() {
        if (cancelled) return
        cancelled = true
        onCancel(this)
    }
}
