package dev.partydeck.app.ui.game

import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.offset
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.rotate
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.semantics.LiveRegionMode
import androidx.compose.ui.semantics.clearAndSetSemantics
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.heading
import androidx.compose.ui.semantics.liveRegion
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import dev.partydeck.app.ui.theme.PartyDeckColors
import dev.partydeck.app.ui.theme.SectionLabel
import dev.partydeck.core.GameView
import dev.partydeck.core.PlayerId
import dev.partydeck.core.PlayerView
import dev.partydeck.resources.Res
import dev.partydeck.resources.game_active_seat_status
import dev.partydeck.resources.game_card_count
import dev.partydeck.resources.game_claim_facedown
import dev.partydeck.resources.game_claim_sentence
import dev.partydeck.resources.game_fuse_tests
import dev.partydeck.resources.game_hide_players
import dev.partydeck.resources.game_hide_previous_reveal
import dev.partydeck.resources.game_latest_claim
import dev.partydeck.resources.game_open_instruction
import dev.partydeck.resources.game_open_round
import dev.partydeck.resources.game_out
import dev.partydeck.resources.game_player_fallback
import dev.partydeck.resources.game_player_numbered
import dev.partydeck.resources.game_player_you
import dev.partydeck.resources.game_players_turn
import dev.partydeck.resources.game_previous_reveal
import dev.partydeck.resources.game_rank_table
import dev.partydeck.resources.game_round_label
import dev.partydeck.resources.game_seat_claim_pending
import dev.partydeck.resources.game_seat_next_deal
import dev.partydeck.resources.game_seat_numbered_name
import dev.partydeck.resources.game_seat_summary
import dev.partydeck.resources.game_view_players
import dev.partydeck.resources.game_watching_table
import dev.partydeck.resources.game_you
import dev.partydeck.resources.game_your_turn
import org.jetbrains.compose.resources.pluralStringResource
import org.jetbrains.compose.resources.stringResource

@Composable
internal fun playerName(view: GameView, playerId: PlayerId?): String {
    val seat = view.players.indexOfFirst { it.id == playerId }
    if (seat < 0) return stringResource(Res.string.game_player_fallback)
    val name = view.players[seat].displayName
    return if (view.players.count { it.displayName.equals(name, ignoreCase = true) } > 1) {
        stringResource(Res.string.game_player_numbered, name, seat + 1)
    } else name
}

@Composable
internal fun PublicGameTable(
    view: GameView,
    largeText: Boolean,
    modifier: Modifier = Modifier,
    compact: Boolean = false,
    showCompactRoster: Boolean = false,
    decorateClaim: Boolean = false,
) {
    val claimForDecoration = view.latestClaim.takeIf { decorateClaim }
    Column(modifier) {
        TurnHeading(view, Modifier.padding(horizontal = 20.dp), compact)
        Spacer(Modifier.height(if (compact) 10.dp else 16.dp))
        LatestClaim(view, largeText, Modifier.padding(horizontal = 20.dp), compact)
        Spacer(Modifier.height(if (compact) 6.dp else 16.dp))
        PlayerRail(view, largeText, collapse = compact && !showCompactRoster)
        if (claimForDecoration != null) {
            Box(Modifier.fillMaxWidth().padding(top = 12.dp), contentAlignment = Alignment.Center) {
                ClaimPile(claimForDecoration.cardCount, Modifier.size(width = 112.dp, height = 104.dp))
            }
        }
        view.roundOutcome?.takeIf { it.roundNumber < view.roundNumber }?.let { outcome ->
            var showHistory by rememberSaveable(outcome.roundNumber) { mutableStateOf(false) }
            TextButton(
                onClick = { showHistory = !showHistory },
                modifier = Modifier.padding(horizontal = 20.dp).heightIn(min = 48.dp),
                contentPadding = PaddingValues(horizontal = 0.dp, vertical = 12.dp),
            ) {
                Text(
                    text = stringResource(
                        if (showHistory) Res.string.game_hide_previous_reveal else Res.string.game_previous_reveal,
                        outcome.roundNumber,
                    ),
                    color = PartyDeckColors.Muted,
                )
            }
            if (showHistory) {
                ChallengeResult(
                    view,
                    outcome,
                    largeText,
                    modifier = Modifier.padding(horizontal = 20.dp, vertical = 12.dp),
                    announceVerdict = false,
                )
            }
        }
    }
}

