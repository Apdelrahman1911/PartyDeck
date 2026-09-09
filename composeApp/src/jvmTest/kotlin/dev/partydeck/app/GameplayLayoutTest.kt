package dev.partydeck.app

import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Surface
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.toAwtImage
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.test.ExperimentalTestApi
import androidx.compose.ui.test.SemanticsNodeInteraction
import androidx.compose.ui.test.assertCountEquals
import androidx.compose.ui.test.assertIsEnabled
import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.assertIsNotEnabled
import androidx.compose.ui.test.assertIsOn
import androidx.compose.ui.test.assertIsOff
import androidx.compose.ui.test.captureToImage
import androidx.compose.ui.test.hasContentDescription
import androidx.compose.ui.test.isDisplayed
import androidx.compose.ui.test.onNodeWithTag
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.test.performClick
import androidx.compose.ui.test.performScrollTo
import androidx.compose.ui.test.v2.runSkikoComposeUiTest
import androidx.compose.ui.unit.Density
import androidx.compose.ui.unit.dp
import dev.partydeck.app.controller.PendingAction
import dev.partydeck.app.ui.game.GameplayScreen
import dev.partydeck.app.ui.shell.ScreenHeader
import dev.partydeck.app.ui.shell.ShellIconAction
import dev.partydeck.app.ui.theme.PartyDeckColors
import dev.partydeck.app.ui.theme.PartyDeckTheme
import dev.partydeck.core.CardRank
import dev.partydeck.core.GameAction
import dev.partydeck.core.GameDecision
import dev.partydeck.core.GamePhase
import dev.partydeck.core.LastLightEngine
import dev.partydeck.core.PlayerIdentity
import dev.partydeck.resources.Res
import dev.partydeck.resources.icon_info
import dev.partydeck.resources.icon_settings
import java.io.File
import javax.imageio.ImageIO
import kotlin.random.Random
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFalse
import kotlin.test.assertTrue
import kotlin.time.Duration.Companion.seconds

/** Exercises real projected hands at small viewport sizes; all fixture outcomes use the engine. */
@OptIn(ExperimentalTestApi::class)
class GameplayLayoutTest {
    @Test
    fun fifthCardAndPrivateHandControlsWorkOnNarrowPhone() = qualifyGame(360, 640, 1f, "game-phone")

    @Test
    fun handAndResultsRemainUsableAtLargeText() = qualifyGame(320, 740, 2f, "game-large-text")

    @Test
    fun handAndResultsRemainUsableOnShortLandscapePhone() = qualifyGame(844, 390, 1f, "game-landscape")

    private fun qualifyGame(width: Int, height: Int, scale: Float, prefix: String) = runSkikoComposeUiTest(
        size = Size(width.toFloat(), height.toFloat()),
        density = Density(1f, scale),
        testTimeout = 60.seconds,
    ) {
        val engine = LastLightEngine(Random(77))
        var authority = engine.start(players())
        val viewer = authority.turnPlayerId!!
        var view by mutableStateOf(engine.viewFor(authority, viewer))
        var privacyEpoch by mutableStateOf(0L)
        var canSend by mutableStateOf(true)
        var pending by mutableStateOf<PendingAction?>(null)
        var playedCards: List<String> = emptyList()
        var plays = 0
        var continued = false
        var rematched = false
        setContent {
            GameTestFrame {
                    GameplayScreen(
                        view = view,
                        isHost = true,
                        canSendAction = canSend,
                        pendingAction = pending,
                        privateContentVisible = true,
                        canAdvanceRound = true,
                        canReturnToLobby = true,
                        onPlay = { playedCards = it; plays++ },
                        onChallenge = {},
                        onNextRound = { continued = true },
                        onReturnToLobby = { rematched = true },
                        privacyEpoch = privacyEpoch,
                    )
            }
        }
        fun capture(suffix: String) {
            waitForIdle()
            val file = File("build/ui-snapshots/$prefix-$suffix.png").apply { parentFile.mkdirs() }
            ImageIO.write(onNodeWithTag("game-snapshot").captureToImage().toAwtImage(), "png", file)
        }

        onNodeWithTag("game-card-0").assertDoesNotExist()
        onAllNodes(hasContentDescription("Card ", substring = true)).assertCountEquals(0)
        capture("concealed")
        onNodeWithTag("game-reveal-hand").bringIntoView().performClick()
        onNodeWithTag("game-card-0").bringIntoView()
        capture("hand")
        onNodeWithTag("game-card-4").performScrollTo().assertIsDisplayed().performClick()
        onNodeWithTag("game-card-4").assertIsOn()
        capture("selected")
        onNodeWithTag("game-play").bringIntoView().assertIsEnabled().performClick()
        assertEquals(listOf(view.yourHand[4].id), playedCards)
        assertEquals(1, plays)
        runOnUiThread { canSend = false; pending = PendingAction.PLAY_CARDS }
        onNodeWithTag("game-play").assertIsNotEnabled().performClick()
        assertEquals(1, plays, "A pending play must not be submitted twice")
        runOnUiThread { canSend = true; pending = null }
        onNodeWithTag("game-hide-hand").bringIntoView().performClick()
        onNodeWithTag("game-card-0").assertDoesNotExist()
        onAllNodes(hasContentDescription("Card ", substring = true)).assertCountEquals(0)
        onNodeWithTag("game-reveal-hand").bringIntoView().performClick()
        // The UI must conceal even when a quick background/foreground cycle is conflated.
        runOnUiThread { privacyEpoch++ }
        onNodeWithTag("game-card-0").assertDoesNotExist()
        onAllNodes(hasContentDescription("Card ", substring = true)).assertCountEquals(0)

        authority = (engine.apply(authority, GameAction.Play(viewer, listOf(view.yourHand.first().id))) as GameDecision.Applied).state
        authority = (engine.apply(authority, GameAction.Challenge(authority.turnPlayerId!!)) as GameDecision.Applied).state
        runOnUiThread { view = engine.viewFor(authority, viewer) }
        capture("round-result")
        onNodeWithTag("game-next-round").bringIntoView().performClick()
        assertEquals(true, continued)

        var transitions = 0
        while (authority.phase != GamePhase.FINISHED) {
            check(transitions++ < 150) { "Fixture match failed to finish within its rule bound" }
            authority = when (authority.phase) {
                GamePhase.ROUND_ENDED -> (engine.advanceRound(authority) as GameDecision.Applied).state
                GamePhase.PLAYING -> {
                    val actor = authority.turnPlayerId!!
                    val actorView = engine.viewFor(authority, actor)
                    val action = if (actorView.availableActions.canChallenge) GameAction.Challenge(actor)
                    else GameAction.Play(actor, listOf(actorView.yourHand.first().id))
                    (engine.apply(authority, action) as GameDecision.Applied).state
                }
                GamePhase.FINISHED -> authority
            }
        }
        runOnUiThread { view = engine.viewFor(authority, viewer) }
        capture("winner")
        onNodeWithTag("game-rematch").bringIntoView().performClick()
        assertEquals(true, rematched)
    }

