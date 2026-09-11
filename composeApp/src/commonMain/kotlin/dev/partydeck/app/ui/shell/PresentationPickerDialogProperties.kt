package dev.partydeck.app.ui.shell

import androidx.compose.ui.window.DialogProperties

/** Native entry must not leave the picker layer waiting for another Compose animation frame. */
internal expect fun presentationPickerDialogProperties(): DialogProperties
