package dev.partydeck.app.ui.game

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.BoxWithConstraints
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.IntrinsicSize
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.semantics.heading
import androidx.compose.ui.semantics.isTraversalGroup
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import dev.partydeck.app.controller.PendingAction
import dev.partydeck.app.ui.theme.DeckButton
import dev.partydeck.app.ui.theme.PartyDeckColors
import dev.partydeck.core.CardId
import dev.partydeck.core.GamePhase
import dev.partydeck.core.GameView
import dev.partydeck.resources.Res
import dev.partydeck.resources.game_challenge_player
import dev.partydeck.resources.game_claim_preview
import dev.partydeck.resources.game_empty_hand_safe
import dev.partydeck.resources.game_empty_hand_title
import dev.partydeck.resources.game_forced_instruction
import dev.partydeck.resources.game_forced_title
import dev.partydeck.resources.game_last_play_pending
import dev.partydeck.resources.game_play_cards
import dev.partydeck.resources.game_select_to_play
import dev.partydeck.resources.game_sending_challenge
import dev.partydeck.resources.game_sending_play
import dev.partydeck.resources.game_spectating_detail
import dev.partydeck.resources.game_spectating_title
import dev.partydeck.resources.game_unknown_spectator
import dev.partydeck.resources.game_waiting_connection
import dev.partydeck.resources.game_waiting_player
import dev.partydeck.resources.game_wild_matches
import org.jetbrains.compose.resources.pluralStringResource
import org.jetbrains.compose.resources.stringResource

/**
 * A presentation of a recipient-specific view. No authority state, transport, RNG, or platform API
 * is accepted here. Insets, session errors, navigation, and authentication belong to the shell.
 */
@Composable
fun GameplayScreen(
    view: GameView,
    isHost: Boolean,
    canSendAction: Boolean,
    pendingAction: PendingAction?,
    privateContentVisible: Boolean,
    canAdvanceRound: Boolean,
    canReturnToLobby: Boolean,
    onPlay: (List<CardId>) -> Unit,
    onChallenge: () -> Unit,
    onNextRound: () -> Unit,
    onReturnToLobby: () -> Unit,
    privacyEpoch: Long = 0,
    modifier: Modifier = Modifier,
) {
    val largeText = LocalDensity.current.fontScale >= 1.3f
    var selectedIds by remember(view.viewerId, view.roundNumber) { mutableStateOf(emptySet<CardId>()) }
    // A newly entered game screen is concealed, including after returning from another route.
    var handConcealed by rememberSaveable(view.viewerId) { mutableStateOf(true) }
    var seenPrivacyEpoch by rememberSaveable(view.viewerId) { mutableStateOf(privacyEpoch) }
    var limitReached by remember(view.viewerId, view.roundNumber) { mutableStateOf(false) }
    val privacyChanged = seenPrivacyEpoch != privacyEpoch
    val handShown = privateContentVisible && !privacyChanged && !handConcealed
    val availableIds = view.yourHand.mapTo(mutableSetOf()) { it.id }
    val safeSelection = selectedIds.intersect(availableIds)
    val selectionLimit = view.availableActions.maxPlayableCards.takeIf { it > 0 } ?: 3

    LaunchedEffect(privacyEpoch, privateContentVisible) {
        if (privacyChanged || !privateContentVisible) {
            handConcealed = true
            selectedIds = emptySet()
            limitReached = false
        }
        seenPrivacyEpoch = privacyEpoch
    }
    LaunchedEffect(view.yourHand, view.phase) {
        selectedIds = if (view.phase == GamePhase.PLAYING) selectedIds.intersect(availableIds) else emptySet()
        limitReached = false
    }

    BoxWithConstraints(
        modifier = modifier.fillMaxSize().testTag("game-table").semantics { isTraversalGroup = true },
        contentAlignment = Alignment.TopCenter,
    ) {
        val compactHeight = maxHeight < 660.dp && !largeText
        when (view.phase) {
            GamePhase.ROUND_ENDED -> RoundResultScreen(
                view = view,
                isHost = isHost,
                canSendAction = canSendAction,
                canAdvanceRound = canAdvanceRound,
                pendingAction = pendingAction,
                largeText = largeText,
                onNextRound = onNextRound,
                modifier = Modifier.widthIn(max = 620.dp),
            )
            GamePhase.FINISHED -> MatchResultScreen(
                view = view,
                isHost = isHost,
                canSendAction = canSendAction,
                canReturnToLobby = canReturnToLobby,
                pendingAction = pendingAction,
                largeText = largeText,
                onReturnToLobby = onReturnToLobby,
                modifier = Modifier.widthIn(max = 560.dp),
            )
            GamePhase.PLAYING -> PlayingLayout(
                view = view,
                largeText = largeText,
                hand = {
                    val viewer = view.players.firstOrNull { it.id == view.viewerId }
                    when {
                        viewer == null || viewer.eliminated -> SpectatorMessage(viewer == null)
                        view.yourHand.isEmpty() -> EmptyHandMessage(view.latestClaim?.playerId == view.viewerId)
                        view.forcedChallenge && view.availableActions.canChallenge -> Unit
                        else -> PrivateHand(
                            cards = view.yourHand,
                            selectedIds = if (handShown) safeSelection else emptySet(),
                            selectionLimit = selectionLimit,
                            shown = handShown,
                            canReveal = privateContentVisible && !privacyChanged,
                            canSelect = handShown && canSendAction && view.availableActions.canPlay,
                            largeText = largeText,
                            selectionLimitReached = handShown && limitReached,
                            onToggle = { id ->
                                if (handShown && canSendAction && view.availableActions.canPlay && id in availableIds) {
                                    when {
                                        id in safeSelection -> {
                                            selectedIds = safeSelection - id
                                            limitReached = false
                                        }
                                        safeSelection.size < selectionLimit -> {
                                            selectedIds = safeSelection + id
                                            limitReached = false
                                        }
                                        else -> limitReached = true
                                    }
                                }
                            },
                            onHide = {
                                handConcealed = true
                                selectedIds = emptySet()
                                limitReached = false
                            },
                            onShow = {
                                if (privateContentVisible && !privacyChanged) handConcealed = false
                            },
                        )
                    }
                },
                actions = {
                    GameActions(
                        view = view,
                        selectedIds = if (handShown) safeSelection else emptySet(),
                        canSendAction = canSendAction,
                        pendingAction = pendingAction,
                        largeText = largeText,
                        compact = compactHeight,
                        onPlay = { onPlay(view.yourHand.filter { it.id in safeSelection }.map { it.id }) },
                        onChallenge = onChallenge,
                    )
                },
            )
        }
    }
}

