package dev.partydeck.godot.bridge

import dev.partydeck.core.GameView
import dev.partydeck.core.LastLightRules
import dev.partydeck.games.ENGINE_BRIDGE_PROTOCOL_VERSION
import dev.partydeck.games.EngineCommand
import dev.partydeck.games.EngineEvent
import dev.partydeck.games.EngineEventBody
import dev.partydeck.games.EngineFailure
import dev.partydeck.games.EngineLaunch
import dev.partydeck.games.EnginePayload
import dev.partydeck.games.MAX_ENGINE_PAYLOAD_BYTES
import kotlinx.serialization.Serializable
import kotlinx.serialization.SerializationException
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonElement
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.encodeToJsonElement
import kotlinx.serialization.json.put

const val LAST_LIGHT_VIEW_SCHEMA = "last-light-view-v1"
const val LAST_LIGHT_INTENT_SCHEMA = "last-light-intent-v1"
const val MAX_RENDERER_EVENT_BYTES = 4_096

enum class PresentationMode(val wireName: String) { TWO_D("2d"), THREE_D("3d") }

data class PresentationPreferences(
    val reduceMotion: Boolean = false,
    val soundEnabled: Boolean = true,
    val textScale: Double = 1.0,
) {
    init { require(textScale.isFinite() && textScale in 1.0..2.0) }
}

/** Supplied by the native/session owner, never by renderer JSON. */
@Serializable
data class PresentationControls(
    val isHost: Boolean,
    val canSendAction: Boolean,
    val canAdvanceRound: Boolean,
    val canReturnToLobby: Boolean,
)

@Serializable
data class PresentationSnapshot(val game: GameView, val controls: PresentationControls)

sealed interface RendererIntent {
    data class Play(val cardIds: List<String>) : RendererIntent
    data object Challenge : RendererIntent
    data object AdvanceRound : RendererIntent
    data object ReturnToLobby : RendererIntent
}

/** No authority-state overload exists. The only view input is the existing safe GameView. */
object LastLightWireCodec {
    private val json = Json {
        encodeDefaults = true
        explicitNulls = true
        ignoreUnknownKeys = false
        isLenient = false
        coerceInputValues = false
    }

    fun viewPayload(view: GameView, controls: PresentationControls): EnginePayload {
        validateSnapshot(PresentationSnapshot(view, controls))
        val document = bounded(json.encodeToJsonElement(PresentationSnapshot(view, controls)))
        return EnginePayload(LAST_LIGHT_VIEW_SCHEMA, document)
    }

    fun decodeViewPayload(payload: EnginePayload): PresentationSnapshot {
        wireRequire(payload.schemaId == LAST_LIGHT_VIEW_SCHEMA, "Unsupported view schema.")
        requireViewShape(parseObject(payload.document, MAX_ENGINE_PAYLOAD_BYTES))
        val snapshot = try {
            json.decodeFromString<PresentationSnapshot>(payload.document)
        } catch (_: SerializationException) {
            throw BridgeFormatException("Invalid recipient-view schema.")
        } catch (_: IllegalArgumentException) {
            throw BridgeFormatException("Invalid recipient-view value.")
        }
        validateSnapshot(snapshot)
        return snapshot
    }

    fun intentPayload(intent: RendererIntent): EnginePayload {
        val element = when (intent) {
            is RendererIntent.Play -> {
                validateSelection(intent.cardIds)
                buildJsonObject {
                    put("type", "play")
                    put("cardIds", JsonArray(intent.cardIds.map(::JsonPrimitive)))
                }
            }
            RendererIntent.Challenge -> buildJsonObject { put("type", "challenge") }
            RendererIntent.AdvanceRound -> buildJsonObject { put("type", "advance_round") }
            RendererIntent.ReturnToLobby -> buildJsonObject { put("type", "return_to_lobby") }
        }
        return EnginePayload(LAST_LIGHT_INTENT_SCHEMA, bounded(element, MAX_RENDERER_EVENT_BYTES))
    }

    fun decodeIntentPayload(payload: EnginePayload): RendererIntent {
        wireRequire(payload.schemaId == LAST_LIGHT_INTENT_SCHEMA, "Unsupported intent schema.")
        val value = parseObject(payload.document, MAX_RENDERER_EVENT_BYTES)
        return when (value.string("type")) {
            "play" -> {
                value.exactKeys("type", "cardIds")
                val cards = value["cardIds"] as? JsonArray
                    ?: throw BridgeFormatException("Card selection must be an array.")
                val ids = cards.map { it.stringValue() }
                validateSelection(ids)
                RendererIntent.Play(ids)
            }
            "challenge" -> { value.exactKeys("type"); RendererIntent.Challenge }
            "advance_round" -> { value.exactKeys("type"); RendererIntent.AdvanceRound }
            "return_to_lobby" -> { value.exactKeys("type"); RendererIntent.ReturnToLobby }
            else -> throw BridgeFormatException("Unknown renderer intent.")
        }
    }

    fun encodeLaunch(
        launch: EngineLaunch,
        mode: PresentationMode,
        preferences: PresentationPreferences = PresentationPreferences(),
    ): String {
        wireRequire(launch.gameId.value == "last-light", "Unsupported game.")
        decodeViewPayload(launch.initialView)
        return bounded(buildJsonObject {
            common(launch.presentationId, "launch", launch.protocolVersion)
            put("gameId", launch.gameId.value)
            put("presentationMode", mode.wireName)
            put("revision", counter(launch.initialRevision))
            put("schemaId", launch.initialView.schemaId)
            put("payload", json.parseToJsonElement(launch.initialView.document))
            put("preferences", buildJsonObject {
                put("reduceMotion", preferences.reduceMotion)
                put("soundEnabled", preferences.soundEnabled)
                put("textScale", preferences.textScale)
            })
        })
    }

