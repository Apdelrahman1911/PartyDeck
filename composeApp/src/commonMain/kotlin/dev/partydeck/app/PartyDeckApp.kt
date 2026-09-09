package dev.partydeck.app

import androidx.compose.foundation.Image
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.BoxWithConstraints
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.safeDrawingPadding
import androidx.compose.foundation.layout.size
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.SnackbarHost
import androidx.compose.material3.SnackbarHostState
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.semantics.heading
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import dev.partydeck.app.controller.AppScreen
import dev.partydeck.app.controller.AppUiState
import dev.partydeck.app.controller.PartyDeckController
import dev.partydeck.app.controller.RecoveryAction
import dev.partydeck.app.ui.game.GameplayScreen
import dev.partydeck.app.ui.shell.ConnectionBanner
import dev.partydeck.app.ui.shell.HomeScreen
import dev.partydeck.app.ui.shell.HostJoinScreen
import dev.partydeck.app.ui.shell.HowToPlayScreen
import dev.partydeck.app.ui.shell.InlineProblem
import dev.partydeck.app.ui.shell.LobbyScreen
import dev.partydeck.app.ui.shell.ScreenHeader
import dev.partydeck.app.ui.shell.ScrollablePage
import dev.partydeck.app.ui.shell.SettingsScreen
import dev.partydeck.app.ui.shell.ShellIconAction
import dev.partydeck.app.ui.theme.DeckButton
import dev.partydeck.app.ui.theme.PartyDeckColors
import dev.partydeck.app.ui.theme.PartyDeckTheme
import dev.partydeck.app.ui.theme.LocalReduceMotion
import dev.partydeck.games.PartyDeckGames
import dev.partydeck.resources.*
import dev.partydeck.session.SessionPhase
import org.jetbrains.compose.resources.painterResource
import org.jetbrains.compose.resources.stringResource

/** Platform owners retain the controller and forward lifecycle; composition only renders it. */
@Composable
fun PartyDeckApp(
    controller: PartyDeckController,
    modifier: Modifier = Modifier,
) {
    val state by controller.state.collectAsStateWithLifecycle()
    PartyDeckTheme(reduceMotion = state.effectiveReduceMotion) {
        val snackbars = remember { SnackbarHostState() }
        val copiedMessage = stringResource(Res.string.shell_invitation_copied)
        LaunchedEffect(state.notice?.occurrenceId) {
            if (state.notice != null) {
                snackbars.showSnackbar(copiedMessage)
                controller.dismissNotice()
            }
        }
        val onRecover = {
            when (state.problem?.recovery) {
                RecoveryAction.RETRY_CONNECTION -> controller.retryConnection()
                RecoveryAction.EDIT_INVITE -> {
                    controller.dismissProblem()
                    controller.navigate(AppScreen.JOIN)
                }
                RecoveryAction.RETURN_HOME -> controller.leaveSession()
                else -> controller.dismissProblem()
            }
        }
        Surface(modifier.fillMaxSize(), color = PartyDeckColors.Ink) {
            BoxWithConstraints(Modifier.fillMaxSize().safeDrawingPadding()) {
                val maxProblemHeight = minOf(240.dp, maxHeight * 0.45f)
                val maxConnectionHeight = maxHeight * 0.30f
                Column(Modifier.fillMaxSize()) {
                    if (state.screen == AppScreen.SESSION) {
                        val session = state.session
                        ConnectionBanner(
                            connection = state.connection,
                            pausedPlayerNames = session?.players
                                ?.filter { it.id in session.pausedPlayerIds }
                                ?.map { it.displayName }.orEmpty(),
                            canReturnToLobby = session?.let {
                                it.phase == SessionPhase.GAME && it.selfPlayerId == it.hostPlayerId &&
                                    it.pausedPlayerIds.isNotEmpty() && it.controls.canReturnToLobby
                            } == true,
                            canSendAction = state.canSendSessionAction,
                            onReturnToLobby = controller::returnToLobby,
                            modifier = Modifier.heightIn(max = maxConnectionHeight),
                        )
                    }
                    if (state.screen != AppScreen.HOST && state.screen != AppScreen.JOIN) {
                        state.problem?.let {
                            InlineProblem(
                                problem = it,
                                onRecover = onRecover,
                                onDismiss = controller::dismissProblem,
                                modifier = Modifier.padding(horizontal = 16.dp, vertical = 8.dp)
                                    .heightIn(max = maxProblemHeight),
                            )
                        }
                    }
                    Box(Modifier.weight(1f)) {
                        when (state.screen) {
                            AppScreen.HOME -> HomeScreen(
                                onHost = { controller.navigate(AppScreen.HOST) },
                                onJoin = { controller.navigate(AppScreen.JOIN) },
                                onPractice = controller::startPractice,
                                onHowTo = { controller.navigate(AppScreen.HOW_TO) },
                                onSettings = { controller.navigate(AppScreen.SETTINGS) },
                            )
                            AppScreen.HOST, AppScreen.JOIN -> HostJoinScreen(
                                state = state,
                                onBack = { controller.requestBack() },
                                onNameChange = controller::setDisplayName,
                                onInvitationChange = controller::setJoinAddress,
                                onSubmit = if (state.screen == AppScreen.HOST) controller::host else controller::join,
                                onScanInvitation = controller::scanInvitation,
                                onRecover = onRecover,
                                onDismissProblem = controller::dismissProblem,
                            )
                            AppScreen.SESSION -> SessionScreen(state, controller, onRecover)
                            AppScreen.SETTINGS -> SettingsScreen(
                                state = state,
                                onBack = { controller.requestBack() },
                                onSettingsChange = controller::updateSettings,
                            )
                            AppScreen.HOW_TO -> HowToPlayScreen(
                                hasSession = state.session != null,
                                onBack = { controller.requestBack() },
                                onPractice = controller::startPractice,
                            )
                        }
                    }
                }
                SnackbarHost(snackbars, Modifier.align(Alignment.BottomCenter).padding(16.dp))
            }
        }
        if (state.leaveConfirmationRequested) {
            LeaveTableDialog(
                state,
                onLeave = controller::leaveSession,
                onStay = controller::dismissLeaveConfirmation,
            )
        }
    }
}

