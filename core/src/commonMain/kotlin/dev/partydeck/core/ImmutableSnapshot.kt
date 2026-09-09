package dev.partydeck.core

/** Copies input values into a read-only implementation with no mutable backing-list escape. */
internal fun <T> Iterable<T>.immutableSnapshot(): List<T> = ImmutableSnapshot(this)

private class ImmutableSnapshot<T>(source: Iterable<T>) : AbstractList<T>() {
    private val values = source.toList()

    override val size: Int
        get() = values.size

    override fun get(index: Int): T = values[index]
}
