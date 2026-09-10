package dev.partydeck.godot.compare

import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFalse
import kotlin.test.assertTrue

class RendererExitWaitTest {
    @Test
    fun earlyMonitorWakesDoNotReplaceActualExitConfirmation() {
        var now = 100L
        val waits = mutableListOf<Long>()
        val confirmed = waitForRendererExit(1_500, { now }) { remaining ->
            waits += remaining
            when (waits.size) {
                1 -> { now += 190; false }
                2 -> { now += 20; false }
                else -> true
            }
        }
        assertTrue(confirmed)
        assertEquals(listOf(1_500L, 1_310L, 1_290L), waits)
    }

    @Test
    fun repeatedWakesShareOneDeadlineAndNeverCountAsExit() {
        var now = 0L
        val waits = mutableListOf<Long>()
        val confirmed = waitForRendererExit(1_500, { now }) { remaining ->
            waits += remaining
            now += minOf(900L, remaining)
            false
        }
        assertFalse(confirmed)
        assertEquals(listOf(1_500L, 600L), waits)
        assertEquals(1_500L, now)
    }

    @Test
    fun interruptionStopsRetryWithoutClaimingExit() {
        var waits = 0
        try {
            val confirmed = waitForRendererExit(1_500, { 0L }) {
                waits += 1
                Thread.currentThread().interrupt()
                false
            }
            assertFalse(confirmed)
            assertEquals(1, waits)
            assertTrue(Thread.currentThread().isInterrupted)
        } finally {
            Thread.interrupted()
        }
    }
}
