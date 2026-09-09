package dev.partydeck.session

import dev.partydeck.core.LastLightRules
import kotlinx.serialization.KSerializer
import kotlinx.serialization.builtins.serializer
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.intOrNull

sealed interface WireDecodeResult<out T> {
    data class Success<T>(val value: T) : WireDecodeResult<T>
    data class Failure(val error: SessionError) : WireDecodeResult<Nothing>
}

/** Versioned bounded wire messages. Decode failures never contain input, cards, or credentials. */
object SessionCodec {
    private val json = Json {
        classDiscriminator = "type"
        encodeDefaults = true
        explicitNulls = true
        ignoreUnknownKeys = false
        isLenient = false
        coerceInputValues = false
    }

    fun encodeClient(message: ClientMessage): ByteArray {
        require(isBoundedClientMessage(message)) { "Client message exceeds protocol bounds" }
        return encode(ClientMessage.serializer(), message)
    }

    fun encodeServer(message: ServerMessage): ByteArray {
        require(isBoundedServerMessage(message)) { "Server message exceeds protocol bounds" }
        return encode(ServerMessage.serializer(), message)
    }

    fun decodeClient(bytes: ByteArray): WireDecodeResult<ClientMessage> =
        decode(bytes, ClientMessage.serializer(), ::isBoundedClientMessage)

    fun decodeServer(bytes: ByteArray): WireDecodeResult<ServerMessage> =
        decode(bytes, ServerMessage.serializer(), ::isBoundedServerMessage)

    private fun <T> encode(serializer: KSerializer<T>, value: T): ByteArray {
        val bytes = json.encodeToString(serializer, value).encodeToByteArray()
        require(bytes.size <= MAX_WIRE_BYTES) { "Encoded message exceeds protocol bounds" }
        return bytes
    }

    private fun <T> decode(
        bytes: ByteArray,
        serializer: KSerializer<T>,
        withinBounds: (T) -> Boolean,
    ): WireDecodeResult<T> {
        if (bytes.size > MAX_WIRE_BYTES) return WireDecodeResult.Failure(SessionError.PAYLOAD_TOO_LARGE)
        return try {
            val text = bytes.decodeToString(throwOnInvalidSequence = true)
            JsonPreflight(text) { literal -> json.decodeFromString(String.serializer(), literal) }.validate()
            val objectValue = json.parseToJsonElement(text) as? JsonObject
                ?: return WireDecodeResult.Failure(SessionError.MALFORMED_MESSAGE)
            val version = objectValue["protocolVersion"] as? JsonPrimitive
                ?: return WireDecodeResult.Failure(SessionError.MALFORMED_MESSAGE)
            if (version.isString || version.intOrNull == null) {
                return WireDecodeResult.Failure(SessionError.MALFORMED_MESSAGE)
            }
            if (version.intOrNull != PROTOCOL_VERSION) {
                return WireDecodeResult.Failure(SessionError.UNSUPPORTED_VERSION)
            }
            val decoded = json.decodeFromJsonElement(serializer, objectValue)
            if (withinBounds(decoded)) WireDecodeResult.Success(decoded)
            else WireDecodeResult.Failure(SessionError.MALFORMED_MESSAGE)
        } catch (_: Exception) {
            // Serialization errors can include raw JSON. Return only a fixed, safe protocol reason.
            WireDecodeResult.Failure(SessionError.MALFORMED_MESSAGE)
        }
    }
}

private fun isBoundedServerMessage(message: ServerMessage): Boolean {
    if (message.sessionId.isBlank() || message.sessionId.length > MAX_ID_LENGTH) return false
    return when (message) {
        is ServerMessage.Welcome -> message.playerId == message.view.selfPlayerId &&
            isCredential(message.reconnectToken) && message.nextCommandId > 0 &&
            isBoundedView(message.view, message.sessionId)
        is ServerMessage.Snapshot -> isBoundedView(message.view, message.sessionId)
        is ServerMessage.Receipt -> message.receipt.revision >= 0 &&
            (message.receipt.gameError == null || message.receipt.error == SessionError.ILLEGAL_GAME_ACTION)
        is ServerMessage.AdmissionRejected, is ServerMessage.Ended -> true
    }
}

private fun isBoundedView(view: SessionView, sessionId: String): Boolean {
    if (view.sessionId != sessionId || view.revision < 0 || view.players.size !in 1..LastLightRules.MAX_PLAYERS) return false
    if (view.players.any { !boundedId(it.id) || normalizeDisplayName(it.displayName) != it.displayName }) return false
    val playerIds = view.players.map { it.id }.toSet()
    if (playerIds.size != view.players.size || view.selfPlayerId !in playerIds || view.hostPlayerId !in playerIds) return false
    if (view.pausedPlayerIds.size > LastLightRules.MAX_PLAYERS || view.pausedPlayerIds.any { it !in playerIds }) return false
    val game = view.game ?: return view.phase != SessionPhase.GAME && view.pausedPlayerIds.isEmpty()
    if (view.phase != SessionPhase.GAME || game.viewerId != view.selfPlayerId || game.roundNumber < 1) return false
    if (game.players.size !in LastLightRules.MIN_PLAYERS..LastLightRules.MAX_PLAYERS) return false
    if (game.players.map { it.id }.toSet() != playerIds || game.players.size != playerIds.size) return false
    if (game.players.any {
        normalizeDisplayName(it.displayName) != it.displayName ||
            it.handCount !in 0..LastLightRules.HAND_SIZE || it.penaltyAttempts !in 0..LastLightRules.FUSE_LIGHTS
    }) return false
    if (game.yourHand.size > LastLightRules.HAND_SIZE || game.yourHand.any { !boundedId(it.id) }) return false
    if (game.turnPlayerId != null && game.turnPlayerId !in playerIds) return false
    if (game.winnerId != null && game.winnerId !in playerIds) return false
    game.latestClaim?.let {
        if (it.playerId !in playerIds || it.cardCount !in 1..LastLightRules.MAX_PLAY_CARDS) return false
    }
    game.roundOutcome?.let {
        if (it.roundNumber !in 1..game.roundNumber || it.revealedCards.size !in 1..LastLightRules.MAX_PLAY_CARDS ||
            it.revealedCards.any { card -> !boundedId(card.id) } || it.penaltyAttempt !in 1..LastLightRules.FUSE_LIGHTS ||
            it.claimantId !in playerIds || it.challengerId !in playerIds || it.penalizedPlayerId !in playerIds
        ) return false
    }
    return true
}

