package dev.partydeck.transport

/** Four-byte network-order length. Empty records are transport keepalives, never app messages. */
internal object FrameCodec {
    fun encode(payload: ByteArray): ByteArray {
        require(payload.size <= MAX_FRAME_BYTES) { "Message exceeds transport limit" }
        val size = payload.size
        return ByteArray(size + 4).also {
            it[0] = (size ushr 24).toByte()
            it[1] = (size ushr 16).toByte()
            it[2] = (size ushr 8).toByte()
            it[3] = size.toByte()
            payload.copyInto(it, destinationOffset = 4)
        }
    }
}

/** Holds at most one bounded payload. Length is validated before payload allocation. */
internal class FrameDecoder {
    private var headerBytes = 0
    private var length = 0L
    private var body: ByteArray? = null
    private var bodyBytes = 0

    val hasPartialFrame: Boolean get() = headerBytes != 0 || body != null

    fun accept(bytes: ByteArray, onFrame: (ByteArray) -> Boolean): Boolean {
        var index = 0
        while (index < bytes.size) {
            if (body == null) {
                while (headerBytes < 4 && index < bytes.size) {
                    length = (length shl 8) or (bytes[index++].toLong() and 0xff)
                    headerBytes++
                }
                if (headerBytes < 4) return true
                if (length > MAX_FRAME_BYTES) {
                    throw TransportException(TransportFailure(TransportFailureCode.INVALID_FRAME, "Invalid message length"))
                }
                if (length == 0L) {
                    headerBytes = 0
                    if (!onFrame(EMPTY_RECORD)) return false
                    continue
                }
                body = ByteArray(length.toInt())
                bodyBytes = 0
            }

            val currentBody = checkNotNull(body)
            val count = minOf(currentBody.size - bodyBytes, bytes.size - index)
            bytes.copyInto(currentBody, bodyBytes, index, index + count)
            index += count
            bodyBytes += count
            if (bodyBytes == currentBody.size) {
                body = null
                bodyBytes = 0
                headerBytes = 0
                length = 0
                if (!onFrame(currentBody)) return false
            }
        }
        return true
    }

    private companion object {
        val EMPTY_RECORD = ByteArray(0)
    }
}
