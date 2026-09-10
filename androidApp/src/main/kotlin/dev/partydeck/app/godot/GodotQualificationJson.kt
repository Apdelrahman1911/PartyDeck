package dev.partydeck.app.godot

import dev.partydeck.godot.bridge.validateBoundedJson
import org.json.JSONArray
import org.json.JSONException
import org.json.JSONObject

/** Android parsing stays separate from pure schema/currentness checks and host unit tests. */
internal object GodotQualificationJson {
    private const val MAX_INPUT_BYTES = 16_384
    private const val MAX_OUTPUT_BYTES = 8_192

    fun decode(document: String): Map<*, *>? = try {
        // JSONObject alone accepts duplicate keys, comments and loose quoting.
        validateBoundedJson(document, MAX_INPUT_BYTES)
        objectValue(JSONObject(document))
    } catch (_: IllegalArgumentException) { null }
      catch (_: JSONException) { null }

    fun encode(snapshot: QualificationSnapshot): String? {
        val scene = snapshot.scene
        val controls = JSONArray()
        for (control in scene.controls) controls.put(JSONObject()
            .put("role", control.role.wireName).put("slot", control.slot)
            .put("rect", array(control.rect)).put("clip", array(control.clip))
            .put("visible", control.visible).put("enabled", control.enabled).put("selected", control.selected))
        // Reconstruct every field; neither the parsed object nor a renderer string is published.
        val document = JSONObject().put("schemaVersion", 1).put("mode", snapshot.mode)
            .put("request", scene.request.toString()).put("sequence", scene.sequence.toString())
            .put("generation", snapshot.generation.toString()).put("command", snapshot.command.toString())
            .put("input", snapshot.input.toString()).put("projectionRevision", scene.projectionRevision.toString())
            .put("requestedUptimeMs", snapshot.requestedUptimeMs).put("capturedUptimeMs", snapshot.capturedUptimeMs)
            .put("expiresUptimeMs", snapshot.expiresUptimeMs).put("surface", array(snapshot.surface))
            .put("viewport", array(scene.viewport)).put("sceneStateApplied", true)
            .put("handConcealed", scene.handConcealed).put("selectedCount", scene.selectedCount)
            .put("privateFaceCount", scene.privateFaceCount).put("privateLabelCount", scene.privateLabelCount)
            .put("controls", controls).toString()
        return document.takeIf { it.length <= MAX_OUTPUT_BYTES && it.encodeToByteArray().size <= MAX_OUTPUT_BYTES }
    }

    private fun objectValue(value: JSONObject): Map<String, Any?> = value.keys().asSequence().associateWith {
        primitive(value.get(it))
    }

    private fun primitive(value: Any?): Any? = when (value) {
        is JSONObject -> objectValue(value)
        is JSONArray -> (0 until value.length()).map { primitive(value.get(it)) }
        JSONObject.NULL -> null
        else -> value
    }

    private fun array(values: List<Number>): JSONArray = JSONArray().also { result -> values.forEach { result.put(it) } }
}
