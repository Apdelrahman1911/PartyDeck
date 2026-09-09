package dev.partydeck.app.scanner

import com.google.zxing.BarcodeFormat
import com.google.zxing.EncodeHintType
import com.google.zxing.qrcode.QRCodeWriter
import com.google.zxing.qrcode.decoder.ErrorCorrectionLevel
import dev.partydeck.transport.LanEndpoint
import dev.partydeck.transport.LanInvitation
import java.nio.ByteBuffer
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertIs

class QrInvitationDecoderTest {
    @Test
    fun decodesAnExactInvitationFromPaddedCameraRowsAndInterleavedPixels() {
        val invitation = invitation()
        val size = 640
        val image = qrLuminance(invitation, size)
        val pixelStride = 2
        val rowStride = size * pixelStride + 13
        val prefix = 7
        // The final camera row need not include its padding bytes.
        val source = ByteBuffer.allocate(prefix + (size - 1) * rowStride + (size - 1) * pixelStride + 1)
        for (row in 0 until size) {
            for (column in 0 until size) {
                source.put(prefix + row * rowStride + column * pixelStride, image[row * size + column])
            }
        }
        source.position(prefix)
        val copied = ByteArray(size * size)

        copyPlaneLuminance(source, size, size, rowStride, pixelStride, copied)

        assertEquals(prefix, source.position(), "Analyzing must not mutate the camera buffer's position")
        assertEquals(invitation, assertIs<QrReadResult.Invitation>(QrInvitationDecoder().decode(copied, size, size)).value)
    }

    @Test
    fun readsTheInvitationAtEveryQuarterTurnWithoutRotatingCameraFrames() {
        val invitation = invitation()
        val size = 640
        var image = qrLuminance(invitation, size)
        val decoder = QrInvitationDecoder()
        repeat(4) {
            assertEquals(invitation, assertIs<QrReadResult.Invitation>(decoder.decode(image, size, size)).value)
            val rotated = ByteArray(image.size)
            for (row in 0 until size) for (column in 0 until size) {
                rotated[row * size + column] = image[(size - column - 1) * size + row]
            }
            image = rotated
        }
    }

    @Test
    fun rejectsUnrelatedMalformedAndOversizedQrPayloads() {
        val decoder = QrInvitationDecoder()
        for (payload in listOf("https://example.invalid", "partydeck:v1:invalid", "x".repeat(2049))) {
            assertIs<QrReadResult.NotInvitation>(decoder.decode(qrLuminance(payload, 800), 800, 800))
        }
        assertIs<QrReadResult.NoCode>(decoder.decode(ByteArray(320 * 320) { 244.toByte() }, 320, 320))
    }

    @Test
    fun rejectsTruncatedOrOversizedPlanesBeforeReadingCameraMemory() {
        assertFailsWith<IllegalArgumentException> {
            copyPlaneLuminance(ByteBuffer.allocate(19), 4, 3, 8, 1, ByteArray(12))
        }
        assertFailsWith<IllegalArgumentException> {
            copyPlaneLuminance(ByteBuffer.allocate(20), 4, 3, 3, 1, ByteArray(12))
        }
        assertFailsWith<IllegalArgumentException> {
            copyPlaneLuminance(ByteBuffer.allocate(1), Int.MAX_VALUE, 3, Int.MAX_VALUE, 1, ByteArray(1))
        }
    }

    private fun invitation(): String = LanInvitation(
        sessionId = "scanner-fixture",
        admissionSecret = "a".repeat(64),
        endpoint = LanEndpoint("192.168.1.10", 7654, "PartyDeck fixture"),
        certificateSha256 = "b".repeat(64),
    ).encode()

    private fun qrLuminance(text: String, size: Int): ByteArray {
        val code = QRCodeWriter().encode(text, BarcodeFormat.QR_CODE, size, size, mapOf(
            EncodeHintType.ERROR_CORRECTION to ErrorCorrectionLevel.M,
            EncodeHintType.MARGIN to 4,
        ))
        // Ink/paper luminance rather than ideal 0/255 values exercises the production binarizer.
        return ByteArray(size * size) { index -> if (code[index % size, index / size]) 22 else 244.toByte() }
    }
}
