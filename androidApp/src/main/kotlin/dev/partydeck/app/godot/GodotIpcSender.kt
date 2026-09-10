package dev.partydeck.app.godot

import android.os.Handler
import android.os.Looper
import android.os.Messenger
import android.os.RemoteException
import java.io.IOException
import kotlinx.coroutines.CompletableDeferred

internal class GodotIpcException : IOException("The renderer connection closed.")

/** Main-owned stop-and-wait sender. Transport ACKs never acknowledge an authority action. */
internal class GodotIpcSender(
    private val identity: GodotIpcIdentity,
    private val reply: Messenger,
    maxBytes: Int,
    initiallyEnabled: Boolean = true,
    private val onFailure: () -> Unit,
) {
    private data class Pending(val content: GodotIpcContent, val completion: CompletableDeferred<Unit>?)

    private val main = Handler(Looper.getMainLooper())
    private val window = GodotIpcWindow<Pending>(GODOT_IPC_MAX_MESSAGES, maxBytes, { it.content.bytes })
    private var peer: Messenger? = null
    private var stopped = false
    private var failed = false
    private var enabled = initiallyEnabled
    private val sentControls = mutableSetOf<GodotIpcOperation>()
    private val timeout = Runnable { fail() }

    fun attach(value: Messenger): Boolean {
        checkMain()
        if (peer != null) return false
        peer = value
        pump()
        return true
    }

    fun offer(content: GodotIpcContent, completion: CompletableDeferred<Unit>? = null): Boolean {
        checkMain()
        if (stopped) {
            completion?.completeExceptionally(GodotIpcException())
            return false
        }
        val admitted = try { content.valid() && window.offer(Pending(content, completion)) } catch (_: Exception) { false }
        if (!admitted) {
            completion?.completeExceptionally(GodotIpcException())
            fail()
            return false
        }
        pump()
        return !stopped
    }

    fun enableData() {
        checkMain()
        enabled = true
        pump()
    }

    fun acknowledge(sequence: Long, superseded: Boolean): Boolean {
        checkMain()
        if (stopped) return false
        val outstanding = window.outstanding ?: return false
        if (outstanding.sequence != sequence || superseded && outstanding.value.content.kind != GodotIpcKind.COMMAND) return false
        val released = window.acknowledge(sequence) ?: return false
        main.removeCallbacks(timeout)
        released.completion?.complete(Unit)
        pump()
        return true
    }

    fun acknowledgeReceived(sequence: Long, superseded: Boolean = false): Boolean = send(
        GodotIpcPacket(GodotIpcHeader(identity, reply), GodotIpcOperation.ACK, sequence, superseded = superseded),
    )

    /** One-shot terminal controls bypass any stalled DATA window. */
    fun control(operation: GodotIpcOperation): Boolean {
        checkMain()
        require(operation != GodotIpcOperation.DATA && operation != GodotIpcOperation.ACK)
        if (operation in sentControls) return true
        if (peer == null) return false
        sentControls += operation
        return send(GodotIpcPacket(GodotIpcHeader(identity, reply), operation))
    }

    /** Clear suspended writers immediately; keep just the endpoint for terminal controls. */
    fun stop() {
        checkMain()
        if (stopped) return
        stopped = true
        main.removeCallbacks(timeout)
        window.clear().forEach { it.completion?.completeExceptionally(GodotIpcException()) }
    }

    fun dispose() {
        stop()
        peer = null
        sentControls.clear()
    }

    private fun pump() {
        if (stopped || !enabled || peer == null) return
        val item = window.takeForSend() ?: return
        main.postDelayed(timeout, GODOT_IPC_TIMEOUT_MS)
        send(GodotIpcPacket(GodotIpcHeader(identity, reply), GodotIpcOperation.DATA, item.sequence, item.value.content))
    }

    private fun send(packet: GodotIpcPacket): Boolean {
        checkMain()
        val remote = peer ?: return false
        return try {
            remote.send(GodotIpcWire.message(packet))
            true
        } catch (_: RemoteException) {
            fail()
            false
        } catch (_: RuntimeException) {
            fail()
            false
        }
    }

    private fun fail() {
        if (failed) return
        failed = true
        stop()
        onFailure()
    }

    private fun checkMain() { check(Looper.myLooper() == Looper.getMainLooper()) }
}
