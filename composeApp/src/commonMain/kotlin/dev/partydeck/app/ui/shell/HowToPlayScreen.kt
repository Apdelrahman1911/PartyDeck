package dev.partydeck.app.ui.shell

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.semantics.heading
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.unit.dp
import dev.partydeck.app.ui.theme.DeckButton
import dev.partydeck.app.ui.theme.PartyDeckColors
import dev.partydeck.app.ui.theme.SectionLabel
import dev.partydeck.resources.*
import org.jetbrains.compose.resources.StringResource
import org.jetbrains.compose.resources.stringResource

@Composable
fun HowToPlayScreen(
    hasSession: Boolean,
    onBack: () -> Unit,
    onPractice: () -> Unit,
    modifier: Modifier = Modifier,
) {
    ScrollablePage(modifier) {
        ScreenHeader(stringResource(Res.string.shell_how_to), onBack)
        SectionLabel(stringResource(Res.string.shell_rules_eyebrow))
        Spacer(Modifier.height(10.dp))
        Text(
            stringResource(Res.string.shell_rules_title),
            style = MaterialTheme.typography.headlineLarge,
            modifier = Modifier.semantics { heading() },
        )
        Spacer(Modifier.height(16.dp))
        Text(
            stringResource(Res.string.shell_rules_intro),
            style = MaterialTheme.typography.bodyLarge,
            color = PartyDeckColors.Muted,
        )
        Spacer(Modifier.height(32.dp))
        RuleStep(1, Res.string.shell_rules_step_one_title, Res.string.shell_rules_step_one)
        RuleStep(2, Res.string.shell_rules_step_two_title, Res.string.shell_rules_step_two)
        RuleStep(3, Res.string.shell_rules_step_three_title, Res.string.shell_rules_step_three)
        RuleStep(4, Res.string.shell_rules_step_four_title, Res.string.shell_rules_step_four)
        RuleStep(5, Res.string.shell_rules_step_five_title, Res.string.shell_rules_step_five)
        HorizontalDivider(color = PartyDeckColors.Divider)
        Spacer(Modifier.height(24.dp))
        Text(stringResource(Res.string.shell_rules_empty_title), style = MaterialTheme.typography.titleMedium)
        Spacer(Modifier.height(10.dp))
        Text(
            stringResource(Res.string.shell_rules_empty_description),
            style = MaterialTheme.typography.bodyMedium,
            color = PartyDeckColors.Muted,
        )
        Spacer(Modifier.height(28.dp))
        DeckButton(
            stringResource(if (hasSession) Res.string.shell_return_table else Res.string.shell_practice_action),
            onClick = if (hasSession) onBack else onPractice,
            modifier = Modifier.fillMaxWidth(),
        )
        Spacer(Modifier.height(24.dp))
    }
}

@Composable
private fun RuleStep(number: Int, title: StringResource, description: StringResource) {
    val numberLineHeight = MaterialTheme.typography.labelMedium.lineHeight
    val badgeSize = maxOf(32.dp, with(LocalDensity.current) { numberLineHeight.toDp() } + 8.dp)
    Row(
        Modifier.fillMaxWidth().padding(bottom = 28.dp),
        horizontalArrangement = Arrangement.spacedBy(16.dp),
        verticalAlignment = Alignment.Top,
    ) {
        Box(
            Modifier.size(badgeSize).background(PartyDeckColors.Citron, CircleShape),
            contentAlignment = Alignment.Center,
        ) {
            Text(number.toString(), style = MaterialTheme.typography.labelMedium, color = PartyDeckColors.Ink)
        }
        Column(Modifier.weight(1f)) {
            Text(stringResource(title), style = MaterialTheme.typography.titleMedium)
            Spacer(Modifier.height(8.dp))
            Text(stringResource(description), style = MaterialTheme.typography.bodyMedium, color = PartyDeckColors.Muted)
        }
    }
}