@Composable
private fun PlayingLayout(
    view: GameView,
    largeText: Boolean,
    hand: @Composable () -> Unit,
    actions: @Composable () -> Unit,
) {
    BoxWithConstraints(Modifier.fillMaxSize()) {
        val split = maxWidth >= 720.dp && maxHeight >= 260.dp && !largeText
        val scrollEverything = largeText || maxHeight < 480.dp
        val compact = maxHeight < 660.dp
        when {
            split -> Row(Modifier.fillMaxSize().padding(vertical = 12.dp)) {
                PublicGameTable(
                    view,
                    largeText = false,
                    modifier = Modifier.weight(1f).verticalScroll(rememberScrollState()),
                )
                Column(Modifier.weight(1f).verticalScroll(rememberScrollState())) {
                    hand()
                    actions()
                }
            }
            scrollEverything -> Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState())) {
                PublicGameTable(view, largeText, Modifier.padding(top = 12.dp), compact = !largeText)
                Spacer(Modifier.height(24.dp))
                hand()
                actions()
            }
            else -> Column(Modifier.fillMaxSize()) {
                BoxWithConstraints(Modifier.weight(1f).fillMaxWidth()) {
                    val publicHeight = maxHeight
                    PublicGameTable(
                        view,
                        largeText = false,
                        modifier = Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(vertical = 12.dp),
                        compact = compact,
                        showCompactRoster = publicHeight >= 280.dp,
                        decorateClaim = compact && publicHeight >= 360.dp && view.forcedChallenge,
                    )
                }
                HorizontalDivider(
                    modifier = Modifier.padding(horizontal = 20.dp, vertical = 8.dp),
                    color = PartyDeckColors.Divider,
                )
                hand()
                actions()
            }
        }
    }
}

