package dev.partydeck.godot.compare

import android.os.Handler
import android.os.Looper
import android.util.AtomicFile
import android.util.Log
import java.io.File
import java.util.concurrent.Executors

/** Atomic, app-private evidence. One pending snapshot replaces older unwritten snapshots. */
internal class EvidenceRecorder(directory: File, private val onFailure: () -> Unit) {
    private data class Pending(val document: String, val finished: (() -> Unit)? = null)
    private val destination = AtomicFile(File(directory, FILE_NAME))
    private val main = Handler(Looper.getMainLooper())
    private val writer = Executors.newSingleThreadExecutor { task -> Thread(task, "GodotEvidenceWriter") }
    private val lock = Any()
    private var pending: Pending? = null
    private var scheduled = false
    private var finishing = false
    private var closed = false

    fun record(document: String) = submit(Pending(document))

    /** Calls back on the Activity thread only after attempting the final atomic write. */
    fun finish(document: String, onCommitted: () -> Unit) = submit(Pending(document, onCommitted))

    private fun submit(next: Pending) {
        synchronized(lock) {
            if (closed || finishing) return
            require(next.document.length <= 32_768)
            if (next.finished != null) finishing = true
            pending = next
            if (scheduled) return
            scheduled = true
        }
        writer.execute(::drain)
    }

    private fun drain() {
        while (true) {
            val next = synchronized(lock) {
                val value = pending
                pending = null
                if (value == null) scheduled = false
                value
            } ?: return
            try {
                val output = destination.startWrite()
                try {
                    output.write(next.document.toByteArray(Charsets.UTF_8))
                    destination.finishWrite(output)
                } catch (failure: Exception) {
                    destination.failWrite(output)
                    throw failure
                }
            } catch (_: Exception) {
                // Never log documents, card bindings, or exception messages containing their data.
                Log.e(TAG, "App-private evidence write failed")
                main.post { onFailure() }
            }
            if (next.finished != null) {
                synchronized(lock) {
                    closed = true
                    pending = null
                }
                writer.shutdown()
                main.post { next.finished.invoke() }
                return
            }
        }
    }

    companion object {
        const val FILE_NAME = "godot-qualification.json"
        const val TAG = "PartyDeckGodotHost"
    }
}
