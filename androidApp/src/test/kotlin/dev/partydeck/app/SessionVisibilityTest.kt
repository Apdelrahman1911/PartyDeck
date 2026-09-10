package dev.partydeck.app

import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFalse
import kotlin.test.assertTrue

class SessionVisibilityTest {
    @Test
    fun focusAndPauseConcealImmediatelyWithoutTreatingAVisibleShellAsBackground() {
        val visibility = SessionVisibility()
        val shell = startedShell(visibility)
        assertState(visibility, 0, foreground = true, backgrounded = false)

        visibility.updateShell(shell, started = true, resumed = true, focused = false)
        assertState(visibility, 10, foreground = false, backgrounded = false)
        visibility.updateShell(shell, started = true, resumed = false, focused = true)
        assertState(visibility, 20, foreground = false, backgrounded = false)

        visibility.stopShell(shell, changingConfigurations = false, nowMillis = 30)
        assertState(visibility, 30, foreground = false, backgrounded = true)
        // Focus and resume alone cannot make a stopped window visible or interactive.
        visibility.updateShell(shell, started = false, resumed = true, focused = true)
        assertState(visibility, 40, foreground = false, backgrounded = true)
        visibility.updateShell(shell, started = true, resumed = true, focused = true)
        assertState(visibility, 50, foreground = true, backgrounded = false)
    }

    @Test
    fun handoffPreservesVisibilityInEitherCallbackOrderAndWaitsForActualChildFocus() {
        for (childStartsFirst in listOf(false, true)) {
            val visibility = SessionVisibility()
            val shell = startedShell(visibility)
            visibility.selectPresentation("table")
            assertTrue(visibility.rendererOpening("table", deadlineMillis = 10_000))
            assertTrue(visibility.shellCanLaunch(shell))
            assertState(visibility, 0, foreground = false, backgrounded = false,
                shellSelected = false, deadline = 10_000)

            if (childStartsFirst) {
                visibility.updateRenderer("table", 4, started = true, resumed = false, focused = false)
            }
            visibility.stopShell(shell, changingConfigurations = false, nowMillis = 100)
            if (!childStartsFirst) {
                assertState(visibility, 100, foreground = false, backgrounded = false,
                    shellSelected = false, deadline = 10_000)
                assertState(visibility, 5_000, foreground = false, backgrounded = false,
                    shellSelected = false, deadline = 10_000)
                visibility.updateRenderer("table", 4, started = true, resumed = false, focused = false)
            }
            assertState(visibility, 50_000, foreground = false, backgrounded = false, shellSelected = false)
            visibility.updateRenderer("table", 5, started = true, resumed = true, focused = false)
            assertState(visibility, 50_010, foreground = false, backgrounded = false, shellSelected = false)
            visibility.updateRenderer("table", 6, started = true, resumed = true, focused = true)
            assertState(visibility, 50_020, foreground = true, backgrounded = false, shellSelected = false)
        }
    }

    @Test
    fun slowColdStartupUsesTheHostsDeadlineWithoutRenewingItFromShellCallbacks() {
        val visibility = SessionVisibility()
        val shell = startedShell(visibility)
        visibility.selectPresentation("table")
        visibility.rendererOpening("table", deadlineMillis = 10_000)
        visibility.stopShell(shell, changingConfigurations = false, nowMillis = 100)
        visibility.stopShell(shell, changingConfigurations = false, nowMillis = 900)
        assertFalse(visibility.rendererOpening("table", deadlineMillis = 90_000))
        // The covered child may already be visible while binding or launch preparation
        // delays its first native lifecycle report beyond the short transition grace.
        assertState(visibility, 5_000, foreground = false, backgrounded = false,
            shellSelected = false, deadline = 10_000)
        assertState(visibility, 9_999, foreground = false, backgrounded = false,
            shellSelected = false, deadline = 10_000)
        assertState(visibility, 10_000, foreground = false, backgrounded = true, shellSelected = false)

        visibility.stopShell(shell, changingConfigurations = true, nowMillis = 20_000)
        assertFalse(visibility.rendererOpening("table", deadlineMillis = 90_000))
        assertState(visibility, 20_000, foreground = false, backgrounded = true, shellSelected = false)
    }

