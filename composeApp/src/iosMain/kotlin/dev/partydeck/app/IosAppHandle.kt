@file:OptIn(kotlinx.cinterop.ExperimentalForeignApi::class)

package dev.partydeck.app

import androidx.compose.ui.window.ComposeUIViewController
import dev.partydeck.app.controller.PartyDeckController
import dev.partydeck.app.godot.IosGodotNativePort
import dev.partydeck.app.godot.IosGodotPresentationHost
import dev.partydeck.app.godot.IosGodotRegistration
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
    private val presentationHost = IosGodotPresentationHost(
        onLifecycle = ::nativeLifecycleChanged,
        onClosing = { applyLifecycle() },
        onExit = ::nativeExitRequested,
        onUseCompose = ::nativeUseCompose,
    )
    private val controller = PartyDeckController(services, transportFactory, ownerScope, presentationHost)
    private var sceneForeground = false
    private var sceneBackgrounded = false
    private var closed = false

    val viewController: UIViewController = ComposeUIViewController {
        PartyDeckApp(controller)
    }

    init {
        controller.setForeground(false)
    }

    fun setForeground(value: Boolean) {
        if (closed) return
        sceneForeground = value
        presentationHost.updateLifecycle(sceneForeground, sceneBackgrounded)
        applyLifecycle()
    }

    fun setBackgrounded(value: Boolean) {
        if (closed) return
        sceneBackgrounded = value
        presentationHost.updateLifecycle(sceneForeground, sceneBackgrounded)
        applyLifecycle()
    }

    /** No native renderer is offered until the retained owner installs and advertises this port. */
    fun installGodotPort(port: IosGodotNativePort): IosGodotRegistration? =
        if (closed) null else presentationHost.install(port)

    private fun nativeLifecycleChanged(presentationId: String) {
        if (!closed && controller.state.value.presentation.presentationId == presentationId) applyLifecycle()
    }

    private fun nativeExitRequested(presentationId: String) {
        if (!closed) controller.requestPresentationExit(presentationId)
    }

    private fun nativeUseCompose(presentationId: String) {
        if (!closed && controller.state.value.presentation.presentationId == presentationId) {
            controller.useComposePresentation()
        }
    }

    private fun applyLifecycle() {
        if (closed) return
        val native = presentationHost.currentLifecycle()?.takeIf {
            controller.state.value.presentation.presentationId == it.presentationId
        }
        val backgrounded = sceneBackgrounded || native?.isBackgrounded == true
        val foreground = sceneForeground && !backgrounded && native?.isForeground != false
        controller.setForeground(foreground)
        controller.setBackgrounded(backgrounded)
        native?.let { controller.refreshPresentationLifecycle(it.presentationId) }
    }

    /** Called only by the explicitly compiled/activated Debug qualification observer. */
    fun enableSessionQualificationObservation(): Boolean =
        !closed && controller.enableSessionQualificationObservation()

    /** Fixed allowlist of public counters and viewer receipts; never a serialized SessionView. */
    fun sessionQualificationSnapshot(): String? = if (closed) null else controller.sessionQualificationSnapshot()

    fun setSystemReduceMotion(value: Boolean) {
        if (!closed) controller.setSystemReduceMotion(value)
    }

    fun setPresentationTextScale(value: Double) {
        if (!closed) controller.setPresentationTextScale(value)
    }

    /** Backgrounding only pauses the retained owner; this method ends it permanently. */
    fun close() {
        if (closed) return
        closed = true
        controller.close()
        presentationHost.close()
        services.feedback.close()
        ownerScope.cancel()
    }
}
