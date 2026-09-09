package dev.partydeck.transport

import kotlin.io.encoding.Base64
import kotlin.test.Test
import kotlin.test.assertContentEquals
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertFalse
import kotlin.test.assertTrue

/** Independent adversarial checks; transport implementation ownership remains separate. */
class SecurityTransportTest {
    @Test
    fun arbitraryFragmentationPreservesFramesAndKeepalives() {
        val payloads = listOf(byteArrayOf(), ByteArray(37) { it.toByte() }, byteArrayOf(), byteArrayOf(0, -1, 4))
        val stream = payloads.fold(byteArrayOf()) { result, payload -> result + FrameCodec.encode(payload) }
        for (split in 0..stream.size) {
            val decoder = FrameDecoder()
            val received = mutableListOf<ByteArray>()
            val collect: (ByteArray) -> Boolean = { received.add(it); true }
            assertTrue(decoder.accept(stream.copyOfRange(0, split), collect))
            assertTrue(decoder.accept(stream.copyOfRange(split, stream.size), collect))
            assertEquals(payloads.size, received.size, "Split $split")
            payloads.indices.forEach { assertContentEquals(payloads[it], received[it], "Split $split frame $it") }
            assertFalse(decoder.hasPartialFrame)
        }
    }

    @Test
    fun oversizedUnsignedLengthsFailBeforeAnyPayloadIsDelivered() {
        val maliciousLengths = listOf(65_537L, 0x7fffffffL, 0x80000000L, 0xffffffffL)
        for (length in maliciousLengths) {
            val header = ByteArray(4) { index -> (length ushr ((3 - index) * 8)).toByte() }
            var deliveries = 0
            val exception = assertFailsWith<TransportException> {
                FrameDecoder().accept(header) { deliveries++; true }
            }
            assertEquals(TransportFailureCode.INVALID_FRAME, exception.failure.code)
            assertEquals(0, deliveries)
        }
    }

    @Test
    fun maximumFrameIsDetachedFromInputAndPartialStateIsAccurate() {
        val payload = ByteArray(MAX_FRAME_BYTES) { (it xor 0x55).toByte() }
        val encoded = FrameCodec.encode(payload)
        val decoder = FrameDecoder()
        var received: ByteArray? = null
        decoder.accept(encoded.copyOfRange(0, 3)) { error("Incomplete header must not deliver") }
        assertTrue(decoder.hasPartialFrame)
        decoder.accept(encoded.copyOfRange(3, encoded.lastIndex)) { error("Incomplete body must not deliver") }
        assertTrue(decoder.hasPartialFrame)
        decoder.accept(encoded.copyOfRange(encoded.lastIndex, encoded.size)) { received = it; true }
        assertFalse(decoder.hasPartialFrame)
        encoded.fill(0)
        assertContentEquals(payload, received)
    }

    @Test
    fun rejectedDeliveryStopsTheCurrentReadImmediately() {
        val stream = FrameCodec.encode(byteArrayOf(1)) + FrameCodec.encode(byteArrayOf(2))
        val received = mutableListOf<ByteArray>()
        assertFalse(FrameDecoder().accept(stream) { received.add(it); false })
        assertEquals(1, received.size)
        assertContentEquals(byteArrayOf(1), received.single())
    }

    @Test
    fun authenticInvitationRoundTripsWithoutLeakingCredentialToDiagnostics() {
        val invite = invitation()
        assertEquals(invite, LanInvitation.decode(invite.encode()))
        assertFalse(invite.toString().contains(invite.admissionSecret))
        assertFalse(invite.toString().contains(invite.certificateSha256))
    }

    @Test
    fun duplicateAndEscapedInvitationIdentityFieldsAreRejected() {
        val secret = "a".repeat(64)
        val pin = "b".repeat(64)
        val base = "\"sessionId\":\"room\",\"admissionSecret\":\"$secret\",\"endpoint\":{\"host\":\"127.0.0.1\",\"port\":12345,\"serviceName\":null}"
        val invalidJson = listOf(
            "{$base,\"certificateSha256\":\"$pin\",\"certificateSha256\":\"$pin\",\"version\":1}",
            "{$base,\"certificateSha256\":\"$pin\",\"\\u0063ertificateSha256\":\"$pin\",\"version\":1}",
            "{$base,\"certificateSha256\":\"$pin\",\"version\":2,\"version\":1}",
            "{$base,\"certificateSha256\":\"$pin\",\"version\":1,\"\\u0076ersion\":1}",
            "{$base,\"certificateSha256\":\"$pin\",\"version\":1}".replace(
                "\"host\":\"127.0.0.1\"",
                "\"host\":\"untrusted.invalid\",\"\\u0068ost\":\"127.0.0.1\"",
            ),
        )
        invalidJson.forEach { json ->
            assertFailsWith<IllegalArgumentException> { LanInvitation.decode(encodedJson(json.encodeToByteArray())) }
        }
    }

    @Test
    fun malformedInvitationEncodingUtf8AndNativeServiceNamesAreRejected() {
        val valid = invitation().encode()
        listOf("", "partydeck:v1:", valid + "=", "partydeck:v2:" + valid.substringAfter("partydeck:v1:"), "x".repeat(2_049))
            .forEach { assertFailsWith<IllegalArgumentException> { LanInvitation.decode(it) } }
        listOf(byteArrayOf(0xc0.toByte(), 0xaf.toByte()), byteArrayOf(0xed.toByte(), 0xa0.toByte(), 0x80.toByte()))
            .forEach { invalidUtf8 ->
                assertFailsWith<IllegalArgumentException> { LanInvitation.decode(encodedJson(invalidUtf8)) }
            }
        listOf("room\u0000tail", "room\nother", "room\u007f").forEach { service ->
            assertFailsWith<IllegalArgumentException> { LanEndpoint("127.0.0.1", 12345, service) }
        }
    }

    private fun invitation() = LanInvitation(
        sessionId = "room",
        admissionSecret = "a".repeat(64),
        endpoint = LanEndpoint("127.0.0.1", 12345),
        certificateSha256 = "b".repeat(64),
    )

    private fun encodedJson(bytes: ByteArray): String =
        "partydeck:v1:" + Base64.UrlSafe.withPadding(Base64.PaddingOption.ABSENT).encode(bytes)
}
