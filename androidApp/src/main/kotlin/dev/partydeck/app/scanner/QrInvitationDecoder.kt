package dev.partydeck.app.scanner

import com.google.zxing.BinaryBitmap
import com.google.zxing.DecodeHintType
import com.google.zxing.LuminanceSource
import com.google.zxing.PlanarYUVLuminanceSource
import com.google.zxing.ReaderException
import com.google.zxing.common.HybridBinarizer
import com.google.zxing.qrcode.QRCodeReader
import dev.partydeck.transport.LanInvitation
import java.nio.ByteBuffer

internal sealed interface QrReadResult {
    data object NoCode : QrReadResult
    data object NotInvitation : QrReadResult
    data class Invitation(val value: String) : QrReadResult
}

/** QR detection handles rotation and perspective; camera frames never need a rotated bitmap copy. */
internal class QrInvitationDecoder {
    private val reader = QRCodeReader()
    private val hints = mapOf(DecodeHintType.TRY_HARDER to true)

    fun decode(luminance: ByteArray, width: Int, height: Int): QrReadResult {
        val source = PlanarYUVLuminanceSource(luminance, width, height, 0, 0, width, height, false)
        val value = read(source) ?: read(source.invert()) ?: return QrReadResult.NoCode
        if (value.length !in 1..MAX_INVITATION_LENGTH) return QrReadResult.NotInvitation
        return try {
            LanInvitation.decode(value)
            QrReadResult.Invitation(value)
        } catch (_: IllegalArgumentException) {
            QrReadResult.NotInvitation
        }
    }

    private fun read(source: LuminanceSource): String? = try {
        reader.decode(BinaryBitmap(HybridBinarizer(source)), hints).text
    } catch (_: ReaderException) {
        // A preview frame usually contains no complete QR code. This is an expected scan outcome.
        null
    } finally {
        reader.reset()
    }

    private companion object {
        const val MAX_INVITATION_LENGTH = 2048
    }
}

/** Copies only visible Y pixels; device-specific row padding and pixel stride are not image data. */
internal fun copyPlaneLuminance(
    source: ByteBuffer,
    width: Int,
    height: Int,
    rowStride: Int,
    pixelStride: Int,
    destination: ByteArray,
) {
    require(width > 0 && height > 0 && rowStride > 0 && pixelStride > 0)
    val pixels = width.toLong() * height
    require(pixels <= MAX_ANALYSIS_PIXELS && destination.size.toLong() >= pixels)
    val rowBytes = (width - 1L) * pixelStride + 1L
    require(rowBytes <= rowStride)
    val requiredBytes = (height - 1L) * rowStride + rowBytes
    require(requiredBytes <= source.remaining().toLong())
    val buffer = source.duplicate()
    val start = buffer.position()
    for (row in 0 until height) {
        val offset = start + row * rowStride
        if (pixelStride == 1) {
            buffer.position(offset)
            buffer.get(destination, row * width, width)
        } else {
            for (column in 0 until width) {
                destination[row * width + column] = buffer.get(offset + column * pixelStride)
            }
        }
    }
}

internal const val MAX_ANALYSIS_PIXELS = 1920L * 1080L
