package dev.partydeck.app.ui.game

import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.animation.core.tween
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.BoxWithConstraints
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.itemsIndexed
import androidx.compose.foundation.selection.toggleable
import androidx.compose.foundation.shape.RoundedCornerShape
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
import androidx.compose.ui.draw.rotate
import androidx.compose.ui.focus.onFocusChanged
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.semantics.LiveRegionMode
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.clearAndSetSemantics
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.liveRegion
import androidx.compose.ui.semantics.onClick
import androidx.compose.ui.semantics.selected
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.semantics.stateDescription
import androidx.compose.ui.unit.dp
import dev.partydeck.app.ui.theme.DeckButton
import dev.partydeck.app.ui.theme.LocalReduceMotion
import dev.partydeck.app.ui.theme.PartyDeckColors
import dev.partydeck.core.Card
import dev.partydeck.core.CardId
import dev.partydeck.resources.Res
import dev.partydeck.resources.game_card_count
import dev.partydeck.resources.game_card_description
import dev.partydeck.resources.game_card_selected
import dev.partydeck.resources.game_card_unselected
import dev.partydeck.resources.game_deselect_card
import dev.partydeck.resources.game_hand_hidden
import dev.partydeck.resources.game_hand_hidden_detail
import dev.partydeck.resources.game_hand_scroll
import dev.partydeck.resources.game_hide_hand
import dev.partydeck.resources.game_select_card
import dev.partydeck.resources.game_selected_count
import dev.partydeck.resources.game_selection_limit
import dev.partydeck.resources.game_show_hand
import dev.partydeck.resources.game_your_hand
import org.jetbrains.compose.resources.pluralStringResource
import org.jetbrains.compose.resources.stringResource

@Composable
internal fun PrivateHand(
    cards: List<Card>,
    selectedIds: Set<CardId>,
    selectionLimit: Int,
    shown: Boolean,
    canReveal: Boolean,
    canSelect: Boolean,
    largeText: Boolean,
    selectionLimitReached: Boolean,
    onToggle: (CardId) -> Unit,
    onHide: () -> Unit,
    onShow: () -> Unit,
    modifier: Modifier = Modifier,
) {
    Column(modifier.testTag("game-hand")) {
        val heading: @Composable () -> Unit = {
            Column {
                Text(
                    stringResource(Res.string.game_your_hand),
                    style = MaterialTheme.typography.titleSmall,
                    color = PartyDeckColors.Paper,
                )
                Text(
                    text = if (shown && canSelect) {
                        stringResource(Res.string.game_selected_count, selectedIds.size, selectionLimit)
                    } else {
                        pluralStringResource(Res.plurals.game_card_count, cards.size, cards.size)
                    },
                    style = MaterialTheme.typography.labelMedium,
                    color = PartyDeckColors.Muted,
                )
            }
        }
        val hide: @Composable () -> Unit = {
            if (shown) {
                TextButton(
                    onClick = onHide,
                    modifier = Modifier.heightIn(min = 48.dp).testTag("game-hide-hand"),
                    contentPadding = PaddingValues(horizontal = 12.dp, vertical = 12.dp),
                ) {
                    Text(stringResource(Res.string.game_hide_hand), color = PartyDeckColors.Paper)
                }
            }
        }
        if (largeText) {
            Column(Modifier.fillMaxWidth().padding(horizontal = 20.dp)) {
                heading()
                hide()
            }
        } else {
            Row(
                modifier = Modifier.fillMaxWidth().padding(horizontal = 20.dp),
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                Box(Modifier.weight(1f)) { heading() }
                hide()
            }
        }

        if (!shown) {
            ConcealedHand(
                canReveal = canReveal,
                onShow = onShow,
                modifier = Modifier.padding(horizontal = 20.dp, vertical = 12.dp),
            )
        } else if (largeText) {
            Column(
                modifier = Modifier.padding(horizontal = 20.dp, vertical = 12.dp),
                verticalArrangement = Arrangement.spacedBy(10.dp),
            ) {
                cards.forEachIndexed { index, card ->
                    key(card.id) {
                        LargeHandCard(
                            card = card,
                            index = index,
                            count = cards.size,
                            isSelected = card.id in selectedIds,
                            canSelect = canSelect,
                            onToggle = { onToggle(card.id) },
                        )
                    }
                }
            }
        } else {
            BoxWithConstraints(Modifier.fillMaxWidth()) {
                val availableWidth = maxWidth - 40.dp
                val gapCount = (cards.size - 1).coerceAtLeast(0)
                val smallestRow = 64.dp * cards.size + 6.dp * gapCount
                val scrolls = smallestRow > availableWidth
                val gap = if (!scrolls && gapCount > 0) {
                    ((availableWidth - 64.dp * cards.size) / gapCount).coerceIn(6.dp, 8.dp)
                } else 8.dp
                val cardWidth = 64.dp
                Column {
                    LazyRow(
                        modifier = Modifier.fillMaxWidth(),
                        contentPadding = PaddingValues(horizontal = 20.dp, vertical = 10.dp),
                        horizontalArrangement = Arrangement.spacedBy(gap),
                    ) {
                        itemsIndexed(cards, key = { _, card -> card.id }) { index, card ->
                            HandCard(
                                card = card,
                                index = index,
                                count = cards.size,
                                isSelected = card.id in selectedIds,
                                canSelect = canSelect,
                                onToggle = { onToggle(card.id) },
                                modifier = Modifier.width(cardWidth).height(cardWidth * 1.5f + 8.dp),
                            )
                        }
                    }
                    if (scrolls) {
                        Text(
                            text = stringResource(Res.string.game_hand_scroll, cards.size),
                            color = PartyDeckColors.Muted,
                            style = MaterialTheme.typography.labelSmall,
                            modifier = Modifier.padding(horizontal = 20.dp),
                        )
                    }
                }
            }
        }

        if (selectionLimitReached) {
            Text(
                text = pluralStringResource(
                    Res.plurals.game_selection_limit,
                    selectionLimit,
                    selectionLimit,
                ),
                color = PartyDeckColors.Citron,
                style = MaterialTheme.typography.bodySmall,
                modifier = Modifier.padding(horizontal = 20.dp, vertical = 6.dp)
                    .heightIn(min = 48.dp)
                    .semantics { liveRegion = LiveRegionMode.Polite },
            )
        }
    }
}

