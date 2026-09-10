package dev.partydeck.app.godot

/** Counts the outstanding item too; an ACK releases capacity only for that exact item. */
internal class GodotIpcWindow<T>(
    private val maxCount: Int,
    private val maxBytes: Int,
    private val sizeOf: (T) -> Int,
    initialSequence: Long = 1,
) {
    data class Item<T>(val sequence: Long, val value: T, val bytes: Int)

    private val queued = ArrayDeque<Item<T>>()
    private var nextSequence = initialSequence
    var outstanding: Item<T>? = null
        private set
    var bytes: Int = 0
        private set
    val count: Int get() = queued.size + if (outstanding == null) 0 else 1

    init {
        require(maxCount > 0 && maxBytes > 0 && initialSequence > 0)
    }

    fun offer(value: T): Boolean {
        val cost = sizeOf(value)
        if (cost < 0 || cost > maxBytes || count >= maxCount || bytes > maxBytes - cost ||
            nextSequence == Long.MAX_VALUE
        ) return false
        queued.addLast(Item(nextSequence++, value, cost))
        bytes += cost
        return true
    }

    fun takeForSend(): Item<T>? {
        if (outstanding != null || queued.isEmpty()) return null
        return queued.removeFirst().also { outstanding = it }
    }

    fun acknowledge(sequence: Long): T? {
        val item = outstanding ?: return null
        if (sequence != item.sequence) return null
        outstanding = null
        bytes -= item.bytes
        return item.value
    }

    fun clear(): List<T> {
        val removed = buildList {
            outstanding?.let { add(it.value) }
            queued.forEach { add(it.value) }
        }
        outstanding = null
        queued.clear()
        bytes = 0
        return removed
    }
}
