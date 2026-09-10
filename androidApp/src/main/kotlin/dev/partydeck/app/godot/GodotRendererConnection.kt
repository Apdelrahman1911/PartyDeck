package dev.partydeck.app.godot

import android.content.ComponentName
import android.content.Context
import android.content.Intent
import android.content.ServiceConnection
import android.os.Handler
import android.os.IBinder
import android.os.Looper
import android.os.Messenger
import android.os.RemoteException
import java.util.NoSuchElementException
import java.util.concurrent.atomic.AtomicBoolean

/** Private child-side connection. All public methods and native callbacks are main-owned. */
class GodotRendererConnection(context: Context, listener: Listener) {
    interface Listener {
        /** Startup is admitted under the opaque cover, before a Godot instance is created. */
        fun onLaunchDocument(document: String): Boolean
        /** Invoke afterDelivery only after the plugin's native delivery callback. */
        fun onCommandDocument(document: String, acceptReady: Boolean, afterDelivery: () -> Unit): Boolean
        fun onCloseRequested()
        fun onConnectionLost()
    }

    private val context = context.applicationContext
    private val main = Handler(Looper.getMainLooper())
    private var listener: Listener? = listener
    private var inbox: GodotIpcInbox? = null
    private var sender: GodotIpcSender? = null
    private var identity: GodotIpcIdentity? = null
    private var peer: IBinder? = null
    private var deathRecipient: IBinder.DeathRecipient? = null
    private val deathQueued = AtomicBoolean()
    private val commandEpoch = GodotCommandEpoch()
    private val closeHandshake = GodotCloseHandshake()
    private var bindingAttempted = false
    private var bindingUsed = false
    private var launchReceived = false
    private var closing = false
    private var lost = false
    private var disposed = false
    private var incomingSequence = 1L
    private var deliveryPending = false
    private var pendingLifecycle: GodotRendererLifecycle? = null
    private var returnRequest: GodotIpcOperation? = null
    private var nativeClosed = false
    private var nativeCloseCallback: (() -> Unit)? = null
    private val startupTimeout = Runnable { connectionLost() }
    private val closeNotificationTimeout = Runnable {
        if (closeHandshake.expired()) completeNativeCloseNotification()
    }
    private val deathNotice = Runnable { if (!disposed && peer != null) connectionLost() }

    private val serviceConnection = object : ServiceConnection {
        override fun onServiceConnected(name: ComponentName, service: IBinder) {
            checkMain()
            if (disposed || lost) {
                unbind()
                return
            }
            if (peer != null || inbox?.pinPeer(service) != true) {
                connectionLost()
                return
            }
            peer = service
            val death = IBinder.DeathRecipient {
                if (deathQueued.compareAndSet(false, true)) main.post(deathNotice)
            }
            deathRecipient = death
            try {
                service.linkToDeath(death, 0)
            } catch (_: RemoteException) {
                connectionLost()
                return
            }
            val outbox = sender ?: return
            if (!outbox.attach(Messenger(service)) || !outbox.control(GodotIpcOperation.HELLO)) {
                connectionLost()
                return
            }
            returnRequest?.let(outbox::control)
            if (nativeClosed) outbox.control(GodotIpcOperation.NATIVE_CLOSED)
        }

        override fun onServiceDisconnected(name: ComponentName) { connectionLost() }
        override fun onBindingDied(name: ComponentName) { connectionLost(); unbind() }
        override fun onNullBinding(name: ComponentName) { connectionLost(); unbind() }
    }

    fun bind(intent: Intent): Boolean {
        checkMain()
        if (bindingUsed || disposed) return false
        bindingUsed = true
        val parsed = identityFrom(intent) ?: return false
        identity = parsed
        val incoming = GodotIpcInbox(parsed, acceptsHello = false, maxBytes = GODOT_IPC_MAX_COMMAND_BYTES,
            onPacket = ::receive, onFailure = ::connectionLost)
        inbox = incoming
        sender = GodotIpcSender(parsed, incoming.messenger, GODOT_IPC_MAX_EVENT_BYTES,
            initiallyEnabled = false, onFailure = ::connectionLost)
        main.postDelayed(startupTimeout, GODOT_IPC_TIMEOUT_MS)
        // Extras do not participate in Intent.filterEquals and are not promised to onBind.
        // A distinct nonsecret action prevents Android reusing a retired binding's Binder.
        val serviceIntent = Intent(context, GodotSessionBrokerService::class.java)
            .setAction(BIND_ACTION_PREFIX + parsed.presentationId)
        bindingAttempted = true
        val bound = try {
            context.bindService(serviceIntent, serviceConnection, Context.BIND_AUTO_CREATE)
        } catch (_: RuntimeException) {
            false
        }
        if (!bound) {
            connectionLost()
            unbind()
        }
        return bound && !lost && !disposed
    }