    @Test
    fun forcedChallengeKeepsOneClearActionAndGatesPendingRequests() = runSkikoComposeUiTest(
        size = Size(360f, 640f), density = Density(1f), testTimeout = 45.seconds,
    ) {
        val engine = LastLightEngine(Random(18))
        var authority = engine.start(players().take(2))
        for (count in listOf(3, 3, 2)) {
            val actor = authority.turnPlayerId!!
            val cards = engine.viewFor(authority, actor).yourHand.take(count).map { it.id }
            authority = (engine.apply(authority, GameAction.Play(actor, cards)) as GameDecision.Applied).state
        }
        val view = engine.viewFor(authority, authority.turnPlayerId)
        assertTrue(view.forcedChallenge)
        assertTrue(view.availableActions.canChallenge)
        assertFalse(view.availableActions.canPlay)
        var canSend by mutableStateOf(true)
        var pending by mutableStateOf<PendingAction?>(null)
        var challenges = 0
        setContent {
            GameTestFrame {
                GameplayScreen(
                    view = view, isHost = false, canSendAction = canSend, pendingAction = pending,
                    privateContentVisible = true, canAdvanceRound = false, canReturnToLobby = false,
                    onPlay = { error("A forced challenge must never submit cards") },
                    onChallenge = { challenges++ }, onNextRound = {}, onReturnToLobby = {},
                )
            }
        }
        onNodeWithTag("game-play").assertDoesNotExist()
        onNodeWithTag("game-card-0").assertDoesNotExist()
        onNodeWithTag("game-challenge").bringIntoView().assertIsEnabled()
        val file = File("build/ui-snapshots/game-forced-challenge.png").apply { parentFile.mkdirs() }
        ImageIO.write(onNodeWithTag("game-snapshot").captureToImage().toAwtImage(), "png", file)
        runOnUiThread { canSend = false; pending = PendingAction.CHALLENGE }
        onNodeWithTag("game-challenge").assertIsNotEnabled().performClick()
        assertEquals(0, challenges)
        runOnUiThread { canSend = true; pending = null }
        onNodeWithTag("game-challenge").performClick()
        assertEquals(1, challenges)
    }