private fun boundedId(id: String): Boolean = id.isNotBlank() && id.length <= MAX_ID_LENGTH && hasValidSurrogates(id)

/**
 * Enforces RFC 8259 grammar and resource limits before allocating a JSON tree. Kotlin serialization
 * 1.11 has no stable nesting limit and accepts repeated keys; decoded key equality must be checked
 * before its parser can replace an earlier member. This scanner does not construct application data.
 */
private class JsonPreflight(
    private val source: String,
    private val decodeString: (String) -> String,
) {
    private var offset = 0

    fun validate() {
        value(0)
        whitespace()
        checkWire(offset == source.length)
    }

    private fun value(depth: Int) {
        whitespace()
        checkWire(offset < source.length)
        when (source[offset]) {
            '{' -> objectValue(depth + 1)
            '[' -> arrayValue(depth + 1)
            '"' -> stringValue()
            't' -> literal("true")
            'f' -> literal("false")
            'n' -> literal("null")
            '-', in '0'..'9' -> numberValue()
            else -> malformed()
        }
    }

    private fun objectValue(depth: Int) {
        checkWire(depth <= MAX_DEPTH)
        offset++
        whitespace()
        if (take('}')) return
        val names = mutableSetOf<String>()
        while (true) {
            whitespace()
            checkWire(names.size < MAX_MEMBERS)
            val name = stringValue()
            checkWire(name.length <= MAX_KEY_LENGTH && names.add(name))
            whitespace()
            checkWire(take(':'))
            value(depth)
            whitespace()
            if (take('}')) return
            checkWire(take(','))
        }
    }

    private fun arrayValue(depth: Int) {
        checkWire(depth <= MAX_DEPTH)
        offset++
        whitespace()
        if (take(']')) return
        var count = 0
        while (true) {
            checkWire(count++ < MAX_ARRAY_ITEMS)
            value(depth)
            whitespace()
            if (take(']')) return
            checkWire(take(','))
        }
    }

    private fun stringValue(): String {
        val start = offset
        checkWire(take('"'))
        while (offset < source.length) {
            checkWire(offset - start <= MAX_STRING_SOURCE_LENGTH)
            val character = source[offset++]
            when {
                character == '"' -> {
                    val decoded = decodeString(source.substring(start, offset))
                    checkWire(hasValidSurrogates(decoded))
                    return decoded
                }
                character.code < 0x20 -> malformed()
                character == '\\' -> {
                    checkWire(offset < source.length)
                    when (source[offset++]) {
                        '"', '\\', '/', 'b', 'f', 'n', 'r', 't' -> Unit
                        'u' -> repeat(4) {
                            checkWire(offset < source.length && source[offset] in HEX_DIGITS)
                            offset++
                        }
                        else -> malformed()
                    }
                }
            }
        }
        malformed()
    }

    private fun numberValue() {
        take('-')
        if (!take('0')) {
            checkWire(offset < source.length && source[offset] in '1'..'9')
            digits()
        }
        if (take('.')) {
            checkWire(offset < source.length && source[offset] in '0'..'9')
            digits()
        }
        if (take('e') || take('E')) {
            if (!take('+')) take('-')
            checkWire(offset < source.length && source[offset] in '0'..'9')
            digits()
        }
    }

    private fun digits() {
        while (offset < source.length && source[offset] in '0'..'9') offset++
    }

    private fun literal(expected: String) {
        checkWire(source.startsWith(expected, offset))
        offset += expected.length
    }

    private fun whitespace() {
        while (offset < source.length && source[offset] in JSON_WHITESPACE) offset++
    }

    private fun take(character: Char): Boolean {
        if (offset >= source.length || source[offset] != character) return false
        offset++
        return true
    }

    private fun checkWire(condition: Boolean) {
        if (!condition) malformed()
    }

    private fun malformed(): Nothing = throw IllegalArgumentException("Malformed protocol input")

    private companion object {
        const val MAX_DEPTH = 16
        const val MAX_MEMBERS = 32
        const val MAX_ARRAY_ITEMS = 64
        const val MAX_KEY_LENGTH = 64
        const val MAX_STRING_SOURCE_LENGTH = 1_024
        const val HEX_DIGITS = "0123456789abcdefABCDEF"
        const val JSON_WHITESPACE = " \t\r\n"
    }
}
