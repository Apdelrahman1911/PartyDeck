package dev.partydeck.app.godot

import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFalse
import kotlin.test.assertNull
import kotlin.test.assertSame
import kotlin.test.assertTrue

/** Pure IPC accounting review: retained items include the one awaiting native acknowledgment. */
class GodotIpcWindowReviewTest {
    @Test
    fun countPressureIncludesOutstandingAndOnlyItsExactAckRestoresCapacity() {
        val window = GodotIpcWindow<Message>(maxCount = 2, maxBytes = 100, sizeOf = Message::bytes)
        val first = Message("first", 3)
        val second = Message("second", 5)
        val third = Message("third", 7)
        assertTrue(window.offer(first))
        val sent = window.takeForSend()!!
        assertTrue(window.offer(second))
        assertEquals(2, window.count)
        assertEquals(8, window.bytes)
        assertFalse(window.offer(third), "Moving an item into flight created an extra queue slot")
        assertNull(window.takeForSend(), "More than one item entered the unacknowledged window")

        // A guessed ACK for the queued successor cannot acknowledge the outstanding item.
        for (wrong in listOf(0L, -1L, sent.sequence + 1, Long.MAX_VALUE)) {
            assertNull(window.acknowledge(wrong))
            assertSame(sent, window.outstanding)
            assertEquals(2, window.count)
            assertEquals(8, window.bytes)
        }
        assertSame(first, window.acknowledge(sent.sequence))
        assertEquals(1, window.count)
        assertEquals(5, window.bytes)
        assertTrue(window.offer(third))
        val next = window.takeForSend()!!
        assertSame(second, next.value)
        assertEquals(sent.sequence + 1, next.sequence)
        assertNull(window.acknowledge(sent.sequence), "A replayed ACK released a different in-flight item")
        assertSame(next, window.outstanding)
        assertEquals(12, window.bytes)
        assertSame(second, window.acknowledge(next.sequence))
        val last = window.takeForSend()!!
        assertSame(third, last.value)
        assertEquals(next.sequence + 1, last.sequence, "A rejected offer consumed a transport sequence")
    }

    @Test
    fun aggregateBytePressureCountsUtf8AndOutstandingDataUntilAcknowledged() {
        val window = GodotIpcWindow<String>(maxCount = 16, maxBytes = 10, sizeOf = { it.encodeToByteArray().size })
        val first = "éé" // Four UTF-8 bytes, although String.length is two.
        val second = "🙂" // Four UTF-8 bytes, although String.length is two.
        assertTrue(window.offer(first))
        val outstanding = window.takeForSend()!!
        assertTrue(window.offer(second))
        assertTrue(window.offer("ab"))
        assertEquals(3, window.count)
        assertEquals(10, window.bytes)
        assertFalse(window.offer("x"), "Aggregate bytes exceeded the bound while count was below it")
        assertEquals(first, window.acknowledge(outstanding.sequence))
        assertEquals(6, window.bytes)
        assertTrue(window.offer(first), "Exact byte capacity was not restored by acknowledgment")
        assertEquals(10, window.bytes)
        assertEquals(listOf(second, "ab", first), window.clear())
        assertEquals(0, window.bytes)
    }

    @Test
    fun byteArithmeticCannotWrapAndRejectedSizesDoNotDisplaceAcceptedItems() {
        val window = GodotIpcWindow<Message>(maxCount = 8, maxBytes = Int.MAX_VALUE, sizeOf = Message::bytes)
        val large = Message("large cost without large allocation", Int.MAX_VALUE - 2)
        val remainder = Message("remainder", 2)
        assertTrue(window.offer(large))
        val outstanding = window.takeForSend()!!
        assertTrue(window.offer(remainder))
        assertEquals(Int.MAX_VALUE, window.bytes)
        assertFalse(window.offer(Message("overflow", 1)))
        assertFalse(window.offer(Message("negative", Int.MIN_VALUE)))
        assertEquals(2, window.count)
        assertEquals(Int.MAX_VALUE, window.bytes)
        assertSame(large, window.acknowledge(outstanding.sequence))
        assertEquals(2, window.bytes)
        assertFalse(window.offer(Message("too large alongside retained data", Int.MAX_VALUE)))
        val next = window.takeForSend()!!
        assertSame(remainder, next.value)
        assertEquals(outstanding.sequence + 1, next.sequence)
        assertSame(remainder, window.acknowledge(next.sequence))
        assertEquals(0, window.bytes)
        assertTrue(window.offer(Message("full capacity", Int.MAX_VALUE)))
        assertEquals(Int.MAX_VALUE, window.bytes)
    }

