@file:OptIn(kotlinx.coroutines.ExperimentalCoroutinesApi::class)

package dev.partydeck.app.controller

import dev.partydeck.core.GamePhase
import dev.partydeck.games.EmbeddedGameFactory
import dev.partydeck.games.EmbeddedGameSession
import dev.partydeck.games.EngineCommand
import dev.partydeck.games.EngineEvent
import dev.partydeck.games.EngineEventBody
import dev.partydeck.games.EngineLaunch
import dev.partydeck.games.GameId
import dev.partydeck.godot.bridge.LastLightWireCodec
import dev.partydeck.godot.bridge.PresentationPreferences
import dev.partydeck.godot.bridge.RendererIntent
import dev.partydeck.transport.LanTransport
import dev.partydeck.transport.LanTransportFactory
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.channels.Channel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.receiveAsFlow
import kotlinx.coroutines.test.TestScope
import kotlinx.coroutines.test.advanceTimeBy
import kotlinx.coroutines.test.runCurrent
import kotlinx.coroutines.test.runTest
import kotlin.random.Random
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFalse
import kotlin.test.assertNotNull
import kotlin.test.assertNull
import kotlin.test.assertTrue
import kotlin.test.fail

/** Tests shell sound requests, not native playback or physical network delivery. */
class MobileCardPlayFeedbackTest {
    @Test
    fun acceptedRendererPlayRequestsOneShellCueAndDuplicateInputsStaySilent() = runTest {
        val fixture = Fixture(backgroundScope)
        try {
            fixture.controller.startPractice()
            runCurrent()
            reachOwnPlay(fixture)
            val native = openThreeD(fixture)
            val before = assertNotNull(fixture.controller.state.value.session)
            val card = assertNotNull(before.game).yourHand.first().id
            val revision = native.latestView().revision
            fixture.feedback.requests.clear()

            native.intent(RendererIntent.Play(listOf(card)), revision)
            native.intent(RendererIntent.Play(listOf(card)), revision)
            runCurrent()

            assertEquals(before.revision + 1, fixture.controller.state.value.session?.revision)
            assertEquals(listOf(FeedbackCue.CARD_PLAY), fixture.feedback.requests.map { it.cue })
            assertTrue(fixture.feedback.requests.single().settings.soundEnabled)
            assertFalse(native.preferences.soundEnabled, "The embedded renderer must not duplicate shell audio")

            native.intent(RendererIntent.Play(listOf(card)), revision)
            fixture.controller.refreshPresentationLifecycle(native.launch.presentationId)
            runCurrent()
            assertEquals(1, fixture.feedback.requests.size, "Rejected input and projection refresh are silent")
        } finally {
            fixture.controller.close()
            runCurrent()
            fixture.controller.awaitClosed()
        }
    }

    @Test
    fun acceptedOtherSeatPlayAlsoRequestsShellCardSoundWhileThreeDIsSelected() = runTest {
        val fixture = Fixture(backgroundScope)
        try {
            fixture.controller.startPractice()
            runCurrent()
            val native = openThreeD(fixture)
            repeat(120) {
                val before = assertNotNull(fixture.controller.state.value.session)
                val game = assertNotNull(before.game)
                when {
                    game.phase == GamePhase.ROUND_ENDED -> fixture.controller.nextRound()
                    game.phase == GamePhase.FINISHED -> fail("No other-seat play was observed in the match")
                    game.availableActions.canPlay -> fixture.controller.playCards(listOf(game.yourHand.first().id))
                    game.availableActions.canChallenge -> fixture.controller.challenge()
                    else -> {
                        fixture.feedback.requests.clear()
                        advanceTimeBy(850)
                        runCurrent()
                        val after = assertNotNull(fixture.controller.state.value.session)
                        val next = assertNotNull(after.game)
                        val claim = next.latestClaim
                        if (next.phase == GamePhase.PLAYING && claim != null && claim != game.latestClaim) {
                            assertTrue(after.revision > before.revision)
                            assertTrue(claim.playerId != after.selfPlayerId)
                            assertEquals(GameplayPresentation.GODOT_3D, fixture.controller.state.value.presentation.selected)
                            assertEquals(1, fixture.feedback.requests.count { it.cue == FeedbackCue.CARD_PLAY })
                            assertTrue(fixture.feedback.requests.single { it.cue == FeedbackCue.CARD_PLAY }.settings.soundEnabled)
                            assertFalse(native.preferences.soundEnabled)
                            return@runTest
                        }
                    }
                }
                runCurrent()
            }
            fail("No accepted other-seat card play arrived within the bounded practice flow")
        } finally {
            fixture.controller.close()
            runCurrent()
            fixture.controller.awaitClosed()
        }
    }