    @Test
    fun actualStoppedChildCancelsAnUnobservedHandoffImmediately() {
        val visibility = SessionVisibility()
        val shell = startedShell(visibility)
        visibility.selectPresentation("table")
        visibility.rendererOpening("table", deadlineMillis = 10_000)
        visibility.stopShell(shell, changingConfigurations = false, nowMillis = 100)

        assertTrue(visibility.updateRenderer("table", 1, started = false, resumed = false, focused = false))
        assertState(visibility, 101, foreground = false, backgrounded = true, shellSelected = false)
        visibility.rendererClosing("table", nowMillis = 200)
        visibility.rendererClosed("table", nowMillis = 300)
        assertState(visibility, 300, foreground = false, backgrounded = true, shellSelected = false)
    }

    @Test
    fun definitiveUnobservedLaunchFailureEndsTheOpeningLeaseWithoutInventingVisibility() {
        val visibility = SessionVisibility()
        val shell = startedShell(visibility)
        visibility.selectPresentation("table")
        visibility.rendererOpening("table", deadlineMillis = 10_000)
        visibility.stopShell(shell, changingConfigurations = false, nowMillis = 100)
        visibility.rendererClosed("table", nowMillis = 300)
        assertState(visibility, 300, foreground = false, backgrounded = true, shellSelected = false)
    }

    @Test
    fun earlyReturnBeforeHelloPreservesTheSessionUntilTheShellReturnsInEitherDeathOrder() {
        for (deathBeforeReturn in listOf(false, true)) {
            val visibility = SessionVisibility()
            val shell = startedShell(visibility)
            visibility.selectPresentation("table")
            visibility.rendererOpening("table", deadlineMillis = 10_000)
            visibility.stopShell(shell, changingConfigurations = false, nowMillis = 100)
            // Exit/Standard can arrive after HELLO without LAUNCH acceptance or LIFE DATA.
            visibility.selectPresentation(null)
            visibility.rendererClosing("table", nowMillis = 200)
            assertState(visibility, 200, foreground = false, backgrounded = false, deadline = 3_200)
            assertFalse(visibility.rendererClosing("table", nowMillis = 250))
            if (deathBeforeReturn) {
                visibility.rendererClosed("table", nowMillis = 300)
                assertState(visibility, 300, foreground = false, backgrounded = false, deadline = 1_300)
            }

            visibility.updateShell(shell, started = true, resumed = false, focused = false)
            assertState(visibility, 400, foreground = false, backgrounded = false,
                deadline = if (deathBeforeReturn) null else 3_200)
            if (!deathBeforeReturn) visibility.rendererClosed("table", nowMillis = 500)
            visibility.updateShell(shell, started = true, resumed = true, focused = true)
            assertState(visibility, 600, foreground = true, backgrounded = false)
        }
    }

    @Test
    fun stoppedEvidenceOrUserDepartureEndsAnUnobservedEarlyReturnAssumption() {
        for (userDeparture in listOf(false, true)) {
            val visibility = SessionVisibility()
            val shell = startedShell(visibility)
            visibility.selectPresentation("table")
            visibility.rendererOpening("table", deadlineMillis = 10_000)
            visibility.stopShell(shell, changingConfigurations = false, nowMillis = 100)
            visibility.rendererClosing("table", nowMillis = 200)
            visibility.selectPresentation(null)
            if (userDeparture) visibility.userLeavingShell(shell)
            else visibility.updateRenderer("table", 1, started = false, resumed = false, focused = false)
            assertState(visibility, 300, foreground = false, backgrounded = true, deadline = 3_200)

            visibility.rendererClosed("table", nowMillis = 400)
            assertState(visibility, 400, foreground = false, backgrounded = true)
        }
    }

    @Test
    fun expiredOpeningOrClosingCannotExtendAnUnobservedEarlyReturn() {
        for (validOpeningAtClose in listOf(false, true)) {
            val visibility = SessionVisibility()
            val shell = startedShell(visibility)
            visibility.selectPresentation("table")
            visibility.rendererOpening("table", deadlineMillis = 10_000)
            visibility.stopShell(shell, changingConfigurations = false, nowMillis = 100)
            visibility.selectPresentation(null)
            val closingTime = if (validOpeningAtClose) 200L else 10_000L
            visibility.rendererClosing("table", nowMillis = closingTime)
            assertState(visibility, closingTime, foreground = false, backgrounded = !validOpeningAtClose,
                deadline = closingTime + 3_000)
            assertState(visibility, closingTime + 3_000, foreground = false, backgrounded = true)
            assertFalse(visibility.rendererClosing("table", nowMillis = closingTime + 3_001))
            visibility.rendererClosed("table", nowMillis = closingTime + 3_002)
            assertState(visibility, closingTime + 3_002, foreground = false, backgrounded = true)
        }
    }

