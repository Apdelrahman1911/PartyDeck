package dev.partydeck.godot.bridge

import dev.partydeck.core.AvailableActions
import dev.partydeck.core.GameAction
import dev.partydeck.core.GameDecision
import dev.partydeck.core.GameState
import dev.partydeck.core.GameView
import dev.partydeck.core.LastLightEngine
import dev.partydeck.core.PlayerIdentity
import dev.partydeck.games.EngineEvent
import dev.partydeck.games.EngineEventBody
import dev.partydeck.games.EnginePayload
import dev.partydeck.games.MAX_ENGINE_PAYLOAD_BYTES
import kotlin.random.Random
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertFalse
import kotlin.test.assertIs
import kotlin.test.assertNotEquals
import kotlin.test.assertTrue
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonElement
import kotlinx.serialization.json.JsonNull
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.jsonArray
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive

/** Independently authored boundary tests; no shipping source is owned by this reviewer. */
class BridgeAdversarialReviewTest {
    private val controls = PresentationControls(false, true, false, false)

    @Test
    fun actualAuthorityViewsExposeOnlyTheRecipientHandAndResolvedPublicProof() {
        val fixture = fixture()
        for (state in listOf(fixture.opening, fixture.resolved, fixture.nextRound)) {
            for (viewer in state.players.map { it.identity.id } + listOf(null)) {
                val view = fixture.engine.viewFor(state, viewer)
                val payload = LastLightWireCodec.viewPayload(view, controls)
                assertEquals(view, LastLightWireCodec.decodeViewPayload(payload).game)
                val root = Json.parseToJsonElement(payload.document).jsonObject
                assertEquals(setOf("game", "controls"), root.keys)
                val game = root.getValue("game").jsonObject
                assertEquals(
                    setOf(
                        "viewerId", "phase", "roundNumber", "tableRank", "players", "yourHand",
                        "turnPlayerId", "latestClaim", "forcedChallenge", "availableActions",
                        "roundOutcome", "winnerId",
                    ), game.keys,
                )
                game.getValue("players").jsonArray.forEach { player ->
                    assertEquals(
                        setOf("id", "displayName", "handCount", "penaltyAttempts", "eliminated"),
                        player.jsonObject.keys,
                    )
                }
                val allowed = view.yourHand.map { it.id }.toSet() +
                    view.roundOutcome?.revealedCards.orEmpty().map { it.id }
                assertEquals(allowed, allCardIds(root))
                val otherSecretIds = state.players.filter { it.identity.id != viewer }
                    .flatMap { it.hand }.map { it.id }.toSet() + state.undealtCards.map { it.id }
                assertTrue(allCardIds(root).intersect(otherSecretIds).isEmpty())
                val forbidden = setOf(
                    "burnoutStep", "undealtCards", "discardedCards", "pendingPlay",
                    "openerPlayerId", "admissionSecret", "reconnectToken", "randomState",
                )
                assertTrue(objectPaths(root).none { (_, value) -> value.keys.any { it in forbidden } })
            }
        }
        val previous = fixture.engine.viewFor(fixture.nextRound, fixture.viewer)
        assertTrue(previous.roundOutcome!!.roundNumber < previous.roundNumber)
    }

    @Test
    fun missingUnknownAndQuotedPrimitiveFieldsCannotBeRepairedByDtoDefaults() {
        val fixture = fixture()
        val marker = "private-review-marker"
        for (state in listOf(fixture.opening, fixture.resolved)) {
            val view = fixture.engine.viewFor(state, fixture.viewer)
            val original = Json.parseToJsonElement(LastLightWireCodec.viewPayload(view, controls).document)
            for ((path, value) in objectPaths(original)) {
                for (key in value.keys) {
                    val changed = replace(original, path) { JsonObject(value - key) }
                    rejectView(changed, "missing ${path.joinToString(".")}.$key")
                }
                val changed = replace(original, path) {
                    JsonObject(value + ("reconnectToken" to JsonPrimitive(marker)))
                }
                val failure = rejectView(changed, "unknown field at ${path.joinToString(".")}")
                assertFalse(failure.message.orEmpty().contains(marker))
            }
            for ((path, value) in primitivePaths(original)) {
                if (!value.isString && value != JsonNull) {
                    val changed = replace(original, path) { JsonPrimitive(value.content) }
                    rejectView(changed, "quoted primitive at ${path.joinToString(".")}")
                }
            }
        }
    }

