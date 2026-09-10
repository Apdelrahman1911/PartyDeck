package dev.partydeck.app

import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
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
import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.assertIsEnabled
import androidx.compose.ui.test.assertIsNotEnabled
import androidx.compose.ui.test.assertIsOff
import androidx.compose.ui.test.assertIsOn
import androidx.compose.ui.test.captureToImage
import androidx.compose.ui.test.onNodeWithTag
import androidx.compose.ui.test.performClick
import androidx.compose.ui.test.performScrollTo
import androidx.compose.ui.test.v2.runSkikoComposeUiTest
import androidx.compose.ui.unit.Density
import dev.partydeck.app.controller.AppScreen
import dev.partydeck.app.controller.AppUiState
import dev.partydeck.app.controller.ConnectionStatus
import dev.partydeck.app.controller.ConnectionUiState
import dev.partydeck.app.controller.GameplayPresentation
import dev.partydeck.app.controller.GameplayPresentationState
import dev.partydeck.app.controller.PendingAction
import dev.partydeck.app.controller.PresentationLifecycle
import dev.partydeck.app.controller.SessionMode
import dev.partydeck.app.ui.shell.GameplayPresentationPicker
import dev.partydeck.app.ui.theme.PartyDeckColors
import dev.partydeck.app.ui.theme.PartyDeckTheme
import dev.partydeck.core.LastLightEngine
import dev.partydeck.core.PlayerIdentity
import dev.partydeck.session.LobbyPlayer
import dev.partydeck.session.SessionPhase
import dev.partydeck.session.SessionView
import java.io.File
import javax.imageio.ImageIO
import kotlin.random.Random
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertSame
import kotlin.time.Duration.Companion.seconds

/** Shell state fixtures with real safe core views; these do not instantiate or qualify Godot. */
@OptIn(ExperimentalTestApi::class)
class PresentationLayoutTest {
    @Test
    fun pickerOffersOnlyAvailableStylesAtTwoHundredPercentText() = runSkikoComposeUiTest(
        size = Size(320f, 740f), density = Density(1f, 2f), testTimeout = 45.seconds,
    ) {
        var state by mutableStateOf(GameplayPresentationState())
        val choices = mutableListOf<GameplayPresentation>()
        setContent {
            PresentationTestFrame {
                GameplayPresentationPicker(
                    state = state,
                    onSelect = { choices += it; state = state.copy(selected = it) },
                )
            }
        }
        onNodeWithTag("presentation-picker").assertDoesNotExist()
        runOnUiThread {
            state = state.copy(available = setOf(GameplayPresentation.COMPOSE, GameplayPresentation.GODOT_2D))
        }
        onNodeWithTag("presentation-picker").assertIsDisplayed().performClick()
        onNodeWithTag("presentation-choice-godot_3d").assertDoesNotExist()
        onNodeWithTag("presentation-choice-compose").performScrollTo().assertIsDisplayed()
        onNodeWithTag("presentation-choice-godot_2d").performScrollTo().assertIsDisplayed()
        onNodeWithTag("presentation-options").presentationSnapshot("picker-two-available-large-text")
        onNodeWithTag("presentation-choice-godot_2d").performClick()
        assertEquals(listOf(GameplayPresentation.GODOT_2D), choices)

        runOnUiThread { state = state.copy(available = GameplayPresentation.entries.toSet()) }
        onNodeWithTag("presentation-picker").performClick()
        onNodeWithTag("presentation-choice-godot_3d").performScrollTo().assertIsDisplayed()
        onNodeWithTag("presentation-options").presentationSnapshot("picker-three-available-large-text")
        onNodeWithTag("presentation-choice-godot_3d").performClick()
        assertEquals(listOf(GameplayPresentation.GODOT_2D, GameplayPresentation.GODOT_3D), choices)
        onNodeWithTag("presentation-picker").performClick()
        onNodeWithTag("presentation-choice-compose").performScrollTo().assertIsDisplayed().performClick()
        assertEquals(GameplayPresentation.COMPOSE, choices.last())
    }

