package dev.partydeck.app

import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.heightIn
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
import androidx.compose.ui.test.assertIsOn
import androidx.compose.ui.test.assertTextContains
import androidx.compose.ui.test.assertTextEquals
import androidx.compose.ui.test.captureToImage
import androidx.compose.ui.test.onNodeWithTag
import androidx.compose.ui.test.onAllNodesWithTag
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.test.performClick
import androidx.compose.ui.test.performScrollTo
import androidx.compose.ui.test.performScrollToIndex
import androidx.compose.ui.test.performTextReplacement
import androidx.compose.ui.test.v2.runSkikoComposeUiTest
import androidx.compose.ui.unit.Density
import androidx.compose.ui.unit.dp
import com.google.zxing.BinaryBitmap
import com.google.zxing.DecodeHintType
import com.google.zxing.RGBLuminanceSource
import com.google.zxing.common.HybridBinarizer
import com.google.zxing.qrcode.QRCodeReader
import dev.partydeck.app.controller.AppScreen
import dev.partydeck.app.controller.AppSettings
import dev.partydeck.app.controller.AppUiState
import dev.partydeck.app.controller.ConnectionStatus
import dev.partydeck.app.controller.ConnectionUiState
import dev.partydeck.app.controller.Feedback
import dev.partydeck.app.controller.FeedbackCue
import dev.partydeck.app.controller.HostInvitation
import dev.partydeck.app.controller.PartyDeckController
import dev.partydeck.app.controller.PendingAction
import dev.partydeck.app.controller.PlatformServices
import dev.partydeck.app.controller.RecoveryAction
import dev.partydeck.app.controller.SessionMode
import dev.partydeck.app.controller.SettingsStore
import dev.partydeck.app.controller.UiProblem
import dev.partydeck.app.controller.UiProblemCode
import dev.partydeck.app.ui.shell.HostJoinScreen
import dev.partydeck.app.ui.shell.ConnectionBanner
import dev.partydeck.app.ui.shell.InvitationDialog
import dev.partydeck.app.ui.shell.LobbyScreen
import dev.partydeck.app.ui.shell.SettingsScreen
import dev.partydeck.app.ui.shell.splitLicenseText
import dev.partydeck.app.ui.theme.PartyDeckColors
import dev.partydeck.app.ui.theme.PartyDeckTheme
import dev.partydeck.session.LobbyPlayer
import dev.partydeck.session.SessionControls
import dev.partydeck.session.SessionPhase
import dev.partydeck.session.SessionView
import dev.partydeck.transport.LanEndpoint
import dev.partydeck.transport.LanInvitation
import dev.partydeck.transport.LanTransport
import dev.partydeck.transport.LanTransportFactory
import java.awt.image.BufferedImage
import java.io.File
import javax.imageio.ImageIO
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import kotlin.random.Random
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertNull
import kotlin.test.assertTrue
import kotlin.time.Duration.Companion.seconds

/**
 * Rendered viewport fixtures, including 200% text. These are not native keyboard/safe-area tests.
 * QR decoding inspects the actual dialog pixels and uses only explicitly synthetic credentials.
 */
@OptIn(ExperimentalTestApi::class)
class ShellLayoutTest {
    @Test
    fun sixSeatHostCanDealOnCompactPhone() = qualifyLobby(360, 640, 1f, true, "lobby-host-phone")

    @Test
    fun sixSeatGuestCanChangeReadinessOnCompactPhone() = qualifyLobby(360, 640, 1f, false, "lobby-guest-phone")

    @Test
    fun sixSeatHostCanDealAtTwoHundredPercentText() = qualifyLobby(320, 740, 2f, true, "lobby-host-large-text")

    @Test
    fun sixSeatGuestCanChangeReadinessAtTwoHundredPercentText() =
        qualifyLobby(320, 740, 2f, false, "lobby-guest-large-text")