    fun encodeCommand(presentationId: String, command: EngineCommand): String = bounded(buildJsonObject {
        when (command) {
            is EngineCommand.ShowView -> {
                decodeViewPayload(command.payload)
                common(presentationId, "view")
                put("revision", counter(command.revision))
                put("schemaId", command.payload.schemaId)
                put("payload", json.parseToJsonElement(command.payload.document))
            }
            is EngineCommand.SetForeground -> {
                common(presentationId, "foreground")
                put("isForeground", command.isForeground)
            }
        }
    })

    fun encodeClose(presentationId: String): String = bounded(buildJsonObject { common(presentationId, "close") })

    fun decodeEvent(document: String): EngineEvent {
        val value = parseObject(document, MAX_RENDERER_EVENT_BYTES)
        val presentationId = value.string("presentationId").also(::validatePresentationId)
        val versionText = (value["protocolVersion"] as? JsonPrimitive)?.takeUnless { it.isString }?.content
        wireRequire(versionText != null && versionText.matches(Regex("[1-9][0-9]{0,9}")), "Invalid protocol number.")
        val version = versionText!!.toIntOrNull() ?: throw BridgeFormatException("Protocol number overflow.")
        val sequence = parseCounter(value.string("sequence"))
        val commonKeys = arrayOf("protocolVersion", "presentationId", "sequence", "type")
        val body = when (value.string("type")) {
            "ready" -> { value.exactKeys(*commonKeys); EngineEventBody.Ready }
            "intent" -> {
                value.exactKeys(*commonKeys, "expectedRevision", "schemaId", "payload")
                val payload = EnginePayload(value.string("schemaId"), bounded(value.required("payload"), MAX_RENDERER_EVENT_BYTES))
                decodeIntentPayload(payload)
                EngineEventBody.PlayerIntent(parseCounter(value.string("expectedRevision")), payload)
            }
            "exit" -> { value.exactKeys(*commonKeys); EngineEventBody.ExitRequested }
            "failed" -> {
                value.exactKeys(*commonKeys, "reason")
                val reason = EngineFailure.entries.firstOrNull { it.name == value.string("reason") }
                    ?: throw BridgeFormatException("Unknown renderer failure.")
                EngineEventBody.Failed(reason)
            }
            else -> throw BridgeFormatException("Unknown renderer event.")
        }
        return EngineEvent(presentationId, version, sequence, body)
    }

    fun encodeEvent(event: EngineEvent): String = bounded(buildJsonObject {
        val type = when (event.body) {
            EngineEventBody.Ready -> "ready"
            is EngineEventBody.PlayerIntent -> "intent"
            EngineEventBody.ExitRequested -> "exit"
            is EngineEventBody.Failed -> "failed"
        }
        common(event.presentationId, type, event.protocolVersion)
        put("sequence", counter(event.sequence))
        when (val body = event.body) {
            is EngineEventBody.PlayerIntent -> {
                decodeIntentPayload(body.payload)
                put("expectedRevision", counter(body.expectedRevision))
                put("schemaId", body.payload.schemaId)
                put("payload", json.parseToJsonElement(body.payload.document))
            }
            is EngineEventBody.Failed -> put("reason", body.reason.name)
            else -> Unit
        }
    }, MAX_RENDERER_EVENT_BYTES)

    private fun kotlinx.serialization.json.JsonObjectBuilder.common(
        presentationId: String,
        type: String,
        protocolVersion: Int = ENGINE_BRIDGE_PROTOCOL_VERSION,
    ) {
        validatePresentationId(presentationId)
        put("protocolVersion", protocolVersion)
        put("presentationId", presentationId)
        put("type", type)
    }

    private fun parseObject(document: String, limit: Int): JsonObject {
        StrictJson.validate(document, limit)
        val element = try { json.parseToJsonElement(document) } catch (_: SerializationException) {
            throw BridgeFormatException("Invalid JSON document.")
        }
        return element as? JsonObject ?: throw BridgeFormatException("Document must be a JSON object.")
    }

    private fun bounded(element: JsonElement, limit: Int = MAX_ENGINE_PAYLOAD_BYTES): String =
        element.toString().also { StrictJson.validate(it, limit) }
}

internal fun validatePresentationId(value: String) = validateText(value, 128, "presentation identifier")

internal fun validateText(value: String, limit: Int, description: String) {
    wireRequire(value.isNotBlank() && value.length <= limit && value.none { it.code < 32 || it.code == 127 }, "Invalid $description.")
    validUnicode(value)
}

internal fun validateSelection(ids: List<String>) {
    wireRequire(ids.size in 1..LastLightRules.MAX_PLAY_CARDS && ids.distinct().size == ids.size, "Invalid card selection count.")
    ids.forEach { validateText(it, 64, "card identifier") }
}

private fun counter(value: Long): String {
    wireRequire(value >= 0, "Counter cannot be negative.")
    return value.toString()
}

private fun parseCounter(value: String): Long {
    wireRequire(value.length <= 19 && value.matches(Regex("0|[1-9][0-9]*")), "Counter must be a canonical decimal string.")
    return value.toLongOrNull() ?: throw BridgeFormatException("Counter overflow.")
}

private fun JsonObject.exactKeys(vararg names: String) {
    wireRequire(keys == names.toSet(), "Unexpected or missing document fields.")
}

private fun JsonObject.required(name: String): JsonElement = this[name] ?: throw BridgeFormatException("Missing document field.")
private fun JsonObject.string(name: String): String = required(name).stringValue()
private fun JsonElement.stringValue(): String =
    (this as? JsonPrimitive)?.takeIf { it.isString }?.content ?: throw BridgeFormatException("Expected a string field.")
