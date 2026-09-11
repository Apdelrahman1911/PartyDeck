package dev.partydeck.app.ui.shell

import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.selection.selectable
import androidx.compose.foundation.selection.selectableGroup
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.RadioButton
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.SideEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.heading
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.semantics.stateDescription
import androidx.compose.ui.unit.dp
import dev.partydeck.app.controller.GameplayPresentation
import dev.partydeck.app.controller.GameplayPresentationState
import dev.partydeck.app.controller.PresentationLifecycle
import dev.partydeck.app.controller.PresentationSelection
import dev.partydeck.app.ui.theme.DeckButton
import dev.partydeck.app.ui.theme.LocalReduceMotion
import dev.partydeck.app.ui.theme.PartyDeckColors
import dev.partydeck.resources.*
import org.jetbrains.compose.resources.stringResource

/** Availability comes from the platform owner; an unavailable style is never offered. */
@Composable
internal fun GameplayPresentationPicker(
    state: GameplayPresentationState,
    onPrepareSelection: (GameplayPresentation) -> PresentationSelection?,
    modifier: Modifier = Modifier,
) {
    val choices = GameplayPresentation.entries.filter { it in state.available }
    if (choices.none { it != GameplayPresentation.COMPOSE }) return
    var expanded by remember { mutableStateOf(false) }
    var selection by remember { mutableStateOf<PresentationSelection?>(null) }
    DisposableEffect(Unit) {
        onDispose { selection?.cancel() }
    }
    val selectedLabel = presentationLabel(state.selected)
    TextButton(
        onClick = {
            selection?.cancel()
            selection = null
            expanded = true
        },
        modifier = modifier.heightIn(min = 48.dp).testTag("presentation-picker")
            .semantics { stateDescription = selectedLabel },
    ) {
        Text(stringResource(Res.string.presentation_choose), color = PartyDeckColors.Citron)
    }
    if (expanded) {
        AlertDialog(
            onDismissRequest = { expanded = false },
            properties = presentationPickerDialogProperties(),
            modifier = Modifier.testTag("presentation-options"),
            title = { Text(stringResource(Res.string.presentation_choose)) },
            text = {
                Column(Modifier.verticalScroll(rememberScrollState())) {
                    Text(stringResource(Res.string.presentation_local_choice))
                    Spacer(Modifier.height(8.dp))
                    Text(stringResource(Res.string.presentation_accessibility_route))
                    Spacer(Modifier.height(16.dp))
                    // The row owns the click and radio semantics, as recommended by Compose.
                    Column(Modifier.selectableGroup()) {
                        choices.forEach { choice ->
                            Row(
                                modifier = Modifier.fillMaxWidth().heightIn(min = 56.dp)
                                    .selectable(
                                        selected = choice == state.selected,
                                        onClick = {
                                            expanded = false
                                            selection?.cancel()
                                            selection = onPrepareSelection(choice)
                                        },
                                        role = Role.RadioButton,
                                    )
                                    .padding(vertical = 12.dp)
                                    .testTag("presentation-choice-${choice.name.lowercase()}"),
                                verticalAlignment = Alignment.CenterVertically,
                            ) {
                                RadioButton(selected = choice == state.selected, onClick = null)
                                Text(
                                    presentationLabel(choice),
                                    modifier = Modifier.padding(start = 16.dp),
                                    style = MaterialTheme.typography.bodyLarge,
                                )
                            }
                        }
                    }
                }
            },
            confirmButton = {
                TextButton(
                    onClick = { expanded = false },
                    modifier = Modifier.heightIn(min = 48.dp).testTag("presentation-picker-done"),
                ) { Text(stringResource(Res.string.shell_done)) }
            },
            containerColor = PartyDeckColors.Surface,
        )
    } else {
        val disposedPickerSelection = selection
        // SideEffect follows Dialog's disposal; this picker disables Skiko's deferred exit.
        SideEffect { disposedPickerSelection?.commit() }
    }
}

/** Native attachment is platform-owned. The shell beneath it contains no private game content. */
@Composable
internal fun EmbeddedPresentationCover(
    lifecycle: PresentationLifecycle,
    onUseCompose: () -> Unit,
    modifier: Modifier = Modifier,
) {
    ScrollablePage(modifier.testTag("presentation-cover")) {
        Spacer(Modifier.height(24.dp))
        Text(
            stringResource(
                if (lifecycle == PresentationLifecycle.OPENING) Res.string.presentation_opening
                else Res.string.presentation_open,
            ),
            modifier = Modifier.semantics { heading() },
            style = MaterialTheme.typography.headlineMedium,
        )
        Spacer(Modifier.height(16.dp))
        Text(
            stringResource(Res.string.presentation_standard_available),
            style = MaterialTheme.typography.bodyLarge,
        )
        Spacer(Modifier.height(24.dp))
        DeckButton(
            text = stringResource(Res.string.presentation_use_standard),
            onClick = onUseCompose,
            modifier = Modifier.fillMaxWidth().testTag("presentation-use-standard"),
        )
        if (lifecycle == PresentationLifecycle.OPENING && !LocalReduceMotion.current) {
            Spacer(Modifier.height(24.dp))
            CircularProgressIndicator(Modifier.size(28.dp))
        }
    }
}

@Composable
private fun presentationLabel(presentation: GameplayPresentation): String = stringResource(
    when (presentation) {
        GameplayPresentation.COMPOSE -> Res.string.presentation_standard
        GameplayPresentation.GODOT_2D -> Res.string.presentation_two_d
        GameplayPresentation.GODOT_3D -> Res.string.presentation_three_d
    },
)
