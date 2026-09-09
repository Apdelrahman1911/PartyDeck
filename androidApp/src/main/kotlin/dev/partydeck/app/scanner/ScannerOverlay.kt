package dev.partydeck.app.scanner

import android.content.Context
import android.graphics.Canvas
import android.graphics.Paint
import android.graphics.Path
import android.graphics.RectF
import android.view.View
import kotlin.math.min

/** A static framing guide; it does not imply a code has been recognized. */
internal class ScannerOverlay(context: Context) : View(context) {
    private val density = resources.displayMetrics.density
    private val scrim = Paint().apply { color = 0xA6191526.toInt() }
    private val stroke = Paint(Paint.ANTI_ALIAS_FLAG).apply {
        color = 0xFFF16B48.toInt()
        strokeWidth = 3f * density
        style = Paint.Style.STROKE
        strokeCap = Paint.Cap.ROUND
    }
    private val frame = RectF()
    private val outside = Path()

    init {
        importantForAccessibility = IMPORTANT_FOR_ACCESSIBILITY_NO
    }

    override fun onSizeChanged(width: Int, height: Int, oldWidth: Int, oldHeight: Int) {
        val size = min(min(width - 48f * density, height - 240f * density), 300f * density)
            .coerceAtLeast(72f * density)
        val centerY = ((height - 160f * density) / 2f + 20f * density).coerceAtLeast(100f * density)
        frame.set((width - size) / 2f, centerY - size / 2f, (width + size) / 2f, centerY + size / 2f)
        outside.reset()
        outside.fillType = Path.FillType.EVEN_ODD
        outside.addRect(0f, 0f, width.toFloat(), height.toFloat(), Path.Direction.CW)
        outside.addRoundRect(frame, 22f * density, 22f * density, Path.Direction.CW)
    }

    override fun onDraw(canvas: Canvas) {
        canvas.drawPath(outside, scrim)
        canvas.drawRoundRect(frame, 22f * density, 22f * density, stroke)
    }
}
