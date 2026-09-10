package dev.partydeck.godot.bridge

import dev.partydeck.games.MAX_ENGINE_PAYLOAD_BYTES

/** A schema error contains a bounded explanation, never the rejected private document. */
class BridgeFormatException(message: String) : IllegalArgumentException(message)

/**
 * Strict JSON preflight for platform messages before a platform JSON parser runs.
 * This checks syntax and resource bounds; callers must still validate their message schema.
 */
fun validateBoundedJson(document: String, maxBytes: Int) {
    require(maxBytes in 1..MAX_ENGINE_PAYLOAD_BYTES) { "Invalid JSON byte limit." }
    StrictJson.validate(document, maxBytes)
}

internal fun wireRequire(condition: Boolean, message: String) {
    if (!condition) throw BridgeFormatException(message)
}

/**
 * Preflight before the JSON library can overwrite duplicate keys or accept a loose token.
 * Storage, token count, and recursion are bounded independently of the eventual schema.
 */
internal object StrictJson {
    fun validate(document: String, byteLimit: Int) {
        wireRequire(document.length <= byteLimit, "Document exceeds the size limit.")
        validUnicode(document)
        wireRequire(document.encodeToByteArray().size <= byteLimit, "Document exceeds the UTF-8 size limit.")
        Reader(document).read()
    }

    private class Reader(private val text: String) {
        private var position = 0
        private var tokens = 0

        fun read() {
            value(0)
            whitespace()
            wireRequire(position == text.length, "Unexpected data after JSON document.")
        }

        private fun value(depth: Int) {
            wireRequire(depth <= 16 && ++tokens <= 4_096, "JSON structure exceeds its limit.")
            whitespace()
            when (peek()) {
                '{' -> objectValue(depth)
                '[' -> arrayValue(depth)
                '"' -> string()
                't' -> literal("true")
                'f' -> literal("false")
                'n' -> literal("null")
                '-', in '0'..'9' -> number()
                else -> throw BridgeFormatException("Invalid JSON value.")
            }
        }

        private fun objectValue(depth: Int) {
            position++
            whitespace()
            if (take('}')) return
            val keys = mutableSetOf<String>()
            while (true) {
                whitespace()
                wireRequire(peek() == '"', "JSON object keys must be strings.")
                wireRequire(keys.add(string()), "Duplicate JSON object key.")
                whitespace()
                wireRequire(take(':'), "Missing JSON key separator.")
                value(depth + 1)
                whitespace()
                if (take('}')) return
                wireRequire(take(','), "Missing JSON object separator.")
            }
        }

        private fun arrayValue(depth: Int) {
            position++
            whitespace()
            if (take(']')) return
            while (true) {
                value(depth + 1)
                whitespace()
                if (take(']')) return
                wireRequire(take(','), "Missing JSON array separator.")
            }
        }

        private fun string(): String {
            wireRequire(take('"'), "Expected JSON string.")
            val decoded = StringBuilder()
            while (position < text.length) {
                when (val char = text[position++]) {
                    '"' -> return decoded.toString().also(::validUnicode)
                    '\\' -> {
                        wireRequire(position < text.length, "Truncated JSON escape.")
                        decoded.append(when (text[position++]) {
                            '"' -> '"'
                            '\\' -> '\\'
                            '/' -> '/'
                            'b' -> '\b'
                            'f' -> '\u000c'
                            'n' -> '\n'
                            'r' -> '\r'
                            't' -> '\t'
                            'u' -> unicodeEscape()
                            else -> throw BridgeFormatException("Invalid JSON escape.")
                        })
                    }
                    else -> {
                        wireRequire(char.code >= 0x20, "Unescaped control character in JSON string.")
                        decoded.append(char)
                    }
                }
            }
            throw BridgeFormatException("Unterminated JSON string.")
        }

        private fun unicodeEscape(): Char {
            wireRequire(position + 4 <= text.length, "Truncated Unicode escape.")
            var code = 0
            repeat(4) {
                val digit = when (val char = text[position++]) {
                    in '0'..'9' -> char.code - '0'.code
                    in 'a'..'f' -> char.code - 'a'.code + 10
                    in 'A'..'F' -> char.code - 'A'.code + 10
                    else -> throw BridgeFormatException("Invalid Unicode escape.")
                }
                code = code * 16 + digit
            }
            return code.toChar()
        }

        private fun number() {
            take('-')
            if (!take('0')) {
                wireRequire(peek() in '1'..'9', "Invalid JSON number.")
                digits()
            }
            if (take('.')) {
                wireRequire(peek() in '0'..'9', "Invalid JSON fraction.")
                digits()
            }
            if (take('e') || take('E')) {
                if (!take('+')) take('-')
                wireRequire(peek() in '0'..'9', "Invalid JSON exponent.")
                digits()
            }
        }

        private fun digits() {
            while (peek() in '0'..'9') position++
        }

        private fun literal(value: String) {
            wireRequire(text.startsWith(value, position), "Invalid JSON literal.")
            position += value.length
        }

        private fun whitespace() {
            while (peek() == ' ' || peek() == '\t' || peek() == '\r' || peek() == '\n') position++
        }

        private fun take(char: Char): Boolean = if (peek() == char) {
            position++
            true
        } else false

        private fun peek(): Char = text.getOrNull(position) ?: '\u0000'
    }
}

internal fun validUnicode(value: String) {
    var index = 0
    while (index < value.length) {
        val char = value[index++]
        when (char) {
            in '\uD800'..'\uDBFF' -> {
                wireRequire(index < value.length && value[index] in '\uDC00'..'\uDFFF', "Unpaired Unicode surrogate.")
                index++
            }
            in '\uDC00'..'\uDFFF' -> throw BridgeFormatException("Unpaired Unicode surrogate.")
        }
    }
}