    fun sendRendererEvent(document: String): Boolean {
        checkMain()
        if (closing || lost || disposed || !launchReceived) return false
        return sender?.offer(GodotIpcContent(GodotIpcKind.EVENT, document = document,
            generation = commandEpoch.generation)) == true
    }

    fun reportLifecycle(started: Boolean, resumed: Boolean, focused: Boolean) {
        checkMain()
        if (lost || disposed) return
        val generation = commandEpoch.advance() ?: run { connectionLost(); return }
        val snapshot = GodotRendererLifecycle(started, resumed, focused, generation)
        if (!launchReceived) pendingLifecycle = snapshot else sendLifecycle(snapshot)
    }

    fun requestExit() = requestReturn(GodotIpcOperation.EXIT_REQUESTED)

    fun requestStandardTable() = requestReturn(GodotIpcOperation.STANDARD_TABLE_REQUESTED)

    /**
     * Native cleanup is already complete. Keep binding briefly so an early Back/Leave can
     * send HELLO and its pending return control before this process exits. The first call
     * owns the callback, delivered once on main after parent Close or bounded connection
     * failure. This notification is separate from the parent's proof of process death.
     */
    fun reportNativeClosed(afterNotification: () -> Unit = {}) {
        checkMain()
        if (nativeClosed) return
        nativeClosed = true
        if (disposed) { afterNotification(); return }
        nativeCloseCallback = afterNotification
        closing = true
        main.removeCallbacks(startupTimeout)
        sender?.stop()
        inbox?.retire()
        sender?.control(GodotIpcOperation.NATIVE_CLOSED)
        if (lost || !bindingAttempted && peer == null) closeHandshake.connectionLost()
        if (closeHandshake.nativeClosed()) completeNativeCloseNotification()
        else main.postDelayed(closeNotificationTimeout, GODOT_IPC_CLOSE_TIMEOUT_MS)
    }

    fun dispose() {
        checkMain()
        if (disposed) return
        disposed = true
        commandEpoch.close()
        main.removeCallbacks(startupTimeout)
        main.removeCallbacks(closeNotificationTimeout)
        main.removeCallbacks(deathNotice)
        nativeCloseCallback = null
        sender?.dispose()
        sender = null
        inbox?.close()
        inbox = null
        val binder = peer
        val death = deathRecipient
        if (binder != null && death != null) {
            try { binder.unlinkToDeath(death, 0) } catch (_: NoSuchElementException) { /* Already dead. */ }
        }
        peer = null
        deathRecipient = null
        identity = null
        pendingLifecycle = null
        listener = null
        unbind()
    }

    private fun requestReturn(operation: GodotIpcOperation) {
        checkMain()
        if (disposed || lost || returnRequest != null) return
        returnRequest = operation
        closing = true
        sender?.control(operation)
    }

    private fun receive(packet: GodotIpcPacket) {
        checkMain()
        if (disposed || lost || inbox?.isCurrent(packet.header) != true) return
        when (packet.operation) {
            GodotIpcOperation.DATA -> receiveData(packet)
            GodotIpcOperation.ACK -> if (!nativeClosed && sender?.acknowledge(packet.sequence, packet.superseded) != true) connectionLost()
            GodotIpcOperation.CLOSE -> {
                if (closeHandshake.parentClosed()) completeNativeCloseNotification()
                if (closing) return
                closing = true
                inbox?.retire()
                listener?.onCloseRequested()
            }
            GodotIpcOperation.ABORT -> connectionLost()
            else -> connectionLost()
        }
    }