    private fun qualifyLobby(width: Int, height: Int, scale: Float, host: Boolean, name: String) =
        runSkikoComposeUiTest(
            size = Size(width.toFloat(), height.toFloat()),
            density = Density(1f, scale),
            testTimeout = 45.seconds,
        ) {
            var state by mutableStateOf(lobbyFixture(host))
            var startRequests = 0
            val readyRequests = mutableListOf<Boolean>()
            setContent {
                ShellTestFrame {
                    LobbyScreen(
                        state = state,
                        onBack = {},
                        onHowTo = {},
                        onSettings = {},
                        onReady = { ready ->
                            readyRequests += ready
                            val session = state.session!!
                            state = state.copy(session = session.copy(players = session.players.map {
                                if (it.id == session.selfPlayerId) it.copy(isReady = ready) else it
                            }))
                        },
                        onStart = { startRequests++ },
                        onCopyInvitation = {},
                        onShareInvitation = {},
                        onKickPlayer = {},
                        onRecover = {},
                        onDismissProblem = {},
                    )
                }
            }
            waitForIdle()
            onNodeWithTag("shell-snapshot-root").shellSnapshot(name)
            val action = onNodeWithTag(if (host) "lobby-start" else "lobby-ready")
            // At regular text the footer is docked even with all six seats occupied.
            if (scale < 1.5f) action.assertIsDisplayed()
            for (player in state.session!!.players) {
                onNodeWithText(player.displayName).performScrollTo().assertIsDisplayed()
            }
            onNodeWithTag("shell-snapshot-root").shellSnapshot("$name-roster")
            if (scale >= 1.5f) action.performScrollTo()
            action.assertIsDisplayed().assertIsEnabled().performClick()
            if (host) {
                assertEquals(1, startRequests)
            } else {
                assertEquals(listOf(true), readyRequests)
                if (scale >= 1.5f) action.performScrollTo()
                action.assertIsDisplayed().performClick()
                assertEquals(listOf(true, false), readyRequests)
            }
            onNodeWithTag("shell-snapshot-root").shellSnapshot("$name-action")
            runOnUiThread {
                state = state.copy(pendingAction = if (host) PendingAction.START_GAME else PendingAction.READY)
            }
            action.assertIsNotEnabled()
        }

    @Test
    fun joinRetainsInputsAndRecoveryInConstrainedLargeTextViewport() = runSkikoComposeUiTest(
        size = Size(320f, 420f),
        density = Density(1f, 2f),
        testTimeout = 45.seconds,
    ) {
        val invitation = syntheticInvitation().encode()
        var state by mutableStateOf(AppUiState(screen = AppScreen.JOIN, displayName = "Rowan", joinAddress = invitation))
        var submitted = 0
        var recovered = 0
        setContent {
            ShellTestFrame {
                HostJoinScreen(
                    state = state,
                    onBack = {},
                    onNameChange = { state = state.copy(displayName = it) },
                    onInvitationChange = { state = state.copy(joinAddress = it) },
                    onSubmit = {
                        submitted++
                        state = state.copy(problem = UiProblem(1, UiProblemCode.CONNECTION_FAILED, RecoveryAction.RETRY_CONNECTION))
                    },
                    onScanInvitation = {},
                    onRecover = { recovered++ },
                    onDismissProblem = { state = state.copy(problem = null) },
                )
            }
        }
        onNodeWithTag("join-scan").assertDoesNotExist()
        onNodeWithTag("join-name").performScrollTo().performTextReplacement("Ada Lovelace")
        onNodeWithTag("join-submit").performScrollTo().assertIsDisplayed().assertIsEnabled().performClick()
        assertEquals(1, submitted)
        assertEquals("Ada Lovelace", state.displayName)
        assertEquals(invitation, state.joinAddress)
        onNodeWithTag("join-name").performScrollTo().assertTextContains("Ada Lovelace")
        onNodeWithTag("join-invitation").performScrollTo().assertTextContains(invitation)
        onNodeWithTag("shell-snapshot-root").shellSnapshot("join-constrained-large-text-input")
        onNodeWithTag("problem-panel").performScrollTo().assertIsDisplayed()
        onNodeWithTag("problem-recover").assertIsDisplayed()
        onNodeWithTag("problem-dismiss").assertIsDisplayed()
        onNodeWithTag("shell-snapshot-root").shellSnapshot("join-constrained-large-text-error")
        onNodeWithTag("problem-recover").performClick()
        assertEquals(1, recovered)
        onNodeWithTag("problem-dismiss").assertIsDisplayed().performClick()
        assertNull(state.problem)
        onNodeWithTag("join-submit").performScrollTo().assertIsDisplayed().assertIsEnabled()
        runOnUiThread {
            state = state.copy(connection = ConnectionUiState(ConnectionStatus.RECONNECTING, SessionMode.LAN_CLIENT))
        }
        onNodeWithTag("join-submit").assertIsNotEnabled()
        onNodeWithTag("join-name").assertIsNotEnabled()
        onNodeWithTag("join-invitation").assertIsNotEnabled()
        assertEquals("Ada Lovelace", state.displayName)
        assertEquals(invitation, state.joinAddress)
    }

