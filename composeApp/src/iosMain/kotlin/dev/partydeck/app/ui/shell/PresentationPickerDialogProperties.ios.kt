package dev.partydeck.app.ui.shell

import androidx.compose.ui.ExperimentalComposeUiApi
import androidx.compose.ui.window.DialogProperties

@OptIn(ExperimentalComposeUiApi::class)
internal actual fun presentationPickerDialogProperties(): DialogProperties =
    DialogProperties(animateTransition = false)
