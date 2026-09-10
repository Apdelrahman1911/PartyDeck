package dev.partydeck.app.godot

import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFalse
import kotlin.test.assertNotNull
import kotlin.test.assertNull
import kotlin.test.assertTrue

class GodotQualificationObservationTest {
    private val token = Any()
    private val surface = QualificationSurface(token, 0, 150, 800, 1200, 2.0, 4)

    @Test
    fun requestsRequireCurrentCommandDeliveryAndVisibleNativeSurface() {
        val observer = observer()
        assertNull(observer.begin(1000, surface))
        val old = observer.commandQueued(false, null)
        val current = observer.commandQueued(true, "8")
        observer.commandDelivered(old)
        assertNull(observer.begin(1100, surface))
        observer.commandDelivered(current)
        assertNull(observer.begin(1200, null))
        assertEquals("1", observer.begin(1300, surface))
    }

    @Test
    fun onlyOneRequestIsPendingAndRefreshRateIsBounded() {
        val observer = ready()
        assertEquals("1", observer.begin(1000, surface))
        assertNull(observer.begin(1700, surface))
        observer.receive(document(), 1800, surface)
        assertNotNull(observer.snapshot)
        assertEquals("2", observer.begin(1800, surface))
        observer.receive(document(request = "2", sequence = "2"), 1850, surface)
        assertNull(observer.begin(2000, surface))
        assertNotNull(observer.snapshot)
        assertEquals("3", observer.begin(2300, surface))
        assertNull(observer.snapshot)
    }

    @Test
    fun oldRepliesDoNotConsumeAReplacementRequest() {
        val observer = ready()
        observer.begin(1000, surface)
        observer.inputChanged()
        assertEquals("2", observer.begin(1700, surface))
        observer.receive(document(), 1750, surface)
        assertTrue(observer.waiting)
        assertNull(observer.snapshot)
        observer.receive(document(request = "2", sequence = "2"), 1800, surface)
        assertFalse(observer.waiting)
        assertEquals(2L, observer.snapshot?.scene?.request)
    }

    @Test
    fun commandsAndLocalInputsRevokePublishedStateWithoutAuthorityProgress() {
        val observer = published()
        val stamp = observer.commandQueued(true, "7")
        assertNull(observer.snapshot)
        assertNull(observer.begin(1600, surface))
        observer.commandDelivered(stamp)
        observer.begin(1700, surface)
        observer.receive(document(request = "2", sequence = "2"), 1750, surface)
        val second = assertNotNull(observer.snapshot)
        observer.inputChanged()
        assertNull(observer.snapshot)
        observer.begin(2300, surface)
        observer.receive(document(request = "3", sequence = "3"), 2350, surface)
        val third = assertNotNull(observer.snapshot)
        assertEquals(second.scene.projectionRevision, third.scene.projectionRevision)
        assertTrue(third.input > second.input && third.generation > second.generation)
    }

    @Test
    fun geometryIdentityDensityAndPrivacyChangesInvalidatePendingReplies() {
        for (changed in listOf(surface.copy(viewToken = Any()), surface.copy(x = 1), surface.copy(width = 799),
            surface.copy(density = 2.1), surface.copy(privacyGeneration = 5), null)) {
            val observer = ready()
            observer.begin(1000, surface)
            observer.receive(document(), 1100, changed)
            assertNull(observer.snapshot)
            assertFalse(observer.waiting)
        }
        val observer = published()
        observer.nativeChanged(surface.copy(y = 151))
        assertNull(observer.snapshot)
    }

    @Test
    fun wrongIdentityModeRevisionSequenceAndViewportCannotPublish() {
        for (bad in listOf(document() + ("presentationId" to "another-private-identity"),
            document() + ("presentationMode" to "3d"), document() + ("revision" to "6"),
            document() + ("sceneStateApplied" to false), document() + ("foreground" to false),
            document() + ("viewport" to mapOf("width" to 500, "height" to 600)))) {
            val observer = ready()
            observer.begin(1000, surface)
            observer.receive(bad, 1100, surface)
            assertNull(observer.snapshot)
        }
        val observer = published()
        observer.begin(1700, surface)
        observer.receive(document(request = "2", sequence = "1"), 1750, surface)
        assertNull(observer.snapshot)
    }

    @Test
    fun timeoutAndFiniteExpiryRevokeWithoutIssuingRequests() {
        val observer = ready()
        observer.begin(1000, surface)
        assertEquals(3000L, observer.deadline)
        observer.receive(document(), 3000, surface)
        assertFalse(observer.waiting)
        assertNull(observer.snapshot)
        assertNull(observer.deadline)
        observer.begin(3100, surface)
        observer.receive(document(request = "2", sequence = "2"), 3200, surface)
        assertEquals(15200L, observer.deadline)
        observer.expire(15199)
        assertNotNull(observer.snapshot)
        observer.expire(15200)
        assertNull(observer.snapshot)
        assertNull(observer.deadline)
        assertFalse(observer.waiting)
    }

    @Test
    fun clockRegressionAndCounterExhaustionDisableOnlyObservation() {
        val observer = published()
        observer.expire(1000)
        assertTrue(observer.disabled)
        assertNull(observer.snapshot)
        assertNull(observer.begin(2000, surface))
        for (field in listOf("generation", "command", "input", "request")) {
            val exhausted = ready()
            exhausted.javaClass.getDeclaredField(field).also { it.isAccessible = true }.setLong(exhausted, Long.MAX_VALUE)
            when (field) {
                "generation" -> exhausted.invalidate()
                "command" -> exhausted.commandQueued(false, null)
                "input" -> exhausted.inputChanged()
                "request" -> exhausted.begin(1000, surface)
            }
            assertTrue(exhausted.disabled, field)
            assertNull(exhausted.begin(2000, surface), field)
        }
        val lateClock = ready()
        assertNull(lateClock.begin(Long.MAX_VALUE, surface))
        assertTrue(lateClock.disabled)
    }

