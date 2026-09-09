@file:OptIn(kotlinx.cinterop.ExperimentalForeignApi::class)

package dev.partydeck.app

import androidx.compose.ui.window.ComposeUIViewController
import dev.partydeck.app.controller.PartyDeckController
import dev.partydeck.transport.LanTransportFactory
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import platform.UIKit.UIViewController

/** A small synchronous facade for the retained SwiftUI owner. All calls come from the main thread. */
class IosAppHandle(
    transportFactory: LanTransportFactory,
    nativeActions: IosNativeActions,
) {
    private val ownerScope = CoroutineScope(SupervisorJob() + Dispatchers.Main.immediate)
    private val services = IosPlatformServices(nativeActions)
    private val controller = PartyDeckController(services, transportFactory, ownerScope)
    private var closed = false

    val viewController: UIViewController = ComposeUIViewController {
        PartyDeckApp(controller)
    }

    init {
        controller.setForeground(false)
    }

    fun setForeground(value: Boolean) {
        if (!closed) controller.setForeground(value)
    }

    fun setBackgrounded(value: Boolean) {
        if (!closed) controller.setBackgrounded(value)
    }

    fun setSystemReduceMotion(value: Boolean) {
        if (!closed) controller.setSystemReduceMotion(value)
    }

    /** Backgrounding only pauses the retained owner; this method ends it permanently. */
    fun close() {
        if (closed) return
        closed = true
        controller.close()
        services.feedback.close()
        ownerScope.cancel()
    }
}