    private fun receiveData(packet: GodotIpcPacket) {
        if (closing) return
        if (deliveryPending || packet.sequence != incomingSequence || incomingSequence == Long.MAX_VALUE) {
            connectionLost()
            return
        }
        incomingSequence++
        val content = packet.content ?: run { connectionLost(); return }
        when (content.kind) {
            GodotIpcKind.LAUNCH -> {
                if (launchReceived) {
                    connectionLost()
                    return
                }
                launchReceived = true
                // Queue the latest pre-bind facts first. Native launch may synchronously
                // publish a newer lifecycle or Ready; neither may overtake this snapshot.
                pendingLifecycle?.let(::sendLifecycle)
                pendingLifecycle = null
                val accepted = try { listener?.onLaunchDocument(checkNotNull(content.document)) == true } catch (_: Exception) { false }
                if (!accepted || closing || disposed) {
                    if (!closing && !disposed) connectionLost()
                    return
                }
                main.removeCallbacks(startupTimeout)
                if (sender?.acknowledgeReceived(packet.sequence) != true) return
                sender?.enableData()
            }
            GodotIpcKind.COMMAND -> {
                if (!launchReceived) {
                    connectionLost()
                    return
                }
                when (val admission = commandEpoch.admit(content.generation, content.acceptReady)) {
                    GodotCommandEpoch.Admission.Invalid -> connectionLost()
                    GodotCommandEpoch.Admission.Superseded -> sender?.acknowledgeReceived(packet.sequence, superseded = true)
                    is GodotCommandEpoch.Admission.Deliver -> {
                        deliveryPending = true
                        val once = AtomicBoolean()
                        val accepted = try {
                            listener?.onCommandDocument(checkNotNull(content.document), admission.acceptReady) {
                                checkMain()
                                if (once.compareAndSet(false, true) && !disposed && !lost && !closing) {
                                    deliveryPending = false
                                    sender?.acknowledgeReceived(packet.sequence)
                                }
                            } == true
                        } catch (_: Exception) { false }
                        if (!accepted) connectionLost()
                    }
                }
            }
            else -> connectionLost()
        }
    }

    private fun sendLifecycle(state: GodotRendererLifecycle) {
        sender?.offer(GodotIpcContent(GodotIpcKind.LIFECYCLE, generation = state.generation,
            started = state.started, resumed = state.resumed, focused = state.focused))
    }

    private fun connectionLost() {
        checkMain()
        if (lost || disposed) return
        lost = true
        closing = true
        main.removeCallbacks(startupTimeout)
        sender?.control(GodotIpcOperation.ABORT)
        sender?.stop()
        inbox?.retire()
        pendingLifecycle = null
        if (closeHandshake.connectionLost()) completeNativeCloseNotification()
        listener?.onConnectionLost()
    }

    private fun completeNativeCloseNotification() {
        checkMain()
        main.removeCallbacks(closeNotificationTimeout)
        val callback = nativeCloseCallback
        nativeCloseCallback = null
        callback?.invoke()
    }

    private fun unbind() {
        if (!bindingAttempted) return
        bindingAttempted = false
        try { context.unbindService(serviceConnection) } catch (_: IllegalArgumentException) { /* Bind failed or already removed. */ }
    }

    private fun checkMain() { check(Looper.myLooper() == Looper.getMainLooper()) }

    companion object {
        const val EXTRA_PRESENTATION_ID = "dev.partydeck.godot.presentation"
        const val EXTRA_HANDOFF_TOKEN = "dev.partydeck.godot.handoff"
        private const val BIND_ACTION_PREFIX = "dev.partydeck.godot.BIND_PRESENTATION."

        internal fun bindingPresentationId(intent: Intent): String? = intent.action
            ?.takeIf { it.startsWith(BIND_ACTION_PREFIX) }
            ?.removePrefix(BIND_ACTION_PREFIX)
            ?.takeIf { it.isNotBlank() && it.length <= 128 && it.none(Char::isISOControl) }

        internal fun launchIntent(context: Context, identity: GodotIpcIdentity): Intent =
            Intent(context, SessionGodotActivity::class.java)
                .putExtra(EXTRA_PRESENTATION_ID, identity.presentationId)
                .putExtra(EXTRA_HANDOFF_TOKEN, identity.token)

        internal fun identityFrom(intent: Intent): GodotIpcIdentity? = try {
            val id = intent.getStringExtra(EXTRA_PRESENTATION_ID)
            val token = intent.getStringExtra(EXTRA_HANDOFF_TOKEN)
            if (id == null || token == null) null else GodotIpcIdentity(id, token).takeIf { it.isValid() }
        } catch (_: RuntimeException) {
            null
        }
    }
}
