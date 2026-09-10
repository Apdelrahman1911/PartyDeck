package dev.partydeck.app.godot

import android.app.Service
import android.content.Intent
import android.os.IBinder
import android.os.Looper

/**
 * Private, explicitly bound service in the shell process. It delegates only to a registration
 * installed by the retained shell owner; process recreation cannot create or restore a session.
 */
class GodotSessionBrokerService : Service() {
    private val registrations = mutableMapOf<String, GodotPresentationSession>()

    override fun onBind(intent: Intent): IBinder? {
        val presentationId = GodotRendererConnection.bindingPresentationId(intent) ?: return null
        val current = GodotSessionRegistry.resolve(presentationId) ?: return null
        // Android can deliver an old unbind after the previous renderer's death. Retain at
        // most the current registration and attribute every callback to its binding action.
        registrations.entries.removeAll { it.value.isReleased }
        registrations[presentationId] = current
        current.serviceBound()
        return current.brokerBinder
    }

    override fun onUnbind(intent: Intent): Boolean {
        GodotRendererConnection.bindingPresentationId(intent)?.let { registrations.remove(it)?.serviceUnbound() }
        return false
    }

    override fun onDestroy() {
        registrations.values.toSet().forEach { it.serviceDestroyed() }
        registrations.clear()
        super.onDestroy()
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        // This service has no started-service ownership or independent work.
        stopSelf(startId)
        return START_NOT_STICKY
    }
}

/** One active or retiring handoff per shell process. No authority/session constructor lives here. */
internal object GodotSessionRegistry {
    private var current: GodotPresentationSession? = null
    private val observers = mutableSetOf<AndroidGodotPresentationHost>()

    val vacant: Boolean get() { checkMain(); return current == null }

    fun observe(host: AndroidGodotPresentationHost) {
        checkMain()
        observers += host
        host.registryAvailabilityChanged(vacant)
    }

    fun removeObserver(host: AndroidGodotPresentationHost) { checkMain(); observers -= host }

    fun register(session: GodotPresentationSession): Boolean {
        checkMain()
        if (current != null) return false
        current = session
        observers.toList().forEach { it.registryAvailabilityChanged(false) }
        return true
    }

    fun resolve(presentationId: String): GodotPresentationSession? {
        checkMain()
        return current?.takeIf { it.identity.presentationId == presentationId }
    }

    fun release(session: GodotPresentationSession) {
        checkMain()
        if (current !== session) return
        current = null
        observers.toList().forEach { it.registryAvailabilityChanged(true) }
    }

    private fun checkMain() { check(Looper.myLooper() == Looper.getMainLooper()) }
}
