package dev.partydeck.app

import android.app.Application
import android.content.Intent
import android.os.Handler
import android.os.Looper
import android.os.SystemClock
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import dev.partydeck.app.controller.GameplayPresentation
import dev.partydeck.app.controller.PartyDeckController
import dev.partydeck.app.godot.AndroidGodotPresentationHost
import dev.partydeck.app.godot.GodotRendererLifecycle
import dev.partydeck.app.platform.AndroidPlatformServices
import dev.partydeck.transport.AndroidLanTransportFactory
import java.lang.ref.WeakReference
import kotlinx.coroutines.flow.distinctUntilChanged
import kotlinx.coroutines.flow.map
import kotlinx.coroutines.launch

/** The session survives Activity recreation; process death intentionally starts a fresh session. */
class PartyDeckAndroidViewModel(
    application: Application,
    qualifiedPresentations: Set<GameplayPresentation> = emptySet(),
) : AndroidViewModel(application), AndroidGodotPresentationHost.Listener {
    private data class PendingLaunch(val presentationId: String, val attachment: Long)

    private val main = Handler(Looper.getMainLooper())
    private val visibility = SessionVisibility()
    private var activity = WeakReference<MainActivity>(null)
    private var attachment: Long? = null
    private var pendingLaunch: PendingLaunch? = null
    private var cleared = false
    private var publishingVisibility = false
    private var visibilityDirty = false
    private val visibilityDeadline = Runnable { publishVisibility() }

    val services = AndroidPlatformServices(application)
    // Product entries stay absent until their real session/lifecycle capability is qualified.
    // The host creates no renderer until a qualified factory is opened by the common owner.
    private val rendererHost = AndroidGodotPresentationHost(
        context = application,
        listener = this,
        qualifiedPresentations = qualifiedPresentations,
    )
    val controller = PartyDeckController(
        services = services,
        transportFactory = AndroidLanTransportFactory(application),
        parentScope = viewModelScope,
        presentationHost = rendererHost,
    )

    init {
        viewModelScope.launch {
            controller.state.map { it.presentation.presentationId }.distinctUntilChanged().collect {
                publishVisibility()
            }
        }
    }

    internal fun attachActivity(value: MainActivity): Long {
        check(!cleared)
        val oldAttachment = attachment
        if (oldAttachment != null && activity.get() === value) return oldAttachment
        if (oldAttachment != null) activity.get()?.onShellInteractivityChanged(oldAttachment, false)
        val identity = visibility.attachShell(SystemClock.elapsedRealtime())
        attachment = identity
        activity = WeakReference(value)
        services.attachActivity(value)
        publishVisibility()
        return identity
    }

    internal fun updateActivityVisibility(
        value: MainActivity,
        identity: Long,
        started: Boolean,
        resumed: Boolean,
        focused: Boolean,
    ) {
        if (!ownsActivity(value, identity)) return
        visibility.updateShell(identity, started, resumed, focused)
        publishVisibility()
    }

    internal fun stopActivity(value: MainActivity, identity: Long, changingConfigurations: Boolean) {
        if (!ownsActivity(value, identity)) return
        visibility.stopShell(identity, changingConfigurations, SystemClock.elapsedRealtime())
        publishVisibility()
    }

    internal fun userLeavingActivity(value: MainActivity, identity: Long) {
        if (!ownsActivity(value, identity)) return
        visibility.userLeavingShell(identity)
        publishVisibility()
    }

    internal fun detachActivity(value: MainActivity, identity: Long) {
        if (!ownsActivity(value, identity)) return
        visibility.detachShell(identity)
        attachment = null
        activity.clear()
        services.detachActivity(value)
        publishVisibility()
    }

    override fun onOpening(presentationId: String, deadlineMillis: Long) {
        if (cleared || controller.state.value.presentation.presentationId != presentationId) return
        if (!visibility.rendererOpening(presentationId, deadlineMillis)) return
        pendingLaunch = attachment?.let { PendingLaunch(presentationId, it) }
        publishVisibility() // Synchronous native shell cover precedes launching the child.
    }

    override fun launchRenderer(intent: Intent): Boolean {
        val pending = pendingLaunch ?: return false
        pendingLaunch = null
        val current = activity.get() ?: return false
        if (!ownsActivity(current, pending.attachment) || current.isFinishing || current.isDestroyed ||
            controller.state.value.presentation.presentationId != pending.presentationId ||
            !visibility.shellCanLaunch(pending.attachment)
        ) return false
        // This internal handoff must not look like the user pressing Home. Actual Home still
        // invokes onUserLeaveHint and cancels any assumed handoff visibility.
        current.startActivity(intent.addFlags(Intent.FLAG_ACTIVITY_NO_USER_ACTION))
        // Unexpected launch exceptions propagate to the host, which quarantines uncertain
        // dispatch until actual child death instead of claiming that nothing launched.
        return true
    }

    override fun onLifecycle(presentationId: String, state: GodotRendererLifecycle) {
        if (cleared || !visibility.updateRenderer(
                presentationId, state.generation, state.started, state.resumed, state.focused,
            )
        ) return
        publishVisibility()
        // The host has already published this generation. Reproject even when the effective
        // foreground Boolean is unchanged, so an older discarded native command cannot stick.
        controller.refreshPresentationLifecycle(presentationId)
    }

    override fun onClosing(presentationId: String) {
        if (cleared) return
        if (pendingLaunch?.presentationId == presentationId) pendingLaunch = null
        if (visibility.rendererClosing(presentationId, SystemClock.elapsedRealtime())) publishVisibility()
    }

    override fun onClosed(presentationId: String) {
        if (cleared) return
        if (pendingLaunch?.presentationId == presentationId) pendingLaunch = null
        if (visibility.rendererClosed(presentationId, SystemClock.elapsedRealtime())) publishVisibility()
    }

    override fun onExitRequested(presentationId: String) {
        if (cleared) return
        controller.requestPresentationExit(presentationId)
        publishVisibility()
    }

    override fun onStandardTableRequested(presentationId: String) {
        if (cleared || controller.state.value.presentation.presentationId != presentationId) return
        controller.useComposePresentation()
        publishVisibility()
    }

    private fun ownsActivity(value: MainActivity, identity: Long): Boolean =
        !cleared && attachment == identity && activity.get() === value && services.isAttachedActivity(value)

    private fun publishVisibility() {
        if (cleared) return
        visibilityDirty = true
        if (publishingVisibility) return
        publishingVisibility = true
        try {
            while (!cleared) {
                visibilityDirty = false
                val selected = controller.state.value.presentation.presentationId
                visibility.selectPresentation(selected)
                val snapshot = visibility.snapshot(SystemClock.elapsedRealtime())
                val identity = attachment
                if (identity != null) {
                    activity.get()?.onShellInteractivityChanged(identity, snapshot.shellSelected && snapshot.foreground)
                }
                // Conceal first. Actual visibility can keep a LAN client connected through a
                // focus interruption, while real background uses the existing runtime policy.
                if (!snapshot.foreground) controller.setForeground(false)
                if (visibilityDirty || selected != controller.state.value.presentation.presentationId) continue
                controller.setBackgrounded(snapshot.backgrounded)
                if (visibilityDirty || selected != controller.state.value.presentation.presentationId) continue
                if (snapshot.foreground) controller.setForeground(true)
                // A controller setter can synchronously close a failed presentation and call
                // back into this owner. Only the resulting current snapshot may set a deadline.
                if (cleared || visibilityDirty || selected != controller.state.value.presentation.presentationId) continue
                main.removeCallbacks(visibilityDeadline)
                snapshot.nextDeadlineMillis?.let { deadline ->
                    main.postDelayed(visibilityDeadline, (deadline - SystemClock.elapsedRealtime()).coerceAtLeast(0))
                }
                break
            }
        } finally {
            publishingVisibility = false
        }
    }

    override fun onCleared() {
        cleared = true
        main.removeCallbacks(visibilityDeadline)
        pendingLaunch = null
        activity.clear()
        attachment = null
        rendererHost.close()
        controller.close()
        services.close()
        super.onCleared()
    }
}
