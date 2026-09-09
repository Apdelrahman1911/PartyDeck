package dev.partydeck.app.ui.shell

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ColumnScope
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.RowScope
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.semantics.LiveRegionMode
import androidx.compose.ui.semantics.heading
import androidx.compose.ui.semantics.liveRegion
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.unit.dp
import dev.partydeck.app.controller.ConnectionStatus
import dev.partydeck.app.controller.ConnectionUiState
import dev.partydeck.app.controller.RecoveryAction
import dev.partydeck.app.controller.UiProblem
import dev.partydeck.app.controller.UiProblemCode
import dev.partydeck.app.ui.theme.PartyDeckColors
import dev.partydeck.resources.*
import org.jetbrains.compose.resources.DrawableResource
import org.jetbrains.compose.resources.painterResource
import org.jetbrains.compose.resources.pluralStringResource
import org.jetbrains.compose.resources.stringResource

@Composable
internal fun ScrollablePage(
    modifier: Modifier = Modifier,
    maxWidth: Int = 640,
    content: @Composable ColumnScope.() -> Unit,
) {
    Box(modifier.fillMaxSize(), contentAlignment = Alignment.TopCenter) {
        Column(
            modifier = Modifier
                .widthIn(max = maxWidth.dp)
                .fillMaxSize()
                .verticalScroll(rememberScrollState())
                .padding(horizontal = 24.dp, vertical = 12.dp),
            content = content,
        )
    }
}

@Composable
internal fun ScreenHeader(
    title: String,
    onBack: () -> Unit,
    modifier: Modifier = Modifier,
    trailing: @Composable RowScope.() -> Unit = {},
) {
    Row(
        modifier = modifier.fillMaxWidth().padding(bottom = 16.dp),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(8.dp),
    ) {
        ShellIconAction(
            icon = Res.drawable.icon_arrow_back,
            label = stringResource(Res.string.shell_back),
            onClick = onBack,
            modifier = Modifier.testTag("navigation-back"),
        )
        Text(title, Modifier.weight(1f), style = MaterialTheme.typography.titleSmall)
        trailing()
    }
}

@Composable
internal fun ShellIconAction(
    icon: DrawableResource,
    label: String,
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
    enabled: Boolean = true,
    tint: Color = PartyDeckColors.Paper,
) {
    IconButton(onClick = onClick, modifier = modifier.size(48.dp), enabled = enabled) {
        Icon(painterResource(icon), label, Modifier.size(24.dp), tint = tint)
    }
}

@Composable
internal fun InformationLine(
    icon: DrawableResource,
    text: String,
    modifier: Modifier = Modifier,
) {
    Row(
        modifier = modifier,
        horizontalArrangement = Arrangement.spacedBy(12.dp),
        verticalAlignment = Alignment.Top,
    ) {
        Icon(
            painter = painterResource(icon),
            contentDescription = null,
            modifier = Modifier.padding(top = 3.dp).size(18.dp),
            tint = PartyDeckColors.Muted,
        )
        Text(text, style = MaterialTheme.typography.bodyMedium, color = PartyDeckColors.Muted)
    }
}

@Composable
internal fun InlineProblem(
    problem: UiProblem,
    onRecover: () -> Unit,
    onDismiss: () -> Unit,
    modifier: Modifier = Modifier,
) {
    Surface(
        modifier = modifier.fillMaxWidth().testTag("problem-panel")
            .semantics { liveRegion = LiveRegionMode.Polite },
        color = MaterialTheme.colorScheme.errorContainer,
        shape = MaterialTheme.shapes.medium,
    ) {
        Column(
            Modifier.heightIn(max = 260.dp).verticalScroll(rememberScrollState())
                .padding(start = 16.dp, end = 8.dp, top = 8.dp, bottom = 12.dp),
        ) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text(
                    text = stringResource(Res.string.shell_problem_title),
                    modifier = Modifier.weight(1f).semantics { heading() },
                    style = MaterialTheme.typography.titleSmall,
                )
                ShellIconAction(
                    icon = Res.drawable.icon_close,
                    label = stringResource(Res.string.shell_dismiss),
                    onClick = onDismiss,
                    modifier = Modifier.testTag("problem-dismiss"),
                )
            }
            Text(
                problemMessage(problem.code),
                Modifier.padding(end = 8.dp),
                style = MaterialTheme.typography.bodyMedium,
            )
            if (problem.recovery != RecoveryAction.DISMISS) {
                TextButton(
                    onClick = onRecover,
                    modifier = Modifier.heightIn(min = 48.dp).testTag("problem-recover"),
                ) {
                    Text(recoveryLabel(problem.recovery), color = PartyDeckColors.Paper)
                }
            }
        }
    }
}