    @Test
    fun muteAndUnmuteReachShellFeedbackWithoutRestartingTheNativePresentation() = runTest {
        for (soundEnabled in listOf(false, true)) {
            val fixture = Fixture(backgroundScope)
            try {
                fixture.controller.startPractice()
                runCurrent()
                reachOwnPlay(fixture)
                val native = openThreeD(fixture)
                fixture.controller.updateSettings(fixture.controller.state.value.settings.copy(soundEnabled = false))
                if (soundEnabled) {
                    fixture.controller.updateSettings(fixture.controller.state.value.settings.copy(soundEnabled = true))
                }
                runCurrent()
                fixture.feedback.requests.clear()
                val game = assertNotNull(fixture.controller.state.value.session?.game)
                native.intent(RendererIntent.Play(listOf(game.yourHand.first().id)), native.latestView().revision)
                runCurrent()

                assertEquals(listOf(FeedbackCue.CARD_PLAY), fixture.feedback.requests.map { it.cue })
                assertEquals(soundEnabled, fixture.feedback.requests.single().settings.soundEnabled)
                assertEquals(0, native.closeCalls)
                assertEquals(1, fixture.host.opened.size)
                assertFalse(native.preferences.soundEnabled)
            } finally {
                fixture.controller.close()
                runCurrent()
                fixture.controller.awaitClosed()
            }
        }
    }

    @Test
    fun backgroundResumeAndReturnDoNotReplayTheLastAcceptedPlay() = runTest {
        val fixture = Fixture(backgroundScope)
        try {
            fixture.controller.startPractice()
            runCurrent()
            reachOwnPlay(fixture)
            val native = openThreeD(fixture)
            val game = assertNotNull(fixture.controller.state.value.session?.game)
            native.intent(RendererIntent.Play(listOf(game.yourHand.first().id)), native.latestView().revision)
            runCurrent()
            assertTrue(fixture.feedback.requests.any { it.cue == FeedbackCue.CARD_PLAY })
            val accepted = fixture.controller.state.value.session
            fixture.feedback.requests.clear()

            fixture.controller.setBackgrounded(true)
            runCurrent()
            advanceTimeBy(3_000)
            runCurrent()
            assertFalse(fixture.feedback.foregroundEdges.last())
            assertTrue(fixture.feedback.requests.isEmpty())
            assertEquals(accepted, fixture.controller.state.value.session)

            fixture.controller.setBackgrounded(false)
            fixture.controller.setForeground(true)
            runCurrent()
            assertTrue(fixture.feedback.foregroundEdges.last())
            assertTrue(fixture.feedback.requests.isEmpty(), "Resuming an existing claim is not another play")

            fixture.controller.useComposePresentation()
            runCurrent()
            assertEquals(1, native.closeCalls)
            assertEquals(accepted, fixture.controller.state.value.session)
            assertTrue(fixture.feedback.requests.isEmpty(), "Returning to the standard table does not replay a claim")
            fixture.controller.leaveSession()
            runCurrent()
            advanceTimeBy(3_000)
            runCurrent()
            assertNull(fixture.controller.state.value.session)
            assertTrue(fixture.feedback.requests.isEmpty(), "A departed session cannot emit its delayed bot feedback")
        } finally {
            fixture.controller.close()
            runCurrent()
            fixture.controller.awaitClosed()
        }
    }

