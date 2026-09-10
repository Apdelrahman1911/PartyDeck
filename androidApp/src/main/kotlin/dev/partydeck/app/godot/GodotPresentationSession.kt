package dev.partydeck.app.godot

import android.os.Handler
import android.os.IBinder
import android.os.Looper
import android.os.Messenger
import android.os.RemoteException
import android.os.SystemClock
import dev.partydeck.app.controller.LifecycleBoundEmbeddedGameSession
import dev.partydeck.games.ENGINE_BRIDGE_PROTOCOL_VERSION
import dev.partydeck.games.EngineCommand
import dev.partydeck.games.EngineEvent
import dev.partydeck.games.EngineEventBody
import dev.partydeck.games.EngineFailure
import dev.partydeck.godot.bridge.LastLightWireCodec
import java.util.NoSuchElementException
import java.util.concurrent.atomic.AtomicBoolean
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.channels.Channel
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.flow
import kotlinx.coroutines.withContext
import kotlinx.coroutines.withTimeoutOrNull

/**
 * Safe projections and bounded typed events only. This class never owns a SessionRuntime,
 * LastLightBridgeAdapter, EngineEventGate, qualification driver, or authority state.
 */
internal class GodotPresentationSession(
    val identity: GodotIpcIdentity,
    launchDocument: String,
    owner: AndroidGodotPresentationHost,
) : LifecycleBoundEmbeddedGameSession {
    private data class QueuedEvent(val event: EngineEvent, val generation: Long, val bytes: Int)

    private val main = Handler(Looper.getMainLooper())
    private var owner: AndroidGodotPresentationHost? = owner
    private var launchDocument: String? = launchDocument
    private var wasLaunched = false
    private var attached = false
    private var helloReceived = false
    private var serviceBound = false
    private var nativeClosed = false
    private var released = false
    val isReleased: Boolean get() = released
    var isClosing = false
        private set
    private var failed = false
    private var returnRequested = false
    private var confirmationSent = false
    private var incomingSequence = 1L
    private var openingDeadline = 0L
    private var highestEventSequence = -1L
    private var lifecycle = GodotRendererLifecycle(false, false, false, 0)
    override val lifecycleGeneration: Long get() { checkMain(); return lifecycle.generation }
    private var peer: IBinder? = null
    private var deathRecipient: IBinder.DeathRecipient? = null
    private val deathQueued = AtomicBoolean()
    private val processGone = CompletableDeferred<Unit>()
    private val eventChannel = Channel<QueuedEvent>(GODOT_IPC_MAX_MESSAGES)
    private var eventCount = 0
    private var eventBytes = 0
    private var subscribed = false
    private val openingTimeout = Runnable { fail(EngineFailure.INITIALIZATION_FAILED) }
    private val deathNotice = Runnable { rendererDied() }
    private val inbox = GodotIpcInbox(identity, acceptsHello = true, maxBytes = GODOT_IPC_MAX_EVENT_BYTES,
        onPacket = ::receive, onFailure = { fail(EngineFailure.INVALID_PAYLOAD) })
    private val sender = GodotIpcSender(identity, inbox.messenger, GODOT_IPC_MAX_COMMAND_BYTES,
        onFailure = { fail(EngineFailure.RENDERER_LOST) })
    val brokerBinder: IBinder get() = inbox.messenger.binder

    override val events: Flow<EngineEvent> = flow {
        checkMain()
        check(!subscribed) { "The renderer event stream has one owner." }
        subscribed = true
        for (queued in eventChannel) {
            try {
                checkMain()
                val event = queued.event
                val input = event.body is EngineEventBody.PlayerIntent
                if ((!isClosing || event.body is EngineEventBody.Failed) &&
                    (!input || !returnRequested && lifecycle.interactive && queued.generation == lifecycle.generation)) {
                    emit(event)
                }
            } finally {
                eventCount--
                eventBytes -= queued.bytes
            }
        }
        val terminal = terminalFailure
        terminalFailure = null
        if (terminal != null) emit(terminal)
        else if (terminalException) throw GodotIpcException()
    }

    fun startOpening(): Long {
        checkMain()
        check(openingDeadline == 0L)
        openingDeadline = SystemClock.elapsedRealtime() + GODOT_IPC_TIMEOUT_MS
        main.postDelayed(openingTimeout, GODOT_IPC_TIMEOUT_MS)
        return openingDeadline
    }
    fun launched() { checkMain(); wasLaunched = true }
    fun serviceBound() { checkMain(); serviceBound = true }

    fun serviceUnbound() {
        checkMain()
        serviceBound = false
        if (!isClosing && !released) fail(EngineFailure.RENDERER_LOST)
    }

    fun serviceDestroyed() {
        checkMain()
        serviceBound = false
        if (!isClosing && !released) fail(EngineFailure.RENDERER_LOST)
        // Retirement owns the peer death watch, independently of the Service instance.
    }

    /** Definitive pre-launch failure is the only release which does not require peer death. */
    fun launchFailed() {
        checkMain()
        if (released) return
        fail(EngineFailure.INITIALIZATION_FAILED)
        if (!wasLaunched) release()
    }

    suspend fun cancelOpen() {
        checkMain()
        if (!wasLaunched) launchFailed()
        else {
            beginClose()
            withTimeoutOrNull(GODOT_IPC_CLOSE_TIMEOUT_MS) { processGone.await() }
        }
    }

    fun detachOwner() {
        checkMain()
        owner = null
        beginClose()
    }

    override suspend fun send(command: EngineCommand) {
        // The production coordinator uses the overload with a generation captured at enqueue.
        checkMain()
        send(command, lifecycle.generation)
    }

    override suspend fun send(command: EngineCommand, lifecycleGeneration: Long) {
        withContext(Dispatchers.Main.immediate) {
            if (isClosing || released || lifecycleGeneration < 0) throw GodotIpcException()
            val document = try { LastLightWireCodec.encodeCommand(identity.presentationId, command) } catch (_: Exception) {
                fail(EngineFailure.INVALID_PAYLOAD)
                throw GodotIpcException()
            }
            val complete = CompletableDeferred<Unit>()
            val confirmsReady = !confirmationSent
            confirmationSent = true
            if (!sender.offer(GodotIpcContent(GodotIpcKind.COMMAND, document, acceptReady = confirmsReady,
                    generation = lifecycleGeneration), complete)) throw GodotIpcException()
            // Cancellation does not retract a document already handed to the native endpoint.
            complete.await()
        }
    }

    override suspend fun close() {
        withContext(Dispatchers.Main.immediate) {
            beginClose()
            if (withTimeoutOrNull(GODOT_IPC_CLOSE_TIMEOUT_MS) { processGone.await(); true } != true) {
                // Unknown/live renderer lifetime remains registered: never assume a fresh process.
                throw GodotIpcException()
            }
        }
    }

    private fun receive(packet: GodotIpcPacket) {
        checkMain()
        if (released || inbox.isCurrent(packet.header).not()) return
        when (packet.operation) {
            GodotIpcOperation.HELLO -> {
                if (helloReceived) { fail(EngineFailure.INVALID_PAYLOAD); return }
                helloReceived = true
                if (!isClosing && SystemClock.elapsedRealtime() >= openingDeadline) {
                    fail(EngineFailure.INITIALIZATION_FAILED)
                    return
                }
                if (!attachPeer()) return
                main.removeCallbacks(openingTimeout)
                if (isClosing) sender.control(GodotIpcOperation.CLOSE)
                else {
                    val document = launchDocument
                    launchDocument = null
                    if (document == null || !sender.offer(GodotIpcContent(GodotIpcKind.LAUNCH, document))) {
                        fail(EngineFailure.INITIALIZATION_FAILED)
                    }
                }
            }
            GodotIpcOperation.DATA -> receiveData(packet)
            GodotIpcOperation.ACK -> if (!isClosing && !sender.acknowledge(packet.sequence, packet.superseded)) fail(EngineFailure.INVALID_PAYLOAD)
            GodotIpcOperation.EXIT_REQUESTED, GodotIpcOperation.STANDARD_TABLE_REQUESTED -> {
                if (!helloReceived || isClosing || returnRequested) return
                returnRequested = true
                if (packet.operation == GodotIpcOperation.EXIT_REQUESTED) owner?.requestExit(this)
                else owner?.requestStandardTable(this)
                beginClose()
            }
            GodotIpcOperation.NATIVE_CLOSED -> {
                if (!helloReceived) { fail(EngineFailure.INVALID_PAYLOAD); return }
                nativeClosed = true
                if (!isClosing) fail(EngineFailure.RENDERER_LOST)
                // Teardown completion is not process death. Keep the token and death watch.
            }
            GodotIpcOperation.ABORT -> fail(EngineFailure.RENDERER_LOST)
            else -> fail(EngineFailure.INVALID_PAYLOAD)
        }
    }

    private fun receiveData(packet: GodotIpcPacket) {
        if (!helloReceived || packet.sequence != incomingSequence || incomingSequence == Long.MAX_VALUE) {
            fail(EngineFailure.INVALID_PAYLOAD)
            return
        }
        incomingSequence++
        val content = packet.content ?: run { fail(EngineFailure.INVALID_PAYLOAD); return }
        when (content.kind) {
            GodotIpcKind.LIFECYCLE -> {
                if (content.generation <= lifecycle.generation) { fail(EngineFailure.INVALID_PAYLOAD); return }
                lifecycle = GodotRendererLifecycle(content.started, content.resumed, content.focused, content.generation)
                // The coordinator reads this exact generation during the synchronous callback.
                owner?.lifecycle(this, lifecycle)
            }
            GodotIpcKind.EVENT -> if (!isClosing) {
                val document = content.document ?: run { fail(EngineFailure.INVALID_PAYLOAD); return }
                val event = try { LastLightWireCodec.decodeEvent(document) } catch (_: Exception) {
                    fail(EngineFailure.INVALID_PAYLOAD)
                    return
                }
                if (event.presentationId != identity.presentationId || event.protocolVersion != ENGINE_BRIDGE_PROTOCOL_VERSION) {
                    fail(EngineFailure.INVALID_PAYLOAD)
                    return
                }
                highestEventSequence = maxOf(highestEventSequence, event.sequence)
                if (event.body !is EngineEventBody.PlayerIntent ||
                    !returnRequested && lifecycle.interactive && content.generation == lifecycle.generation) {
                    if (!enqueueEvent(QueuedEvent(event, content.generation, content.bytes))) {
                        fail(EngineFailure.INTERNAL_ERROR)
                        return
                    }
                }
            }
            else -> { fail(EngineFailure.INVALID_PAYLOAD); return }
        }
        // This acknowledges bounded transport admission, never common/authority acceptance.
        sender.acknowledgeReceived(packet.sequence)
    }

    private fun attachPeer(): Boolean {
        if (attached) return true
        val binder = inbox.peerBinder ?: return false
        attached = true
        peer = binder
        val death = IBinder.DeathRecipient {
            if (deathQueued.compareAndSet(false, true)) main.post(deathNotice)
        }
        deathRecipient = death
        try {
            binder.linkToDeath(death, 0)
        } catch (_: RemoteException) {
            rendererDied()
            return false
        }
        if (!sender.attach(Messenger(binder))) {
            fail(EngineFailure.RENDERER_LOST)
            return false
        }
        return true
    }

    private fun beginClose() {
        if (isClosing || released) return
        isClosing = true
        main.removeCallbacks(openingTimeout)
        launchDocument = null
        sender.stop()
        inbox.retire()
        clearEvents()
        eventChannel.close()
        try {
            owner?.closing(this)
        } finally {
            if (attachPeer()) sender.control(GodotIpcOperation.CLOSE)
        }
        // With no HELLO yet, retain a tombstone. Its late HELLO receives CLOSE, never launch.
    }

    private fun fail(reason: EngineFailure) {
        if (failed || released) return
        failed = true
        publishFailure(reason)
        beginClose()
    }

    private fun publishFailure(reason: EngineFailure) {
        // Install this before closing the channel, which may resume its reader immediately.
        terminalFailure = if (highestEventSequence == Long.MAX_VALUE) null else EngineEvent(
            identity.presentationId, ENGINE_BRIDGE_PROTOCOL_VERSION, highestEventSequence + 1,
            EngineEventBody.Failed(reason),
        )
        terminalException = terminalFailure == null
    }

    private var terminalFailure: EngineEvent? = null
    private var terminalException = false

    private fun enqueueEvent(event: QueuedEvent): Boolean {
        if (eventCount >= GODOT_IPC_MAX_MESSAGES || event.bytes > GODOT_IPC_MAX_EVENT_BYTES ||
            eventBytes > GODOT_IPC_MAX_EVENT_BYTES - event.bytes) return false
        eventCount++
        eventBytes += event.bytes
        if (eventChannel.trySend(event).isSuccess) return true
        eventCount--
        eventBytes -= event.bytes
        return false
    }

    private fun clearEvents() {
        while (true) {
            val removed = eventChannel.tryReceive().getOrNull() ?: break
            eventCount--
            eventBytes -= removed.bytes
        }
    }

    private fun rendererDied() {
        checkMain()
        if (released) return
        if (!isClosing) fail(EngineFailure.RENDERER_LOST)
        release()
    }

    private fun release() {
        if (released) return
        released = true
        isClosing = true
        main.removeCallbacks(openingTimeout)
        main.removeCallbacks(deathNotice)
        sender.dispose()
        inbox.close()
        val binder = peer
        val death = deathRecipient
        if (binder != null && death != null) {
            try { binder.unlinkToDeath(death, 0) } catch (_: NoSuchElementException) { /* Already dead. */ }
        }
        peer = null
        deathRecipient = null
        launchDocument = null
        eventChannel.close()
        val previousOwner = owner
        owner = null
        try {
            previousOwner?.released(this)
        } finally {
            GodotSessionRegistry.release(this)
            // The awaiting common close may immediately try a pending new presentation.
            processGone.complete(Unit)
        }
    }

    private fun checkMain() { check(Looper.myLooper() == Looper.getMainLooper()) }
}
