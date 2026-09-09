package dev.partydeck.app.ui.shell

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.Image
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.BoxWithConstraints
import androidx.compose.foundation.layout.Column
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
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.rotate
import androidx.compose.ui.graphics.ColorFilter
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.semantics.heading
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import dev.partydeck.app.ui.theme.DeckButton
import dev.partydeck.app.ui.theme.PartyDeckColors
import dev.partydeck.app.ui.theme.SectionLabel
import dev.partydeck.games.PartyDeckGames
import dev.partydeck.resources.*
import org.jetbrains.compose.resources.DrawableResource
import org.jetbrains.compose.resources.painterResource
import org.jetbrains.compose.resources.stringResource

@Composable
fun HomeScreen(
    onHost: () -> Unit,
    onJoin: () -> Unit,
    onPractice: () -> Unit,
    onHowTo: () -> Unit,
    onSettings: () -> Unit,
    modifier: Modifier = Modifier,
) {
    BoxWithConstraints(modifier.fillMaxSize()) {
        val availableWidth = maxWidth
        val fontScale = LocalDensity.current.fontScale
        val largeText = fontScale >= 1.5f
        val shortHeight = maxHeight < 500.dp
        val compact = maxHeight < 700.dp || fontScale > 1.3f
        val wide = (maxWidth >= 760.dp || (shortHeight && maxWidth >= 600.dp)) && !largeText
        Column(
            Modifier.fillMaxSize().verticalScroll(rememberScrollState())
                .padding(horizontal = 24.dp, vertical = 12.dp),
            horizontalAlignment = Alignment.CenterHorizontally,
        ) {
            Row(
                modifier = Modifier.widthIn(max = 1000.dp).fillMaxWidth(),
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                if (!largeText) Image(painterResource(Res.drawable.partydeck_mark), null, Modifier.size(40.dp))
                Text(
                    stringResource(Res.string.shell_app_name),
                    modifier = Modifier.weight(1f),
                    style = MaterialTheme.typography.titleMedium,
                )
                ShellIconAction(
                    Res.drawable.icon_settings,
                    stringResource(Res.string.shell_settings),
                    onSettings,
                    Modifier.testTag("home-settings"),
                )
            }
            Spacer(Modifier.height(if (largeText) 12.dp else if (compact) 20.dp else 36.dp))
            if (wide) {
                Row(
                    modifier = Modifier.widthIn(max = 1000.dp).fillMaxWidth(),
                    horizontalArrangement = Arrangement.spacedBy(48.dp),
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    Column(Modifier.weight(1f)) {
                        if (!shortHeight) {
                            HomeTitle(compact = compact)
                            Spacer(Modifier.height(28.dp))
                        }
                        HomeActions(onHost, onJoin, onPractice, onHowTo, horizontalActions = true)
                    }
                    HeroCards(
                        Modifier.weight(1f),
                        height = if (shortHeight) minOf(250.dp, (availableWidth - 96.dp) * 0.45f) else 360.dp,
                    )
                }
            } else {
                Column(Modifier.widthIn(max = 480.dp).fillMaxWidth()) {
                    if (!largeText) {
                        HomeTitle(compact)
                        HeroCards(
                            modifier = Modifier.fillMaxWidth().padding(vertical = 6.dp),
                            height = if (compact) 128.dp else 208.dp,
                        )
                    }
                    HomeActions(onHost, onJoin, onPractice, onHowTo)
                }
            }
            Spacer(Modifier.height(12.dp))
        }
    }
}

@Composable
private fun HomeTitle(compact: Boolean) {
    SectionLabel(stringResource(Res.string.shell_home_eyebrow))
    Spacer(Modifier.height(10.dp))
    Text(
        text = stringResource(Res.string.shell_home_title),
        modifier = Modifier.semantics { heading() },
        style = if (compact) MaterialTheme.typography.headlineLarge else MaterialTheme.typography.displayMedium,
    )
}