    @Test
    fun fallbackPreservesSessionAndPendingWhileConcealingHandAndClearingSelection() = runSkikoComposeUiTest(
        size = Size(320f, 740f), density = Density(1f, 2f), testTimeout = 60.seconds,
    ) {
        var state by mutableStateOf(gameFixture())
        val session = state.session!!
        var useStandardRequests = 0
        var plays = 0
        setContent {
            PresentationTestFrame {
                Column(Modifier.fillMaxSize()) {
                    GameplayPresentationPicker(
                        state.presentation,
                        onSelect = {
                            state = state.copy(
                                privacyEpoch = state.privacyEpoch + 1,
                                presentation = state.presentation.copy(
                                    selected = it, lifecycle = PresentationLifecycle.OPENING,
                                    presentationId = "ui-state-fixture",
                                ),
                            )
                        },
                        modifier = Modifier.fillMaxWidth(),
                    )
                    SessionGameSurface(
                        state = state,
                        onUseCompose = {
                            useStandardRequests++
                            state = state.copy(
                                privacyEpoch = state.privacyEpoch + 1,
                                presentation = state.presentation.copy(
                                    selected = GameplayPresentation.COMPOSE,
                                    lifecycle = PresentationLifecycle.CLOSING,
                                ),
                            )
                        },
                        onPlay = { plays++ }, onChallenge = {}, onNextRound = {}, onReturnToLobby = {},
                        modifier = Modifier.weight(1f).fillMaxWidth(),
                    )
                }
            }
        }
        onNodeWithTag("game-reveal-hand").performScrollTo().performClick()
        onNodeWithTag("game-card-0").performScrollTo().performClick().assertIsOn()
        onNodeWithTag("game-play").performScrollTo().assertIsEnabled()

        onNodeWithTag("presentation-picker").performClick()
        onNodeWithTag("presentation-choice-godot_2d").performScrollTo().performClick()
        onNodeWithTag("game-table").assertDoesNotExist()
        onNodeWithTag("game-card-0").assertDoesNotExist()
        onNodeWithTag("presentation-use-standard").performScrollTo().assertIsDisplayed().assertIsEnabled()
        onNodeWithTag("presentation-snapshot-root").presentationSnapshot("opening-large-text")
        runOnUiThread {
            state = state.copy(
                pendingAction = PendingAction.PLAY_CARDS,
                presentation = state.presentation.copy(lifecycle = PresentationLifecycle.ACTIVE),
            )
        }
        onNodeWithTag("game-table").assertDoesNotExist()
        onNodeWithTag("game-card-0").assertDoesNotExist()
        onNodeWithTag("presentation-use-standard").performScrollTo().assertIsDisplayed().performClick()
        assertEquals(1, useStandardRequests)
        assertSame(session, state.session, "Changing the presentation must retain the session projection")
        assertEquals(PendingAction.PLAY_CARDS, state.pendingAction)
        onNodeWithTag("presentation-cover").assertDoesNotExist()
        onNodeWithTag("game-card-0").assertDoesNotExist()
        onNodeWithTag("game-reveal-hand").performScrollTo().assertIsDisplayed()
        onNodeWithTag("presentation-snapshot-root").presentationSnapshot("fallback-concealed-large-text")
        onNodeWithTag("game-play").performScrollTo().assertIsNotEnabled().performClick()
        assertEquals(0, plays)
        onNodeWithTag("game-reveal-hand").performScrollTo().performClick()
        onNodeWithTag("game-card-0").performScrollTo().assertIsOff()
        runOnUiThread {
            state = state.copy(
                pendingAction = null,
                presentation = state.presentation.copy(lifecycle = PresentationLifecycle.COMPOSE, presentationId = null),
            )
        }
        onNodeWithTag("game-card-0").assertIsOff()
        onNodeWithTag("game-play").performScrollTo().assertIsNotEnabled()
        onNodeWithTag("game-card-0").performScrollTo().performClick()
        onNodeWithTag("game-play").performScrollTo().assertIsEnabled().performClick()
        assertEquals(1, plays, "A fresh selection is required after returning to the standard table")
    }
}

@Composable
private fun PresentationTestFrame(content: @Composable () -> Unit) {
    PartyDeckTheme(reduceMotion = true) {
        Surface(Modifier.fillMaxSize().testTag("presentation-snapshot-root"), color = PartyDeckColors.Ink) {
            content()
        }
    }
}

private val presentationSnapshots = File("build/ui-snapshots/presentation-${System.currentTimeMillis()}")

private fun SemanticsNodeInteraction.presentationSnapshot(name: String) {
    val output = File(presentationSnapshots, "$name.png").apply { parentFile.mkdirs() }
    check(!output.exists()) { "Preserve previous screenshot bytes" }
    ImageIO.write(captureToImage().toAwtImage(), "png", output)
}

private fun gameFixture(): AppUiState {
    val roster = listOf("Ari", "Moxie", "Pip", "Orbit").mapIndexed { index, name ->
        PlayerIdentity("seat-$index", name)
    }
    val engine = LastLightEngine(Random(2))
    val authority = engine.start(roster)
    val viewer = authority.turnPlayerId!!
    return AppUiState(
        screen = AppScreen.SESSION,
        connection = ConnectionUiState(ConnectionStatus.CONNECTED, SessionMode.PRACTICE),
        presentation = GameplayPresentationState(available = GameplayPresentation.entries.toSet()),
        session = SessionView(
            sessionId = "presentation-ui-fixture", revision = 0,
            selfPlayerId = viewer, hostPlayerId = viewer, phase = SessionPhase.GAME,
            players = roster.map { LobbyPlayer(it.id, it.displayName, isReady = true, isConnected = true) },
            game = engine.viewFor(authority, viewer),
        ),
    )
}
