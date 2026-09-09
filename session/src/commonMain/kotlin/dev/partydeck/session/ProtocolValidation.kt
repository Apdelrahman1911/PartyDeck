package dev.partydeck.session

import dev.partydeck.core.LastLightRules

internal const val MAX_ID_LENGTH = 64
internal const val MAX_SELECTION_ITEMS = 32

internal fun isCredential(value: String): Boolean =
    value.length == 64 && value.all { it in '0'..'9' || it in 'a'..'f' }

/** Compares the entire fixed-size credential rather than returning on a matching prefix. */
internal fun credentialMatches(expected: String?, supplied: String): Boolean {
    if (expected == null || !isCredential(supplied)) return false
    var difference = 0
    for (index in expected.indices) difference = difference or (expected[index].code xor supplied[index].code)
    return difference == 0
}

internal fun normalizeDisplayName(raw: String): String? {
    if (raw.length > LastLightRules.MAX_DISPLAY_NAME_LENGTH * 4) return null
    val name = raw.trim()
    if (name.isEmpty() || name.length > LastLightRules.MAX_DISPLAY_NAME_LENGTH || !hasValidSurrogates(name)) return null
    if (name.any {
        it.code < 0x20 || it.code in 0x7f..0x9f || it in '\u2028'..'\u202e' ||
            it in '\u2066'..'\u2069' || it == '\u061c' || it == '\u200e' || it == '\u200f'
    }) return null
    // A name made entirely of invisible formatting is not a usable table label.
    if (name.all { it.isWhitespace() || it in '\u200b'..'\u200d' || it == '\u2060' || it == '\ufeff' }) return null
    return name
}

internal fun hasValidSurrogates(value: String): Boolean {
    var index = 0
    while (index < value.length) {
        val char = value[index]
        if (char in '\ud800'..'\udbff') {
            if (index + 1 >= value.length || value[index + 1] !in '\udc00'..'\udfff') return false
            index++
        } else if (char in '\udc00'..'\udfff') return false
        index++
    }
    return true
}

internal fun isBoundedClientMessage(message: ClientMessage): Boolean {
    if (message.sessionId.isEmpty() || message.sessionId.length > MAX_ID_LENGTH) return false
    return when (message) {
        is ClientMessage.Join -> message.admissionSecret.length <= 128 &&
            message.displayName.length <= LastLightRules.MAX_DISPLAY_NAME_LENGTH * 4
        is ClientMessage.Resume -> message.playerId.length in 1..MAX_ID_LENGTH && message.reconnectToken.length <= 128
        is ClientMessage.Command -> when (val intent = message.intent) {
            is ClientIntent.PlayCards -> intent.cardIds.size <= MAX_SELECTION_ITEMS &&
                intent.cardIds.all { it.length in 1..MAX_ID_LENGTH }
            is ClientIntent.KickPlayer -> intent.playerId.length in 1..MAX_ID_LENGTH
            else -> true
        }
    }
}
