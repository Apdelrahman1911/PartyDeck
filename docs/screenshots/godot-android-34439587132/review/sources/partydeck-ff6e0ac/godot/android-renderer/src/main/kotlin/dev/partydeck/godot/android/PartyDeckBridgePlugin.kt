package dev.partydeck.godot.android

import android.os.Handler
import android.os.Looper
import dev.partydeck.games.EngineEventBody
import dev.partydeck.games.MAX_ENGINE_PAYLOAD_BYTES
import dev.partydeck.godot.bridge.LastLightWireCodec
import dev.partydeck.godot.bridge.MAX_RENDERER_EVENT_BYTES
import org.godotengine.godot.Godot
import org.godotengine.godot.plugin.GodotPlugin
import org.godotengine.godot.plugin.SignalInfo
import org.godotengine.godot.plugin.UsedByGodot
import java.util.concurrent.atomic.AtomicBoolean
import java.util.concurrent.atomic.AtomicLong
import java.util.concurrent.atomic.AtomicReference
import javax.microedition.khronos.opengles.GL10

/** Runtime plugin installed explicitly by the owning native Godot host. */
class PartyDeckBridgePlugin(
    engine: Godot,
    launchDocument: String,
    private val displayScale: Double,
    private val listener: Listener,
) : GodotPlugin(engine) {
    interface Listener {
        fun onRendererEvent(document: String)
        fun onRendererDiagnostics(document: String)
        fun onBridgeFailure(code: String)
        fun onNativeSetup()
        fun onNativeMainLoop()
    }

    private sealed interface Inbound {
        data class Event(val document: String, val inputGeneration: Long?) : Inbound
        data class Diagnostics(val document: String) : Inbound
    }

    private sealed interface Outbound {
        data class Command(val document: String, val afterDelivery: (() -> Unit)?) : Outbound
        data class Diagnostics(val requestId: String) : Outbound
        data class Close(val document: String) : Outbound
    }

    private val main = Handler(Looper.getMainLooper())
    private val active = AtomicBoolean(true)
    private val inputGate = RendererInputGate()
    private val initialLaunch = AtomicReference<String?>(launchDocument)
    private val nativeSetup = AtomicBoolean(false)
    private val rendererReady = AtomicBoolean(false)
    private val diagnosticsExpected = AtomicBoolean(false)
    private data class DrawContinuation(val afterFrame: Long, val action: () -> Unit)
    private val renderedFrames = AtomicLong(0)
    private val afterDraw = AtomicReference<DrawContinuation?>(null)
    val nativeTerminating = AtomicBoolean(false)
    private val incoming = BoundedDispatchQueue<Inbound>(
        capacity = 32,
        schedule = { task -> main.post { task() } },
        consume = { input, done ->
            if (active.get()) when (input) {
                is Inbound.Event -> if (input.inputGeneration == null || inputGate.accepts(input.inputGeneration)) {
                    listener.onRendererEvent(input.document)
                }
                is Inbound.Diagnostics -> listener.onRendererDiagnostics(input.document)
            }
            done()
        },
        onFailure = { fail("inbound_backpressure_or_dispatch") },
    )
    private val outgoing = BoundedDispatchQueue<Outbound>(
        capacity = 16,
        schedule = { task -> engine.runOnRenderThread { task() } },
        consume = { output, done ->
            if (active.get() || output is Outbound.Close) {
                when (output) {
                    is Outbound.Command -> emitSignal("command_received", output.document)
                    is Outbound.Close -> emitSignal("command_received", output.document)
                    is Outbound.Diagnostics -> emitSignal("diagnostics_requested", output.requestId)
                }
                // emitSignal queues a second Runnable in Godot 4.7.2. Acknowledge after
                // that Runnable so a stalled engine cannot accumulate native emissions.
                engine.runOnRenderThread {
                    done()
                    if (output is Outbound.Command && output.afterDelivery != null) {
                        main.post { if (active.get()) output.afterDelivery.invoke() }
                    }
                }
            } else done()
        },
        onFailure = { fail("outbound_backpressure_or_dispatch") },
        initiallyStarted = false,
    )

    init {
        require(withinUtf8Limit(launchDocument, MAX_ENGINE_PAYLOAD_BYTES))
        require(displayScale.isFinite() && displayScale in 0.5..8.0)
    }

    override fun getPluginName() = "PartyDeckBridge"

    override fun getPluginSignals(): Set<SignalInfo> = setOf(
        SignalInfo("command_received", String::class.java),
        SignalInfo("diagnostics_requested", String::class.java),
    )

    @UsedByGodot
    fun get_launch_document(): String = if (active.get()) initialLaunch.get().orEmpty() else ""

    /** Android dp scale only. User font scale is independently carried in launch preferences. */
    @UsedByGodot
    fun get_display_scale(): Double = displayScale

    @UsedByGodot
    fun renderer_event(document: String) {
        if (!active.get()) return
        val inputGeneration = inputGate.capture()
        if (!withinUtf8Limit(document, MAX_RENDERER_EVENT_BYTES)) {
            fail("oversized_renderer_event")
            return
        }
        val playerInput = try {
            LastLightWireCodec.decodeEvent(document).body is EngineEventBody.PlayerIntent
        } catch (_: IllegalArgumentException) {
            fail("invalid_renderer_event")
            return
        }
        if (playerInput && inputGeneration == null) return
        incoming.offer(Inbound.Event(document, if (playerInput) inputGeneration else null))
    }

    @UsedByGodot
    fun renderer_diagnostics(document: String) {
        // Correlation is checked on the owning main thread. A delayed response from a
        // cancelled request must not consume the newer request's only callback slot.
        if (!active.get() || !diagnosticsExpected.get()) return
        if (!withinUtf8Limit(document, MAX_DIAGNOSTICS_BYTES)) {
            fail("oversized_renderer_diagnostics")
            return
        }
        incoming.offer(Inbound.Diagnostics(document))
    }

    override fun onGodotSetupCompleted() {
        nativeSetup.set(true)
        startDeliveryIfReady()
        main.post { if (active.get()) listener.onNativeSetup() }
    }

    override fun onGodotMainLoopStarted() {
        main.post { if (active.get()) listener.onNativeMainLoop() }
    }

    override fun onGodotTerminating() {
        nativeTerminating.set(true)
    }

    override fun onGLDrawFrame(gl: GL10?) {
        val frame = renderedFrames.incrementAndGet()
        val continuation = afterDraw.get()
        if (continuation != null && frame >= continuation.afterFrame && afterDraw.compareAndSet(continuation, null)) {
            main.post { if (active.get()) continuation.action() }
        }
    }

    /** Observe two draws after command delivery, keeping the native cover over the old buffer. */
    fun afterForegroundDraw(action: () -> Unit) {
        if (active.get()) afterDraw.set(DrawContinuation(renderedFrames.get() + 2, action))
    }

    override fun onMainDestroy() = dispose()

    fun acceptReady() {
        rendererReady.set(true)
        startDeliveryIfReady()
    }

    /** Cover/input ownership is native. Ready, failure and exit remain deliverable while covered. */
    fun setInputEnabled(enabled: Boolean) {
        inputGate.setEnabled(enabled && active.get())
    }

    fun send(document: String, afterDelivery: (() -> Unit)? = null): Boolean {
        if (!withinUtf8Limit(document, MAX_ENGINE_PAYLOAD_BYTES)) {
            fail("oversized_host_command")
            return false
        }
        return active.get() && outgoing.offer(Outbound.Command(document, afterDelivery))
    }

    fun requestDiagnostics(requestId: String): Boolean {
        if (!active.get() || !rendererReady.get()) return false
        if (!diagnosticsExpected.compareAndSet(false, true)) return false
        if (outgoing.offer(Outbound.Diagnostics(requestId))) return true
        diagnosticsExpected.set(false)
        return false
    }

    fun cancelDiagnosticsRequest() { diagnosticsExpected.set(false) }

    fun close(document: String, afterDelivery: () -> Unit) {
        if (!active.getAndSet(false)) return
        inputGate.setEnabled(false)
        initialLaunch.set(null)
        afterDraw.set(null)
        incoming.close()
        diagnosticsExpected.set(false)
        outgoing.finish(Outbound.Close(document)) { main.post { afterDelivery() } }
    }

    fun dispose() {
        active.set(false)
        inputGate.setEnabled(false)
        initialLaunch.set(null)
        afterDraw.set(null)
        diagnosticsExpected.set(false)
        incoming.close()
        outgoing.close()
    }

    private fun startDeliveryIfReady() {
        if (active.get() && nativeSetup.get() && rendererReady.get()) outgoing.start()
    }

    private fun fail(code: String) {
        if (!active.getAndSet(false)) return
        inputGate.setEnabled(false)
        initialLaunch.set(null)
        afterDraw.set(null)
        incoming.close()
        outgoing.close()
        main.post { listener.onBridgeFailure(code) }
    }

    companion object {
        const val MAX_DIAGNOSTICS_BYTES = 16_384

        fun withinUtf8Limit(document: String, limit: Int): Boolean =
            document.length <= limit && document.toByteArray(Charsets.UTF_8).size <= limit
    }
}