    @Test
    fun anActualShellReturnConsumesTheEarlyClosingAssumptionBeforeAnotherStop() {
        val visibility = SessionVisibility()
        val shell = startedShell(visibility)
        visibility.selectPresentation("table")
        visibility.rendererOpening("table", deadlineMillis = 10_000)
        visibility.stopShell(shell, changingConfigurations = false, nowMillis = 100)
        visibility.rendererClosing("table", nowMillis = 200)
        visibility.selectPresentation(null)
        visibility.updateShell(shell, started = true, resumed = false, focused = false)
        assertState(visibility, 300, foreground = false, backgrounded = false, deadline = 3_200)
        visibility.stopShell(shell, changingConfigurations = false, nowMillis = 400)
        assertState(visibility, 400, foreground = false, backgrounded = true, deadline = 3_200)
        visibility.rendererClosed("table", nowMillis = 500)
        assertState(visibility, 500, foreground = false, backgrounded = true)
    }

    @Test
    fun openingFromAnAlreadyStoppedShellCannotAssumeVisibility() {
        val visibility = SessionVisibility()
        visibility.attachShell(nowMillis = 0)
        visibility.selectPresentation("table")
        visibility.rendererOpening("table", deadlineMillis = 10_000)
        assertState(visibility, 100, foreground = false, backgrounded = true, shellSelected = false)

        visibility.updateRenderer("table", 1, started = true, resumed = false, focused = false)
        assertState(visibility, 200, foreground = false, backgrounded = false, shellSelected = false)
    }

    @Test
    fun userDepartureCancelsHandoffGraceAndDoesNotGrantInputBeforeAnActualReturn() {
        val visibility = SessionVisibility()
        val shell = startedShell(visibility)
        visibility.selectPresentation("table")
        visibility.rendererOpening("table", deadlineMillis = 10_000)
        visibility.stopShell(shell, changingConfigurations = false, nowMillis = 100)
        assertTrue(visibility.userLeavingShell(shell))
        assertState(visibility, 101, foreground = false, backgrounded = true, shellSelected = false)
        visibility.stopShell(shell, changingConfigurations = true, nowMillis = 200)
        assertState(visibility, 200, foreground = false, backgrounded = true, shellSelected = false)

        visibility.updateRenderer("table", 1, started = true, resumed = false, focused = false)
        assertState(visibility, 300, foreground = false, backgrounded = false, shellSelected = false)
        visibility.updateRenderer("table", 2, started = true, resumed = true, focused = true)
        assertState(visibility, 400, foreground = true, backgrounded = false, shellSelected = false)
    }

    @Test
    fun repeatedOrRetiringWindowInteractivityCannotUndoTheShellsUserDeparture() {
        val visibility = SessionVisibility()
        val shell = startedShell(visibility)
        visibility.selectPresentation("table")
        visibility.rendererOpening("table", deadlineMillis = 10_000)
        visibility.updateRenderer("table", 1, started = true, resumed = true, focused = true)
        visibility.rendererClosing("table", nowMillis = 100)
        visibility.selectPresentation(null)
        visibility.userLeavingShell(shell)

        visibility.updateShell(shell, started = true, resumed = true, focused = true)
        assertFalse(visibility.shellCanLaunch(shell))
        visibility.updateRenderer("table", 2, started = true, resumed = false, focused = false)
        visibility.updateRenderer("table", 3, started = true, resumed = true, focused = true)
        assertState(visibility, 200, foreground = false, backgrounded = false, deadline = 3_100)

        visibility.updateShell(shell, started = true, resumed = false, focused = false)
        visibility.updateShell(shell, started = true, resumed = true, focused = true)
        assertTrue(visibility.shellCanLaunch(shell))
        assertState(visibility, 300, foreground = true, backgrounded = false, deadline = 3_100)
    }

    @Test
    fun onlyTheControllerSelectedSurfaceCanOwnInput() {
        val visibility = SessionVisibility()
        val shell = startedShell(visibility)
        visibility.selectPresentation("table")
        visibility.rendererOpening("table", deadlineMillis = 10_000)
        visibility.updateRenderer("table", 1, started = true, resumed = true, focused = false)
        visibility.updateShell(shell, started = true, resumed = true, focused = true)
        assertState(visibility, 0, foreground = false, backgrounded = false, shellSelected = false)

        visibility.updateRenderer("table", 2, started = true, resumed = true, focused = true)
        visibility.updateShell(shell, started = true, resumed = false, focused = false)
        assertState(visibility, 10, foreground = true, backgrounded = false, shellSelected = false)
        visibility.selectPresentation(null)
        assertState(visibility, 20, foreground = false, backgrounded = false)
        visibility.updateShell(shell, started = true, resumed = true, focused = true)
        assertState(visibility, 30, foreground = true, backgrounded = false)
    }