@Composable
private fun ConcealedHand(
    canReveal: Boolean,
    onShow: () -> Unit,
    modifier: Modifier = Modifier,
) {
    Surface(
        modifier = modifier.fillMaxWidth(),
        shape = RoundedCornerShape(18.dp),
        color = PartyDeckColors.Surface,
        border = BorderStroke(1.dp, PartyDeckColors.Divider),
    ) {
        Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(14.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(14.dp)) {
                Box(Modifier.size(width = 46.dp, height = 62.dp), contentAlignment = Alignment.Center) {
                    CardBack(Modifier.size(width = 36.dp, height = 54.dp).rotate(-9f))
                    CardBack(Modifier.size(width = 36.dp, height = 54.dp).rotate(6f))
                }
                Column(Modifier.weight(1f)) {
                    Text(
                        stringResource(Res.string.game_hand_hidden),
                        style = MaterialTheme.typography.titleSmall,
                    )
                    Text(
                        stringResource(Res.string.game_hand_hidden_detail),
                        style = MaterialTheme.typography.bodySmall,
                        color = PartyDeckColors.Muted,
                    )
                }
            }
            DeckButton(
                text = stringResource(Res.string.game_show_hand),
                onClick = onShow,
                enabled = canReveal,
                secondary = true,
                modifier = Modifier.fillMaxWidth().testTag("game-reveal-hand"),
            )
        }
    }
}

@Composable
private fun cardSemantics(
    card: Card,
    index: Int,
    count: Int,
    isSelected: Boolean,
    canSelect: Boolean,
    onToggle: () -> Unit,
): Modifier {
    val description = stringResource(Res.string.game_card_description, rankName(card.rank), index + 1, count)
    val state = stringResource(if (isSelected) Res.string.game_card_selected else Res.string.game_card_unselected)
    val action = stringResource(if (isSelected) Res.string.game_deselect_card else Res.string.game_select_card)
    return Modifier
        .toggleable(value = isSelected, enabled = canSelect, role = Role.Checkbox) { onToggle() }
        .semantics {
            contentDescription = description
            selected = isSelected
            stateDescription = state
            onClick(label = action, action = null)
        }
        .testTag("game-card-$index")
}

@Composable
private fun HandCard(
    card: Card,
    index: Int,
    count: Int,
    isSelected: Boolean,
    canSelect: Boolean,
    onToggle: () -> Unit,
    modifier: Modifier = Modifier,
) {
    val reduceMotion = LocalReduceMotion.current
    val lift by animateFloatAsState(
        targetValue = if (isSelected && !reduceMotion) 1f else 0f,
        animationSpec = tween(if (reduceMotion) 0 else 140),
        label = "hand-card-selection",
    )
    var focused by remember { mutableStateOf(false) }
    Box(
        modifier
            .onFocusChanged { focused = it.isFocused }
            .then(cardSemantics(card, index, count, isSelected, canSelect, onToggle))
            .border(
                2.dp,
                if (focused) PartyDeckColors.Citron else Color.Transparent,
                RoundedCornerShape(12.dp),
            )
            .padding(top = 8.dp),
    ) {
        CardFace(
            rank = card.rank,
            selected = isSelected,
            modifier = Modifier.matchParentSize().graphicsLayer {
                translationY = -6.dp.toPx() * lift
            },
        )
    }
}

@Composable
private fun LargeHandCard(
    card: Card,
    index: Int,
    count: Int,
    isSelected: Boolean,
    canSelect: Boolean,
    onToggle: () -> Unit,
) {
    var focused by remember { mutableStateOf(false) }
    Surface(
        modifier = Modifier.fillMaxWidth()
            .onFocusChanged { focused = it.isFocused }
            .then(cardSemantics(card, index, count, isSelected, canSelect, onToggle)),
        shape = RoundedCornerShape(14.dp),
        color = PartyDeckColors.Paper,
        contentColor = PartyDeckColors.Ink,
        border = BorderStroke(
            if (isSelected || focused) 3.dp else 1.dp,
            if (isSelected || focused) PartyDeckColors.Ink else PartyDeckColors.Paper,
        ),
    ) {
        Row(
            modifier = Modifier.padding(16.dp).clearAndSetSemantics { },
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(16.dp),
        ) {
            RankSymbol(card.rank, Modifier.size(42.dp))
            Text(rankName(card.rank), style = MaterialTheme.typography.titleSmall, modifier = Modifier.weight(1f))
            if (isSelected) SelectionMark(Modifier.size(24.dp)) else Spacer(Modifier.size(24.dp))
        }
    }
}
