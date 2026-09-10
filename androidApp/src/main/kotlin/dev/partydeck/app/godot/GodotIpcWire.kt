package dev.partydeck.app.godot

import android.os.Bundle
import android.os.Message
import android.os.Messenger
import dev.partydeck.games.MAX_ENGINE_PAYLOAD_BYTES
import dev.partydeck.godot.bridge.MAX_RENDERER_EVENT_BYTES

internal const val GODOT_IPC_TIMEOUT_MS = 10_000L
internal const val GODOT_IPC_CLOSE_TIMEOUT_MS = 2_500L
internal const val GODOT_IPC_MAX_COMMAND_BYTES = 256 * 1_024
internal const val GODOT_IPC_MAX_EVENT_BYTES = 64 * 1_024
internal const val GODOT_IPC_MAX_MESSAGES = 16

internal data class GodotIpcIdentity(val presentationId: String, val token: String) {
    fun isValid(): Boolean = presentationId.isNotBlank() && presentationId.length <= 128 &&
        presentationId.none(Char::isISOControl) && token.length == 43 &&
        token.all { it in 'a'..'z' || it in 'A'..'Z' || it in '0'..'9' || it == '-' || it == '_' }
}

internal enum class GodotIpcOperation(val code: Int) {
    HELLO(1), DATA(2), ACK(3), CLOSE(4), NATIVE_CLOSED(5), ABORT(6),
    EXIT_REQUESTED(7), STANDARD_TABLE_REQUESTED(8),
}

internal enum class GodotIpcKind(val code: Int) {
    LAUNCH(1), COMMAND(2), EVENT(3), LIFECYCLE(4),
}

internal data class GodotIpcContent(
    val kind: GodotIpcKind,
    val document: String? = null,
    val acceptReady: Boolean = false,
    val generation: Long = 0,
    val started: Boolean = false,
    val resumed: Boolean = false,
    val focused: Boolean = false,
) {
    val bytes: Int get() = 512 + (document?.encodeToByteArray(throwOnInvalidSequence = true)?.size ?: 0)

    fun valid(): Boolean {
        val limit = when (kind) {
            GodotIpcKind.LAUNCH, GodotIpcKind.COMMAND -> MAX_ENGINE_PAYLOAD_BYTES
            GodotIpcKind.EVENT -> MAX_RENDERER_EVENT_BYTES
            else -> 0
        }
        if (limit > 0) {
            val text = document ?: return false
            if (text.length > limit || text.encodeToByteArray(throwOnInvalidSequence = true).size > limit) return false
        } else if (document != null) return false
        if (generation < 0) return false
        // Android lifecycle callbacks can report focus before/after resume and pause. Keep
        // the actual facts; interactivity is their conjunction at the native/shell owners.
        if (kind == GodotIpcKind.LIFECYCLE && generation == 0L) return false
        return true
    }
}

internal data class GodotIpcHeader(val identity: GodotIpcIdentity, val reply: Messenger)
internal data class GodotIpcPacket(
    val header: GodotIpcHeader,
    val operation: GodotIpcOperation,
    val sequence: Long = 0,
    val content: GodotIpcContent? = null,
    val superseded: Boolean = false,
) {
    val bytes: Int get() = content?.bytes ?: 512
}

/** Only primitive Bundle fields cross this boundary. Documents never appear in exceptions/logs. */
internal object GodotIpcWire {
    private const val VERSION = 1
    private const val ID = "presentation"
    private const val TOKEN = "token"
    private const val SEQUENCE = "sequence"
    private const val SUPERSEDED = "superseded"
    private const val KIND = "kind"
    private const val DOCUMENT = "document"
    private const val READY = "ready"
    private const val GENERATION = "generation"
    private const val STARTED = "started"
    private const val RESUMED = "resumed"
    private const val FOCUSED = "focused"

    fun header(message: Message): GodotIpcHeader? {
        val data = message.peekData() ?: return null
        val identity = GodotIpcIdentity(data.string(ID), data.string(TOKEN))
        if (!identity.isValid()) return null
        return GodotIpcHeader(identity, message.replyTo ?: return null)
    }

