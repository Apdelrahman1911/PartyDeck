package dev.partydeck.app.ui.shell

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.BoxWithConstraints
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.key
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.semantics.heading
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.unit.dp
import dev.partydeck.app.controller.AppUiState
import dev.partydeck.app.controller.PendingAction
import dev.partydeck.app.ui.theme.DeckButton
import dev.partydeck.app.ui.theme.PartyDeckColors
import dev.partydeck.app.ui.theme.SectionLabel
import dev.partydeck.core.LastLightRules
import dev.partydeck.core.PlayerId
import dev.partydeck.games.PartyDeckGames
import dev.partydeck.resources.*
import dev.partydeck.session.LobbyPlayer
import org.jetbrains.compose.resources.painterResource
import org.jetbrains.compose.resources.stringResource

@Composable
fun LobbyScreen(
    state: AppUiState,
    onBack: () -> Unit,
    onHowTo: () -> Unit,
    onSettings: () -> Unit,
    onReady: (Boolean) -> Unit,
    onStart: () -> Unit,
    onCopyInvitation: () -> Unit,
    onShareInvitation: () -> Unit,
    onKickPlayer: (PlayerId) -> Unit,
    onRecover: () -> Unit,
    onDismissProblem: () -> Unit,
    modifier: Modifier = Modifier,
) {
    val session = state.session ?: return
    val isHost = session.selfPlayerId == session.hostPlayerId
    var invitationVisible by remember(session.sessionId) { mutableStateOf(false) }
    var removingPlayerId by remember(session.sessionId) { mutableStateOf<PlayerId?>(null) }
    BoxWithConstraints(modifier.fillMaxSize()) {
        val dockActions = maxHeight >= 500.dp && LocalDensity.current.fontScale < 1.5f
        Column(Modifier.fillMaxSize()) {
            ScrollablePage(Modifier.weight(1f)) {
                ScreenHeader(PartyDeckGames.lastLight.title, onBack) {
                    ShellIconAction(Res.drawable.icon_info, stringResource(Res.string.shell_how_to), onHowTo)
                    ShellIconAction(Res.drawable.icon_settings, stringResource(Res.string.shell_settings), onSettings)
                }
                SectionLabel(
                    stringResource(if (state.isPractice) Res.string.shell_practice_label else Res.string.shell_lobby_eyebrow),
                    color = PartyDeckColors.Citron,
                )
                Spacer(Modifier.height(10.dp))
                Text(
                    stringResource(Res.string.shell_lobby_title),
                    style = MaterialTheme.typography.headlineLarge,
                    modifier = Modifier.semantics { heading() },
                )
                Spacer(Modifier.height(8.dp))
                Text(
                    stringResource(if (state.isPractice) Res.string.shell_practice_description else Res.string.shell_lobby_description),
                    style = MaterialTheme.typography.bodyMedium,
                    color = PartyDeckColors.Muted,
                )
                if (isHost && state.invitation != null) {
                    Spacer(Modifier.height(24.dp))
                    Surface(
                        onClick = { invitationVisible = true },
                        modifier = Modifier.fillMaxWidth().testTag("lobby-invitation"),
                        color = PartyDeckColors.Surface,
                        contentColor = PartyDeckColors.Paper,
                        shape = MaterialTheme.shapes.medium,
                        border = BorderStroke(1.dp, PartyDeckColors.Outline),
                    ) {
                        Row(
                            Modifier.padding(16.dp),
                            horizontalArrangement = Arrangement.spacedBy(16.dp),
                            verticalAlignment = Alignment.CenterVertically,
                        ) {
                            Icon(
                                painterResource(Res.drawable.icon_qr_scan), null,
                                Modifier.size(28.dp), tint = PartyDeckColors.Citron,
                            )
                            Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                                Text(stringResource(Res.string.shell_invite_friends), style = MaterialTheme.typography.titleSmall)
                                Text(
                                    stringResource(Res.string.shell_invite_description),
                                    style = MaterialTheme.typography.bodySmall,
                                    color = PartyDeckColors.Muted,
                                )
                            }
                            Icon(painterResource(Res.drawable.icon_arrow_forward), null, Modifier.size(20.dp))
                        }
                    }
                }
                Spacer(Modifier.height(28.dp))
                SectionLabel(stringResource(Res.string.shell_seats_label))
                Text(
                    stringResource(Res.string.shell_seat_count, session.players.size, LastLightRules.MAX_PLAYERS),
                    modifier = Modifier.padding(top = 6.dp, bottom = 8.dp),
                    style = MaterialTheme.typography.bodySmall,
                    color = PartyDeckColors.Muted,
                )
                session.players.forEachIndexed { index, player ->
                    key(player.id) {
                        SeatRow(
                            player = player,
                            seat = index + 1,
                            isSelf = player.id == session.selfPlayerId,
                            isHost = player.id == session.hostPlayerId,
                            onRemove = if (isHost && !player.isConnected && player.id != session.selfPlayerId) {
                                { removingPlayerId = player.id }
                            } else null,
                            canRemove = state.canSendSessionAction,
                        )
                        HorizontalDivider(color = PartyDeckColors.Divider)
                    }
                }
                if (session.players.size < LastLightRules.MAX_PLAYERS) {
                    Row(
                        Modifier.fillMaxWidth().padding(vertical = 16.dp),
                        horizontalArrangement = Arrangement.spacedBy(16.dp),
                        verticalAlignment = Alignment.CenterVertically,
                    ) {
                        Box(
                            Modifier.size(40.dp).background(PartyDeckColors.Surface, CircleShape),
                            contentAlignment = Alignment.Center,
                        ) {
                            Icon(painterResource(Res.drawable.icon_plus), null, Modifier.size(20.dp), tint = PartyDeckColors.Muted)
                        }
                        Column(Modifier.weight(1f)) {
                            Text(stringResource(Res.string.shell_empty_seat), style = MaterialTheme.typography.bodyMedium)
                            Text(
                                stringResource(Res.string.shell_open_seats, LastLightRules.MAX_PLAYERS - session.players.size),
                                style = MaterialTheme.typography.bodySmall,
                                color = PartyDeckColors.Muted,
                            )
                        }
                    }
                }
                Spacer(Modifier.height(20.dp))
                if (!dockActions) {
                    LobbyActions(state, onReady, onStart)
                    Spacer(Modifier.height(24.dp))
                }
                if (isHost && !state.isPractice) {
                    InformationLine(Res.drawable.icon_nearby, stringResource(Res.string.shell_host_foreground))
                    Spacer(Modifier.height(12.dp))
                }
            }
            if (dockActions) {
                Box(Modifier.fillMaxWidth(), contentAlignment = Alignment.Center) {
                    Column(Modifier.widthIn(max = 640.dp).fillMaxWidth().padding(horizontal = 24.dp)) {
                        HorizontalDivider(color = PartyDeckColors.Divider)
                        Spacer(Modifier.height(16.dp))
                        LobbyActions(state, onReady, onStart)
                        Spacer(Modifier.height(16.dp))
                    }
                }
            }
        }
    }
    if (invitationVisible && state.invitation != null) {
        InvitationDialog(
            invitation = state.invitation,
            invitationCopied = state.notice != null,
            problem = state.problem,
            onCopy = onCopyInvitation,
            onShare = onShareInvitation,
            onDismiss = { invitationVisible = false },
            onRecover = onRecover,
            onDismissProblem = onDismissProblem,
        )
    }
    session.players.firstOrNull { it.id == removingPlayerId }?.let { player ->
        AlertDialog(
            onDismissRequest = { removingPlayerId = null },
            title = { Text(stringResource(Res.string.shell_remove_player_title)) },
            text = { Text(stringResource(Res.string.shell_remove_player_description, player.displayName)) },
            confirmButton = {
                TextButton(onClick = {
                    removingPlayerId = null
                    onKickPlayer(player.id)
                }) { Text(stringResource(Res.string.shell_remove_action), color = PartyDeckColors.Copper) }
            },
            dismissButton = {
                TextButton(onClick = { removingPlayerId = null }) { Text(stringResource(Res.string.shell_cancel)) }
            },
            containerColor = PartyDeckColors.Surface,
        )
    }
}

