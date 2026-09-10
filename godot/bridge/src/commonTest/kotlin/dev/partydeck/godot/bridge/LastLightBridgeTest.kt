package dev.partydeck.godot.bridge

import dev.partydeck.core.AvailableActions
import dev.partydeck.core.GameAction
import dev.partydeck.core.GameDecision
import dev.partydeck.core.GamePhase
import dev.partydeck.core.GameState
import dev.partydeck.core.LastLightEngine
import dev.partydeck.core.PlayerIdentity
import dev.partydeck.games.EngineEvent
import dev.partydeck.games.EngineEventBody
import dev.partydeck.games.EnginePayload
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonElement
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlin.random.Random
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertFalse
import kotlin.test.assertIs
import kotlin.test.assertTrue

class LastLightBridgeTest {
    @Test
    fun everyRecipientGetsOnlyOwnHandAndResolvedPublicProof() {
        val engine = LastLightEngine(Random(57))
        var state = engine.start(roster(4))
        fun checkProjections() {
            for (recipient in state.players.map { it.identity.id } + listOf(null)) {
                val view = engine.viewFor(state, recipient)
                val payload = LastLightWireCodec.viewPayload(view, PresentationControls(false, true, false, false))
                val tree = Json.parseToJsonElement(payload.document)
                val strings = stringValues(tree)
                val publicProof = view.roundOutcome?.revealedCards.orEmpty().map { it.id }.toSet()
                val hiddenCards = state.players.filter { it.identity.id != recipient }.flatMap { it.hand } + state.undealtCards
                assertTrue(hiddenCards.filterNot { it.id in publicProof }.none { it.id in strings })
                assertTrue(view.yourHand.all { it.id in strings })
                assertTrue(publicProof.all { it in strings })
                val bannedKeys = setOf("burnoutStep", "pendingPlay", "discardedCards", "undealtCards", "admission", "reconnectToken", "random")
                assertTrue(keys(tree).intersect(bannedKeys).isEmpty())
                assertEquals(view, LastLightWireCodec.decodeViewPayload(payload).game)
            }
        }
        checkProjections()
        val opener = checkNotNull(state.turnPlayerId)
        val card = engine.viewFor(state, opener).yourHand.first()
        state = applied(engine.apply(state, GameAction.Play(opener, listOf(card.id))))
        checkProjections()
        state = applied(engine.apply(state, GameAction.Challenge(checkNotNull(state.turnPlayerId))))
        checkProjections()
    }

    @Test
    fun priorRoundProofAndPausedActionSubsetRemainValid() {
        val engine = LastLightEngine(Random(67))
        var state = engine.start(roster(4))
        val opener = checkNotNull(state.turnPlayerId)
        state = applied(engine.apply(state, GameAction.Play(opener, listOf(engine.viewFor(state, opener).yourHand.first().id))))
        state = applied(engine.apply(state, GameAction.Challenge(checkNotNull(state.turnPlayerId))))
        state = applied(engine.advanceRound(state))
        val viewer = checkNotNull(state.turnPlayerId)
        val paused = engine.viewFor(state, viewer).copy(availableActions = AvailableActions())
        val payload = LastLightWireCodec.viewPayload(paused, PresentationControls(true, false, false, true))
        val decoded = LastLightWireCodec.decodeViewPayload(payload).game
        assertEquals(2, decoded.roundNumber)
        assertEquals(1, decoded.roundOutcome?.roundNumber)
        assertFalse(decoded.availableActions.canPlay)
        assertTrue(decoded.yourHand.isNotEmpty())
    }

    @Test
    fun missingDefaultFieldsAndPrimitiveCoercionsCannotWeakenTheViewSchema() {
        val driver = QualificationAuthorityDriver(Random(5), "shape-test")
        val original = LastLightWireCodec.viewPayload(driver.view, PresentationControls(true, true, false, false))
        val mutations = listOf(
            original.document.replace("\"canChallenge\":false,", ""),
            original.document.replace("\"canPlay\":true", "\"canPlay\":\"true\""),
            original.document.replace("\"roundNumber\":1", "\"roundNumber\":\"1\""),
            original.document.replace("\"isHost\":true", "\"isHost\":true,\"burnoutStep\":6"),
        )
        mutations.forEach { mutated ->
            assertTrue(mutated != original.document)
            assertFailsWith<BridgeFormatException> { LastLightWireCodec.decodeViewPayload(EnginePayload(LAST_LIGHT_VIEW_SCHEMA, mutated)) }
        }
    }

    @Test
    fun exactLongCountersAndStrictEventShapeSurviveTheJsonBoundary() {
        val good = event("precision", Long.MAX_VALUE, EngineEventBody.PlayerIntent(
            9_007_199_254_740_993L, LastLightWireCodec.intentPayload(RendererIntent.Challenge),
        ))
        val decoded = LastLightWireCodec.decodeEvent(good)
        assertEquals(Long.MAX_VALUE, decoded.sequence)
        assertEquals(9_007_199_254_740_993L, assertIs<EngineEventBody.PlayerIntent>(decoded.body).expectedRevision)
        val bad = listOf(
            good.replace("\"sequence\":\"9223372036854775807\"", "\"sequence\":9223372036854775807"),
            good.replace("\"9223372036854775807\"", "\"9223372036854775808\""),
            good.replace("\"sequence\":", "\"sequence\":\"0\",\"sequ\\u0065nce\":"),
            good.dropLast(1) + ",}",
            good.replace("\"challenge\"", "\"challenge\",\"playerId\":\"another-seat\""),
            good.replace("\"precision\"", "\"\\uD800\""),
        )
        bad.forEach { assertFailsWith<IllegalArgumentException> { LastLightWireCodec.decodeEvent(it) } }
    }

