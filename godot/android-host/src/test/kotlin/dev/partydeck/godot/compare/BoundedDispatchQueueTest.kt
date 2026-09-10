package dev.partydeck.godot.compare

import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFalse
import kotlin.test.assertTrue

class BoundedDispatchQueueTest {
    @Test
    fun startupRetainsCommandsAndWaitsForNativeEmissionAcknowledgment() {
        val scheduled = ArrayDeque<() -> Unit>()
        val delivered = mutableListOf<String>()
        val acknowledgments = ArrayDeque<() -> Unit>()
        val queue = BoundedDispatchQueue<String>(8, { scheduled.addLast(it) }, { value, done ->
            delivered += value
            acknowledgments.addLast(done)
        }, { error("Unexpected overflow") }, initiallyStarted = false)
        assertTrue(queue.offer("foreground"))
        assertTrue(queue.offer("view"))
        assertTrue(scheduled.isEmpty())
        queue.start()
        scheduled.removeFirst().invoke()
        assertEquals(listOf("foreground"), delivered)
        assertTrue(scheduled.isEmpty(), "Next native emission must wait for the first native Runnable")
        acknowledgments.removeFirst().invoke()
        scheduled.removeFirst().invoke()
        assertEquals(listOf("foreground", "view"), delivered)
    }

    @Test
    fun closeDropsPreviouslyQueuedCallbacksAndLaterInputs() {
        val scheduled = ArrayDeque<() -> Unit>()
        val delivered = mutableListOf<String>()
        val queue = BoundedDispatchQueue<String>(8, { scheduled.addLast(it) }, { value, done ->
            delivered += value
            done()
        }, { error("Unexpected overflow") })
        queue.offer("old presentation intent")
        queue.close()
        assertFalse(queue.offer("late intent"))
        scheduled.removeFirst().invoke()
        assertTrue(delivered.isEmpty(), "Queued callbacks must recheck the closed lifetime")
    }

    @Test
    fun stalledConsumerHasABoundedQueueAndOneTerminalFailure() {
        val scheduled = ArrayDeque<() -> Unit>()
        var failures = 0
        var delivered = 0
        val queue = BoundedDispatchQueue<String>(4, { scheduled.addLast(it) }, { _, _ -> delivered++ }, { failures++ })
        queue.offer("first")
        scheduled.removeFirst().invoke() // Stalled native delivery never acknowledges.
        repeat(3) { assertTrue(queue.offer("waiting $it")) }
        assertFalse(queue.offer("overflow"))
        repeat(100) { assertFalse(queue.offer("later")) }
        assertEquals(1, failures)
        assertEquals(1, delivered)
        assertTrue(scheduled.isEmpty())
    }

    @Test
    fun terminalCloseReplacesWaitingViewsAndFinishesAfterActualDelivery() {
        val scheduled = ArrayDeque<() -> Unit>()
        val delivered = mutableListOf<String>()
        val acknowledgments = ArrayDeque<() -> Unit>()
        var finished = 0
        val queue = BoundedDispatchQueue<String>(8, { scheduled.addLast(it) }, { value, done ->
            delivered += value
            acknowledgments.addLast(done)
        }, { error("Unexpected overflow") })
        queue.offer("in flight")
        scheduled.removeFirst().invoke()
        queue.offer("discarded snapshot")
        queue.finish("close") { finished++ }
        assertFalse(queue.offer("late snapshot"))
        val firstAck = acknowledgments.removeFirst()
        firstAck()
        firstAck() // A duplicate callback cannot start parallel deliveries.
        assertEquals(1, scheduled.size)
        scheduled.removeFirst().invoke()
        assertEquals(listOf("in flight", "close"), delivered)
        assertEquals(0, finished)
        acknowledgments.removeFirst().invoke()
        assertEquals(1, finished)
        assertFalse(queue.offer("after close"))
    }
}