    @Test
    fun clearingDisposesEveryRetainedItemOnceAndDoesNotReuseItsSequence() {
        val window = GodotIpcWindow<Message>(maxCount = 3, maxBytes = 20, sizeOf = Message::bytes)
        val first = Message("outstanding", 3)
        val second = Message("queued first", 4)
        val third = Message("queued second", 5)
        assertTrue(window.offer(first))
        assertTrue(window.offer(second))
        val old = window.takeForSend()!!
        assertTrue(window.offer(third))
        assertEquals(listOf(first, second, third), window.clear())
        assertTrue(window.clear().isEmpty(), "Disposal returned the same suspended writer twice")
        assertNull(window.outstanding)
        assertEquals(0, window.count)
        assertEquals(0, window.bytes)
        assertNull(window.takeForSend())
        assertNull(window.acknowledge(old.sequence))

        val replacement = Message("replacement", 6)
        assertTrue(window.offer(replacement))
        val sent = window.takeForSend()!!
        assertEquals(old.sequence + 3, sent.sequence)
        assertNull(window.acknowledge(old.sequence), "A delayed ACK from disposed data became current again")
        assertSame(sent, window.outstanding)
        assertEquals(6, window.bytes)
        assertEquals(listOf(replacement), window.clear())
    }

    @Test
    fun oversizeAdmissionFailurePreservesFifoAndTheNextAssignableSequence() {
        val window = GodotIpcWindow<Message>(maxCount = 3, maxBytes = 5, sizeOf = Message::bytes)
        val first = Message("first", 2)
        val second = Message("second", 3)
        val third = Message("third", 1)
        assertTrue(window.offer(first))
        val sent = window.takeForSend()!!
        assertFalse(window.offer(Message("single oversize", 6)))
        assertFalse(window.offer(Message("invalid size", -1)))
        assertTrue(window.offer(second))
        assertFalse(window.offer(third))
        assertSame(first, window.acknowledge(sent.sequence))
        assertTrue(window.offer(third))
        val next = window.takeForSend()!!
        assertSame(second, next.value)
        assertEquals(sent.sequence + 1, next.sequence)
        assertSame(second, window.acknowledge(next.sequence))
        val last = window.takeForSend()!!
        assertSame(third, last.value)
        assertEquals(next.sequence + 1, last.sequence)
        assertSame(third, window.acknowledge(last.sequence))
        assertEquals(0, window.count)
        assertEquals(0, window.bytes)
    }

    @Test
    fun sequenceExhaustionRejectsFurtherDataEvenAfterAckOrDisposal() {
        val window = GodotIpcWindow<Message>(
            maxCount = 3, maxBytes = 10, sizeOf = Message::bytes, initialSequence = Long.MAX_VALUE - 2,
        )
        val first = Message("penultimate", 1)
        val second = Message("last assignable", 1)
        assertTrue(window.offer(first))
        assertTrue(window.offer(second))
        assertFalse(window.offer(Message("would exhaust", 1)))
        val sent = window.takeForSend()!!
        assertEquals(Long.MAX_VALUE - 2, sent.sequence)
        assertSame(first, window.acknowledge(sent.sequence))
        val last = window.takeForSend()!!
        assertEquals(Long.MAX_VALUE - 1, last.sequence)
        assertSame(second, window.acknowledge(last.sequence))
        assertEquals(0, window.count)
        assertFalse(window.offer(Message("would wrap after ACK", 1)))
        assertTrue(window.clear().isEmpty())
        assertFalse(window.offer(Message("would wrap after disposal", 1)))
        assertEquals(0, window.bytes)
    }

    private data class Message(val description: String, val bytes: Int)
}
