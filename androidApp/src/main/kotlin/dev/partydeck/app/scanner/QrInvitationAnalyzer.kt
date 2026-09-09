package dev.partydeck.app.scanner

import android.os.SystemClock
import android.util.Log
import androidx.camera.core.ImageAnalysis
import androidx.camera.core.ImageProxy
import java.util.concurrent.atomic.AtomicBoolean

/** One CameraX worker, one reused luminance buffer, and at most six decode attempts per second. */
internal class QrInvitationAnalyzer(
    private val onInvitation: (String) -> Unit,
    private val onOtherCode: () -> Unit,
    private val onFailure: () -> Unit,
) : ImageAnalysis.Analyzer {
    private val closed = AtomicBoolean(false)
    private val active = AtomicBoolean(true)
    private val found = AtomicBoolean(false)
    private val decoder = QrInvitationDecoder()
    private var lastFrameAt = 0L
    private var lastOtherCodeAt = 0L
    private var luminance = ByteArray(0)

    fun setActive(value: Boolean) {
        active.set(value)
        if (value) found.set(false)
    }

    override fun analyze(image: ImageProxy) {
        var copiedFrame = false
        try {
            val now = SystemClock.elapsedRealtime()
            if (closed.get() || !active.get() || found.get() || now - lastFrameAt < FRAME_INTERVAL_MILLIS) return
            lastFrameAt = now
            val pixels = image.width.toLong() * image.height
            require(pixels in 1..MAX_ANALYSIS_PIXELS)
            if (luminance.size != pixels.toInt()) luminance = ByteArray(pixels.toInt())
            val plane = image.planes.first()
            copiedFrame = true
            copyPlaneLuminance(plane.buffer, image.width, image.height, plane.rowStride, plane.pixelStride, luminance)
            val result = decoder.decode(luminance, image.width, image.height)
            if (closed.get() || !active.get()) return
            when (result) {
                is QrReadResult.Invitation -> if (found.compareAndSet(false, true)) onInvitation(result.value)
                QrReadResult.NotInvitation -> if (now - lastOtherCodeAt >= OTHER_CODE_INTERVAL_MILLIS) {
                    lastOtherCodeAt = now
                    onOtherCode()
                }
                QrReadResult.NoCode -> Unit
            }
        } catch (failure: RuntimeException) {
            if (closed.compareAndSet(false, true)) {
                Log.w(TAG, "Camera frame analysis is unavailable", failure)
                onFailure()
            }
        } finally {
            // Do not keep a captured frame between attempts or outside this scanner's lifetime.
            if (copiedFrame) luminance.fill(0)
            image.close()
        }
    }

    fun close() {
        active.set(false)
        closed.set(true)
    }

    private companion object {
        const val TAG = "PartyDeckScanner"
        const val FRAME_INTERVAL_MILLIS = 170L
        const val OTHER_CODE_INTERVAL_MILLIS = 1500L
    }
}