@Composable
private fun TurnHeading(view: GameView, modifier: Modifier = Modifier, compact: Boolean = false) {
    val ownTurn = view.viewerId != null && view.turnPlayerId == view.viewerId
    val turn = when {
        ownTurn -> stringResource(Res.string.game_your_turn)
        view.turnPlayerId != null -> stringResource(Res.string.game_players_turn, playerName(view, view.turnPlayerId))
        else -> stringResource(Res.string.game_watching_table)
    }
    Row(
        modifier = modifier.fillMaxWidth(),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(16.dp),
    ) {
        Column(Modifier.weight(1f)) {
            Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                Text(
                    text = turn,
                    style = MaterialTheme.typography.labelLarge,
                    color = if (ownTurn) PartyDeckColors.Citron else PartyDeckColors.Muted,
                    modifier = Modifier.weight(1f).semantics { liveRegion = LiveRegionMode.Polite },
                )
                if (compact) SectionLabel(stringResource(Res.string.game_round_label, view.roundNumber))
            }
            Text(
                text = stringResource(Res.string.game_rank_table, rankName(view.tableRank)),
                style = MaterialTheme.typography.headlineMedium,
                color = PartyDeckColors.Paper,
                modifier = Modifier.semantics { heading() },
            )
            if (!compact) SectionLabel(stringResource(Res.string.game_round_label, view.roundNumber))
        }
        Box(
            modifier = Modifier.size(60.dp).background(PartyDeckColors.Citron, CircleShape),
            contentAlignment = Alignment.Center,
        ) {
            RankSymbol(view.tableRank, Modifier.size(42.dp))
        }
    }
}

@Composable
private fun PlayerRail(view: GameView, largeText: Boolean, collapse: Boolean = false) {
    var expanded by rememberSaveable { mutableStateOf(false) }
    if (largeText || collapse) {
        Column(Modifier.padding(horizontal = 20.dp)) {
            TextButton(
                onClick = { expanded = !expanded },
                modifier = Modifier.heightIn(min = 48.dp),
                contentPadding = PaddingValues(horizontal = 0.dp, vertical = 12.dp),
            ) {
                Text(
                    text = if (expanded) stringResource(Res.string.game_hide_players)
                    else stringResource(Res.string.game_view_players, view.players.size),
                )
            }
            if (expanded) {
                Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
                    view.players.forEach { player -> PublicSeat(view, player, compact = false) }
                }
            }
        }
    } else {
        LazyRow(
            modifier = Modifier.fillMaxWidth(),
            contentPadding = PaddingValues(horizontal = 20.dp),
            horizontalArrangement = Arrangement.spacedBy(10.dp),
        ) {
            items(view.players, key = { it.id }) { player ->
                PublicSeat(view, player, compact = true, modifier = Modifier.width(120.dp))
            }
        }
    }
}

@Composable
private fun PublicSeat(
    view: GameView,
    player: PlayerView,
    compact: Boolean,
    modifier: Modifier = Modifier,
) {
    val active = player.id == view.turnPlayerId
    val self = player.id == view.viewerId
    val status = when {
        player.eliminated -> stringResource(Res.string.game_out)
        active -> stringResource(
            Res.string.game_active_seat_status,
            pluralStringResource(Res.plurals.game_card_count, player.handCount, player.handCount),
        )
        player.handCount == 0 && view.latestClaim?.playerId == player.id -> stringResource(Res.string.game_seat_claim_pending)
        player.handCount == 0 -> stringResource(Res.string.game_seat_next_deal)
        else -> pluralStringResource(Res.plurals.game_card_count, player.handCount, player.handCount)
    }
    val uniqueName = playerName(view, player.id)
    val spokenName = if (self) stringResource(Res.string.game_player_you, uniqueName) else uniqueName
    val visibleName = when {
        self -> stringResource(Res.string.game_you)
        view.players.count { it.displayName.equals(player.displayName, ignoreCase = true) } > 1 -> stringResource(
            Res.string.game_seat_numbered_name,
            view.players.indexOfFirst { it.id == player.id } + 1,
            player.displayName,
        )
        else -> player.displayName
    }
    val fuse = stringResource(Res.string.game_fuse_tests, player.penaltyAttempts)
    val description = stringResource(Res.string.game_seat_summary, spokenName, status, fuse)
    Column(
        modifier = modifier
            .background(if (active) PartyDeckColors.Surface else Color.Transparent, RoundedCornerShape(12.dp))
            .padding(horizontal = 10.dp, vertical = 8.dp)
            .clearAndSetSemantics { contentDescription = description },
    ) {
        Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(6.dp)) {
            if (active) Box(Modifier.size(6.dp).background(PartyDeckColors.Citron, CircleShape))
            Text(
                text = visibleName,
                style = MaterialTheme.typography.labelMedium,
                fontWeight = FontWeight.SemiBold,
                color = if (player.eliminated) PartyDeckColors.Muted else PartyDeckColors.Paper,
                maxLines = if (compact) 1 else Int.MAX_VALUE,
                overflow = TextOverflow.Ellipsis,
            )
        }
        Text(
            status,
            style = MaterialTheme.typography.labelSmall,
            color = if (active) PartyDeckColors.Citron else PartyDeckColors.Muted,
        )
        Spacer(Modifier.height(6.dp))
        FuseLights(player.penaltyAttempts, player.eliminated, compact = true)
    }
}