    @Test
    fun pausedHostCanConfirmReturnToLobbyAtLargeText() = runSkikoComposeUiTest(
        size = Size(320f, 740f),
        density = Density(1f, 2f),
        testTimeout = 45.seconds,
    ) {
        var requests = 0
        var canSend by mutableStateOf(true)
        setContent {
            ShellTestFrame {
                Box(Modifier.fillMaxSize()) {
                    ConnectionBanner(
                        connection = ConnectionUiState(ConnectionStatus.CONNECTED, SessionMode.LAN_HOST),
                        pausedPlayerNames = listOf("Alexandria Montgomery", "Juniper"),
                        canReturnToLobby = true,
                        canSendAction = canSend,
                        onReturnToLobby = { requests++ },
                        modifier = Modifier.heightIn(max = 222.dp),
                    )
                }
            }
        }
        onNodeWithTag("session-return-lobby").assertIsDisplayed().performClick()
        assertEquals(0, requests, "A paused match is not ended before the host confirms")
        onNodeWithTag("return-lobby-dialog").shellSnapshot("paused-host-return-large-text")
        onNodeWithTag("return-lobby-cancel").assertIsDisplayed().performClick()
        assertEquals(0, requests)
        onNodeWithTag("session-return-lobby").performClick()
        onNodeWithTag("return-lobby-confirm").assertIsDisplayed().performClick()
        assertEquals(1, requests)
        runOnUiThread { canSend = false }
        onNodeWithTag("session-return-lobby").assertIsNotEnabled()
    }

    @Test
    fun settingsKeepLabelsAndTogglesReachableAtLargeText() = runSkikoComposeUiTest(
        size = Size(320f, 740f),
        density = Density(1f, 2f),
        testTimeout = 45.seconds,
    ) {
        var state by mutableStateOf(AppUiState(screen = AppScreen.SETTINGS))
        setContent {
            ShellTestFrame {
                SettingsScreen(
                    state = state,
                    onBack = {},
                    onSettingsChange = { state = state.copy(settings = it) },
                )
            }
        }
        onNodeWithTag("settings-sound").assertIsDisplayed().assertIsOn()
        onNodeWithTag("shell-snapshot-root").shellSnapshot("settings-large-text")
        onNodeWithTag("settings-sound").performClick()
        assertEquals(false, state.settings.soundEnabled)
        onNodeWithTag("settings-haptics").performScrollTo().assertIsDisplayed().assertIsOn().performClick()
        assertEquals(false, state.settings.hapticsEnabled)
        onNodeWithTag("settings-reduce-motion").performScrollTo().assertIsDisplayed().performClick().assertIsOn()
        assertEquals(true, state.settings.reduceMotion)
        onNodeWithTag("shell-snapshot-root").shellSnapshot("settings-large-text-motion")
    }