    private fun TestScope.reachOwnPlay(fixture: Fixture) {
        repeat(120) {
            val game = assertNotNull(fixture.controller.state.value.session?.game)
            if (game.availableActions.canPlay) return
            when {
                game.phase == GamePhase.ROUND_ENDED -> fixture.controller.nextRound()
                game.availableActions.canChallenge -> fixture.controller.challenge()
                else -> advanceTimeBy(850)
            }
            runCurrent()
        }
        fail("Practice did not offer a human play within the bounded flow")
    }

    private fun TestScope.openThreeD(fixture: Fixture): NativeSession {
        assertTrue(fixture.controller.selectPresentation(GameplayPresentation.GODOT_3D))
        val native = fixture.host.opened.single()
        native.ready()
        runCurrent()
        assertEquals(PresentationLifecycle.ACTIVE, fixture.controller.state.value.presentation.lifecycle)
        fixture.feedback.requests.clear()
        return native
    }

    private class Fixture(scope: CoroutineScope) {
        val feedback = RecordingFeedback()
        val host = NativeHost()
        val controller = PartyDeckController(
            object : PlatformServices {
                private var token = 0L
                override val feedback = this@Fixture.feedback
                override val settingsStore = object : SettingsStore {
                    override suspend fun load() = AppSettings()
                    override suspend fun save(settings: AppSettings) = Unit
                }
                override val canScanInvitation = false
                override fun secureToken() = (++token).toString(16).padStart(64, '0')
                override fun gameRandom() = Random(12)
                override fun copyText(value: String) = Unit
                override fun shareText(value: String) = Unit
                override fun scanInvitation(onResult: (String?) -> Unit) = onResult(null)
            },
            object : LanTransportFactory {
                override fun create(): LanTransport = error("Practice must not acquire network resources")
            },
            scope,
            host,
        )

        init {
            // The Android owner initially publishes an unattached window, then real interactivity.
            controller.setForeground(false)
            controller.setForeground(true)
        }
    }

    private class RecordingFeedback : Feedback {
        data class Request(val cue: FeedbackCue, val settings: AppSettings)
        val requests = mutableListOf<Request>()
        val foregroundEdges = mutableListOf<Boolean>()
        override fun play(cue: FeedbackCue, settings: AppSettings) { requests += Request(cue, settings) }
        override fun setForeground(value: Boolean) { foregroundEdges += value }
        override fun close() = Unit
    }

    private class NativeHost : EmbeddedPresentationHost {
        override val available = MutableStateFlow(setOf(GameplayPresentation.GODOT_3D))
        val opened = mutableListOf<NativeSession>()
        override fun createFactory(presentation: GameplayPresentation, preferences: PresentationPreferences): EmbeddedGameFactory =
            object : EmbeddedGameFactory {
                override val engineId = "godot-3d"
                override val protocolVersion = 1
                override val supportedGames = setOf(GameId("last-light"))
                override suspend fun open(launch: EngineLaunch): EmbeddedGameSession =
                    NativeSession(launch, preferences).also { opened += it }
            }
    }

    private class NativeSession(val launch: EngineLaunch, val preferences: PresentationPreferences) : EmbeddedGameSession {
        private val incoming = Channel<EngineEvent>(32)
        override val events = incoming.receiveAsFlow()
        private val commands = mutableListOf<EngineCommand>()
        private var sequence = 0L
        var closeCalls = 0
        fun ready() = emit(EngineEventBody.Ready)
        fun intent(intent: RendererIntent, revision: Long) =
            emit(EngineEventBody.PlayerIntent(revision, LastLightWireCodec.intentPayload(intent)))
        private fun emit(body: EngineEventBody) {
            assertTrue(incoming.trySend(EngineEvent(launch.presentationId, launch.protocolVersion, sequence++, body)).isSuccess)
        }
        fun latestView() = commands.filterIsInstance<EngineCommand.ShowView>().last()
        override suspend fun send(command: EngineCommand) { commands += command }
        override suspend fun close() {
            closeCalls++
            incoming.close()
        }
    }
}
