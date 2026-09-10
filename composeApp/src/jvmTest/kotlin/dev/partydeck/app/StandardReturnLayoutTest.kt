package dev.partydeck.app

import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.material3.Surface
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.toAwtImage
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.semantics.SemanticsProperties
import androidx.compose.ui.test.ExperimentalTestApi
import androidx.compose.ui.test.SemanticsMatcher
import androidx.compose.ui.test.assertCountEquals
import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.assertIsEnabled
import androidx.compose.ui.test.captureToImage
import androidx.compose.ui.test.getBoundsInRoot
import androidx.compose.ui.test.getUnclippedBoundsInRoot
import androidx.compose.ui.test.hasContentDescription
import androidx.compose.ui.test.onNodeWithTag
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.test.v2.runSkikoComposeUiTest
import androidx.compose.ui.unit.Density
import androidx.compose.ui.unit.dp
import dev.partydeck.app.controller.AppScreen
import dev.partydeck.app.controller.AppUiState
import dev.partydeck.app.controller.ConnectionStatus
import dev.partydeck.app.controller.ConnectionUiState
import dev.partydeck.app.controller.GameplayPresentation
import dev.partydeck.app.controller.GameplayPresentationState
import dev.partydeck.app.controller.PresentationLifecycle
import dev.partydeck.app.controller.SessionMode
import dev.partydeck.app.ui.theme.PartyDeckColors
import dev.partydeck.app.ui.theme.PartyDeckTheme
import dev.partydeck.core.GameAction
import dev.partydeck.core.GameDecision
import dev.partydeck.core.LastLightEngine
import dev.partydeck.core.PlayerIdentity
import dev.partydeck.session.LobbyPlayer
import dev.partydeck.session.SessionPhase
import dev.partydeck.session.SessionView
import java.io.File
import java.nio.file.Files
import javax.imageio.ImageIO
import kotlin.random.Random
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertTrue
import kotlin.time.Duration.Companion.seconds

/**
 * Passive Compose layout checks at the original return's game-content size. These render safe
 * engine projections; they do not instantiate Godot or qualify Android held-input behavior.
 */
@OptIn(ExperimentalTestApi::class)
class StandardReturnLayoutTest {
    @Test
    fun freshLargeTextTableShowsTheWholeConcealedHandControlWithoutScrolling() =
        qualifyConcealedControl(returnFromEmbedded = false)

    @Test
    fun standardReturnShowsTheWholeConcealedHandControlWithoutScrolling() =
        qualifyConcealedControl(returnFromEmbedded = true)

