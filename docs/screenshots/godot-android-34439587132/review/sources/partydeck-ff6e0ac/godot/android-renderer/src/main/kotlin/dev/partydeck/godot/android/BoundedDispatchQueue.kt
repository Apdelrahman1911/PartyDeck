package dev.partydeck.godot.android

/**
 * Bounded FIFO with one delivery in flight. The consumer acknowledges completion;
 * for Godot this occurs after its own queued native signal, not merely after emitSignal().
 * Queued work checks this lifetime again when the target thread actually executes it.
 */
internal class BoundedDispatchQueue<T>(
    private val capacity: Int,
    private val schedule: (() -> Unit) -> Unit,
    private val consume: (T, () -> Unit) -> Unit,
    private val onFailure: () -> Unit,
    initiallyStarted: Boolean = true,
) {
    private data class Item<T>(val value: T, val terminal: Boolean = false)
    private val lock = Any()
    private val pending = ArrayDeque<Item<T>>()
    private var started = initiallyStarted
    private var inFlight = false
    private var closing = false
    private var closed = false
    private var terminalCallback: (() -> Unit)? = null

    init { require(capacity > 0) }

    fun offer(value: T): Boolean {
        var failed = false
        synchronized(lock) {
            if (closed || closing) return false
            if (pending.size + (if (inFlight) 1 else 0) >= capacity) {
                closed = true
                pending.clear()
                failed = true
            } else pending.addLast(Item(value))
        }
        if (failed) onFailure() else kick()
        return !failed
    }

    fun start() {
        synchronized(lock) { if (!closed) started = true }
        kick()
    }

    /** Reject new work, replace waiting work with the terminal message, then acknowledge it. */
    fun finish(value: T, afterDelivery: () -> Unit) {
        synchronized(lock) {
            if (closed || closing) return
            closing = true
            pending.clear()
            pending.addLast(Item(value, terminal = true))
            terminalCallback = afterDelivery
        }
        kick()
    }

    fun close() {
        synchronized(lock) {
            closed = true
            pending.clear()
            terminalCallback = null
        }
    }

    private fun kick() {
        synchronized(lock) {
            if (closed || !started || inFlight || pending.isEmpty()) return
            inFlight = true
        }
        schedule {
            val item = synchronized(lock) {
                if (closed || !started || pending.isEmpty()) {
                    inFlight = false
                    return@schedule
                }
                pending.removeFirst()
            }
            var acknowledged = false
            val acknowledge = {
                var completed: (() -> Unit)? = null
                var continueDelivery = false
                synchronized(lock) {
                    if (!acknowledged) {
                        acknowledged = true
                        inFlight = false
                        if (!closed) {
                            if (item.terminal) {
                                closed = true
                                pending.clear()
                                completed = terminalCallback
                                terminalCallback = null
                            } else continueDelivery = true
                        }
                    }
                }
                completed?.invoke()
                if (continueDelivery) kick()
            }
            try {
                consume(item.value, acknowledge)
            } catch (_: RuntimeException) {
                close()
                onFailure()
            }
        }
    }
}
