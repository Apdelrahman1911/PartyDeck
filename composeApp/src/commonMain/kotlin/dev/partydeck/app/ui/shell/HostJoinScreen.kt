package dev.partydeck.app.ui.shell

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.OutlinedTextFieldDefaults
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalFocusManager
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.semantics.heading
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.input.KeyboardCapitalization
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import dev.partydeck.app.controller.AppScreen
import dev.partydeck.app.controller.AppUiState
import dev.partydeck.app.controller.PendingAction
import dev.partydeck.app.controller.UiProblemCode
import dev.partydeck.app.ui.theme.DeckButton
import dev.partydeck.app.ui.theme.PartyDeckColors
import dev.partydeck.app.ui.theme.SectionLabel
import dev.partydeck.core.LastLightRules
import dev.partydeck.resources.*
import org.jetbrains.compose.resources.painterResource
import org.jetbrains.compose.resources.stringResource

@Composable
fun HostJoinScreen(
    state: AppUiState,
    onBack: () -> Unit,
    onNameChange: (String) -> Unit,
    onInvitationChange: (String) -> Unit,
    onSubmit: () -> Unit,
    onScanInvitation: () -> Unit,
    onRecover: () -> Unit,
    onDismissProblem: () -> Unit,
    modifier: Modifier = Modifier,
) {
    val hosting = state.screen == AppScreen.HOST
    val busy = state.pendingAction == PendingAction.HOST || state.pendingAction == PendingAction.JOIN
    val nameInvalid = state.problem?.code == UiProblemCode.INVALID_NAME ||
        state.displayName.trim().length !in 1..LastLightRules.MAX_DISPLAY_NAME_LENGTH
    val inviteInvalid = state.problem?.code == UiProblemCode.INVALID_INVITE
    val nameValid = state.displayName.trim().length in 1..LastLightRules.MAX_DISPLAY_NAME_LENGTH
    val focus = LocalFocusManager.current
    val submit = {
        focus.clearFocus()
        onSubmit()
    }
    ScrollablePage(modifier.imePadding()) {
        ScreenHeader(
            stringResource(if (hosting) Res.string.shell_host_action else Res.string.shell_join_action),
            onBack,
        )
        SectionLabel(stringResource(Res.string.shell_game_eyebrow))
        Spacer(Modifier.height(10.dp))
        Text(
            stringResource(if (hosting) Res.string.shell_host_title else Res.string.shell_join_title),
            style = MaterialTheme.typography.headlineLarge,
            modifier = Modifier.semantics { heading() },
        )
        Spacer(Modifier.height(16.dp))
        Text(
            stringResource(
                when {
                    hosting -> Res.string.shell_host_description
                    state.canScanInvitation -> Res.string.shell_join_description
                    else -> Res.string.shell_join_paste_description
                },
            ),
            style = MaterialTheme.typography.bodyLarge,
            color = PartyDeckColors.Muted,
        )
        Spacer(Modifier.height(28.dp))
        OutlinedTextField(
            value = state.displayName,
            onValueChange = onNameChange,
            modifier = Modifier.fillMaxWidth().testTag(if (hosting) "host-name" else "join-name"),
            label = { Text(stringResource(Res.string.shell_your_name)) },
            placeholder = { Text(stringResource(Res.string.shell_name_placeholder)) },
            supportingText = {
                Text(
                    stringResource(
                        if (nameInvalid) Res.string.shell_name_error else Res.string.shell_name_hint,
                        LastLightRules.MAX_DISPLAY_NAME_LENGTH,
                    ),
                )
            },
            singleLine = true,
            enabled = !busy,
            isError = nameInvalid,
            shape = MaterialTheme.shapes.medium,
            textStyle = MaterialTheme.typography.bodyLarge,
            colors = OutlinedTextFieldDefaults.colors(
                unfocusedBorderColor = PartyDeckColors.Outline,
                focusedBorderColor = PartyDeckColors.Citron,
            ),
            keyboardOptions = KeyboardOptions(
                capitalization = KeyboardCapitalization.Words,
                autoCorrectEnabled = false,
                imeAction = if (hosting) ImeAction.Done else ImeAction.Next,
            ),
            keyboardActions = KeyboardActions(onDone = { if (hosting && nameValid && !busy) submit() }),
        )
        if (!hosting) {
            Spacer(Modifier.height(16.dp))
            if (state.canScanInvitation) {
                TextButton(
                    onClick = onScanInvitation,
                    enabled = !busy && !state.isScanningInvitation,
                    modifier = Modifier.fillMaxWidth().heightIn(min = 56.dp).testTag("join-scan"),
                ) {
                    Icon(painterResource(Res.drawable.icon_qr_scan), null, Modifier.size(24.dp))
                    Text(
                        stringResource(
                            if (state.isScanningInvitation) Res.string.shell_scanning_invitation
                            else Res.string.shell_scan_invitation,
                        ),
                        modifier = Modifier.padding(start = 12.dp),
                    )
                }
                Spacer(Modifier.height(12.dp))
            }
            OutlinedTextField(
                value = state.joinAddress,
                onValueChange = onInvitationChange,
                modifier = Modifier.fillMaxWidth().testTag("join-invitation"),
                label = { Text(stringResource(Res.string.shell_invitation_label)) },
                placeholder = { Text(stringResource(Res.string.shell_invitation_placeholder)) },
                supportingText = {
                    Text(stringResource(if (inviteInvalid) Res.string.shell_invitation_error else Res.string.shell_invitation_hint))
                },
                minLines = 2,
                maxLines = 4,
                enabled = !busy,
                isError = inviteInvalid,
                shape = MaterialTheme.shapes.medium,
                textStyle = MaterialTheme.typography.bodyMedium,
                colors = OutlinedTextFieldDefaults.colors(
                    unfocusedBorderColor = PartyDeckColors.Outline,
                    focusedBorderColor = PartyDeckColors.Citron,
                ),
                keyboardOptions = KeyboardOptions(
                    autoCorrectEnabled = false,
                    keyboardType = KeyboardType.Uri,
                    imeAction = ImeAction.Done,
                ),
                keyboardActions = KeyboardActions(onDone = {
                    if (nameValid && state.joinAddress.isNotBlank() && !busy) submit()
                }),
            )
        }
        state.problem?.takeUnless {
            it.code == UiProblemCode.INVALID_NAME || it.code == UiProblemCode.INVALID_INVITE
        }?.let { problem ->
            Spacer(Modifier.height(16.dp))
            InlineProblem(problem, onRecover, onDismissProblem)
        }
        Spacer(Modifier.height(28.dp))
        Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
            InformationLine(Res.drawable.icon_nearby, stringResource(Res.string.shell_same_network))
            if (hosting) InformationLine(Res.drawable.icon_people, stringResource(Res.string.shell_host_foreground))
        }
        Spacer(Modifier.height(28.dp))
        if (busy) {
            Row(
                Modifier.fillMaxWidth().padding(bottom = 16.dp),
                horizontalArrangement = Arrangement.spacedBy(12.dp, Alignment.CenterHorizontally),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                if (!state.effectiveReduceMotion) CircularProgressIndicator(Modifier.size(20.dp), strokeWidth = 2.dp)
                Text(
                    stringResource(if (hosting) Res.string.shell_opening_table else Res.string.shell_joining_table),
                    style = MaterialTheme.typography.bodyMedium,
                )
            }
        }
        DeckButton(
            text = stringResource(if (hosting) Res.string.shell_open_table else Res.string.shell_join_action),
            onClick = submit,
            enabled = !busy && nameValid && (hosting || state.joinAddress.isNotBlank()),
            modifier = Modifier.fillMaxWidth().testTag(if (hosting) "host-create" else "join-submit"),
        )
        if (busy) {
            TextButton(onClick = onBack, modifier = Modifier.fillMaxWidth().heightIn(min = 48.dp)) {
                Text(stringResource(Res.string.shell_cancel), color = PartyDeckColors.Paper)
            }
        }
        Spacer(Modifier.height(20.dp))
    }
}