@Composable
private fun HomeActions(
    onHost: () -> Unit,
    onJoin: () -> Unit,
    onPractice: () -> Unit,
    onHowTo: () -> Unit,
    horizontalActions: Boolean = false,
) {
    val game = PartyDeckGames.lastLight
    Row(
        modifier = Modifier.fillMaxWidth(),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(10.dp),
    ) {
        Icon(painterResource(Res.drawable.rank_star), null, Modifier.size(20.dp), tint = PartyDeckColors.Citron)
        Text(game.title, Modifier.semantics { heading() }, style = MaterialTheme.typography.titleMedium)
        HorizontalDivider(Modifier.weight(1f), color = PartyDeckColors.Divider)
    }
    Spacer(Modifier.height(8.dp))
    Text(stringResource(Res.string.shell_home_description), style = MaterialTheme.typography.bodyMedium)
    Spacer(Modifier.height(4.dp))
    Text(
        stringResource(Res.string.shell_home_details, game.minPlayers, game.maxPlayers),
        style = MaterialTheme.typography.bodySmall,
        color = PartyDeckColors.Muted,
    )
    Spacer(Modifier.height(20.dp))
    if (horizontalActions) {
        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(12.dp)) {
            DeckButton(
                stringResource(Res.string.shell_host_action), onHost,
                Modifier.weight(1f).testTag("home-host"),
            )
            DeckButton(
                stringResource(Res.string.shell_join_action), onJoin,
                Modifier.weight(1f).testTag("home-join"), secondary = true,
            )
        }
    } else {
        DeckButton(
            stringResource(Res.string.shell_host_action), onHost,
            Modifier.fillMaxWidth().testTag("home-host"),
        )
        Spacer(Modifier.height(10.dp))
        DeckButton(
            stringResource(Res.string.shell_join_action), onJoin,
            Modifier.fillMaxWidth().testTag("home-join"), secondary = true,
        )
    }
    Spacer(Modifier.height(6.dp))
    TextButton(
        onClick = onPractice,
        modifier = Modifier.fillMaxWidth().heightIn(min = 48.dp).testTag("home-practice"),
    ) {
        Text(stringResource(Res.string.shell_practice_action), textAlign = TextAlign.Center)
    }
    TextButton(
        onClick = onHowTo,
        modifier = Modifier.fillMaxWidth().heightIn(min = 48.dp).testTag("home-how-to"),
    ) {
        Text(stringResource(Res.string.shell_how_to), color = PartyDeckColors.Muted)
    }
}

/** Decorative, original rank composition; the actionable hand belongs to the game screen. */
@Composable
private fun HeroCards(modifier: Modifier, height: Dp) {
    val cardHeight = height * 0.86f
    val cardWidth = cardHeight * (2f / 3f)
    Box(modifier.height(height), contentAlignment = Alignment.Center) {
        Image(
            painterResource(Res.drawable.card_back), null,
            Modifier.offset(x = -cardWidth * 0.68f, y = 5.dp).rotate(-16f).size(cardWidth, cardHeight),
        )
        HeroFace(
            symbol = Res.drawable.rank_moon,
            tint = PartyDeckColors.Copper,
            modifier = Modifier.offset(x = cardWidth * 0.65f, y = 6.dp).rotate(16f).size(cardWidth, cardHeight),
        )
        HeroFace(
            symbol = Res.drawable.rank_crown,
            tint = PartyDeckColors.Ink,
            modifier = Modifier.rotate(-3f).size(cardWidth, cardHeight),
        )
    }
}

@Composable
private fun HeroFace(
    symbol: DrawableResource,
    tint: androidx.compose.ui.graphics.Color,
    modifier: Modifier,
) {
    Surface(
        modifier = modifier,
        color = PartyDeckColors.Paper,
        shape = RoundedCornerShape(10.dp),
        border = BorderStroke(1.dp, PartyDeckColors.Ink.copy(alpha = 0.15f)),
        shadowElevation = 4.dp,
    ) {
        Box(Modifier.fillMaxSize().padding(10.dp)) {
            Image(
                painterResource(symbol), null,
                Modifier.fillMaxSize(0.48f).align(Alignment.Center),
                colorFilter = ColorFilter.tint(tint),
            )
            Image(
                painterResource(symbol), null,
                Modifier.size(15.dp).align(Alignment.TopStart),
                colorFilter = ColorFilter.tint(tint),
            )
            Image(
                painterResource(symbol), null,
                Modifier.size(15.dp).align(Alignment.BottomEnd).rotate(180f),
                colorFilter = ColorFilter.tint(tint),
            )
        }
    }
}
