package dev.partydeck.app.godot

import kotlin.math.abs

/** Native-only identity and geometry. The view token and privacy epoch are never published. */
internal data class QualificationSurface(
    val viewToken: Any,
    val x: Int,
    val y: Int,
    val width: Int,
    val height: Int,
    val density: Double,
    val privacyGeneration: Long,
) {
    fun isValid(): Boolean = x in 0..32_768 && y in 0..32_768 && width in 1..32_768 &&
        height in 1..32_768 && x.toLong() + width <= 32_768 && y.toLong() + height <= 32_768 &&
        density.isFinite() && density in 0.5..8.0 && privacyGeneration >= 0

    fun matchesViewport(viewport: List<Double>): Boolean =
        abs(viewport[0] * density - width) <= 1.0 && abs(viewport[1] * density - height) <= 1.0
}

internal enum class QualificationRole(val wireName: String) {
    REVEAL("reveal"), HIDE("hide"), SELECT("select"), PLAY("play"),
}

internal data class QualificationControl(
    val role: QualificationRole,
    val slot: Int,
    val rect: List<Double>,
    val clip: List<Double>,
    val visible: Boolean,
    val enabled: Boolean,
    val selected: Boolean,
)

/** Identity was compared inside the decoder; no arbitrary renderer string survives decoding. */
internal data class QualificationScene(
    val request: Long,
    val sequence: Long,
    val projectionRevision: Long,
    val viewport: List<Double>,
    val handConcealed: Boolean,
    val selectedCount: Int,
    val privateFaceCount: Int,
    val privateLabelCount: Int,
    val controls: List<QualificationControl>,
)

internal data class QualificationSnapshot(
    val mode: String,
    val scene: QualificationScene,
    val generation: Long,
    val command: Long,
    val input: Long,
    val requestedUptimeMs: Long,
    val capturedUptimeMs: Long,
    val expiresUptimeMs: Long,
    val surface: List<Int>,
)

/** Pure schema checks after the shared strict JSON grammar and byte preflight. */
internal object GodotQualificationSchema {
    private val groups = setOf(
        "partydeck_action_reveal", "partydeck_action_hide", "partydeck_action_play",
        "partydeck_action_challenge", "partydeck_action_next_round", "partydeck_action_lobby",
        "partydeck_action_exit", "partydeck_action_lobby_confirm", "partydeck_action_lobby_cancel",
        "partydeck_hand_card",
    )

    fun counter(value: Any?): Long? = (value as? String)?.takeIf {
        it.matches(Regex("0|[1-9][0-9]{0,18}"))
    }?.toLongOrNull()

    fun decode(value: Map<*, *>, presentationId: String, mode: String): QualificationScene? = try {
        require(mode == "2d" || mode == "3d")
        value.exactKeys("schemaVersion", "requestId", "sequence", "presentationId", "revision",
            "presentationMode", "coordinateSpace", "foreground", "sceneStateApplied", "viewport",
            "handConcealed", "selectedCount", "privateFaceCount", "privateLabelCount", "controls")
        require(integer(value["schemaVersion"], 1..1) == 1)
        require(value["presentationId"] == presentationId && value["presentationMode"] == mode)
        require(value["coordinateSpace"] == "root_viewport")
        require(value["foreground"] == true && value["sceneStateApplied"] == true)
        val viewportValue = requireNotNull(value["viewport"] as? Map<*, *>)
        viewportValue.exactKeys("width", "height")
        val viewport = listOf(dimension(viewportValue["width"]), dimension(viewportValue["height"]))
        val records = requireNotNull(value["controls"] as? List<*>)
        require(records.size <= 32)
        val identities = mutableSetOf<Pair<String, Int>>()
        val controls = mutableListOf<QualificationControl>()
        var selectedCards = 0
        for (record in records) {
            val control = requireNotNull(record as? Map<*, *>)
            control.exactKeys("group", "cardIndex", "rect", "clipRect", "visible", "enabled", "selected")
            val group = requireNotNull(control["group"] as? String)
            require(group in groups)
            val slot = integer(control["cardIndex"], -1..4)
            require(if (group == "partydeck_hand_card") slot >= 0 else slot == -1)
            require(identities.add(group to slot))
            val rect = rectangle(control["rect"])
            val clip = rectangle(control["clipRect"])
            require(clip[0] >= 0 && clip[1] >= 0 && clip[0] + clip[2] <= viewport[0] + 0.001 &&
                clip[1] + clip[3] <= viewport[1] + 0.001)
            val visible = requireNotNull(control["visible"] as? Boolean)
            val enabled = requireNotNull(control["enabled"] as? Boolean)
            val selected = requireNotNull(control["selected"] as? Boolean)
            require(!selected || group == "partydeck_hand_card")
            if (selected) selectedCards++
            require(!visible || (rect[2] > 0 && rect[3] > 0 && clip[2] > 0 && clip[3] > 0 &&
                rect[0] < clip[0] + clip[2] && rect[0] + rect[2] > clip[0] &&
                rect[1] < clip[1] + clip[3] && rect[1] + rect[3] > clip[1]))
            val role = when (group) {
                "partydeck_action_reveal" -> QualificationRole.REVEAL
                "partydeck_action_hide" -> QualificationRole.HIDE
                "partydeck_hand_card" -> QualificationRole.SELECT
                "partydeck_action_play" -> QualificationRole.PLAY
                else -> null
            }
            // Every raw control was checked, including roles that are not published.
            if (role != null) controls += QualificationControl(role, slot, rect, clip, visible, enabled, selected)
        }
        require(controls.size <= 8)
        val concealed = requireNotNull(value["handConcealed"] as? Boolean)
        val selected = integer(value["selectedCount"], 0..3)
        val faces = integer(value["privateFaceCount"], 0..30)
        val labels = integer(value["privateLabelCount"], 0..60)
        require(selected == selectedCards)
        require(!concealed || (selected == 0 && faces == 0 && labels == 0))
        QualificationScene(
            requireNotNull(counter(value["requestId"])), requireNotNull(counter(value["sequence"])),
            requireNotNull(counter(value["revision"])), viewport, concealed, selected, faces, labels,
            controls.sortedWith(compareBy({ it.role.ordinal }, { it.slot })),
        )
    } catch (_: IllegalArgumentException) { null }