    @Test
    fun eventGrammarTypesAndCanonicalCountersFailWithoutLeakingTheDocument() {
        val original = event("review", 0, EngineEventBody.Ready)
        val ready = Json.parseToJsonElement(original)
        for (counter in listOf(
            "", "-0", "-1", "+1", "00", "01", "1.0", "1e0", " 1", "1 ",
            "9223372036854775808", "18446744073709551615", "１",
        )) {
            rejectEvent(replace(ready, listOf("sequence")) { JsonPrimitive(counter) }.toString())
        }
        for (value in listOf(JsonPrimitive(0), JsonPrimitive(true), JsonNull)) {
            rejectEvent(replace(ready, listOf("sequence")) { value }.toString())
        }
        for (token in listOf("\"1\"", "true", "null", "1.0", "1e0", "-1", "2147483648")) {
            val changed = original.replace("\"protocolVersion\":1", "\"protocolVersion\":$token")
            assertNotEquals(original, changed)
            rejectEvent(changed)
        }
        for (document in listOf(
            original.dropLast(1) + ",}",
            original.dropLast(1) + ",\"sequence\":\"1\"}",
            original.dropLast(1) + ",\"\\u0073equence\":\"1\"}",
            original + "{}",
            original.replace("\"review\"", "\"\\ud800\""),
            original.replace("\"review\"", "\"private-review-marker\n\""),
            """{"protocolVersion":1,"presentationId":"review","sequence":"0","type":"reveal"}""",
        )) {
            val failure = rejectEvent(document)
            assertFalse(failure.message.orEmpty().contains("private-review-marker"))
        }
        rejectEvent(intent("review", 1, 0, RendererIntent.Challenge)
            .replace("\"type\":\"challenge\"", "\"type\":\"challenge\",\"playerId\":\"another-seat\""))
        rejectEvent(intent("review", 1, 0, RendererIntent.Challenge)
            .replace("\"type\":\"challenge\"", "\"type\":\"challenge\",\"truthful\":true"))
    }

    @Test
    fun utf8LimitsApplyBeforeParsingAndFullWidthCountersRemainExact() {
        val document = event("é".repeat(64), Long.MAX_VALUE, EngineEventBody.Ready)
        val atLimit = document + " ".repeat(MAX_RENDERER_EVENT_BYTES - document.encodeToByteArray().size)
        assertTrue(atLimit.length < MAX_RENDERER_EVENT_BYTES)
        assertEquals(Long.MAX_VALUE, LastLightWireCodec.decodeEvent(atLimit).sequence)
        rejectEvent(atLimit + " ")

        val fixture = fixture()
        val view = fixture.engine.viewFor(fixture.opening, fixture.viewer)
        val payload = LastLightWireCodec.viewPayload(view, controls)
        val padded = payload.document +
            " ".repeat(MAX_ENGINE_PAYLOAD_BYTES - payload.document.encodeToByteArray().size)
        assertEquals(view, LastLightWireCodec.decodeViewPayload(EnginePayload(payload.schemaId, padded)).game)
        assertFailsWith<IllegalArgumentException> { EnginePayload(payload.schemaId, padded + " ") }

        val adapter = LastLightBridgeAdapter("large-counter", Long.MAX_VALUE - 1, view, controls)
        accepted(adapter.accept(event(adapter.presentationId, 0, EngineEventBody.Ready)))
        adapter.showView(Long.MAX_VALUE, view, controls)
        val action = accepted(adapter.accept(intent(
            adapter.presentationId, Long.MAX_VALUE, Long.MAX_VALUE,
            RendererIntent.Play(listOf(view.yourHand.first().id)),
        )))
        assertEquals(
            GameAction.Play(fixture.viewer, listOf(view.yourHand.first().id)),
            assertIs<BridgeInput.Action>(action).action,
        )
        assertRejected(BridgeRejection.REPLAYED_EVENT, adapter.accept(intent(
            adapter.presentationId, Long.MAX_VALUE, Long.MAX_VALUE,
            RendererIntent.Play(listOf(view.yourHand.last().id)),
        )))
        assertFailsWith<IllegalArgumentException> { adapter.showView(Long.MAX_VALUE, view, controls) }
    }

