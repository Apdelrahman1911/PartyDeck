package dev.partydeck.app.ui.shell

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.selection.toggleable
import androidx.compose.foundation.text.selection.SelectionContainer
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.heading
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.unit.dp
import dev.partydeck.app.controller.AppSettings
import dev.partydeck.app.controller.AppUiState
import dev.partydeck.app.ui.theme.PartyDeckColors
import dev.partydeck.app.ui.theme.SectionLabel
import dev.partydeck.resources.*
import kotlinx.coroutines.CancellationException
import org.jetbrains.compose.resources.DrawableResource
import org.jetbrains.compose.resources.painterResource
import org.jetbrains.compose.resources.stringResource

@Composable
fun SettingsScreen(
    state: AppUiState,
    onBack: () -> Unit,
    onSettingsChange: (AppSettings) -> Unit,
    modifier: Modifier = Modifier,
) {
    var showLicenses by remember { mutableStateOf(false) }
    val largeText = LocalDensity.current.fontScale >= 1.5f
    ScrollablePage(modifier) {
        ScreenHeader(stringResource(Res.string.shell_settings), onBack)
        if (!largeText) {
            SectionLabel(stringResource(Res.string.shell_settings_eyebrow))
            Spacer(Modifier.height(10.dp))
            Text(
                stringResource(Res.string.shell_settings_title),
                style = MaterialTheme.typography.headlineLarge,
                modifier = Modifier.semantics { heading() },
            )
            Spacer(Modifier.height(28.dp))
        }
        PreferenceRow(
            icon = if (state.settings.soundEnabled) Res.drawable.icon_sound else Res.drawable.icon_sound_off,
            title = stringResource(Res.string.shell_sound),
            description = stringResource(Res.string.shell_sound_description),
            checked = state.settings.soundEnabled,
            onCheckedChange = { onSettingsChange(state.settings.copy(soundEnabled = it)) },
            modifier = Modifier.testTag("settings-sound"),
        )
        HorizontalDivider(color = PartyDeckColors.Divider)
        PreferenceRow(
            icon = Res.drawable.icon_haptics,
            title = stringResource(Res.string.shell_haptics),
            description = stringResource(Res.string.shell_haptics_description),
            checked = state.settings.hapticsEnabled,
            onCheckedChange = { onSettingsChange(state.settings.copy(hapticsEnabled = it)) },
            modifier = Modifier.testTag("settings-haptics"),
        )
        HorizontalDivider(color = PartyDeckColors.Divider)
        PreferenceRow(
            icon = Res.drawable.icon_motion,
            title = stringResource(Res.string.shell_reduce_motion),
            description = stringResource(Res.string.shell_reduce_motion_description),
            checked = state.settings.reduceMotion,
            onCheckedChange = { onSettingsChange(state.settings.copy(reduceMotion = it)) },
            modifier = Modifier.testTag("settings-reduce-motion"),
        )
        Text(
            stringResource(Res.string.shell_system_reduce_motion),
            modifier = Modifier.padding(top = 8.dp),
            style = MaterialTheme.typography.bodySmall,
            color = PartyDeckColors.Muted,
        )
        Spacer(Modifier.height(36.dp))
        SectionLabel(stringResource(Res.string.shell_privacy_label))
        Spacer(Modifier.height(12.dp))
        Text(stringResource(Res.string.shell_privacy_description), style = MaterialTheme.typography.bodyMedium)
        Spacer(Modifier.height(32.dp))
        SectionLabel(stringResource(Res.string.shell_credits_label))
        Spacer(Modifier.height(12.dp))
        Text(
            stringResource(Res.string.shell_credits_description),
            style = MaterialTheme.typography.bodyMedium,
            color = PartyDeckColors.Muted,
        )
        TextButton(onClick = { showLicenses = true }, modifier = Modifier.heightIn(min = 48.dp)) {
            Text(stringResource(Res.string.shell_credits_action))
        }
        Spacer(Modifier.height(24.dp))
    }
    if (showLicenses) LicenseDialog(onDismiss = { showLicenses = false })
}

@Composable
private fun PreferenceRow(
    icon: DrawableResource,
    title: String,
    description: String,
    checked: Boolean,
    onCheckedChange: (Boolean) -> Unit,
    modifier: Modifier = Modifier,
) {
    val rowModifier = modifier.fillMaxWidth().heightIn(min = 80.dp)
        .toggleable(value = checked, role = Role.Switch, onValueChange = onCheckedChange)
        .padding(vertical = 18.dp)
    if (LocalDensity.current.fontScale >= 1.5f) {
        Column(rowModifier, verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Row(
                Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(16.dp),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Text(title, Modifier.weight(1f), style = MaterialTheme.typography.titleSmall)
                Switch(checked = checked, onCheckedChange = null)
            }
            Text(description, style = MaterialTheme.typography.bodySmall, color = PartyDeckColors.Muted)
        }
    } else {
        Row(
            modifier = rowModifier,
            horizontalArrangement = Arrangement.spacedBy(16.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Icon(painterResource(icon), null, Modifier.size(24.dp), tint = PartyDeckColors.Muted)
            Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                Text(title, style = MaterialTheme.typography.titleSmall)
                Text(description, style = MaterialTheme.typography.bodySmall, color = PartyDeckColors.Muted)
            }
            Switch(checked = checked, onCheckedChange = null)
        }
    }
}

@Composable
private fun LicenseDialog(onDismiss: () -> Unit) {
    var notices by remember { mutableStateOf<String?>(null) }
    var loadFailed by remember { mutableStateOf(false) }
    var attempt by remember { mutableStateOf(0) }
    LaunchedEffect(attempt) {
        loadFailed = false
        try {
            notices = Res.readBytes("files/licenses/third_party_notices.txt").decodeToString()
        } catch (cancelled: CancellationException) {
            throw cancelled
        } catch (_: Exception) {
            loadFailed = true
        }
    }
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text(stringResource(Res.string.shell_licenses_title)) },
        text = {
            Column(Modifier.verticalScroll(rememberScrollState())) {
                Text(stringResource(Res.string.shell_licenses_description), style = MaterialTheme.typography.bodyMedium)
                Spacer(Modifier.height(20.dp))
                when {
                    loadFailed -> {
                        Text(stringResource(Res.string.shell_licenses_error))
                        TextButton(onClick = { attempt++ }, modifier = Modifier.heightIn(min = 48.dp)) {
                            Text(stringResource(Res.string.shell_retry))
                        }
                    }
                    notices == null -> Text(stringResource(Res.string.shell_licenses_loading))
                    else -> SelectionContainer {
                        Text(notices.orEmpty(), style = MaterialTheme.typography.bodySmall)
                    }
                }
            }
        },
        confirmButton = {
            TextButton(onClick = onDismiss, modifier = Modifier.heightIn(min = 48.dp)) {
                Text(stringResource(Res.string.shell_done))
            }
        },
        containerColor = PartyDeckColors.Surface,
    )
}
