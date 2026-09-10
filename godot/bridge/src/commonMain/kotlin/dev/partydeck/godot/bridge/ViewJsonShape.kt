package dev.partydeck.godot.bridge

import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonElement
import kotlinx.serialization.json.JsonNull
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive

/** Core DTO defaults and JSON primitive coercions are not part of this strict wire schema. */
internal fun requireViewShape(root: JsonObject) {
    root.fields("game", "controls")
    root.obj("controls").apply {
        fields("isHost", "canSendAction", "canAdvanceRound", "canReturnToLobby")
        keys.forEach { boolean(it) }
    }
    root.obj("game").apply {
        fields("viewerId", "phase", "roundNumber", "tableRank", "players", "yourHand", "turnPlayerId", "latestClaim", "forcedChallenge", "availableActions", "roundOutcome", "winnerId")
        nullableString("viewerId")
        string("phase")
        integer("roundNumber")
        string("tableRank")
        array("players").forEach { element ->
            element.obj().apply {
                fields("id", "displayName", "handCount", "penaltyAttempts", "eliminated")
                string("id"); string("displayName")
                integer("handCount"); integer("penaltyAttempts"); boolean("eliminated")
            }
        }
        cards(array("yourHand"))
        nullableString("turnPlayerId")
        nullableObject("latestClaim")?.apply {
            fields("playerId", "cardCount")
            string("playerId"); integer("cardCount")
        }
        boolean("forcedChallenge")
        obj("availableActions").apply {
            fields("canPlay", "canChallenge", "maxPlayableCards")
            boolean("canPlay"); boolean("canChallenge"); integer("maxPlayableCards")
        }
        nullableObject("roundOutcome")?.apply {
            fields("roundNumber", "tableRank", "claimantId", "challengerId", "revealedCards", "truthful", "penalizedPlayerId", "penaltyAttempt", "burnedOut")
            integer("roundNumber"); string("tableRank"); string("claimantId"); string("challengerId")
            cards(array("revealedCards"))
            boolean("truthful"); string("penalizedPlayerId"); integer("penaltyAttempt"); boolean("burnedOut")
        }
        nullableString("winnerId")
    }
}

private fun cards(array: JsonArray) = array.forEach {
    it.obj().apply { fields("id", "rank"); string("id"); string("rank") }
}

private fun JsonObject.fields(vararg expected: String) = wireRequire(keys == expected.toSet(), "Unexpected or missing view fields.")
private fun JsonElement.obj(): JsonObject = this as? JsonObject ?: throw BridgeFormatException("Expected view object.")
private fun JsonObject.obj(key: String) = getValue(key).obj()
private fun JsonObject.array(key: String) = getValue(key) as? JsonArray ?: throw BridgeFormatException("Expected view array.")
private fun JsonObject.string(key: String) = wireRequire((getValue(key) as? JsonPrimitive)?.isString == true, "Expected view string.")
private fun JsonObject.nullableString(key: String) { if (getValue(key) != JsonNull) string(key) }
private fun JsonObject.nullableObject(key: String): JsonObject? = if (getValue(key) == JsonNull) null else obj(key)
private fun JsonObject.boolean(key: String) {
    val value = getValue(key) as? JsonPrimitive
    wireRequire(value != null && !value.isString && value.content in setOf("true", "false"), "Expected view boolean.")
}
private fun JsonObject.integer(key: String) {
    val value = getValue(key) as? JsonPrimitive
    wireRequire(value != null && !value.isString && value.content.matches(Regex("-?(0|[1-9][0-9]*)")) && value.content.toIntOrNull() != null, "Expected exact view integer.")
}
