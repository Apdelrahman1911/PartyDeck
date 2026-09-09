package dev.partydeck.app.ui.game

import androidx.compose.foundation.Canvas
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.semantics.clearAndSetSemantics
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import dev.partydeck.app.ui.theme.PartyDeckColors
import dev.partydeck.core.CardRank
import dev.partydeck.resources.Res
import dev.partydeck.resources.card_back
import dev.partydeck.resources.game_claim_crowns
import dev.partydeck.resources.game_claim_moons
import dev.partydeck.resources.game_claim_stars
import dev.partydeck.resources.game_claim_wilds
import dev.partydeck.resources.game_rank_crown
import dev.partydeck.resources.game_rank_moon
import dev.partydeck.resources.game_rank_star
import dev.partydeck.resources.game_rank_wild
import dev.partydeck.resources.rank_crown
import dev.partydeck.resources.rank_moon
import dev.partydeck.resources.rank_star
import dev.partydeck.resources.rank_wild
import org.jetbrains.compose.resources.painterResource
import org.jetbrains.compose.resources.pluralStringResource
import org.jetbrains.compose.resources.stringResource

@Composable
internal fun rankName(rank: CardRank): String = stringResource(
    when (rank) {
        CardRank.CROWN -> Res.string.game_rank_crown
        CardRank.MOON -> Res.string.game_rank_moon
        CardRank.STAR -> Res.string.game_rank_star
        CardRank.WILD -> Res.string.game_rank_wild
    },
)

@Composable
internal fun rankClaim(rank: CardRank, count: Int): String = pluralStringResource(
    when (rank) {
        CardRank.CROWN -> Res.plurals.game_claim_crowns
        CardRank.MOON -> Res.plurals.game_claim_moons
        CardRank.STAR -> Res.plurals.game_claim_stars
        CardRank.WILD -> Res.plurals.game_claim_wilds
    },
    count,
    count,
)

@Composable
internal fun RankSymbol(
    rank: CardRank,
    modifier: Modifier = Modifier,
    tint: Color = PartyDeckColors.Ink,
) {
    Icon(
        painter = painterResource(
            when (rank) {
                CardRank.CROWN -> Res.drawable.rank_crown
                CardRank.MOON -> Res.drawable.rank_moon
                CardRank.STAR -> Res.drawable.rank_star
                CardRank.WILD -> Res.drawable.rank_wild
            },
        ),
        contentDescription = null,
        tint = tint,
        modifier = modifier,
    )
}

/** Printed artwork only; the caller owns the card's accessible name and action. */
@Composable
internal fun CardFace(
    rank: CardRank,
    modifier: Modifier = Modifier,
    selected: Boolean = false,
) {
    val shape = RoundedCornerShape(9.dp)
    Box(
        modifier
            .clip(shape)
            .background(PartyDeckColors.Paper)
            .border(
                width = if (selected) 3.dp else 1.dp,
                color = if (selected) PartyDeckColors.Ink else PartyDeckColors.Paper,
                shape = shape,
            )
            .clearAndSetSemantics { },
    ) {
        Column(
            modifier = Modifier.fillMaxSize().padding(horizontal = 5.dp, vertical = 9.dp),
            horizontalAlignment = Alignment.CenterHorizontally,
        ) {
            Box(Modifier.weight(1f), contentAlignment = Alignment.Center) {
                RankSymbol(rank, Modifier.size(38.dp))
            }
            Text(
                text = rankName(rank),
                color = PartyDeckColors.Ink,
                style = MaterialTheme.typography.labelMedium,
                fontWeight = FontWeight.SemiBold,
                textAlign = TextAlign.Center,
            )
        }
        if (selected) {
            SelectionMark(Modifier.align(Alignment.TopEnd).padding(4.dp).size(17.dp))
        }
    }
}

@Composable
internal fun CardBack(modifier: Modifier = Modifier) {
    Image(
        painter = painterResource(Res.drawable.card_back),
        contentDescription = null,
        contentScale = ContentScale.FillBounds,
        modifier = modifier.clearAndSetSemantics { },
    )
}

@Composable
internal fun SelectionMark(modifier: Modifier = Modifier) {
    Canvas(modifier.clearAndSetSemantics { }) {
        drawCircle(PartyDeckColors.Citron)
        val stroke = size.minDimension * 0.11f
        drawLine(
            color = PartyDeckColors.Ink,
            start = Offset(size.width * 0.25f, size.height * 0.51f),
            end = Offset(size.width * 0.44f, size.height * 0.69f),
            strokeWidth = stroke,
            cap = StrokeCap.Round,
        )
        drawLine(
            color = PartyDeckColors.Ink,
            start = Offset(size.width * 0.44f, size.height * 0.69f),
            end = Offset(size.width * 0.77f, size.height * 0.32f),
            strokeWidth = stroke,
            cap = StrokeCap.Round,
        )
    }
}