    @Test
    fun configurationReplacementIgnoresEveryOldAttachmentCallbackInEitherOrder() {
        for (oldStopsFirst in listOf(false, true)) {
            val visibility = SessionVisibility()
            val old = startedShell(visibility)
            if (oldStopsFirst) {
                visibility.stopShell(old, changingConfigurations = true, nowMillis = 100)
                visibility.detachShell(old)
            }
            val replacement = visibility.attachShell(nowMillis = 200)
            val deadline = if (oldStopsFirst) 1_100L else 1_200L
            assertFalse(visibility.updateShell(old, started = true, resumed = true, focused = true))
            assertFalse(visibility.stopShell(old, changingConfigurations = true, nowMillis = 300))
            assertFalse(visibility.userLeavingShell(old))
            assertFalse(visibility.detachShell(old))
            assertFalse(visibility.shellCanLaunch(old))
            assertState(visibility, 300, foreground = false, backgrounded = false, deadline = deadline)

            visibility.updateShell(replacement, started = true, resumed = true, focused = false)
            assertState(visibility, 400, foreground = false, backgrounded = false)
            visibility.updateShell(replacement, started = true, resumed = true, focused = true)
            assertState(visibility, 500, foreground = true, backgrounded = false)
        }
    }

    @Test
    fun missingConfigurationReplacementExpiresWithoutRearmingOnAnotherEmptyAttachment() {
        val visibility = SessionVisibility()
        val old = startedShell(visibility)
        visibility.stopShell(old, changingConfigurations = true, nowMillis = 100)
        visibility.detachShell(old)
        visibility.attachShell(nowMillis = 200)
        visibility.attachShell(nowMillis = 500)
        assertState(visibility, 1_099, foreground = false, backgrounded = false, deadline = 1_100)
        assertState(visibility, 1_100, foreground = false, backgrounded = true)
        visibility.attachShell(nowMillis = 2_000)
        assertState(visibility, 2_000, foreground = false, backgrounded = true)
    }

    @Test
    fun closingImmediatelyDeniesRendererInputAndRetainsActualVisibilityUntilStopped() {
        val visibility = activeRenderer()
        assertTrue(visibility.rendererClosing("table", nowMillis = 100))
        assertState(visibility, 100, foreground = false, backgrounded = false,
            shellSelected = false, deadline = 3_100)
        visibility.updateRenderer("table", 2, started = true, resumed = true, focused = true)
        assertFalse(visibility.rendererClosing("table", nowMillis = 1_000))
        assertState(visibility, 1_000, foreground = false, backgrounded = false,
            shellSelected = false, deadline = 3_100)

        visibility.updateRenderer("table", 3, started = false, resumed = false, focused = false)
        assertState(visibility, 1_001, foreground = false, backgrounded = true,
            shellSelected = false, deadline = 3_100)
    }

    @Test
    fun deathOfAVisibleChildBridgesOneBoundedReturnGapWithoutAssumingShellInput() {
        val visibility = activeRenderer()
        visibility.rendererClosing("table", nowMillis = 100)
        visibility.selectPresentation(null)
        assertTrue(visibility.rendererClosed("table", nowMillis = 200))
        assertState(visibility, 200, foreground = false, backgrounded = false, deadline = 1_200)
        assertFalse(visibility.rendererClosed("table", nowMillis = 1_000))
        assertState(visibility, 1_199, foreground = false, backgrounded = false, deadline = 1_200)
        assertState(visibility, 1_200, foreground = false, backgrounded = true)

        val replacement = visibility.attachShell(nowMillis = 1_300)
        visibility.updateShell(replacement, started = true, resumed = true, focused = true)
        assertState(visibility, 1_300, foreground = true, backgrounded = false)
    }

    @Test
    fun aStoppedChildCannotRearmVisibilityWhenItsProcessLaterDies() {
        val visibility = activeRenderer()
        visibility.updateRenderer("table", 2, started = true, resumed = false, focused = false)
        assertState(visibility, 100, foreground = false, backgrounded = false, shellSelected = false)
        visibility.updateRenderer("table", 3, started = false, resumed = false, focused = false)
        assertState(visibility, 200, foreground = false, backgrounded = true, shellSelected = false)
        visibility.rendererClosing("table", nowMillis = 300)
        visibility.selectPresentation(null)
        visibility.rendererClosed("table", nowMillis = 400)
        assertState(visibility, 400, foreground = false, backgrounded = true)
    }

