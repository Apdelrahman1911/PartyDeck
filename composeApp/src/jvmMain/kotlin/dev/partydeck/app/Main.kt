package dev.partydeck.app

import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.unit.dp
import androidx.compose.ui.window.Window
import androidx.compose.ui.window.application
import androidx.compose.ui.window.rememberWindowState
import dev.partydeck.app.controller.PartyDeckController
import dev.partydeck.transport.JvmLanTransportFactory
import java.awt.event.WindowAdapter
import java.awt.event.WindowEvent
import kotlinx.coroutines.launch

fun main() = application {
    val ownerScope = rememberCoroutineScope()
    val controller = remember {
        PartyDeckController(JvmPlatformServices(ownerScope), JvmLanTransportFactory(), ownerScope)
    }
    var closing by remember { mutableStateOf(false) }
    DisposableEffect(controller) {
        onDispose { controller.close() }
    }
    Window(
        onCloseRequest = {
            if (controller.state.value.session != null) {
                controller.requestBack()
            } else if (!closing) {
                closing = true
                ownerScope.launch {
                    controller.close()
                    controller.awaitClosed()
                    exitApplication()
                }
            }
        },
        title = "PartyDeck",
        state = rememberWindowState(width = 440.dp, height = 860.dp),
    ) {
        DisposableEffect(window) {
            val listener = object : WindowAdapter() {
                override fun windowGainedFocus(event: WindowEvent) = controller.setForeground(true)
                override fun windowLostFocus(event: WindowEvent) = controller.setForeground(false)
                override fun windowIconified(event: WindowEvent) = controller.setBackgrounded(true)
                override fun windowDeiconified(event: WindowEvent) = controller.setBackgrounded(false)
            }
            window.addWindowFocusListener(listener)
            window.addWindowListener(listener)
            onDispose {
                window.removeWindowFocusListener(listener)
                window.removeWindowListener(listener)
            }
        }
        PartyDeckApp(controller)
    }
}