    fun decode(message: Message, header: GodotIpcHeader): GodotIpcPacket {
        require(message.arg1 == VERSION && message.arg2 == 0 && message.obj == null && message.callback == null)
        val operation = GodotIpcOperation.entries.singleOrNull { it.code == message.what }
            ?: throw IllegalArgumentException("Invalid IPC operation.")
        val data = requireNotNull(message.peekData())
        val keys = mutableSetOf(ID, TOKEN)
        var sequence = 0L
        var superseded = false
        var content: GodotIpcContent? = null
        if (operation == GodotIpcOperation.DATA || operation == GodotIpcOperation.ACK) {
            keys += SEQUENCE
            sequence = data.long(SEQUENCE)
            require(sequence > 0)
        }
        if (operation == GodotIpcOperation.ACK) {
            keys += SUPERSEDED
            superseded = data.boolean(SUPERSEDED)
        }
        if (operation == GodotIpcOperation.DATA) {
            keys += KIND
            val kind = GodotIpcKind.entries.singleOrNull { it.code == data.int(KIND) }
                ?: throw IllegalArgumentException("Invalid IPC content.")
            content = when (kind) {
                GodotIpcKind.LAUNCH -> {
                    keys += DOCUMENT
                    GodotIpcContent(kind, document = data.string(DOCUMENT))
                }
                GodotIpcKind.COMMAND -> {
                    keys += setOf(DOCUMENT, READY, GENERATION)
                    GodotIpcContent(kind, document = data.string(DOCUMENT), acceptReady = data.boolean(READY),
                        generation = data.long(GENERATION))
                }
                GodotIpcKind.EVENT -> {
                    keys += setOf(DOCUMENT, GENERATION)
                    GodotIpcContent(kind, document = data.string(DOCUMENT), generation = data.long(GENERATION))
                }
                GodotIpcKind.LIFECYCLE -> {
                    keys += setOf(GENERATION, STARTED, RESUMED, FOCUSED)
                    GodotIpcContent(kind, generation = data.long(GENERATION), started = data.boolean(STARTED),
                        resumed = data.boolean(RESUMED), focused = data.boolean(FOCUSED))
                }
            }
            require(content.valid())
        }
        require(data.keySet() == keys)
        return GodotIpcPacket(header, operation, sequence, content, superseded)
    }

    fun message(packet: GodotIpcPacket): Message = Message.obtain().apply {
        what = packet.operation.code
        arg1 = VERSION
        replyTo = packet.header.reply
        data = Bundle().apply {
            putString(ID, packet.header.identity.presentationId)
            putString(TOKEN, packet.header.identity.token)
            if (packet.operation == GodotIpcOperation.DATA || packet.operation == GodotIpcOperation.ACK) {
                putLong(SEQUENCE, packet.sequence)
            }
            if (packet.operation == GodotIpcOperation.ACK) putBoolean(SUPERSEDED, packet.superseded)
            packet.content?.let { content ->
                putInt(KIND, content.kind.code)
                when (content.kind) {
                    GodotIpcKind.LAUNCH -> putString(DOCUMENT, content.document)
                    GodotIpcKind.COMMAND -> {
                        putString(DOCUMENT, content.document)
                        putBoolean(READY, content.acceptReady)
                        putLong(GENERATION, content.generation)
                    }
                    GodotIpcKind.EVENT -> {
                        putString(DOCUMENT, content.document)
                        putLong(GENERATION, content.generation)
                    }
                    GodotIpcKind.LIFECYCLE -> {
                        putLong(GENERATION, content.generation)
                        putBoolean(STARTED, content.started)
                        putBoolean(RESUMED, content.resumed)
                        putBoolean(FOCUSED, content.focused)
                    }
                }
            }
        }
    }

    @Suppress("DEPRECATION")
    private fun Bundle.string(key: String): String = get(key) as? String
        ?: throw IllegalArgumentException("Invalid IPC string.")
    @Suppress("DEPRECATION")
    private fun Bundle.long(key: String): Long = get(key) as? Long
        ?: throw IllegalArgumentException("Invalid IPC counter.")
    @Suppress("DEPRECATION")
    private fun Bundle.int(key: String): Int = get(key) as? Int
        ?: throw IllegalArgumentException("Invalid IPC kind.")
    @Suppress("DEPRECATION")
    private fun Bundle.boolean(key: String): Boolean = get(key) as? Boolean
        ?: throw IllegalArgumentException("Invalid IPC flag.")
}
