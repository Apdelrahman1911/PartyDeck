package dev.partydeck.godot.android

import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFalse
import kotlin.test.assertNull
import kotlin.test.assertTrue

class NativeSignalDispatchTest {
    @Test
    fun nativeBarrierRemainsObservedWhileMainNotificationIsDelayed() {
        val host = Harness()
        host.now = 10
        host.requestClose()
        assertEquals(10L, host.observation.requestedElapsedRealtimeMs)
        assertNull(host.observation.dispatchStartedElapsedRealtimeMs)
        assertFalse(host.observation.acknowledged)

        host.now = 20
        host.renderStep() // Consumer invokes emitSignal, which only queues the native call.
        assertEquals(20L, host.observation.dispatchStartedElapsedRealtimeMs)
        assertTrue(host.nativeSignals.isEmpty())
        assertFalse(host.observation.acknowledged)

        host.renderStep() // Native signal returns; the separate barrier has not run.
        assertEquals(listOf(Item.CLOSE), host.nativeSignals)
        assertFalse(host.observation.acknowledged)
        host.now = 30
        host.renderStep() // Actual NativeSignalDispatch barrier, then queue acknowledgment.
        assertEquals(30L, host.observation.nativeBarrierElapsedRealtimeMs)
        assertTrue(host.observation.acknowledged)
        assertEquals(0, host.mainNotifications)

        host.queue.close() // Host fallback/disposal cannot erase the earlier observation.
        assertTrue(host.observation.acknowledged)
        host.main.removeFirst().invoke()
        assertEquals(1, host.mainNotifications)
        assertEquals(30L, host.observation.nativeBarrierElapsedRealtimeMs)
    }

    @Test
    fun disposalBeforeDispatchCannotAcknowledgeAnAdmittedClose() {
        val host = Harness()
        host.requestClose()
        host.queue.close()
        host.renderStep()
        assertTrue(host.nativeSignals.isEmpty())
        assertNull(host.observation.dispatchStartedElapsedRealtimeMs)
        assertFalse(host.observation.acknowledged)
        assertTrue(host.main.isEmpty())
    }

    @Test
    fun exitBeforeTheBarrierCannotInferCompletionFromAnEarlierNativeCall() {
        val host = Harness()
        host.requestClose()
        host.renderStep()
        host.renderStep()
        assertEquals(listOf(Item.CLOSE), host.nativeSignals)
        host.queue.close()
        host.render.clear() // Godot checks mShouldExit before taking another queued event.
        assertFalse(host.observation.acknowledged)
        assertNull(host.observation.nativeBarrierElapsedRealtimeMs)
        assertTrue(host.main.isEmpty())
    }

    @Test
    fun actualBarrierAfterQueueDisposalStillRecordsDeliveryWithoutAUiCallback() {
        val host = Harness()
        host.requestClose()
        host.renderStep()
        host.renderStep()
        host.queue.close() // Cancels the terminal callback, not an already queued GL Runnable.
        host.now = 40
        host.renderStep()
        assertEquals(listOf(Item.CLOSE), host.nativeSignals)
        assertEquals(40L, host.observation.nativeBarrierElapsedRealtimeMs)
        assertTrue(host.observation.acknowledged)
        assertTrue(host.main.isEmpty())
        assertEquals(0, host.mainNotifications)
    }

    @Test
    fun anInFlightViewBarrierDoesNotAcknowledgeTheWaitingClose() {
        val host = Harness()
        host.queue.offer(Item.VIEW)
        host.renderStep()
        host.requestClose()
        host.renderStep() // Earlier view's native signal.
        host.renderStep() // Earlier view's barrier schedules the terminal consumer.
        assertEquals(listOf(Item.VIEW), host.nativeSignals)
        assertNull(host.observation.dispatchStartedElapsedRealtimeMs)
        assertFalse(host.observation.acknowledged)
        host.renderStep()
        host.renderStep()
        assertEquals(listOf(Item.VIEW, Item.CLOSE), host.nativeSignals)
        assertFalse(host.observation.acknowledged)
        host.renderStep()
        assertTrue(host.observation.acknowledged)
    }

    @Test
    fun failedEmissionCannotScheduleAnAcknowledgmentBarrier() {
        val host = Harness()
        host.failEmission = true
        host.requestClose()
        host.renderStep()
        assertEquals(1, host.failures)
        assertFalse(host.observation.acknowledged)
        assertTrue(host.nativeSignals.isEmpty())
        assertTrue(host.render.isEmpty())
        assertTrue(host.main.isEmpty())
    }

    @Test
    fun duplicateBarrierDoesNotRewriteTheFirstObservationOrNotifyTwice() {
        val host = Harness()
        host.requestClose()
        host.renderStep()
        host.renderStep()
        val barrier = host.render.removeFirst()
        host.now = 50
        barrier()
        host.now = 60
        barrier()
        assertEquals(50L, host.observation.nativeBarrierElapsedRealtimeMs)
        assertEquals(1, host.main.size)
        assertTrue(host.render.isEmpty())
    }

    @Test
    fun aFreshPluginLifetimeCannotInheritAnOldCloseObservation() {
        val first = Harness()
        first.requestClose()
        repeat(3) { first.renderStep() }
        assertTrue(first.observation.acknowledged)
        val second = Harness()
        assertNull(second.observation.requestedElapsedRealtimeMs)
        second.requestClose()
        assertFalse(second.observation.acknowledged)
        assertNull(second.observation.nativeBarrierElapsedRealtimeMs)
    }

    private enum class Item { VIEW, CLOSE }

    private class Harness {
        val render = ArrayDeque<() -> Unit>()
        val main = ArrayDeque<() -> Unit>()
        val nativeSignals = mutableListOf<Item>()
        var now = 0L
        var mainNotifications = 0
        var failures = 0
        var failEmission = false
        private val dispatch = NativeSignalDispatch(schedule = { render.addLast(it) }, nowMillis = { now })
        val observation: CloseSignalObservation get() = dispatch.closeObservation
        val queue = BoundedDispatchQueue<Item>(
            capacity = 8,
            schedule = { render.addLast(it) },
            consume = { value, done ->
                dispatch.dispatch(
                    terminalClose = value == Item.CLOSE,
                    emit = {
                        if (failEmission) throw IllegalStateException("Emission rejected")
                        // Model only GodotPlugin.emitSignal's documented extra queue hop.
                        // The real helper and BoundedDispatchQueue own completion semantics.
                        render.addLast { nativeSignals += value }
                    },
                    afterNativeSignal = done,
                )
            },
            onFailure = { failures += 1 },
        )

        fun requestClose() {
            dispatch.closeRequested()
            queue.finish(Item.CLOSE) { main.addLast { mainNotifications += 1 } }
        }

        fun renderStep() { render.removeFirst().invoke() }
    }
}
