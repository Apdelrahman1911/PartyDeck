package dev.partydeck.app.godot

import android.os.Handler
import android.os.IBinder
import android.os.Looper
import android.os.Message
import android.os.Messenger
import android.os.Process

/**
 * Admission runs on Binder ingress, before a remote Message can enter the main Handler queue.
 * AOSP MessengerImpl captures sendingUid and calls the virtual sendMessageAtTime method.
 * Only immutable, authenticated packets enter this bounded mailbox; one separate Handler
 * drains finite batches on main. Framework/Binder transaction allocation precedes this boundary.
 */
internal class GodotIpcInbox(
    private val identity: GodotIpcIdentity,
    private val acceptsHello: Boolean,
    private val maxBytes: Int,
    onPacket: (GodotIpcPacket) -> Unit,
    onFailure: () -> Unit,
) {
    private data class Retained(val packet: GodotIpcPacket, val bytes: Int)

    private val lock = Any()
    private val queue = ArrayDeque<Retained>()
    private val drainHandler = Handler(Looper.getMainLooper())
    private var packetListener: ((GodotIpcPacket) -> Unit)? = onPacket
    private var failureListener: (() -> Unit)? = onFailure
    private var peer: IBinder? = null
    private var closed = false
    private var failed = false
    private var failurePending = false
    private var scheduled = false
    private var discardDocuments = false
    private var retainedCount = 0
    private var retainedBytes = 0
    private val drainTask = Runnable { drain() }

    private val ingress = object : Handler(Looper.getMainLooper()) {
        override fun sendMessageAtTime(message: Message, uptimeMillis: Long): Boolean {
            try {
                admit(message)
            } finally {
                // We never enqueue this framework message, so no Looper will recycle it.
                message.recycle()
            }
            return true
        }
    }
    val messenger = Messenger(ingress)

    val peerBinder: IBinder? get() = synchronized(lock) { peer }

    /** Child-side binding pins the service Binder before sending HELLO. No replacement. */
    fun pinPeer(binder: IBinder): Boolean = synchronized(lock) {
        if (closed || failed || peer != null) false else {
            peer = binder
            true
        }
    }

    fun isCurrent(header: GodotIpcHeader): Boolean = synchronized(lock) {
        !closed && header.identity == identity && header.reply.binder == peer
    }

    /** Keep minimal retirement/death attachment, without retaining private documents. */
    fun retire() = synchronized(lock) {
        discardDocuments = true
        val replacements = queue.map { retained ->
            val packet = retained.packet.withoutDocument()
            Retained(packet, packet.bytes)
        }
        retainedBytes -= queue.sumOf { it.bytes }
        queue.clear()
        queue.addAll(replacements)
        retainedBytes += replacements.sumOf { it.bytes }
    }

    fun close() = synchronized(lock) {
        if (closed) return@synchronized
        closed = true
        clearQueuedLocked()
        failurePending = false
        packetListener = null
        failureListener = null
        peer = null
        drainHandler.removeCallbacks(drainTask)
        scheduled = false
    }

    private fun admit(message: Message) {
        if (message.sendingUid != Process.myUid()) return
        synchronized(lock) {
            if (closed || failed) return
            val header = try {
                // Do not resolve application Parcelable classes from an unauthenticated Bundle.
                message.peekData()?.classLoader = null
                GodotIpcWire.header(message)
            } catch (_: Exception) {
                null
            } ?: return
            if (header.identity != identity) return
            val currentPeer = peer
            if (currentPeer == null) {
                if (!acceptsHello || message.what != GodotIpcOperation.HELLO.code) return
                // Pin exactly once under the admission lock, including a malformed first HELLO.
                // The main failure callback can then watch this peer's death and request close.
                peer = header.reply.binder
            } else if (header.reply.binder != currentPeer) return

            val packet = try {
                GodotIpcWire.decode(message, header).let { if (discardDocuments) it.withoutDocument() else it }
            } catch (_: Exception) {
                failLocked()
                return
            }
            val bytes = packet.bytes
            if (retainedCount >= GODOT_IPC_MAX_MESSAGES || bytes > maxBytes || retainedBytes > maxBytes - bytes) {
                failLocked()
                return
            }
            queue.addLast(Retained(packet, bytes))
            retainedCount++
            retainedBytes += bytes
            scheduleLocked()
        }
    }

    private fun failLocked() {
        if (failed || closed) return
        failed = true
        failurePending = true
        clearQueuedLocked()
        scheduleLocked()
    }

    private fun clearQueuedLocked() {
        retainedCount -= queue.size
        retainedBytes -= queue.sumOf { it.bytes }
        queue.clear()
        // A currently executing packet stays counted until its callback returns.
    }

    private fun scheduleLocked() {
        if (scheduled || closed) return
        scheduled = true
        if (!drainHandler.post(drainTask)) {
            closed = true
            clearQueuedLocked()
            packetListener = null
            failureListener = null
            peer = null
        }
    }

    private fun drain() {
        check(Looper.myLooper() == Looper.getMainLooper())
        repeat(DRAIN_BATCH) {
            val failure = synchronized(lock) {
                if (failurePending && !closed) {
                    failurePending = false
                    failureListener
                } else null
            }
            if (failure != null) {
                try { failure() } catch (_: Exception) { close() }
            }
            val retained = synchronized(lock) {
                if (closed || failed) null else queue.removeFirstOrNull()
            } ?: return@repeat
            try {
                val listener = synchronized(lock) {
                    if (!closed && !failed && isCurrent(retained.packet.header)) packetListener else null
                }
                listener?.invoke(retained.packet)
            } catch (_: Exception) {
                synchronized(lock) { failLocked() }
            } finally {
                synchronized(lock) {
                    retainedCount--
                    retainedBytes -= retained.bytes
                }
            }
        }
        synchronized(lock) {
            scheduled = false
            if (failurePending || queue.isNotEmpty()) scheduleLocked()
        }
    }

    private fun GodotIpcPacket.withoutDocument(): GodotIpcPacket =
        if (content?.document == null) this else copy(content = content.copy(document = null))

    private companion object { const val DRAIN_BATCH = 8 }
}
