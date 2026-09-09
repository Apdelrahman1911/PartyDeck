package dev.partydeck.session

import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertIs
import kotlin.test.assertTrue

class SessionCodecTest {
    @Test
    fun allClientIntentsRoundTripWithStableDiscriminators() {
        val intents = listOf(
            ClientIntent.SetReady(true), ClientIntent.StartGame, ClientIntent.PlayCards(listOf("r1-c4")),
            ClientIntent.Challenge, ClientIntent.AdvanceRound, ClientIntent.ReturnToLobby,
            ClientIntent.KickPlayer("p2"), ClientIntent.Leave, ClientIntent.EndSession,
        )
        for (intent in intents) {
            val message = ClientMessage.Command("room", 14, 23, intent)
            val bytes = SessionCodec.encodeClient(message)
            assertEquals(message, assertIs<WireDecodeResult.Success<ClientMessage>>(SessionCodec.decodeClient(bytes)).value)
            assertTrue(bytes.decodeToString().contains("\"type\":\"command\""))
            assertTrue(bytes.decodeToString().contains("\"protocolVersion\":1"))
        }
        for (message in listOf(
            ClientMessage.Join("room", "a".repeat(64), "Nour 🌙"),
            ClientMessage.Resume("room", "p2", "b".repeat(64)),
        )) {
            assertEquals(message, assertIs<WireDecodeResult.Success<ClientMessage>>(SessionCodec.decodeClient(SessionCodec.encodeClient(message))).value)
        }
    }

    @Test
    fun wireRejectsVersionAmbiguityAndUnsupportedSchema() {
        val valid = SessionCodec.encodeClient(ClientMessage.Command("room", 1, 0, ClientIntent.Challenge)).decodeToString()
        assertEquals(SessionError.UNSUPPORTED_VERSION, decodeError(valid.replace("\"protocolVersion\":1", "\"protocolVersion\":2")))
        assertEquals(SessionError.MALFORMED_MESSAGE, decodeError(valid.replace(",\"protocolVersion\":1", "")))
        assertEquals(SessionError.MALFORMED_MESSAGE, decodeError(valid.replace("\"protocolVersion\":1", "\"protocolVersion\":\"1\"")))
        assertEquals(SessionError.MALFORMED_MESSAGE, decodeError(valid.replace("\"challenge\"", "\"unknown_intent\"")))
        assertEquals(SessionError.MALFORMED_MESSAGE, decodeError(valid.replace("\"commandId\":1", "\"actorId\":\"p0\",\"commandId\":1")))
    }

    @Test
    fun malformedNumbersStringsAndOversizedSelectionsAreRejectedBeforeAuthority() {
        val valid = SessionCodec.encodeClient(ClientMessage.Command("room", 1, 0, ClientIntent.Challenge)).decodeToString()
        for (invalidNumber in listOf("01", "-01", "+1", "1.", "1e", "NaN")) {
            assertEquals(SessionError.MALFORMED_MESSAGE, decodeError(valid.replace("\"commandId\":1", "\"commandId\":$invalidNumber")))
        }
        assertEquals(SessionError.MALFORMED_MESSAGE, decodeError(valid.replace("\"room\"", "\"bad\\xescape\"")))
        assertEquals(SessionError.MALFORMED_MESSAGE, decodeError(valid.replace("\"room\"", "\"\\ud800\"")))
        val tooManyCards = List(33) { "\"card-$it\"" }.joinToString(",")
        val oversized = """{"type":"command","sessionId":"room","commandId":1,"expectedRevision":0,"intent":{"type":"play_cards","cardIds":[$tooManyCards]},"protocolVersion":1}"""
        assertEquals(SessionError.MALFORMED_MESSAGE, decodeError(oversized))
        assertEquals(SessionError.PAYLOAD_TOO_LARGE, assertIs<WireDecodeResult.Failure>(SessionCodec.decodeClient(ByteArray(MAX_WIRE_BYTES + 1))).error)
    }

    private fun decodeError(text: String): SessionError =
        assertIs<WireDecodeResult.Failure>(SessionCodec.decodeClient(text.encodeToByteArray())).error
}