@Composable
private fun LobbyActions(state: AppUiState, onReady: (Boolean) -> Unit, onStart: () -> Unit) {
    val session = state.session ?: return
    val self = session.players.firstOrNull { it.id == session.selfPlayerId }
    val isHost = session.selfPlayerId == session.hostPlayerId
    if (isHost) {
        val reason = when {
            session.players.any { !it.isConnected } -> Res.string.shell_wait_connection
            session.players.size < LastLightRules.MIN_PLAYERS -> Res.string.shell_wait_players
            !session.controls.canStartGame -> Res.string.shell_wait_ready
            else -> null
        }
        reason?.let {
            Text(
                stringResource(it),
                Modifier.padding(bottom = 14.dp),
                style = MaterialTheme.typography.bodyMedium,
                color = PartyDeckColors.Muted,
            )
        }
        DeckButton(
            text = stringResource(
                if (state.pendingAction == PendingAction.START_GAME) Res.string.shell_starting_game
                else Res.string.shell_start_game,
            ),
            onClick = onStart,
            modifier = Modifier.fillMaxWidth().testTag("lobby-start"),
            enabled = session.controls.canStartGame && state.canSendSessionAction,
        )
    } else {
        Text(
            stringResource(if (self?.isReady == true) Res.string.shell_wait_host else Res.string.shell_lobby_ready_hint),
            Modifier.padding(bottom = 14.dp),
            style = MaterialTheme.typography.bodyMedium,
            color = PartyDeckColors.Muted,
        )
        DeckButton(
            text = stringResource(if (self?.isReady == true) Res.string.shell_unready_action else Res.string.shell_ready_action),
            onClick = { onReady(self?.isReady != true) },
            enabled = self != null && self.isConnected && state.canSendSessionAction,
            secondary = self?.isReady == true,
            modifier = Modifier.fillMaxWidth().testTag("lobby-ready"),
        )
    }
}

