package dev.partydeck.godot.compare

import dev.partydeck.godot.bridge.validateBoundedJson
import org.json.JSONArray
import org.json.JSONObject

/**
 * Read-only qualification data, separate from authority messages. Copy only numeric geometry,
 * booleans and fixed enum/counter fields; never persist arbitrary renderer strings or card data.
 */
internal object RendererDiagnostics {
    private val groups = setOf(
        "partydeck_action_reveal", "partydeck_action_hide", "partydeck_action_play",
        "partydeck_action_challenge", "partydeck_action_next_round", "partydeck_action_lobby",
        "partydeck_action_exit", "partydeck_action_lobby_confirm", "partydeck_action_lobby_cancel",
        "partydeck_hand_card",
    )

    fun decode(document: String, presentationId: String, mode: String): JSONObject? = try {
        require(PartyDeckBridgePlugin.withinUtf8Limit(document, PartyDeckBridgePlugin.MAX_DIAGNOSTICS_BYTES))
        // Android JSONObject accepts comments, single quotes and duplicate keys. The shared
        // strict grammar must reject those and excessive nesting before JSONObject sees them.
        validateBoundedJson(document, PartyDeckBridgePlugin.MAX_DIAGNOSTICS_BYTES)
        val value = JSONObject(document)
        value.requireKeys("schemaVersion", "requestId", "sequence", "presentationId", "revision",
            "presentationMode", "coordinateSpace", "foreground", "viewport", "handConcealed",
            "selectedCount", "privateFaceCount", "privateLabelCount", "controls")
        require(value.integer("schemaVersion", 1..1) == 1)
        require(value.get("presentationId") == presentationId)
        require(value.get("presentationMode") == mode)
        val requestId = value.counter("requestId")
        require(value.get("coordinateSpace") == "root_viewport")
        val viewport = value.get("viewport") as? JSONObject ?: error("Invalid viewport")
        viewport.requireKeys("width", "height")
        val records = value.get("controls") as? JSONArray ?: error("Invalid controls")
        require(records.length() <= 32)
        val safeControls = JSONArray()
        repeat(records.length()) { index ->
            val control = records.get(index) as? JSONObject ?: error("Invalid control")
            control.requireKeys("group", "cardIndex", "rect", "clipRect", "visible", "enabled", "selected")
            val group = control.get("group") as? String ?: error("Invalid group")
            require(group in groups)
            safeControls.put(JSONObject()
                .put("group", group)
                .put("cardIndex", control.integer("cardIndex", -1..4))
                .put("rect", control.rectangle("rect"))
                .put("clipRect", control.rectangle("clipRect"))
                .put("visible", control.boolean("visible"))
                .put("enabled", control.boolean("enabled"))
                .put("selected", control.boolean("selected")))
        }
        JSONObject()
            .put("schemaVersion", 1)
            .put("requestId", requestId)
            .put("sequence", value.counter("sequence"))
            .put("presentationId", presentationId)
            .put("revision", value.counter("revision"))
            .put("presentationMode", mode)
            .put("coordinateSpace", "root_viewport")
            .put("foreground", value.boolean("foreground"))
            .put("viewport", JSONObject()
                .put("width", viewport.dimension("width"))
                .put("height", viewport.dimension("height")))
            .put("handConcealed", value.boolean("handConcealed"))
            .put("selectedCount", value.integer("selectedCount", 0..3))
            .put("privateFaceCount", value.integer("privateFaceCount", 0..30))
            .put("privateLabelCount", value.integer("privateLabelCount", 0..60))
            .put("controls", safeControls)
    } catch (_: Exception) { null }

    private fun JSONObject.requireKeys(vararg allowed: String) {
        require(keys().asSequence().toSet() == allowed.toSet())
    }

    private fun JSONObject.counter(name: String): String {
        val value = get(name) as? String ?: error("Invalid counter")
        require(value.matches(Regex("0|[1-9][0-9]{0,18}")))
        require(value.toLongOrNull() != null)
        return value
    }

    private fun JSONObject.boolean(name: String) = get(name) as? Boolean ?: error("Invalid boolean")

    private fun JSONObject.integer(name: String, range: IntRange): Int {
        val value = (get(name) as? Number)?.toDouble() ?: error("Invalid number")
        require(value.isFinite() && value == value.toInt().toDouble() && value.toInt() in range)
        return value.toInt()
    }

    private fun JSONObject.dimension(name: String): Double {
        val value = (get(name) as? Number)?.toDouble() ?: error("Invalid dimension")
        require(value.isFinite() && value in 1.0..32_768.0)
        return value
    }

    private fun JSONObject.rectangle(name: String): JSONArray {
        val rect = get(name) as? JSONArray ?: error("Invalid rectangle")
        require(rect.length() == 4)
        val safe = JSONArray()
        repeat(4) { coordinate ->
            val numeric = (rect.get(coordinate) as? Number)?.toDouble() ?: error("Invalid coordinate")
            require(numeric.isFinite() && numeric in -32_768.0..32_768.0)
            require(coordinate < 2 || numeric >= 0)
            safe.put(numeric)
        }
        return safe
    }

}