    private fun qualifyConcealedControl(returnFromEmbedded: Boolean) = runSkikoComposeUiTest(
        size = Size(411f, 662f),
        density = Density(1f, 2f),
        testTimeout = 45.seconds,
    ) {
        var state by mutableStateOf(roundTwoClaimFixture())
        setContent {
            PartyDeckTheme(reduceMotion = true) {
                Surface(
                    modifier = Modifier.fillMaxSize().testTag("standard-return-snapshot"),
                    color = PartyDeckColors.Ink,
                ) {
                    SessionGameSurface(
                        state = state,
                        onUseCompose = {},
                        onPlay = {}, onChallenge = {}, onNextRound = {}, onReturnToLobby = {},
                        modifier = Modifier.fillMaxSize(),
                    )
                }
            }
        }
        if (returnFromEmbedded) {
            onNodeWithTag("game-table").assertExists()
            runOnUiThread {
                state = state.copy(
                    privacyEpoch = state.privacyEpoch + 1,
                    presentation = state.presentation.copy(
                        selected = GameplayPresentation.GODOT_2D,
                        lifecycle = PresentationLifecycle.ACTIVE,
                        presentationId = "standard-return-layout-fixture",
                    ),
                )
            }
            onNodeWithTag("presentation-cover").assertExists()
            onNodeWithTag("game-table").assertDoesNotExist()
            runOnUiThread {
                state = state.copy(
                    privacyEpoch = state.privacyEpoch + 1,
                    presentation = state.presentation.copy(
                        selected = GameplayPresentation.COMPOSE,
                        lifecycle = PresentationLifecycle.CLOSING,
                    ),
                )
            }
            onNodeWithTag("presentation-cover").assertDoesNotExist()
        }
        waitForIdle()
        val stage = if (returnFromEmbedded) "returned-concealed" else "fresh-concealed"
        val directory = File("build/ui-snapshots").apply { mkdirs() }
        val output = Files.createTempDirectory(directory.toPath(), "standard-return-font2-")
            .resolve("$stage.png").toFile()
        // Keep the original rendered diagnostic even when a following visibility assertion fails.
        check(ImageIO.write(
            onNodeWithTag("standard-return-snapshot").captureToImage().toAwtImage(), "png", output,
        ))

        onNodeWithText("Your turn").assertIsDisplayed()
        onNodeWithText("THE LAST CLAIM").assertIsDisplayed()
        onNodeWithText("Round 1 reveal").assertExists()
        onAllNodes(
            SemanticsMatcher("private hand card node") {
                it.config.contains(SemanticsProperties.TestTag) &&
                    it.config[SemanticsProperties.TestTag].startsWith("game-card-")
            },
            useUnmergedTree = true,
        ).assertCountEquals(0)
        onAllNodes(hasContentDescription("Card ", substring = true), useUnmergedTree = true)
            .assertCountEquals(0)

        val viewport = onNodeWithTag("game-table").getUnclippedBoundsInRoot()
        assertEquals(411.dp, viewport.right - viewport.left)
        assertEquals(662.dp, viewport.bottom - viewport.top)
        val reveal = onNodeWithTag("game-reveal-hand").assertIsEnabled()
        val fullBounds = reveal.getUnclippedBoundsInRoot()
        val clippedBounds = reveal.getBoundsInRoot()
        assertTrue(
            fullBounds.right - fullBounds.left >= 48.dp && fullBounds.bottom - fullBounds.top >= 56.dp,
            "$stage: Reveal must retain a 48dp touch width and its existing 56dp minimum height: $fullBounds",
        )
        assertTrue(
            fullBounds.left >= viewport.left && fullBounds.top >= viewport.top &&
                fullBounds.right <= viewport.right && fullBounds.bottom <= viewport.bottom,
            "$stage: the entire Reveal must be visible before scrolling: $fullBounds in $viewport",
        )
        assertEquals(fullBounds, clippedBounds, "$stage: Reveal must not be clipped by an ancestor")
        reveal.assertIsDisplayed()
    }
}

/** Reach round two and a new pending claim through real rules; only the recipient view reaches UI. */
private fun roundTwoClaimFixture(): AppUiState {
    val roster = listOf("Ari", "Moxie", "Pip", "Orbit").mapIndexed { index, name ->
        PlayerIdentity("seat-$index", name)
    }
    val engine = LastLightEngine(Random(2))
    var authority = engine.start(roster)
    fun playOneCard() {
        val actor = checkNotNull(authority.turnPlayerId)
        val card = engine.viewFor(authority, actor).yourHand.first()
        authority = (engine.apply(authority, GameAction.Play(actor, listOf(card.id))) as GameDecision.Applied).state
    }
    playOneCard()
    authority = (engine.apply(
        authority, GameAction.Challenge(checkNotNull(authority.turnPlayerId)),
    ) as GameDecision.Applied).state
    authority = (engine.advanceRound(authority) as GameDecision.Applied).state
    playOneCard()
    val viewer = checkNotNull(authority.turnPlayerId)
    val view = engine.viewFor(authority, viewer)
    assertEquals(2, view.roundNumber)
    assertEquals(1, view.roundOutcome?.roundNumber)
    assertEquals(1, view.latestClaim?.cardCount)
    assertEquals(5, view.yourHand.size)
    assertTrue(view.availableActions.canPlay && view.availableActions.canChallenge && !view.forcedChallenge)
    return AppUiState(
        screen = AppScreen.SESSION,
        connection = ConnectionUiState(ConnectionStatus.CONNECTED, SessionMode.PRACTICE),
        presentation = GameplayPresentationState(available = GameplayPresentation.entries.toSet()),
        session = SessionView(
            sessionId = "standard-return-layout-fixture", revision = 0,
            selfPlayerId = viewer, hostPlayerId = viewer, phase = SessionPhase.GAME,
            players = roster.map { LobbyPlayer(it.id, it.displayName, isReady = true, isConnected = true) },
            game = view,
        ),
    )
}