@Composable
private fun GameActions(
    view: GameView,
    selectedIds: Set<CardId>,
    canSendAction: Boolean,
    pendingAction: PendingAction?,
    largeText: Boolean,
    compact: Boolean,
    onPlay: () -> Unit,
    onChallenge: () -> Unit,
) {
    val canPlay = view.availableActions.canPlay
    val canChallenge = view.availableActions.canChallenge && view.latestClaim != null
    val forced = view.forcedChallenge && canChallenge
    val claimantName = playerName(view, view.latestClaim?.playerId)
    Column(
        modifier = Modifier.fillMaxWidth().padding(horizontal = 20.dp, vertical = if (compact) 8.dp else 14.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        when {
            forced -> {
                Text(
                    stringResource(Res.string.game_forced_title),
                    style = MaterialTheme.typography.headlineSmall,
                    color = PartyDeckColors.Copper,
                    modifier = Modifier.semantics { heading() },
                )
                Text(
                    stringResource(Res.string.game_forced_instruction, claimantName),
                    style = MaterialTheme.typography.bodyMedium,
                    color = PartyDeckColors.Paper,
                )
                DeckButton(
                    text = if (pendingAction == PendingAction.CHALLENGE) stringResource(Res.string.game_sending_challenge)
                    else stringResource(Res.string.game_challenge_player, claimantName),
                    onClick = onChallenge,
                    enabled = canSendAction,
                    accent = PartyDeckColors.Copper,
                    modifier = Modifier.fillMaxWidth().testTag("game-challenge"),
                )
            }
            canPlay || canChallenge -> {
                if (!compact) Text(
                    text = if (selectedIds.isNotEmpty()) {
                        stringResource(Res.string.game_claim_preview, rankClaim(view.tableRank, selectedIds.size))
                    } else stringResource(Res.string.game_wild_matches),
                    style = MaterialTheme.typography.bodySmall,
                    color = PartyDeckColors.Muted,
                )
                BoxWithConstraints(Modifier.fillMaxWidth()) {
                    val stacked = largeText || maxWidth < 310.dp
                    val play: @Composable (Modifier) -> Unit = { buttonModifier ->
                        if (canPlay) {
                            val label = when {
                                pendingAction == PendingAction.PLAY_CARDS -> stringResource(Res.string.game_sending_play)
                                selectedIds.isEmpty() -> stringResource(Res.string.game_select_to_play)
                                else -> pluralStringResource(Res.plurals.game_play_cards, selectedIds.size, selectedIds.size)
                            }
                            DeckButton(
                                text = label,
                                onClick = onPlay,
                                enabled = canSendAction && selectedIds.isNotEmpty() && selectedIds.size <= view.availableActions.maxPlayableCards,
                                modifier = buttonModifier.testTag("game-play"),
                            )
                        }
                    }
                    val challenge: @Composable (Modifier) -> Unit = { buttonModifier ->
                        if (canChallenge) {
                            ChallengeButton(
                                text = if (pendingAction == PendingAction.CHALLENGE) stringResource(Res.string.game_sending_challenge)
                                else stringResource(Res.string.game_challenge_player, claimantName),
                                enabled = canSendAction,
                                onClick = onChallenge,
                                maxLabelLines = if (stacked) Int.MAX_VALUE else 2,
                                modifier = buttonModifier,
                            )
                        }
                    }
                    if (stacked) {
                        Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
                            play(Modifier.fillMaxWidth())
                            challenge(Modifier.fillMaxWidth())
                        }
                    } else {
                        Row(
                            modifier = Modifier.height(IntrinsicSize.Min),
                            horizontalArrangement = Arrangement.spacedBy(10.dp),
                            verticalAlignment = Alignment.CenterVertically,
                        ) {
                            play(Modifier.weight(1f).fillMaxHeight())
                            challenge(Modifier.weight(1f).fillMaxHeight())
                        }
                    }
                }
            }
            else -> {
                val ownTurn = view.viewerId != null && view.turnPlayerId == view.viewerId
                Text(
                    text = if (!canSendAction || ownTurn) stringResource(Res.string.game_waiting_connection)
                    else stringResource(Res.string.game_waiting_player, playerName(view, view.turnPlayerId)),
                    style = MaterialTheme.typography.bodyMedium,
                    color = PartyDeckColors.Muted,
                )
            }
        }
    }
}

@Composable
private fun ChallengeButton(
    text: String,
    enabled: Boolean,
    onClick: () -> Unit,
    maxLabelLines: Int,
    modifier: Modifier = Modifier,
) {
    OutlinedButton(
        onClick = onClick,
        enabled = enabled,
        modifier = modifier.heightIn(min = 56.dp).testTag("game-challenge"),
        shape = RoundedCornerShape(28.dp),
        border = BorderStroke(1.dp, PartyDeckColors.Outline),
        colors = ButtonDefaults.outlinedButtonColors(
            contentColor = PartyDeckColors.Copper,
            disabledContentColor = PartyDeckColors.Muted,
        ),
        contentPadding = PaddingValues(horizontal = 16.dp, vertical = 16.dp),
    ) {
        Text(
            text,
            style = MaterialTheme.typography.labelLarge,
            textAlign = TextAlign.Center,
            maxLines = maxLabelLines,
            overflow = TextOverflow.Ellipsis,
        )
    }
}

@Composable
private fun EmptyHandMessage(latestClaimPending: Boolean) {
    Column(Modifier.fillMaxWidth().padding(horizontal = 20.dp, vertical = 14.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
        Text(stringResource(Res.string.game_empty_hand_title), style = MaterialTheme.typography.headlineSmall)
        Text(
            stringResource(if (latestClaimPending) Res.string.game_last_play_pending else Res.string.game_empty_hand_safe),
            style = MaterialTheme.typography.bodyMedium,
            color = PartyDeckColors.Muted,
        )
    }
}

@Composable
private fun SpectatorMessage(unknownViewer: Boolean) {
    Column(Modifier.fillMaxWidth().padding(horizontal = 20.dp, vertical = 14.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
        Text(stringResource(Res.string.game_spectating_title), style = MaterialTheme.typography.headlineSmall)
        Text(
            stringResource(if (unknownViewer) Res.string.game_unknown_spectator else Res.string.game_spectating_detail),
            style = MaterialTheme.typography.bodyMedium,
            color = PartyDeckColors.Muted,
        )
    }
}
