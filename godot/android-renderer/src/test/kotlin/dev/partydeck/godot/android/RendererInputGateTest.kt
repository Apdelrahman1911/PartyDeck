package dev.partydeck.godot.android

import kotlin.test.Test
import kotlin.test.assertFalse
import kotlin.test.assertNotNull
import kotlin.test.assertNull
import kotlin.test.assertTrue

class RendererInputGateTest {
    @Test
    fun queuedInputCannotBecomeValidAgainAfterFocusReturns() {
        val gate = RendererInputGate()
        val queued = assertNotNull(gate.capture())
        gate.setEnabled(false)
        assertNull(gate.capture(), "Covered renderer input is rejected at ingress")
        assertFalse(gate.accepts(queued))
        gate.setEnabled(true)
        assertFalse(gate.accepts(queued), "Resuming cannot resurrect a queued player action")
        assertTrue(gate.accepts(assertNotNull(gate.capture())))
    }

    @Test
    fun initiallyCoveredEntryAcceptsOnlyItsFirstInteractiveGeneration() {
        val gate = RendererInputGate(initiallyEnabled = false)
        assertNull(gate.capture())
        gate.setEnabled(true)
        val current = assertNotNull(gate.capture())
        gate.setEnabled(true)
        assertTrue(gate.accepts(current), "An unchanged draw acknowledgment is not a new lifetime")
        gate.setEnabled(false)
        gate.setEnabled(false)
        gate.setEnabled(true)
        assertFalse(gate.accepts(current))
    }
}
