package dev.partydeck.godot.android

import java.util.concurrent.atomic.AtomicReference

/** Per-plugin observations in Android elapsed-realtime milliseconds; null means unobserved. */
data class CloseSignalObservation(
    val requestedElapsedRealtimeMs: Long? = null,
    val dispatchStartedElapsedRealtimeMs: Long? = null,
    val nativeBarrierElapsedRealtimeMs: Long? = null,
) {
    val acknowledged: Boolean get() = nativeBarrierElapsedRealtimeMs != null
}

/**
 * Godot 4.7.2 emitSignal queues its native call. The following render-queue barrier
 * observes its return independently of any subsequent notification to the main thread.
 * This observation belongs to one plugin lifetime and survives queue disposal.
 */
internal class NativeSignalDispatch(
    private val schedule: (() -> Unit) -> Unit,
    private val nowMillis: () -> Long,
) {
    private val close = AtomicReference(CloseSignalObservation())
    val closeObservation: CloseSignalObservation get() = close.get()

    fun closeRequested() {
        val now = nowMillis()
        close.updateAndGet {
            if (it.requestedElapsedRealtimeMs == null) it.copy(requestedElapsedRealtimeMs = now) else it
        }
    }

    fun dispatch(terminalClose: Boolean, emit: () -> Unit, afterNativeSignal: () -> Unit) {
        if (terminalClose) {
            val now = nowMillis()
            close.updateAndGet {
                if (it.dispatchStartedElapsedRealtimeMs == null) it.copy(dispatchStartedElapsedRealtimeMs = now) else it
            }
        }
        emit()
        schedule {
            if (terminalClose) {
                val now = nowMillis()
                close.updateAndGet {
                    if (it.nativeBarrierElapsedRealtimeMs == null) it.copy(nativeBarrierElapsedRealtimeMs = now) else it
                }
            }
            afterNativeSignal()
        }
    }
}
