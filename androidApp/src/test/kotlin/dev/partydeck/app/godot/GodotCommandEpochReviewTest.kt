package dev.partydeck.app.godot

import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFalse
import kotlin.test.assertIs
import kotlin.test.assertNull
import kotlin.test.assertTrue

/** Exercises freshness and the one-shot native Ready confirmation without Android framework mocks. */
class GodotCommandEpochReviewTest {
    @Test
    fun obsoleteFirstConfirmationIsDeliveredOnlyWithTheFirstCurrentCommand() {
        val epoch = GodotCommandEpoch()
        val firstLifecycle = epoch.advance()!!
        val nextLifecycle = epoch.advance()!!
        assertEquals(GodotCommandEpoch.Admission.Superseded, epoch.admit(firstLifecycle, acceptReady = true))
        assertEquals(GodotCommandEpoch.Admission.Superseded, epoch.admit(firstLifecycle, acceptReady = false))
        val current = epoch.advance()!!
        assertEquals(GodotCommandEpoch.Admission.Superseded, epoch.admit(nextLifecycle, acceptReady = false))
        assertEquals(GodotCommandEpoch.Admission.Superseded, epoch.admit(current + 1, acceptReady = false))
        val delivered = assertIs<GodotCommandEpoch.Admission.Deliver>(epoch.admit(current, acceptReady = false))
        assertTrue(delivered.acceptReady, "Discarded commands consumed the native Ready confirmation")
        assertFalse(assertIs<GodotCommandEpoch.Admission.Deliver>(epoch.admit(current, acceptReady = false)).acceptReady)
    }

    @Test
    fun invalidCommandsCannotPrimeConfirmationAndTheMarkerCannotBeRepeated() {
        val epoch = GodotCommandEpoch()
        val current = epoch.advance()!!
        assertEquals(GodotCommandEpoch.Admission.Invalid, epoch.admit(-1, acceptReady = true))
        assertEquals(GodotCommandEpoch.Admission.Invalid, epoch.admit(current, acceptReady = false))
        assertTrue(assertIs<GodotCommandEpoch.Admission.Deliver>(epoch.admit(current, acceptReady = true)).acceptReady)
        assertEquals(GodotCommandEpoch.Admission.Invalid, epoch.admit(current, acceptReady = true))
        val replacement = epoch.advance()!!
        assertEquals(GodotCommandEpoch.Admission.Invalid, epoch.admit(current, acceptReady = true))
        assertEquals(GodotCommandEpoch.Admission.Invalid, epoch.admit(replacement, acceptReady = true))
        assertFalse(assertIs<GodotCommandEpoch.Admission.Deliver>(epoch.admit(replacement, acceptReady = false)).acceptReady)
    }

    @Test
    fun generationZeroCannotDeliverBeforeTheFirstPublishedLifecycle() {
        val epoch = GodotCommandEpoch()
        assertEquals(0L, epoch.generation)
        assertEquals(GodotCommandEpoch.Admission.Superseded, epoch.admit(0, acceptReady = true))
        assertEquals(GodotCommandEpoch.Admission.Superseded, epoch.admit(0, acceptReady = false))
        assertEquals(GodotCommandEpoch.Admission.Superseded, epoch.admit(1, acceptReady = false))
        val current = epoch.advance()!!
        assertEquals(1L, current)
        assertTrue(assertIs<GodotCommandEpoch.Admission.Deliver>(epoch.admit(current, acceptReady = false)).acceptReady)
    }

    @Test
    fun lateCommandsStaySupersededAcrossLossRegainAndClosedAdmissionCannotRevive() {
        val epoch = GodotCommandEpoch()
        val active = epoch.advance()!!
        assertTrue(assertIs<GodotCommandEpoch.Admission.Deliver>(epoch.admit(active, acceptReady = true)).acceptReady)
        val concealed = epoch.advance()!!
        val resumed = epoch.advance()!!
        val repeatedFacts = epoch.advance()!!
        assertTrue(active < concealed && concealed < resumed && resumed < repeatedFacts)
        for (old in listOf(active, concealed, resumed)) {
            assertEquals(GodotCommandEpoch.Admission.Superseded, epoch.admit(old, acceptReady = false))
        }
        assertFalse(assertIs<GodotCommandEpoch.Admission.Deliver>(epoch.admit(repeatedFacts, acceptReady = false)).acceptReady)
        epoch.close()
        assertEquals(GodotCommandEpoch.Admission.Invalid, epoch.admit(repeatedFacts, acceptReady = false))
        assertEquals(GodotCommandEpoch.Admission.Invalid, epoch.admit(repeatedFacts + 1, acceptReady = true))
        assertNull(epoch.advance())
        epoch.close()
        assertNull(epoch.advance())
        assertEquals(repeatedFacts, epoch.generation)
    }

    @Test
    fun generationExhaustionNeverWrapsOrReopensTheOldEpoch() {
        val epoch = GodotCommandEpoch(initialGeneration = Long.MAX_VALUE - 1)
        assertEquals(Long.MAX_VALUE, epoch.advance())
        assertTrue(assertIs<GodotCommandEpoch.Admission.Deliver>(epoch.admit(Long.MAX_VALUE, acceptReady = true)).acceptReady)
        assertNull(epoch.advance())
        assertEquals(Long.MAX_VALUE, epoch.generation)
        assertEquals(GodotCommandEpoch.Admission.Invalid, epoch.admit(Long.MAX_VALUE, acceptReady = false))
        assertEquals(GodotCommandEpoch.Admission.Invalid, epoch.admit(0, acceptReady = true))
        assertNull(epoch.advance())
    }

    @Test
    fun supersededTransportDataCanReleaseCapacityWithoutConsumingNativeReady() {
        data class Command(val generation: Long, val ready: Boolean, val body: String)
        val epoch = GodotCommandEpoch()
        val oldGeneration = epoch.advance()!!
        val currentGeneration = epoch.advance()!!
        val window = GodotIpcWindow<Command>(maxCount = 2, maxBytes = 16, sizeOf = { it.body.encodeToByteArray().size })
        assertTrue(window.offer(Command(oldGeneration, ready = true, body = "old-view")))
        assertTrue(window.offer(Command(currentGeneration, ready = false, body = "new-view")))
        val old = window.takeForSend()!!
        assertEquals(GodotCommandEpoch.Admission.Superseded, epoch.admit(old.value.generation, old.value.ready))
        assertNull(window.acknowledge(old.sequence + 1))
        assertEquals(2, window.count)
        assertEquals(old.value, window.acknowledge(old.sequence))
        assertEquals(1, window.count)
        val current = window.takeForSend()!!
        val admitted = assertIs<GodotCommandEpoch.Admission.Deliver>(epoch.admit(current.value.generation, current.value.ready))
        assertTrue(admitted.acceptReady)
        assertEquals("new-view", current.value.body)
        assertEquals(current.value, window.acknowledge(current.sequence))
        assertEquals(0, window.count)
        assertEquals(0, window.bytes)
    }
}