@Composable
private fun SessionScreen(state: AppUiState, controller: PartyDeckController, onRecover: () -> Unit) {
    val session = state.session
    when (session?.phase) {
        SessionPhase.LOBBY -> LobbyScreen(
            state = state,
            onBack = { controller.requestBack() },
            onHowTo = { controller.navigate(AppScreen.HOW_TO) },
            onSettings = { controller.navigate(AppScreen.SETTINGS) },
            onReady = controller::setReady,
            onStart = controller::startGame,
            onCopyInvitation = controller::copyInvitation,
            onShareInvitation = controller::shareInvitation,
            onKickPlayer = controller::kickPlayer,
            onRecover = onRecover,
            onDismissProblem = controller::dismissProblem,
        )
        SessionPhase.GAME -> {
            val game = session.game
            if (game == null) {
                SessionLoadingScreen(onBack = { controller.requestBack() })
                return
            }
            Column(Modifier.fillMaxSize()) {
                ScreenHeader(
                    title = PartyDeckGames.lastLight.title,
                    onBack = { controller.requestBack() },
                    modifier = Modifier.padding(horizontal = 16.dp, vertical = 4.dp),
                ) {
                    ShellIconAction(
                        Res.drawable.icon_info,
                        stringResource(Res.string.shell_how_to),
                        { controller.navigate(AppScreen.HOW_TO) },
                    )
                    ShellIconAction(
                        Res.drawable.icon_settings,
                        stringResource(Res.string.shell_settings),
                        { controller.navigate(AppScreen.SETTINGS) },
                    )
                }
                GameplayScreen(
                    view = game,
                    isHost = session.selfPlayerId == session.hostPlayerId,
                    canSendAction = state.canSendSessionAction,
                    pendingAction = state.pendingAction,
                    privateContentVisible = state.isForeground,
                    canAdvanceRound = session.controls.canAdvanceRound,
                    canReturnToLobby = session.controls.canReturnToLobby,
                    onPlay = controller::playCards,
                    onChallenge = controller::challenge,
                    onNextRound = controller::nextRound,
                    onReturnToLobby = controller::returnToLobby,
                    privacyEpoch = state.privacyEpoch,
                    modifier = Modifier.weight(1f).fillMaxWidth(),
                )
            }
        }
        SessionPhase.ENDED -> ScrollablePage {
            Spacer(Modifier.height(36.dp))
            Image(painterResource(Res.drawable.partydeck_mark), null, Modifier.size(80.dp))
            Spacer(Modifier.height(24.dp))
            Text(
                stringResource(Res.string.shell_session_ended_title),
                style = MaterialTheme.typography.headlineLarge,
                modifier = Modifier.semantics { heading() },
            )
            Spacer(Modifier.height(16.dp))
            Text(stringResource(Res.string.shell_session_ended_description), style = MaterialTheme.typography.bodyLarge)
            Spacer(Modifier.height(32.dp))
            DeckButton(stringResource(Res.string.shell_return_home), controller::leaveSession, Modifier.fillMaxWidth())
        }
        null -> SessionLoadingScreen(onBack = { controller.requestBack() })
    }
}

@Composable
private fun SessionLoadingScreen(onBack: () -> Unit) {
    ScrollablePage {
        ScreenHeader(stringResource(Res.string.shell_app_name), onBack)
        Spacer(Modifier.height(48.dp))
        if (!LocalReduceMotion.current) CircularProgressIndicator(Modifier.size(28.dp))
        Spacer(Modifier.height(24.dp))
        Text(stringResource(Res.string.shell_session_loading), style = MaterialTheme.typography.titleMedium)
    }
}

@Composable
private fun LeaveTableDialog(state: AppUiState, onLeave: () -> Unit, onStay: () -> Unit) {
    val session = state.session
    val endsTable = session != null && session.selfPlayerId == session.hostPlayerId && !state.isPractice
    AlertDialog(
        onDismissRequest = onStay,
        title = {
            Text(
                stringResource(if (endsTable) Res.string.shell_end_title else Res.string.shell_leave_title),
                style = MaterialTheme.typography.headlineMedium,
            )
        },
        text = {
            Text(
                stringResource(
                    when {
                        state.isPractice -> Res.string.shell_leave_practice_message
                        endsTable -> Res.string.shell_end_message
                        else -> Res.string.shell_leave_message
                    },
                ),
                style = MaterialTheme.typography.bodyMedium,
            )
        },
        confirmButton = {
            DeckButton(
                text = stringResource(if (endsTable) Res.string.shell_end_table else Res.string.shell_leave_table),
                onClick = onLeave,
                accent = PartyDeckColors.Copper,
                modifier = Modifier.testTag("leave-confirm"),
            )
        },
        dismissButton = {
            TextButton(onClick = onStay, modifier = Modifier.heightIn(min = 48.dp).testTag("leave-cancel")) {
                Text(stringResource(Res.string.shell_stay))
            }
        },
        containerColor = PartyDeckColors.Surface,
    )
}