@Composable
private fun problemMessage(code: UiProblemCode): String = stringResource(
    when (code) {
        UiProblemCode.INVALID_NAME -> Res.string.shell_name_error
        UiProblemCode.INVALID_INVITE -> Res.string.shell_invitation_error
        UiProblemCode.CONNECTION_FAILED -> Res.string.shell_error_connection
        UiProblemCode.LOCAL_NETWORK_PERMISSION_DENIED -> Res.string.shell_error_local_permission
        UiProblemCode.CONNECTION_LOST -> Res.string.shell_error_connection_lost
        UiProblemCode.HOST_UNAVAILABLE -> Res.string.shell_error_host_unavailable
        UiProblemCode.SESSION_ENDED -> Res.string.shell_error_session_ended
        UiProblemCode.SESSION_FULL -> Res.string.shell_error_full
        UiProblemCode.JOIN_REJECTED -> Res.string.shell_error_join_rejected
        UiProblemCode.VERSION_MISMATCH -> Res.string.shell_error_version
        UiProblemCode.ACTION_REJECTED -> Res.string.shell_error_action
        UiProblemCode.STALE_ACTION -> Res.string.shell_error_stale
        UiProblemCode.SETTINGS_UNAVAILABLE -> Res.string.shell_error_settings
        UiProblemCode.COPY_UNAVAILABLE -> Res.string.shell_error_copy
        UiProblemCode.SHARING_UNAVAILABLE -> Res.string.shell_error_share
        UiProblemCode.SCANNING_UNAVAILABLE -> Res.string.shell_error_scan
        else -> Res.string.shell_error_unknown
    },
    dev.partydeck.core.LastLightRules.MAX_DISPLAY_NAME_LENGTH,
)

@Composable
internal fun recoveryLabel(action: RecoveryAction): String = stringResource(
    when (action) {
        RecoveryAction.DISMISS -> Res.string.shell_dismiss
        RecoveryAction.RETRY_CONNECTION -> Res.string.shell_retry
        RecoveryAction.EDIT_INVITE -> Res.string.shell_edit_invitation
        RecoveryAction.RETURN_HOME -> Res.string.shell_return_home
    },
)

@Composable
internal fun ConnectionBanner(
    connection: ConnectionUiState,
    pausedPlayerNames: List<String>,
    modifier: Modifier = Modifier,
) {
    val message = when {
        connection.status == ConnectionStatus.RECONNECTING ->
            stringResource(Res.string.shell_connection_reconnecting)
        connection.status == ConnectionStatus.DISCONNECTED ->
            stringResource(Res.string.shell_connection_disconnected)
        pausedPlayerNames.size == 1 -> stringResource(Res.string.shell_waiting_for_names, pausedPlayerNames.first())
        pausedPlayerNames.size > 1 -> pluralStringResource(
            Res.plurals.shell_waiting_for_others,
            pausedPlayerNames.size - 1,
            pausedPlayerNames.first(),
            pausedPlayerNames.size - 1,
        )
        else -> return
    }
    Row(
        modifier = modifier
            .fillMaxWidth()
            .background(PartyDeckColors.Surface)
            .padding(horizontal = 20.dp, vertical = 12.dp)
            .semantics { liveRegion = LiveRegionMode.Polite },
        horizontalArrangement = Arrangement.spacedBy(10.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Box(Modifier.size(8.dp).background(PartyDeckColors.Copper, CircleShape))
        Text(message, style = MaterialTheme.typography.bodySmall)
    }
}