@Composable
private fun SeatRow(
    player: LobbyPlayer,
    seat: Int,
    isSelf: Boolean,
    isHost: Boolean,
    onRemove: (() -> Unit)?,
    canRemove: Boolean,
) {
    val status = stringResource(
        when {
            !player.isConnected -> Res.string.shell_disconnected
            isHost || player.isReady -> Res.string.shell_ready
            else -> Res.string.shell_not_ready
        },
    )
    val role = when {
        isSelf && isHost -> stringResource(Res.string.shell_you_host)
        isSelf -> stringResource(Res.string.shell_you)
        isHost -> stringResource(Res.string.shell_host)
        else -> null
    }
    Row(
        modifier = Modifier.fillMaxWidth().padding(vertical = 14.dp),
        horizontalArrangement = Arrangement.spacedBy(16.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Box(
            modifier = Modifier.size(40.dp).background(
                if (isSelf) PartyDeckColors.Citron else PartyDeckColors.Surface, CircleShape,
            ),
            contentAlignment = Alignment.Center,
        ) {
            Text(
                seat.toString().padStart(2, '0'),
                style = MaterialTheme.typography.labelMedium,
                color = if (isSelf) PartyDeckColors.Ink else PartyDeckColors.Paper,
            )
        }
        Column(Modifier.weight(1f)) {
            Text(player.displayName, style = MaterialTheme.typography.titleSmall)
            Text(
                text = role?.let { stringResource(Res.string.shell_seat_detail, it, status) } ?: status,
                style = MaterialTheme.typography.bodySmall,
                color = PartyDeckColors.Muted,
            )
        }
        if (onRemove != null) {
            ShellIconAction(
                Res.drawable.icon_close,
                stringResource(Res.string.shell_remove_player, player.displayName),
                onRemove,
                enabled = canRemove,
            )
        } else if (player.isConnected && (player.isReady || isHost) && LocalDensity.current.fontScale < 1.5f) {
            Icon(painterResource(Res.drawable.icon_check), null, Modifier.size(20.dp), tint = PartyDeckColors.Citron)
        }
    }
}