    @Test
    fun invalidNativeBoundsAndUnacknowledgedInvalidRevisionFailClosed() {
        for (bad in listOf(surface.copy(width = 0), surface.copy(y = -1), surface.copy(height = 32768),
            surface.copy(density = Double.NaN), surface.copy(privacyGeneration = -1))) {
            assertNull(ready().begin(1000, bad))
        }
        val observer = ready()
        assertNull(observer.commandQueued(true, "07"))
        assertTrue(observer.disabled)
    }

    @Test
    fun sanitizerDropsNonpublishedRolesAndContainsNoPrivateIdentifiers() {
        val extra = control("partydeck_action_challenge")
        val raw = document() + ("controls" to listOf(control(), extra))
        val safe = assertNotNull(GodotQualificationSchema.decode(raw, PRIVATE_ID, "2d"))
        assertEquals(listOf(QualificationRole.REVEAL), safe.controls.map { it.role })
        assertFalse(safe.toString().contains(PRIVATE_ID))
        assertFalse(safe.toString().contains("partydeck_action_challenge"))
    }

    @Test
    fun sanitizerRejectsUnknownFieldsGroupsDuplicateSlotsAndMalformedFilteredControls() {
        val base = document()
        val controls = listOf(
            listOf(control() + ("cardRank" to "private-rank")),
            listOf(control("private-rank")),
            listOf(control(), control()),
            listOf(control("partydeck_hand_card", -1)),
            listOf(control("partydeck_action_challenge") + ("rect" to listOf(0, 0, Double.NaN, 10))),
            listOf(control("partydeck_action_exit") + ("selected" to true)),
            listOf(control() + ("cardIndex" to 0)),
        )
        for (value in controls) assertNull(GodotQualificationSchema.decode(base + ("controls" to value), PRIVATE_ID, "2d"))
        for (key in listOf("cardId", "playerId", "sessionId", "labels", "resourcePath", "arbitrary")) {
            assertNull(GodotQualificationSchema.decode(base + (key to "private-sentinel"), PRIVATE_ID, "2d"))
        }
    }

    @Test
    fun strictCountersCountsBooleansAndConcealedBindingsAreChecked() {
        val base = document()
        for (bad in listOf<Any?>(null, 1, -1, "", "-1", "01", "+1", "1.0", "1e0", "9223372036854775808")) {
            for (key in listOf("requestId", "sequence", "revision")) {
                assertNull(GodotQualificationSchema.decode(base + (key to bad), PRIVATE_ID, "2d"))
            }
        }
        for ((key, bad) in listOf("selectedCount" to 1, "privateFaceCount" to 1, "privateLabelCount" to 1,
            "handConcealed" to "true", "schemaVersion" to true)) {
            assertNull(GodotQualificationSchema.decode(base + (key to bad), PRIVATE_ID, "2d"))
        }
        val selected = control("partydeck_hand_card", 0) + ("selected" to true)
        val revealed = base + mapOf("handConcealed" to false, "selectedCount" to 1, "privateFaceCount" to 5,
            "privateLabelCount" to 5, "controls" to listOf(selected))
        assertNotNull(GodotQualificationSchema.decode(revealed, PRIVATE_ID, "2d"))
        assertNull(GodotQualificationSchema.decode(revealed + ("selectedCount" to 2), PRIVATE_ID, "2d"))
    }

    @Test
    fun boundedGeometryRejectsOffViewportClipsAndFalseVisibleRectangles() {
        val invalid = listOf(
            control() + ("clipRect" to listOf(-1, 0, 200, 300)),
            control() + ("clipRect" to listOf(0, 0, 401, 600)),
            control() + ("rect" to listOf(0, 0, -10, 20)),
            control() + ("rect" to listOf(0, 0, 0, 0)),
            control() + ("rect" to listOf(0, 0, 32769, 20)),
            control() + ("rect" to listOf(401, 0, 10, 10)),
        )
        for (bad in invalid) assertNull(GodotQualificationSchema.decode(document() + ("controls" to listOf(bad)), PRIVATE_ID, "2d"))
    }

    private fun observer() = GodotQualificationObservation(PRIVATE_ID, "2d", 7)
    private fun ready() = observer().also { it.commandDelivered(it.commandQueued(false, null)) }
    private fun published() = ready().also {
        it.begin(1000, surface)
        it.receive(document(), 1100, surface)
        assertNotNull(it.snapshot)
    }

    private fun document(request: String = "1", sequence: String = "1"): Map<String, Any?> = mapOf(
        "schemaVersion" to 1, "requestId" to request, "sequence" to sequence, "presentationId" to PRIVATE_ID,
        "revision" to "7", "presentationMode" to "2d", "coordinateSpace" to "root_viewport", "foreground" to true,
        "sceneStateApplied" to true, "viewport" to mapOf("width" to 400, "height" to 600),
        "handConcealed" to true, "selectedCount" to 0, "privateFaceCount" to 0, "privateLabelCount" to 0,
        "controls" to listOf(control()),
    )

    private fun control(group: String = "partydeck_action_reveal", slot: Int = -1): Map<String, Any?> = mapOf(
        "group" to group, "cardIndex" to slot, "rect" to listOf(0, 0, 200, 40),
        "clipRect" to listOf(0, 0, 400, 600), "visible" to true, "enabled" to true, "selected" to false,
    )

    companion object { private const val PRIVATE_ID = "private-presentation-sentinel" }
}