    private fun Map<*, *>.exactKeys(vararg keys: String) { require(this.keys == keys.toSet()) }

    private fun integer(value: Any?, range: IntRange): Int {
        val number = requireNotNull(value as? Number).toDouble()
        require(number.isFinite() && number == number.toInt().toDouble() && number.toInt() in range)
        return number.toInt()
    }

    private fun dimension(value: Any?): Double = requireNotNull(value as? Number).toDouble().also {
        require(it.isFinite() && it in 1.0..32_768.0)
    }

    private fun rectangle(value: Any?): List<Double> {
        val values = requireNotNull(value as? List<*>)
        require(values.size == 4)
        return values.mapIndexed { index, item ->
            requireNotNull(item as? Number).toDouble().also {
                require(it.isFinite() && it in -32_768.0..32_768.0 && (index < 2 || it >= 0))
            }
        }
    }
}

/**
 * Main-thread, one-request observation state. This never authorizes input or claims authority
 * acceptance. Timers only revoke; the owner must explicitly request each diagnostic response.
 */
internal class GodotQualificationObservation(
    private val presentationId: String,
    val mode: String,
    initialRevision: Long,
) {
    private data class Request(
        val id: Long, val generation: Long, val command: Long, val input: Long,
        val revision: Long, val requestedAt: Long, val surface: QualificationSurface,
    )

    init { require(mode in setOf("2d", "3d") && initialRevision >= 0) }

    private var generation = 0L
    private var command = 0L
    private var deliveredCommand = -1L
    private var input = 0L
    private var request = 0L
    private var revision = initialRevision
    private var sequence = -1L
    private var clock = -1L
    private var requestedAt = -1L
    private var surface: QualificationSurface? = null
    private var pending: Request? = null
    var snapshot: QualificationSnapshot? = null
        private set
    var disabled = false
        private set
    val waiting: Boolean get() = pending != null
    val deadline: Long? get() = pending?.let { it.requestedAt + REQUEST_TIMEOUT_MS } ?: snapshot?.expiresUptimeMs

    fun invalidate() {
        pending = null
        snapshot = null
        if (generation == Long.MAX_VALUE) disable() else generation++
    }

    fun inputChanged() {
        invalidate()
        if (input == Long.MAX_VALUE) disable() else input++
    }

    /** Called before queuing every view/foreground command, independently of the cover epoch. */
    fun commandQueued(isView: Boolean, newRevision: Any?): Long? {
        invalidate()
        if (disabled) return null
        if (isView) {
            val next = GodotQualificationSchema.counter(newRevision)
            if (next == null || next < revision) { disable(); return null }
            revision = next
        }
        if (command == Long.MAX_VALUE) { disable(); return null }
        command++
        return command
    }

    fun commandDelivered(stamp: Long?) {
        if (!disabled && stamp != null && stamp == command) deliveredCommand = stamp
    }

    fun nativeChanged(current: QualificationSurface?) {
        val valid = current?.takeIf { it.isValid() }
        if (valid != surface) {
            invalidate()
            surface = valid
        }
    }

    fun begin(now: Long, current: QualificationSurface?): String? {
        expire(now)
        nativeChanged(current)
        val native = surface ?: return null
        if (disabled || pending != null || deliveredCommand != command ||
            (requestedAt >= 0 && now - requestedAt < MIN_REQUEST_INTERVAL_MS)) return null
        if (request == Long.MAX_VALUE) { disable(); return null }
        request++
        requestedAt = now
        snapshot = null
        pending = Request(request, generation, command, input, revision, now, native)
        return request.toString()
    }

    fun receive(value: Map<*, *>, now: Long, current: QualificationSurface?) {
        expire(now)
        nativeChanged(current)
        val expected = pending ?: return
        val scene = GodotQualificationSchema.decode(value, presentationId, mode) ?: return
        // A delayed old reply cannot consume, cancel or clear a newer request's plugin slot.
        if (scene.request != expected.id) return
        if (disabled || expected.generation != generation || expected.command != command ||
            deliveredCommand != command || expected.input != input || expected.surface != surface ||
            expected.revision != scene.projectionRevision || scene.sequence <= sequence ||
            !expected.surface.matchesViewport(scene.viewport)) {
            invalidate()
            return
        }
        pending = null
        sequence = scene.sequence
        snapshot = QualificationSnapshot(mode, scene, generation, command, input, expected.requestedAt,
            now, now + PUBLICATION_TTL_MS, listOf(expected.surface.x, expected.surface.y,
                expected.surface.width, expected.surface.height))
    }

    fun expire(now: Long) {
        if (now < 0 || now < clock || now > Long.MAX_VALUE - PUBLICATION_TTL_MS) {
            disable()
            return
        }
        clock = now
        if (deadline?.let { now >= it } == true) invalidate()
    }

    fun disable() {
        disabled = true
        pending = null
        snapshot = null
    }

    companion object {
        const val MIN_REQUEST_INTERVAL_MS = 500L
        const val REQUEST_TIMEOUT_MS = 2_000L
        const val PUBLICATION_TTL_MS = 12_000L
    }
}