    @Test
    fun realAuthorityRejectsStaleAndBackgroundInputThenRecoversWithANewView() {
        val driver = QualificationAuthorityDriver(Random(5), "authority-test")
        assertEquals(BridgeDecision.Accepted(BridgeInput.Ready), driver.handleEvent(event(driver.presentationId, 0, EngineEventBody.Ready)).decision)
        val selected = driver.view.yourHand.first().id
        val before = driver.view
        driver.setForeground(false)
        val background = driver.handleEvent(intent(driver, 1, RendererIntent.Play(listOf(selected))))
        assertEquals(BridgeDecision.Rejected(BridgeRejection.NOT_FOREGROUND), background.decision)
        assertEquals(before, driver.view)
        assertTrue(driver.advanceOtherPlayers().isEmpty())
        driver.setForeground(true)
        val refresh = driver.refreshView()
        assertTrue(refresh.contains("\"revision\":\"1\""))
        val stale = driver.handleEvent(event(driver.presentationId, 2, EngineEventBody.PlayerIntent(
            0, LastLightWireCodec.intentPayload(RendererIntent.Play(listOf(selected))),
        )))
        assertEquals(BridgeDecision.Rejected(BridgeRejection.STALE_REVISION), stale.decision)
        assertEquals(before, driver.view)
        val played = driver.handleEvent(intent(driver, 3, RendererIntent.Play(listOf(selected))))
        assertIs<BridgeDecision.Accepted>(played.decision)
        assertEquals(null, played.authorityRejection)
        assertEquals(4, driver.view.yourHand.size)
        assertFalse(driver.view.yourHand.any { it.id == selected })
        assertEquals(1, played.documents.size)
        driver.close()
        assertEquals(BridgeDecision.Rejected(BridgeRejection.CLOSED), driver.handleEvent(intent(driver, 4, RendererIntent.Challenge)).decision)
    }

    @Test
    fun deterministicCompleteMatchUsesBothViewerIntentsAndRealRoundOutcomes() {
        val coverage = completeMatch(2)
        assertEquals(2 to 2, coverage)
    }

    private fun completeMatch(seed: Int): Pair<Int, Int> {
        val driver = QualificationAuthorityDriver(Random(seed), "match-$seed")
        driver.handleEvent(event(driver.presentationId, 0, EngineEventBody.Ready))
        var sequence = 0L
        var plays = 0
        var challenges = 0
        var operations = 0
        while (driver.view.phase != GamePhase.FINISHED) {
            assertTrue(++operations <= 300, "Authority did not finish seed $seed.")
            val view = driver.view
            if (view.phase == GamePhase.PLAYING && view.turnPlayerId != driver.viewerId) {
                val automatic = driver.advanceOtherPlayers()
                assertTrue(automatic.isNotEmpty())
                assertTrue(automatic.all { it.authorityRejection == null && it.documents.size == 1 })
                continue
            }
            val requested = when {
                view.phase == GamePhase.ROUND_ENDED -> RendererIntent.AdvanceRound
                view.availableActions.canChallenge -> RendererIntent.Challenge.also { challenges++ }
                view.availableActions.canPlay -> RendererIntent.Play(listOf(view.yourHand.first().id)).also { plays++ }
                else -> error("Authority exposed no action for its active recipient.")
            }
            val step = driver.handleEvent(intent(driver, ++sequence, requested))
            assertIs<BridgeDecision.Accepted>(step.decision)
            assertEquals(null, step.authorityRejection)
            assertEquals(1, step.documents.size)
        }
        assertEquals(driver.view.winnerId, driver.view.players.single { !it.eliminated }.id)
        assertTrue(driver.view.roundOutcome != null)
        val returned = driver.handleEvent(intent(driver, ++sequence, RendererIntent.ReturnToLobby))
        assertEquals(BridgeDecision.Accepted(BridgeInput.ReturnToLobby), returned.decision)
        assertTrue(returned.documents.isEmpty())
        assertEquals(BridgeDecision.Rejected(BridgeRejection.CLOSED), driver.handleEvent(intent(driver, ++sequence, RendererIntent.AdvanceRound)).decision)
        return plays to challenges
    }

    private fun intent(driver: QualificationAuthorityDriver, sequence: Long, intent: RendererIntent): String = event(
        driver.presentationId, sequence, EngineEventBody.PlayerIntent(driver.revision, LastLightWireCodec.intentPayload(intent)),
    )
    private fun event(id: String, sequence: Long, body: EngineEventBody): String =
        LastLightWireCodec.encodeEvent(EngineEvent(id, 1, sequence, body))
    private fun roster(count: Int) = List(count) { PlayerIdentity("seat-$it", "Player $it") }
    private fun applied(decision: GameDecision): GameState = assertIs<GameDecision.Applied>(decision).state
    private fun stringValues(element: JsonElement): Set<String> = when (element) {
        is JsonObject -> element.values.flatMap(::stringValues).toSet()
        is JsonArray -> element.flatMap(::stringValues).toSet()
        is JsonPrimitive -> if (element.isString) setOf(element.content) else emptySet()
    }
    private fun keys(element: JsonElement): Set<String> = when (element) {
        is JsonObject -> element.keys + element.values.flatMap(::keys)
        is JsonArray -> element.flatMap(::keys).toSet()
        is JsonPrimitive -> emptySet()
    }
}