@Composable
private fun LatestClaim(
    view: GameView,
    largeText: Boolean,
    modifier: Modifier = Modifier,
    compact: Boolean = false,
) {
    val claim = view.latestClaim
    Row(
        modifier = modifier.fillMaxWidth(),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(if (largeText) 12.dp else 18.dp),
    ) {
        if (!largeText && !compact) ClaimPile(claim?.cardCount ?: 1, Modifier.size(width = 102.dp, height = 96.dp))
        Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(5.dp)) {
            if (claim == null) {
                Text(
                    text = stringResource(Res.string.game_open_round),
                    style = MaterialTheme.typography.headlineSmall,
                    color = PartyDeckColors.Paper,
                )
                Text(
                    stringResource(Res.string.game_open_instruction),
                    style = MaterialTheme.typography.bodySmall,
                    color = PartyDeckColors.Muted,
                )
            } else {
                SectionLabel(stringResource(Res.string.game_latest_claim))
                Text(
                    text = stringResource(
                        Res.string.game_claim_sentence,
                        playerName(view, claim.playerId),
                        rankClaim(view.tableRank, claim.cardCount),
                    ),
                    style = MaterialTheme.typography.titleSmall,
                    color = PartyDeckColors.Paper,
                )
                Text(
                    stringResource(Res.string.game_claim_facedown),
                    style = MaterialTheme.typography.bodySmall,
                    color = PartyDeckColors.Muted,
                )
            }
        }
    }
}

@Composable
private fun ClaimPile(count: Int, modifier: Modifier = Modifier) {
    Box(modifier.clearAndSetSemantics { }, contentAlignment = Alignment.Center) {
        Canvas(Modifier.fillMaxSize()) { drawOval(PartyDeckColors.Surface) }
        repeat(count.coerceIn(1, 3)) { index ->
            val centerOffset = index - (count - 1) / 2f
            CardBack(
                Modifier.size(width = 50.dp, height = 75.dp)
                    .offset(x = (centerOffset * 17).dp, y = (kotlin.math.abs(centerOffset) * 3).dp)
                    .rotate(centerOffset * 13f),
            )
        }
    }
}

/** The six marks describe public tests, never the secret future burnout position. */
@Composable
internal fun FuseLights(
    attempts: Int,
    burnedOut: Boolean,
    compact: Boolean,
    modifier: Modifier = Modifier,
) {
    val description = stringResource(Res.string.game_fuse_tests, attempts)
    val diameter = if (compact) 8.dp else 28.dp
    Row(
        modifier = modifier.semantics { contentDescription = description },
        horizontalArrangement = Arrangement.spacedBy(if (compact) 4.dp else 12.dp),
    ) {
        repeat(6) { index ->
            val tested = index < attempts
            val latestBurnout = burnedOut && index == attempts - 1
            val color = when {
                latestBurnout -> PartyDeckColors.Copper
                tested -> PartyDeckColors.Muted
                else -> PartyDeckColors.Paper
            }
            Canvas(Modifier.size(diameter).clearAndSetSemantics { }) {
                val stroke = if (compact) 1.dp.toPx() else 1.7.dp.toPx()
                drawCircle(color, radius = (size.minDimension - stroke) / 2f, style = Stroke(stroke))
                if (tested) {
                    drawLine(
                        color,
                        Offset(size.width * 0.27f, size.height * 0.73f),
                        Offset(size.width * 0.73f, size.height * 0.27f),
                        strokeWidth = stroke,
                    )
                }
                if (latestBurnout) {
                    drawLine(
                        color,
                        Offset(size.width * 0.27f, size.height * 0.27f),
                        Offset(size.width * 0.73f, size.height * 0.73f),
                        strokeWidth = stroke,
                    )
                }
            }
        }
    }
}
