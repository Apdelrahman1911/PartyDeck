package dev.partydeck.app.godot

/** Native command freshness only; Ready validation and renderer event acceptance stay common. */
internal class GodotCommandEpoch(initialGeneration: Long = 0) {
    sealed interface Admission {
        data object Invalid : Admission
        data object Superseded : Admission
        data class Deliver(val acceptReady: Boolean) : Admission
    }

    var generation: Long = initialGeneration
        private set
    private var confirmationSeen = false
    private var confirmationDelivered = false
    private var closed = false

    init { require(initialGeneration >= 0) }

    /** Every native conceal/lifecycle report advances, even if its boolean facts repeat. */
    fun advance(): Long? {
        if (closed) return null
        if (generation == Long.MAX_VALUE) {
            closed = true
            return null
        }
        generation++
        return generation
    }

    fun admit(commandGeneration: Long, acceptReady: Boolean): Admission {
        if (closed || commandGeneration < 0) return Admission.Invalid
        if (acceptReady) {
            if (confirmationSeen) return Admission.Invalid
            confirmationSeen = true
        } else if (!confirmationSeen) return Admission.Invalid
        if (generation == 0L || commandGeneration != generation) return Admission.Superseded
        // An obsolete first command preserves this confirmation for the first current delivery.
        return Admission.Deliver(!confirmationDelivered).also { confirmationDelivered = true }
    }

    fun close() { closed = true }
}