    @Test
    fun revealedWildAndMismatchingRankExplainTheBluff() = runSkikoComposeUiTest(
        size = Size(360f, 640f), density = Density(1f), testTimeout = 45.seconds,
    ) {
        val fixture = (1..100).firstNotNullOf { seed ->
            val engine = LastLightEngine(Random(seed))
            val initial = engine.start(players())
            val claimant = initial.turnPlayerId!!
            val view = engine.viewFor(initial, claimant)
            val wild = view.yourHand.firstOrNull { it.rank == CardRank.WILD }
            val mismatch = view.yourHand.firstOrNull { it.rank != CardRank.WILD && it.rank != view.tableRank }
            if (wild == null || mismatch == null) null else {
                val played = (engine.apply(initial, GameAction.Play(claimant, listOf(wild.id, mismatch.id))) as GameDecision.Applied).state
                val result = (engine.apply(played, GameAction.Challenge(played.turnPlayerId!!)) as GameDecision.Applied).state
                engine.viewFor(result, claimant)
            }
        }
        assertFalse(fixture.roundOutcome!!.truthful)
        setContent {
            GameTestFrame {
                GameplayScreen(
                    view = fixture, isHost = false, canSendAction = true, pendingAction = null,
                    privateContentVisible = true, canAdvanceRound = false, canReturnToLobby = false,
                    onPlay = {}, onChallenge = {}, onNextRound = {}, onReturnToLobby = {},
                )
            }
        }
        onNodeWithText("Bluff caught.").assertExists()
        onAllNodes(hasContentDescription("Wild · always matches", substring = true)).assertCountEquals(1)
        onAllNodes(hasContentDescription("Doesn’t match", substring = true)).assertCountEquals(1)
        val file = File("build/ui-snapshots/game-bluff-with-wild.png").apply { parentFile.mkdirs() }
        ImageIO.write(onNodeWithTag("game-snapshot").captureToImage().toAwtImage(), "png", file)
    }

    @Test
    fun normalChoiceSupportsThreeCardsAndAReadableLongClaimant() = runSkikoComposeUiTest(
        size = Size(360f, 640f), density = Density(1f), testTimeout = 45.seconds,
    ) {
        val fixture = (1..100).firstNotNullOf { seed ->
            val engine = LastLightEngine(Random(seed))
            val initial = engine.start(players())
            if (initial.turnPlayerId != "e") null else {
                val openingHand = engine.viewFor(initial, "e").yourHand
                val played = (engine.apply(initial, GameAction.Play("e", listOf(openingHand.first().id))) as GameDecision.Applied).state
                engine.viewFor(played, played.turnPlayerId)
            }
        }
        assertTrue(fixture.availableActions.canPlay && fixture.availableActions.canChallenge)
        var canSend by mutableStateOf(true)
        var pending by mutableStateOf<PendingAction?>(null)
        var submitted = emptyList<String>()
        var challenges = 0
        setContent {
            GameTestFrame {
                GameplayScreen(
                    view = fixture, isHost = true, canSendAction = canSend, pendingAction = pending,
                    privateContentVisible = true, canAdvanceRound = false, canReturnToLobby = false,
                    onPlay = { submitted = it; canSend = false; pending = PendingAction.PLAY_CARDS },
                    onChallenge = { challenges++ }, onNextRound = {}, onReturnToLobby = {},
                )
            }
        }
        fun capture(suffix: String) {
            val file = File("build/ui-snapshots/game-$suffix.png").apply { parentFile.mkdirs() }
            ImageIO.write(onNodeWithTag("game-snapshot").captureToImage().toAwtImage(), "png", file)
        }
        onNodeWithTag("game-reveal-hand").bringIntoView().performClick()
        onNodeWithTag("game-challenge").assertIsEnabled()
        onNodeWithTag("game-play").assertIsNotEnabled()
        capture("choice-long-name")
        for (index in 0..2) onNodeWithTag("game-card-$index").performScrollTo().performClick().assertIsOn()
        capture("three-selected")
        onNodeWithTag("game-card-3").performScrollTo().performClick().assertIsOff()
        onNodeWithText("Choose up to 3 cards.").assertExists()
        capture("selection-limit")
        onNodeWithTag("game-play").bringIntoView().performClick()
        assertEquals(fixture.yourHand.take(3).map { it.id }, submitted)
        onNodeWithTag("game-challenge").assertIsNotEnabled().performClick()
        assertEquals(0, challenges, "Play and Challenge cannot both submit during the same pending action")
    }

    private fun players() = listOf(
        PlayerIdentity("a", "Guest"), PlayerIdentity("b", "Guest"), PlayerIdentity("c", "Mina"),
        PlayerIdentity("d", "Ibrahim"), PlayerIdentity("e", "Alexandria Longname"), PlayerIdentity("f", "Noor"),
    )
}

private fun SemanticsNodeInteraction.bringIntoView(): SemanticsNodeInteraction {
    if (!isDisplayed()) performScrollTo()
    return assertIsDisplayed()
}

/** Same header footprint as the real session route; captures include the complete logical viewport. */
@Composable
private fun GameTestFrame(content: @Composable () -> Unit) {
    PartyDeckTheme(reduceMotion = true) {
        Surface(Modifier.fillMaxSize().testTag("game-snapshot"), color = PartyDeckColors.Ink) {
            Column(Modifier.fillMaxSize()) {
                ScreenHeader("Last Light", {}, Modifier.padding(horizontal = 16.dp, vertical = 4.dp)) {
                    ShellIconAction(Res.drawable.icon_info, "How to play", {})
                    ShellIconAction(Res.drawable.icon_settings, "Settings", {})
                }
                Box(Modifier.weight(1f)) { content() }
            }
        }
    }
}