    @Test
    fun hungClosingVisibilityExpiresWithoutClaimingDeathOrAllowingAnotherLifetime() {
        val visibility = activeRenderer()
        visibility.rendererClosing("table", nowMillis = 100)
        visibility.selectPresentation(null)
        assertState(visibility, 3_099, foreground = false, backgrounded = false, deadline = 3_100)
        assertState(visibility, 3_100, foreground = false, backgrounded = true)

        assertFalse(visibility.rendererOpening("replacement", deadlineMillis = 10_000))
        assertFalse(visibility.rendererClosing("table", nowMillis = 4_000))
        assertTrue(visibility.updateRenderer("table", 2, started = true, resumed = true, focused = true))
        assertState(visibility, 4_000, foreground = false, backgrounded = true)
        assertTrue(visibility.rendererClosed("table", nowMillis = 4_100))
        assertState(visibility, 4_100, foreground = false, backgrounded = true)
        assertTrue(visibility.rendererOpening("replacement", deadlineMillis = 10_000))
    }

    @Test
    fun oldOrDuplicateNativeGenerationsCannotChangeTheCurrentWindowFacts() {
        val visibility = activeRenderer()
        assertTrue(visibility.updateRenderer("table", 7, started = true, resumed = true, focused = true))
        assertFalse(visibility.updateRenderer("table", 7, started = false, resumed = false, focused = false))
        assertFalse(visibility.updateRenderer("table", 6, started = false, resumed = false, focused = false))
        assertFalse(visibility.updateRenderer("other", 8, started = false, resumed = false, focused = false))
        assertState(visibility, 100, foreground = true, backgrounded = false, shellSelected = false)

        assertTrue(visibility.updateRenderer("table", 8, started = false, resumed = false, focused = false))
        assertFalse(visibility.updateRenderer("table", 7, started = true, resumed = true, focused = true))
        assertState(visibility, 200, foreground = false, backgrounded = true, shellSelected = false)
    }

    @Test
    fun lateClosingAndLifecycleCallbacksCannotTakeOverAReplacementPresentation() {
        val visibility = activeRenderer()
        visibility.rendererClosing("table", nowMillis = 100)
        visibility.rendererClosed("table", nowMillis = 200)
        visibility.selectPresentation("replacement")
        assertTrue(visibility.rendererOpening("replacement", deadlineMillis = 10_000))
        assertTrue(visibility.updateRenderer("replacement", 1, started = true, resumed = true, focused = true))

        assertFalse(visibility.rendererOpening("table", deadlineMillis = 10_000))
        assertFalse(visibility.updateRenderer("table", Long.MAX_VALUE, started = false, resumed = false, focused = false))
        assertFalse(visibility.rendererClosing("table", nowMillis = 300))
        assertFalse(visibility.rendererClosed("table", nowMillis = 300))
        assertState(visibility, 300, foreground = true, backgrounded = false, shellSelected = false)
    }

    @Test
    fun transitionDeadlinesSaturateWithoutOverflowingIntoImmediateBackground() {
        val visibility = SessionVisibility()
        val shell = startedShell(visibility)
        visibility.stopShell(shell, changingConfigurations = true, nowMillis = Long.MAX_VALUE - 100)
        assertState(visibility, Long.MAX_VALUE - 1, foreground = false, backgrounded = false,
            deadline = Long.MAX_VALUE)
        assertState(visibility, Long.MAX_VALUE, foreground = false, backgrounded = true)
    }

    private fun startedShell(visibility: SessionVisibility): Long = visibility.attachShell(nowMillis = 0).also {
        visibility.updateShell(it, started = true, resumed = true, focused = true)
    }

    private fun activeRenderer(): SessionVisibility = SessionVisibility().also { visibility ->
        val shell = startedShell(visibility)
        visibility.selectPresentation("table")
        visibility.rendererOpening("table", deadlineMillis = 10_000)
        visibility.updateRenderer("table", 1, started = true, resumed = true, focused = true)
        visibility.stopShell(shell, changingConfigurations = false, nowMillis = 0)
    }

    private fun assertState(
        visibility: SessionVisibility,
        now: Long,
        foreground: Boolean,
        backgrounded: Boolean,
        shellSelected: Boolean = true,
        deadline: Long? = null,
    ) {
        assertEquals(SessionVisibility.Snapshot(foreground, backgrounded, shellSelected, deadline),
            visibility.snapshot(now))
    }
}