    @Test
    fun completeBundledNoticesRemainReadableToTheEndAtLargeText() = runSkikoComposeUiTest(
        size = Size(320f, 740f),
        density = Density(1f, 2f),
        testTimeout = 45.seconds,
    ) {
        val document = File("src/commonMain/composeResources/files/licenses/third_party_notices.txt").readText()
        val chunks = splitLicenseText(document)
        assertTrue(chunks.isNotEmpty())
        assertEquals(document, chunks.joinToString(""), "The complete legal text must be preserved")
        assertTrue(chunks.all { it.length <= 1_500 }, "No item may lay out a giant license paragraph")
        setContent {
            ShellTestFrame {
                SettingsScreen(AppUiState(screen = AppScreen.SETTINGS), onBack = {}, onSettingsChange = {})
            }
        }
        onNodeWithTag("settings-licenses").performScrollTo().assertIsDisplayed().performClick()
        waitUntil(timeoutMillis = 10_000) {
            onAllNodesWithTag("licenses-list").fetchSemanticsNodes().isNotEmpty()
        }
        onNodeWithTag("licenses-done").assertIsDisplayed()
        onNodeWithTag("licenses-dialog").shellSnapshot("licenses-large-text-start")
        onNodeWithTag("licenses-list").performScrollToIndex(1)
        onNodeWithTag("license-section-0").assertIsDisplayed().assertTextEquals(chunks.first())
        onNodeWithTag("licenses-dialog").shellSnapshot("licenses-large-text-first-notice")
        // The overview is item 0; the final one-pixel marker follows every unchanged text chunk.
        onNodeWithTag("licenses-list").performScrollToIndex(chunks.size + 1)
        onNodeWithTag("license-document-end").assertIsDisplayed()
        onNodeWithTag("license-section-${chunks.lastIndex}").assertIsDisplayed().assertTextEquals(chunks.last())
        onNodeWithTag("licenses-done").assertIsDisplayed()
        onNodeWithTag("licenses-dialog").shellSnapshot("licenses-large-text-end")
        onNodeWithTag("licenses-done").performClick()
        onNodeWithTag("licenses-dialog").assertDoesNotExist()
        println("License viewport verified ${document.encodeToByteArray().size} UTF-8 bytes in ${chunks.size} bounded text sections")
    }

    @Test
    fun renderedInvitationQrAtNarrowWidthPreservesTheExactPayloadAndFullPin() = runSkikoComposeUiTest(
        size = Size(320f, 740f),
        density = Density(1f),
        testTimeout = 45.seconds,
    ) {
        val fixture = syntheticInvitation()
        val encoded = fixture.encode()
        var copies = 0
        var shares = 0
        var dismissed = false
        setContent {
            ShellTestFrame {
                InvitationDialog(
                    invitation = HostInvitation(encoded, fixture.endpoint.host),
                    invitationCopied = false,
                    problem = null,
                    onCopy = { copies++ },
                    onShare = { shares++ },
                    onDismiss = { dismissed = true },
                    onRecover = {},
                    onDismissProblem = {},
                )
            }
        }
        onNodeWithTag("invitation-qr").performScrollTo().assertIsDisplayed()
        val pixels = onNodeWithTag("invitation-qr").shellSnapshot("invitation-qr-synthetic-320")
        onNodeWithTag("invitation-dialog").shellSnapshot("invitation-dialog-phone")
        val source = RGBLuminanceSource(
            pixels.width,
            pixels.height,
            pixels.getRGB(0, 0, pixels.width, pixels.height, null, 0, pixels.width),
        )
        val decoded = QRCodeReader().decode(
            BinaryBitmap(HybridBinarizer(source)),
            mapOf(DecodeHintType.TRY_HARDER to true),
        ).text
        assertEquals(encoded, decoded)
        assertEquals(fixture, LanInvitation.decode(decoded))
        assertEquals(64, LanInvitation.decode(decoded).certificateSha256.length)
        onNodeWithTag("invitation-share").performScrollTo().assertIsDisplayed().performClick()
        onNodeWithTag("invitation-copy").performScrollTo().assertIsDisplayed().performClick()
        assertEquals(1, shares)
        assertEquals(1, copies)
        onNodeWithTag("invitation-done").assertIsDisplayed().performClick()
        assertTrue(dismissed)
    }

