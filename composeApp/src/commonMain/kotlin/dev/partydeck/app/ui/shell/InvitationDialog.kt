package dev.partydeck.app.ui.shell

import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.BoxWithConstraints
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.aspectRatio
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.remember
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.semantics.LiveRegionMode
import androidx.compose.ui.semantics.liveRegion
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.unit.dp
import dev.partydeck.app.controller.HostInvitation
import dev.partydeck.app.controller.UiProblem
import dev.partydeck.app.controller.UiProblemCode
import dev.partydeck.app.ui.theme.DeckButton
import dev.partydeck.app.ui.theme.PartyDeckColors
import dev.partydeck.resources.*
import io.github.alexzhirkevich.qrose.QrCodePainter
import io.github.alexzhirkevich.qrose.options.QrErrorCorrectionLevel
import io.github.alexzhirkevich.qrose.options.QrOptions
import org.jetbrains.compose.resources.stringResource

@Composable
internal fun InvitationDialog(
    invitation: HostInvitation,
    invitationCopied: Boolean,
    problem: UiProblem?,
    onCopy: () -> Unit,
    onShare: () -> Unit,
    onDismiss: () -> Unit,
    onRecover: () -> Unit,
    onDismissProblem: () -> Unit,
) {
    // Invitations are bounded before encoding; the unchanged string includes the full host pin.
    val painter = remember(invitation.joinAddress) {
        if (invitation.joinAddress.encodeToByteArray().size <= MAX_QR_INVITATION_BYTES) {
            QrCodePainter(
                data = invitation.joinAddress,
                options = QrOptions(errorCorrectionLevel = QrErrorCorrectionLevel.Medium),
            )
        } else null
    }
    AlertDialog(
        onDismissRequest = onDismiss,
        modifier = Modifier.testTag("invitation-dialog"),
        title = { Text(stringResource(Res.string.shell_qr_title), style = MaterialTheme.typography.headlineMedium) },
        text = {
            Column(Modifier.verticalScroll(rememberScrollState())) {
                Text(stringResource(Res.string.shell_qr_description), style = MaterialTheme.typography.bodyMedium)
                Spacer(Modifier.height(20.dp))
                if (painter != null) {
                    BoxWithConstraints(Modifier.fillMaxWidth()) {
                        // Normal QR starts at 21 modules. This margin guarantees >=4 clear
                        // modules on every side, including the smallest supported symbol.
                        val quietZone = maxWidth * (4f / 29f)
                        Image(
                            painter = painter,
                            contentDescription = stringResource(Res.string.shell_qr_accessibility),
                            modifier = Modifier.testTag("invitation-qr").fillMaxWidth().aspectRatio(1f)
                                .background(Color.White).padding(quietZone),
                        )
                    }
                } else {
                    Text(stringResource(Res.string.shell_qr_unavailable), style = MaterialTheme.typography.bodyMedium)
                }
                Spacer(Modifier.height(14.dp))
                Text(invitation.displayAddress, style = MaterialTheme.typography.bodySmall, color = PartyDeckColors.Muted)
                Spacer(Modifier.height(8.dp))
                Text(stringResource(Res.string.shell_qr_private), style = MaterialTheme.typography.bodySmall)
                Spacer(Modifier.height(20.dp))
                DeckButton(
                    stringResource(Res.string.shell_share_invitation), onShare,
                    Modifier.fillMaxWidth().testTag("invitation-share"),
                )
                Spacer(Modifier.height(8.dp))
                DeckButton(
                    stringResource(Res.string.shell_copy_invitation), onCopy,
                    Modifier.fillMaxWidth().testTag("invitation-copy"), secondary = true,
                )
                if (invitationCopied) {
                    Text(
                        stringResource(Res.string.shell_invitation_copied),
                        modifier = Modifier.padding(top = 8.dp).semantics { liveRegion = LiveRegionMode.Polite },
                        style = MaterialTheme.typography.bodySmall,
                        color = PartyDeckColors.Citron,
                    )
                }
                problem?.takeIf {
                    it.code == UiProblemCode.COPY_UNAVAILABLE || it.code == UiProblemCode.SHARING_UNAVAILABLE
                }?.let {
                    Spacer(Modifier.height(12.dp))
                    InlineProblem(it, onRecover, onDismissProblem)
                }
            }
        },
        confirmButton = {
            TextButton(onClick = onDismiss, modifier = Modifier.heightIn(min = 48.dp).testTag("invitation-done")) {
                Text(stringResource(Res.string.shell_done))
            }
        },
        containerColor = PartyDeckColors.Surface,
    )
}

private const val MAX_QR_INVITATION_BYTES = 2048