    @Test
    fun rejectionOrderingBindsTheCurrentRecipientRevisionAndPresentationLifetime() {
        val fixture = fixture()
        val view = fixture.engine.viewFor(fixture.opening, fixture.viewer)
        val cards = view.yourHand.toMutableList()
        val adapter = LastLightBridgeAdapter("old-presentation", 10, view.copy(yourHand = cards), controls)
        cards.clear()
        assertRejected(BridgeRejection.NOT_READY, adapter.accept(intent(
            adapter.presentationId, 0, 10, RendererIntent.Play(listOf(view.yourHand.first().id)),
        )))
        assertRejected(BridgeRejection.WRONG_PRESENTATION, adapter.accept(event("another", Long.MAX_VALUE, EngineEventBody.Ready)))
        assertRejected(BridgeRejection.UNSUPPORTED_PROTOCOL, adapter.accept(
            event(adapter.presentationId, 0, EngineEventBody.Ready, protocol = 2),
        ))
        accepted(adapter.accept(event(adapter.presentationId, 0, EngineEventBody.Ready)))
        assertRejected(BridgeRejection.STALE_REVISION, adapter.accept(intent(
            adapter.presentationId, 1, 9, RendererIntent.Play(listOf(view.yourHand.first().id)),
        )))
        assertRejected(BridgeRejection.REPLAYED_EVENT, adapter.accept(intent(
            adapter.presentationId, 1, 10, RendererIntent.Play(listOf(view.yourHand.first().id)),
        )))
        val foreign = fixture.opening.players.first { it.identity.id != fixture.viewer }.hand.first().id
        assertRejected(BridgeRejection.INVALID_SELECTION, adapter.accept(intent(
            adapter.presentationId, 2, 10, RendererIntent.Play(listOf(foreign)),
        )))
        adapter.setForeground(false)
        assertRejected(BridgeRejection.NOT_FOREGROUND, adapter.accept(intent(
            adapter.presentationId, 3, 10, RendererIntent.Play(listOf(view.yourHand.first().id)),
        )))
        adapter.setForeground(true)
        assertRejected(BridgeRejection.REPLAYED_EVENT, adapter.accept(intent(
            adapter.presentationId, 3, 10, RendererIntent.Play(listOf(view.yourHand.first().id)),
        )))
        val action = assertIs<BridgeInput.Action>(accepted(adapter.accept(intent(
            adapter.presentationId, 4, 10, RendererIntent.Play(listOf(view.yourHand.first().id)),
        )))).action
        assertEquals(fixture.viewer, action.playerId)
        assertIs<GameDecision.Applied>(fixture.engine.apply(fixture.opening, action))

        val otherId = fixture.opening.players.first { it.identity.id != fixture.viewer }.identity.id
        val otherView = fixture.engine.viewFor(fixture.opening, otherId)
        assertFailsWith<IllegalArgumentException> { adapter.showView(11, otherView, controls) }
        assertEquals(10L, adapter.revision)
        adapter.close()
        adapter.close()
        assertRejected(BridgeRejection.CLOSED, adapter.accept(event(adapter.presentationId, 5, EngineEventBody.Ready)))

        val replacement = LastLightBridgeAdapter("new-presentation", 0, view, controls)
        assertRejected(BridgeRejection.WRONG_PRESENTATION, replacement.accept(event(adapter.presentationId, 6, EngineEventBody.Ready)))
        accepted(replacement.accept(event(replacement.presentationId, 0, EngineEventBody.Ready)))
        assertRejected(BridgeRejection.WRONG_PRESENTATION, replacement.accept(intent(
            adapter.presentationId, 7, 0, RendererIntent.Play(listOf(view.yourHand.first().id)),
        )))
    }

    @Test
    fun suppressedActionsAndHostControlsRemainSeparateFromRuleAuthority() {
        val fixture = fixture()
        val view = fixture.engine.viewFor(fixture.opening, fixture.viewer)
        val paused = view.copy(availableActions = AvailableActions())
        val adapter = LastLightBridgeAdapter("paused", 0, paused, controls)
        accepted(adapter.accept(event(adapter.presentationId, 0, EngineEventBody.Ready)))
        for ((sequence, body) in listOf(
            RendererIntent.Play(listOf(view.yourHand.first().id)),
            RendererIntent.AdvanceRound,
            RendererIntent.ReturnToLobby,
        ).withIndex()) {
            assertRejected(BridgeRejection.ACTION_UNAVAILABLE, adapter.accept(intent(
                adapter.presentationId, sequence.toLong() + 1, 0, body,
            )))
        }
        val host = LastLightBridgeAdapter(
            "host-result", 0, fixture.engine.viewFor(fixture.resolved, fixture.viewer),
            PresentationControls(true, true, true, true),
        )
        accepted(host.accept(event(host.presentationId, 0, EngineEventBody.Ready)))
        assertIs<BridgeInput.AdvanceRound>(accepted(host.accept(intent(host.presentationId, 1, 0, RendererIntent.AdvanceRound))))
        val spectator = LastLightBridgeAdapter(
            "spectator", 0, fixture.engine.viewFor(fixture.opening, null), controls,
        )
        accepted(spectator.accept(event(spectator.presentationId, 0, EngineEventBody.Ready)))
        assertRejected(BridgeRejection.ACTION_UNAVAILABLE, spectator.accept(intent(
            spectator.presentationId, 1, 0, RendererIntent.Play(listOf(view.yourHand.first().id)),
        )))
    }