    @Test
    fun globalConnectionFailureKeepsHomeAndRecoveryReachableAtLargeText() = runSkikoComposeUiTest(
        size = Size(320f, 740f),
        density = Density(1f, 2f),
        testTimeout = 45.seconds,
    ) {
        val owner = CoroutineScope(SupervisorJob() + Dispatchers.Unconfined)
        val transport = UnavailableShellTestTransport()
        val controller = PartyDeckController(ShellTestServices(), transport, owner)
        try {
            setContent { PartyDeckApp(controller, Modifier.testTag("shell-snapshot-root")) }
            // Startup fails through the real controller/runtime path; no state hooks are used.
            runOnUiThread { controller.host() }
            waitForIdle()
            assertEquals(AppScreen.HOME, controller.state.value.screen)
            assertEquals(UiProblemCode.CONNECTION_FAILED, controller.state.value.problem?.code)
            val problemBounds = onNodeWithTag("problem-panel").fetchSemanticsNode().boundsInRoot
            assertTrue(problemBounds.height <= 241f, "The global problem must leave room for page content")
            onNodeWithTag("problem-dismiss").assertIsDisplayed()
            onNodeWithTag("problem-recover").assertIsDisplayed()
            onNodeWithTag("shell-snapshot-root").shellSnapshot("global-error-large-text")
            onNodeWithTag("shell-snapshot-root").shellSnapshot("global-error-large-text-recovery")
            onNodeWithTag("problem-recover").performClick()
            waitForIdle()
            assertEquals(2, transport.attempts, "Retry must reach the real controller")
            onNodeWithTag("problem-dismiss").assertIsDisplayed().performClick()
            assertNull(controller.state.value.problem)
            onNodeWithTag("home-host").performScrollTo().assertIsDisplayed().performClick()
            assertEquals(AppScreen.HOST, controller.state.value.screen)
        } finally {
            runOnUiThread { controller.close() }
            owner.cancel()
        }
    }
}

@Composable
private fun ShellTestFrame(content: @Composable () -> Unit) {
    PartyDeckTheme {
        Surface(Modifier.fillMaxSize().testTag("shell-snapshot-root"), color = PartyDeckColors.Ink, content = content)
    }
}

@OptIn(ExperimentalTestApi::class)
private fun SemanticsNodeInteraction.shellSnapshot(name: String): BufferedImage = captureToImage().toAwtImage().also {
    val output = File("build/ui-snapshots/$name.png").apply { parentFile.mkdirs() }
    ImageIO.write(it, "png", output)
}

private fun lobbyFixture(host: Boolean): AppUiState {
    val names = listOf("Rowan", "Alexandria Montgomery", "Samira", "Pip", "Mateo", "Juniper")
    val self = if (host) "seat-0" else "seat-1"
    return AppUiState(
        screen = AppScreen.SESSION,
        connection = ConnectionUiState(ConnectionStatus.CONNECTED, if (host) SessionMode.LAN_HOST else SessionMode.LAN_CLIENT),
        session = SessionView(
            sessionId = "shell-layout-fixture",
            revision = 8,
            selfPlayerId = self,
            hostPlayerId = "seat-0",
            phase = SessionPhase.LOBBY,
            players = names.mapIndexed { index, name ->
                LobbyPlayer("seat-$index", name, isReady = host || index != 1, isConnected = true)
            },
            controls = SessionControls(canStartGame = host),
        ),
        invitation = if (host) HostInvitation(syntheticInvitation().encode(), "192.0.2.44") else null,
    )
}

/** RFC 5737 address and deterministic, synthetic credentials; this cannot identify a real table. */
private fun syntheticInvitation() = LanInvitation(
    sessionId = "shell-qr-layout-fixture",
    admissionSecret = "0123456789abcdef".repeat(4),
    endpoint = LanEndpoint("192.0.2.44", 42424, "PartyDeck layout fixture"),
    certificateSha256 = "fedcba9876543210".repeat(4),
)

private class UnavailableShellTestTransport : LanTransportFactory {
    var attempts = 0
    override fun create(): LanTransport {
        attempts++
        error("Synthetic unavailable transport for shell recovery layout")
    }
}

private class ShellTestServices : PlatformServices {
    override val settingsStore = object : SettingsStore {
        override suspend fun load() = AppSettings()
        override suspend fun save(settings: AppSettings) = Unit
    }
    override val feedback = object : Feedback {
        override fun play(cue: FeedbackCue, settings: AppSettings) = Unit
        override fun setForeground(value: Boolean) = Unit
        override fun close() = Unit
    }
    override val canScanInvitation = false
    private var token = 0L
    override fun secureToken() = (++token).toString(16).padStart(64, '0')
    override fun gameRandom(): Random = Random(42)
    override fun copyText(value: String) = Unit
    override fun shareText(value: String) = Unit
    override fun scanInvitation(onResult: (String?) -> Unit) = onResult(null)
}
