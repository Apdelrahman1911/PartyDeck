package dev.partydeck.app.godot

import kotlin.test.Test
import kotlin.test.assertFalse
import kotlin.test.assertTrue

/** Pure notification ordering; Android binding and process teardown are reviewed separately. */
class GodotCloseHandshakeReviewTest {
    @Test
    fun nativeCleanupDuringOpeningWaitsForDelayedParentClose() {
        val handshake = GodotCloseHandshake()

        // Early Leave may finish native cleanup before the service can receive HELLO/Exit.
        repeat(3) {
            assertFalse(handshake.nativeClosed(), "Native cleanup alone released the pending notification")
        }
        assertTrue(handshake.parentClosed(), "Delayed parent confirmation did not release completed cleanup")
        assertNoFurtherCompletion(handshake)
    }

    @Test
    fun parentCloseBeforeNativeCleanupCannotFinishTheHandshake() {
        val handshake = GodotCloseHandshake()

        repeat(3) {
            assertFalse(handshake.parentClosed(), "Parent Close bypassed native cleanup")
        }
        assertTrue(handshake.nativeClosed(), "Completed cleanup lost the earlier parent confirmation")
        assertNoFurtherCompletion(handshake)
    }

    @Test
    fun connectionFailureBeforeNativeCleanupStillWaitsForCleanup() {
        val handshake = GodotCloseHandshake()

        repeat(3) {
            assertFalse(handshake.connectionLost(), "Connection failure bypassed native cleanup")
        }
        assertTrue(handshake.nativeClosed(), "Completed cleanup still waited on a known failed connection")
        assertNoFurtherCompletion(handshake)
    }

    @Test
    fun connectionFailureAfterNativeCleanupFinishesWithoutParentConfirmation() {
        val handshake = GodotCloseHandshake()

        assertFalse(handshake.nativeClosed())
        assertFalse(handshake.nativeClosed(), "Repeated cleanup supplied a missing peer outcome")
        assertTrue(handshake.connectionLost(), "A failed peer left completed cleanup waiting indefinitely")
        assertNoFurtherCompletion(handshake)
    }

    @Test
    fun anEarlyDeadlineCannotAuthorizeCompletionBeforeNativeCleanup() {
        val handshake = GodotCloseHandshake()

        repeat(3) {
            assertFalse(handshake.expired(), "A notification deadline bypassed native cleanup")
        }
        assertTrue(handshake.nativeClosed(), "Completed cleanup ignored its expired notification deadline")
        assertNoFurtherCompletion(handshake)
    }

    @Test
    fun aDeadlineAfterNativeCleanupBoundsTheWaitForAnUnconnectedParent() {
        val handshake = GodotCloseHandshake()

        assertFalse(handshake.nativeClosed())
        assertFalse(handshake.nativeClosed(), "Early-opening cleanup ended the wait before its deadline")
        assertTrue(handshake.expired(), "Notification timeout did not release completed native cleanup")
        assertNoFurtherCompletion(handshake)
    }

    @Test
    fun competingEarlyParentFailureAndDeadlineSignalsCannotSkipCleanup() {
        val handshake = GodotCloseHandshake()

        assertFalse(handshake.parentClosed())
        assertFalse(handshake.connectionLost())
        assertFalse(handshake.expired())
        assertFalse(handshake.parentClosed())
        assertFalse(handshake.connectionLost())
        assertFalse(handshake.expired())
        assertTrue(handshake.nativeClosed(), "Earlier terminal signals were lost before cleanup completed")
        assertNoFurtherCompletion(handshake)
    }

    private fun assertNoFurtherCompletion(handshake: GodotCloseHandshake) {
        repeat(2) {
            assertFalse(handshake.nativeClosed(), "Repeated native cleanup completed twice")
            assertFalse(handshake.parentClosed(), "Late parent Close completed twice")
            assertFalse(handshake.connectionLost(), "Late connection failure completed twice")
            assertFalse(handshake.expired(), "Late notification deadline completed twice")
        }
    }
}
