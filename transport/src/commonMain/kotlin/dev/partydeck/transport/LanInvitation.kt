package dev.partydeck.transport

import kotlinx.serialization.Serializable
import kotlinx.serialization.SerializationException
import kotlinx.serialization.json.Json
import kotlin.io.encoding.Base64

/**
 * A deliberate out-of-band invitation. It is a bearer admission credential and must not be logged.
 * Its certificate pin authenticates the host; discovery cannot replace that pin.
 */
@Serializable
data class LanInvitation(
    val sessionId: String,
    val admissionSecret: String,
    val endpoint: LanEndpoint,
    val certificateSha256: String,
    val version: Int = 1,
) {
    init {
        require(version == 1) { "Unsupported invitation version" }
        require(sessionId.length in 1..128 && sessionId.all { it.isLetterOrDigit() || it == '-' || it == '_' }) {
            "Invalid session identifier"
        }
        require(isSha256Hex(admissionSecret)) { "Invalid invitation credential" }
        require(isSha256Hex(certificateSha256)) { "Invalid host certificate fingerprint" }
    }

    fun encode(): String = PREFIX + encoding.encode(json.encodeToString(serializer(), this).encodeToByteArray())

    /** Redact the admission credential even when a model is accidentally interpolated into a log. */
    override fun toString(): String = "LanInvitation(version=$version, credential=<redacted>)"

    companion object {
        private const val PREFIX = "partydeck:v1:"
        private const val MAX_INVITATION_CHARACTERS = 2_048
        private val encoding = Base64.UrlSafe.withPadding(Base64.PaddingOption.ABSENT)
        private val json = Json {
            encodeDefaults = true
            ignoreUnknownKeys = false
            isLenient = false
            coerceInputValues = false
        }

        /** Throws [IllegalArgumentException] for malformed, oversized or incompatible invitations. */
        fun decode(value: String): LanInvitation {
            require(value.length <= MAX_INVITATION_CHARACTERS) { "Invitation is too long" }
            val text = value.trim()
            require(text.startsWith(PREFIX)) { "This is not a PartyDeck invitation" }
            val encoded = text.removePrefix(PREFIX)
            require(encoded.isNotEmpty() && encoded.all { it.isLetterOrDigit() || it == '-' || it == '_' }) {
                "Invalid invitation encoding"
            }
            try {
                val bytes = encoding.decode(encoded)
                require(encoding.encode(bytes) == encoded) { "Invalid invitation encoding" }
                val decodedText = bytes.decodeToString(throwOnInvalidSequence = true)
                val invitation = json.decodeFromString(serializer(), decodedText)
                // Version 1 invitations are produced by this canonical encoder. Requiring the
                // exact representation rejects duplicate fields, escaped key aliases, omitted
                // version markers and parser-dependent alternative interpretations.
                require(json.encodeToString(serializer(), invitation) == decodedText) {
                    "Invalid invitation representation"
                }
                return invitation
            } catch (_: SerializationException) {
                throw IllegalArgumentException("Invalid PartyDeck invitation")
            } catch (_: CharacterCodingException) {
                throw IllegalArgumentException("Invalid PartyDeck invitation")
            }
        }
    }
}

internal fun isSha256Hex(value: String): Boolean =
    value.length == 64 && value.all { it in '0'..'9' || it in 'a'..'f' }