    private data class Fixture(
        val engine: LastLightEngine,
        val opening: GameState,
        val resolved: GameState,
        val nextRound: GameState,
        val viewer: String,
    )

    private fun fixture(): Fixture {
        val engine = LastLightEngine(Random(809))
        val opening = engine.start(listOf(
            PlayerIdentity("seat-a", "Ari"), PlayerIdentity("seat-b", "Béa"),
            PlayerIdentity("seat-c", "Cleo"), PlayerIdentity("seat-d", "Dune"),
        ))
        val viewer = opening.turnPlayerId!!
        val play = GameAction.Play(viewer, engine.viewFor(opening, viewer).yourHand.take(2).map { it.id })
        val played = assertIs<GameDecision.Applied>(engine.apply(opening, play)).state
        val resolved = assertIs<GameDecision.Applied>(engine.apply(played, GameAction.Challenge(played.turnPlayerId!!))).state
        val next = assertIs<GameDecision.Applied>(engine.advanceRound(resolved)).state
        return Fixture(engine, opening, resolved, next, viewer)
    }

    private fun event(id: String, sequence: Long, body: EngineEventBody, protocol: Int = 1): String =
        LastLightWireCodec.encodeEvent(EngineEvent(id, protocol, sequence, body))

    private fun intent(id: String, sequence: Long, revision: Long, body: RendererIntent): String =
        event(id, sequence, EngineEventBody.PlayerIntent(revision, LastLightWireCodec.intentPayload(body)))

    private fun accepted(decision: BridgeDecision): BridgeInput =
        assertIs<BridgeDecision.Accepted>(decision).input

    private fun assertRejected(reason: BridgeRejection, decision: BridgeDecision) =
        assertEquals(BridgeDecision.Rejected(reason), decision)

    private fun rejectView(value: JsonElement, label: String): IllegalArgumentException =
        assertFailsWith<IllegalArgumentException>(label) {
            LastLightWireCodec.decodeViewPayload(EnginePayload(LAST_LIGHT_VIEW_SCHEMA, value.toString()))
        }

    private fun rejectEvent(document: String): IllegalArgumentException =
        assertFailsWith<IllegalArgumentException> { LastLightWireCodec.decodeEvent(document) }

    private fun allCardIds(value: JsonElement): Set<String> = objectPaths(value)
        .filter { (_, objectValue) -> objectValue.keys == setOf("id", "rank") }
        .map { (_, objectValue) -> objectValue.getValue("id").jsonPrimitive.content }.toSet()

    private fun objectPaths(value: JsonElement, path: List<String> = emptyList()): List<Pair<List<String>, JsonObject>> =
        when (value) {
            is JsonObject -> listOf(path to value) + value.flatMap { (key, child) -> objectPaths(child, path + key) }
            is JsonArray -> value.flatMapIndexed { index, child -> objectPaths(child, path + index.toString()) }
            else -> emptyList()
        }

    private fun primitivePaths(value: JsonElement, path: List<String> = emptyList()): List<Pair<List<String>, JsonPrimitive>> =
        when (value) {
            is JsonObject -> value.flatMap { (key, child) -> primitivePaths(child, path + key) }
            is JsonArray -> value.flatMapIndexed { index, child -> primitivePaths(child, path + index.toString()) }
            is JsonPrimitive -> listOf(path to value)
        }

    private fun replace(value: JsonElement, path: List<String>, change: (JsonElement) -> JsonElement): JsonElement {
        if (path.isEmpty()) return change(value)
        return when (value) {
            is JsonObject -> JsonObject(value + (path.first() to replace(value.getValue(path.first()), path.drop(1), change)))
            is JsonArray -> JsonArray(value.mapIndexed { index, child ->
                if (index == path.first().toInt()) replace(child, path.drop(1), change) else child
            })
            else -> error("Invalid reviewer mutation path")
        }
    }
}
