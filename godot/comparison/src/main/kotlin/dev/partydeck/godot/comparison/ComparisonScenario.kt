package dev.partydeck.godot.comparison

import dev.partydeck.core.GameAction
import dev.partydeck.core.GamePhase
import dev.partydeck.godot.bridge.BridgeDecision
import dev.partydeck.godot.bridge.BridgeInput
import dev.partydeck.godot.bridge.PresentationMode
import dev.partydeck.godot.bridge.PresentationPreferences
import dev.partydeck.godot.bridge.QualificationAuthorityDriver
import dev.partydeck.godot.bridge.QualificationStep
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonElement
import kotlinx.serialization.json.JsonNull
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.boolean
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.double
import kotlinx.serialization.json.jsonArray
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import kotlinx.serialization.json.put
import java.nio.file.Files
import java.security.SecureRandom
import java.util.UUID
import javax.imageio.ImageIO
import kotlin.random.Random

/** All outcomes come from QualificationAuthorityDriver; this class only chooses legal inputs. */
internal class ComparisonScenario(
    private val options: ComparisonOptions,
    private val renderer: RendererProcess,
    private val mode: String,
    private val provenance: JsonObject,
) {
    private var driver = newDriver()
    private val modeEnum = if (mode == "2d") PresentationMode.TWO_D else PresentationMode.THREE_D
    private val preferences = PresentationPreferences(
        reduceMotion = !options.interactive, soundEnabled = options.interactive, textScale = options.textScale,
    )
    private val trace = mutableListOf<JsonObject>()
    private val captures = mutableListOf<JsonObject>()
    private val inputs = mutableListOf<JsonObject>()
    private val coverage = linkedSetOf<String>()
    private var bridgeEvents = 0
    private var viewerPlays = 0
    private var viewerChallenges = 0
    private var advances = 0
    private var lastViewHash = ""
    private var navigation: String? = null

    fun run(): JsonObject {
        launch()
        if (options.interactive) return interact()
        check(driver.view.availableActions.canPlay) { "Qualification viewer is not the real initial opener" }
        assertConcealed(renderer.state())
        capture("01-concealed")
        coverage += "concealed_start"

        revealAndSelect()
        capture("03-selected")
        checkNoEvent("Reveal/select")
        renderer.click("partydeck_action_hide")
        assertConcealed(renderer.state())
        capture("04-covered")
        checkNoEvent("Hide")
        coverage += "hide_clears_selection"

        revealAndSelect(captureReveal = false)
        renderer.wire(driver.setForeground(false))
        assertConcealed(renderer.state())
        check(!presentation(renderer.state()).flag("foreground")) { "Renderer stayed interactive after foreground loss" }
        capture("05-background-privacy")
        renderer.wire(driver.setForeground(true))
        assertConcealed(renderer.state())
        checkNoEvent("Foreground transition")
        coverage += "foreground_privacy"

        revealAndSelect(captureReveal = false)
        submit("partydeck_action_play", "play", "06-play-pending")
        advanceOpponents()

        var firstOutcome = true
        var firstRedeal = true
        repeat(400) {
            when (driver.view.phase) {
                GamePhase.FINISHED -> return finish()
                GamePhase.ROUND_ENDED -> {
                    check(driver.view.roundOutcome != null) { "Round ended without an authority proof" }
                    assertConcealed(renderer.state())
                    if (firstOutcome) {
                        capture("07-public-round-result")
                        firstOutcome = false
                    }
                    coverage += "public_round_result"
                    submit("partydeck_action_next_round", "advance_round")
                    advances++
                    if (firstRedeal) {
                        capture("08-next-round")
                        firstRedeal = false
                    }
                    coverage += "next_round"
                    advanceOpponents()
                }
                GamePhase.PLAYING -> {
                    if (driver.view.turnPlayerId != driver.viewerId) {
                        advanceOpponents()
                    } else if (driver.view.availableActions.canChallenge) {
                        submit("partydeck_action_challenge", "challenge", if (viewerChallenges == 0) "09-challenge-pending" else null)
                        advanceOpponents()
                    } else {
                        check(driver.view.availableActions.canPlay) { "Viewer has no legal projected action" }
                        revealAndSelect(captureReveal = false)
                        submit("partydeck_action_play", "play")
                        advanceOpponents()
                    }
                }
            }
        }
        error("Real authority did not reach a winner within 400 UI steps")
    }

    private fun launch() {
        val document = driver.launchDocument(modeEnum, preferences)
        showDocument(document)
        val ready = renderer.nextEvent(5000) ?: error("Renderer never emitted Ready")
        check(eventType(ready) == "ready") { "First renderer event was not Ready" }
        accept(ready)
        checkNoEvent("Launch")
    }

    private fun revealAndSelect(captureReveal: Boolean = true) {
        check(driver.view.availableActions.canPlay && driver.view.yourHand.isNotEmpty()) { "Cannot select outside the viewer's legal turn" }
        renderer.click("partydeck_action_reveal")
        val revealed = presentation(renderer.state())
        check(revealed.flag("handVisible")) { "The actual Reveal button did not reveal the hand" }
        val hand = revealed.getValue("game").jsonObject.getValue("yourHand").jsonArray
        check(hand.map { it.jsonObject.text("id") } == driver.view.yourHand.map { it.id }) { "Revealed hand does not belong to the recipient" }
        check(hand.map { it.jsonObject.text("rank") } == driver.view.yourHand.map { it.rank.name }) { "Renderer changed the recipient's ranks" }
        if (captureReveal) capture("02-revealed")
        val result = renderer.click("partydeck_hand_card", 0)
        inputs += result.getValue("input").jsonObject
        val selected = presentation(result.getValue("state").jsonObject).getValue("selectedCardIds").jsonArray
        check(selected == JsonArray(listOf(JsonPrimitive(driver.view.yourHand.first().id)))) { "Actual card click did not select the intended own card" }
        checkNoEvent("Local hand input")
        coverage += "reveal_select"
    }

    private fun submit(group: String, expectedType: String, pendingCapture: String? = null) {
        val before = driver.revision
        val result = renderer.click(group)
        inputs += result.getValue("input").jsonObject
        val pending = presentation(result.getValue("state").jsonObject)
        check(!pending.getValue("controls").jsonObject.flag("canSendAction")) { "Submitted input remained enabled before authority acknowledgment" }
        check(pending.getValue("selectedCardIds").jsonArray.isEmpty()) { "Submission retained its local selection" }
        check(driver.revision == before) { "Renderer input changed authority before the bridge event was accepted" }
        if (pendingCapture != null) capture(pendingCapture)
        val event = renderer.nextEvent(5000) ?: error("Actual $group input emitted no bridge event")
        check(eventType(event) == expectedType) { "Actual $group input emitted an unexpected intent" }
        accept(event)
        check(driver.revision > before) { "An accepted $expectedType did not produce a fresh authority view" }
        assertConcealed(renderer.state())
        checkNoEvent("Acknowledged $expectedType")
        coverage += "pending_until_authority_view"
    }

    private fun accept(document: String) {
        val step = driver.handleEvent(document)
        val decision = step.decision
        check(decision is BridgeDecision.Accepted) { "Shared bridge rejected the renderer event: $decision" }
        check(step.authorityRejection == null) { "Core authority rejected a projected renderer action: ${step.authorityRejection}" }
        bridgeEvents++
        when (val input = decision.input) {
            is BridgeInput.Action -> when (input.action) {
                is GameAction.Play -> { viewerPlays++; coverage += "viewer_play" }
                is GameAction.Challenge -> { viewerChallenges++; coverage += "viewer_challenge" }
            }
            BridgeInput.ReturnToLobby -> navigation = "lobby"
            BridgeInput.ExitRequested -> navigation = "exit"
            is BridgeInput.Failed -> error("Renderer reported ${input.reason}")
            BridgeInput.Ready, BridgeInput.AdvanceRound -> Unit
        }
        deliver(step)
    }

    private fun advanceOpponents() {
        val before = driver.revision
        val steps = driver.advanceOtherPlayers()
        steps.forEach(::deliver)
        if (driver.view.phase == GamePhase.PLAYING && driver.view.turnPlayerId != driver.viewerId) {
            check(driver.revision > before) { "Safe-view opponents made no progress" }
        }
        if (!options.interactive) checkNoEvent("Opponent snapshots")
    }

    private fun deliver(step: QualificationStep) {
        check(step.authorityRejection == null) { "Authority rejected a qualification action" }
        step.documents.forEach(::showDocument)
    }

    private fun showDocument(document: String) {
        val wire = Json.parseToJsonElement(document).jsonObject
        val state = renderer.wire(document)
        if (wire.text("type") in setOf("launch", "view")) {
            val expected = wire.getValue("payload").jsonObject.getValue("game").jsonObject
            val actual = presentation(state).getValue("game").jsonObject
            for (key in listOf("viewerId", "phase", "roundNumber", "tableRank", "players", "turnPlayerId", "latestClaim", "forcedChallenge", "availableActions", "roundOutcome", "winnerId")) {
                check(sameJson(actual[key], expected[key])) { "Renderer changed authoritative field $key" }
            }
            // Automated tests control every input; a human may reveal after this view arrives.
            if (!options.interactive) assertConcealed(state)
            lastViewHash = sha256(expected.toString().toByteArray(Charsets.UTF_8))
            trace += buildJsonObject {
                put("revision", wire.text("revision"))
                put("viewSha256", lastViewHash)
                put("phase", expected.text("phase"))
                put("roundNumber", expected.getValue("roundNumber"))
            }
        }
    }

    private fun finish(): JsonObject {
        check(driver.view.winnerId != null) { "Finished authority has no winner" }
        check(viewerPlays > 0 && viewerChallenges > 0 && advances > 0) {
            "Seed ${options.seed} did not cover viewer play, viewer challenge, and continuation; record a fixed suitable scenario seed"
        }
        assertConcealed(renderer.state())
        capture("10-winner")
        coverage += "winner"
        renderer.click("partydeck_action_lobby")
        // Both presentations may require a visible native-navigation confirmation.
        var event = renderer.nextEvent(100)
        if (event == null) {
            capture("11-lobby-confirmation")
            renderer.click("partydeck_action_lobby_confirm")
            event = renderer.nextEvent(5000)
        }
        check(event != null && eventType(event) == "return_to_lobby") { "Winner lobby action did not request native navigation" }
        accept(event)
        check(navigation == "lobby")
        renderer.wire(driver.close())
        assertClosed()
        coverage += "return_to_lobby"
        val matchTrace = trace.toList()

        renderer.request("reset")
        driver = newDriver()
        navigation = null
        launch()
        assertConcealed(renderer.state())
        capture("12-fresh-presentation")
        renderer.click("partydeck_action_exit")
        val exit = renderer.nextEvent(5000) ?: error("Actual Leave button emitted no ExitRequested")
        check(eventType(exit) == "exit") { "Leave emitted an unexpected bridge event" }
        accept(exit)
        check(navigation == "exit")
        assertClosed()
        coverage += "fresh_entry_and_leave"
        checkNoEvent("Closed presentation")
        return result(matchTrace)
    }

    private fun interact(): JsonObject {
        capture("01-interactive-start")
        println("$mode is playable. Reveal your hand, choose cards, play or challenge; use Continue after a round. Close the table to finish.")
        try {
            while (renderer.isAlive() && navigation == null) {
                val event = renderer.nextEvent(250) ?: continue
                val step = driver.handleEvent(event)
                when (val decision = step.decision) {
                    is BridgeDecision.Rejected -> {
                        println("Rejected renderer input: ${decision.reason}")
                        renderer.wire(driver.refreshView())
                    }
                    is BridgeDecision.Accepted -> {
                        check(step.authorityRejection == null) { "Core authority rejected a legal interactive intent" }
                        bridgeEvents++
                        when (val input = decision.input) {
                            BridgeInput.ReturnToLobby -> navigation = "lobby"
                            BridgeInput.ExitRequested -> navigation = "exit"
                            is BridgeInput.Failed -> error("Renderer reported ${input.reason}")
                            else -> Unit
                        }
                        deliver(step)
                        if (navigation == null) advanceOpponents()
                    }
                }
            }
        } catch (rejected: ProbeRejected) {
            // A human may press Exit while an opponent's view is in flight. Consume the
            // actual terminal event; do not misreport that normal close as a failed game.
            val state = rejected.result as? JsonObject
            val closed = state?.get("presentation")?.jsonObject?.get("closed")?.jsonPrimitive?.boolean == true
            if (rejected.operation != "document" || !closed) throw rejected
            val event = renderer.nextEvent(500) ?: throw rejected
            if (eventType(event) != "exit") throw rejected
            val decision = driver.handleEvent(event).decision
            check(decision is BridgeDecision.Accepted && decision.input == BridgeInput.ExitRequested) {
                "In-flight close did not authenticate its ExitRequested event"
            }
            bridgeEvents++
            navigation = "exit"
        }
        if (navigation == "lobby") renderer.wire(driver.close())
        coverage += "interactive_authority_session"
        return result(trace)
    }

    private fun assertConcealed(state: JsonObject) {
        val presentation = presentation(state)
        check(!presentation.flag("handVisible")) { "A private hand remained revealed" }
        check(presentation.getValue("selectedCardIds").jsonArray.isEmpty()) { "A private selection survived concealment" }
        val game = presentation.getValue("game").jsonObject
        check(game["yourHand"]?.jsonArray.orEmpty().all { "rank" !in it.jsonObject }) { "Concealed card state still includes a private rank" }
        val diagnostics = state.getValue("diagnostics").jsonObject
        check(diagnostics.getValue("privateFaceCount").jsonPrimitive.double == 0.0) { "A real private card face remained bound while concealed" }
        check(diagnostics.getValue("privateLabelCount").jsonPrimitive.double == 0.0) { "A real private rank label remained visible while concealed" }
    }

    private fun assertClosed() {
        val state = renderer.state()
        assertConcealed(state)
        val presentation = presentation(state)
        check(presentation.flag("closed") && presentation.getValue("game").jsonObject.isEmpty()) { "Close retained a game or private card binding" }
        check(!presentation.getValue("controls").jsonObject.flag("canSendAction")) { "Closed presentation accepts input" }
    }

    private fun checkNoEvent(action: String) {
        check(renderer.nextEvent(60) == null) { "$action unexpectedly emitted an authority event" }
    }

    private fun capture(name: String) {
        val captured = renderer.request("capture", buildJsonObject { put("name", name) }).jsonObject
        val path = renderer.output.resolve("$name.png")
        val image = ImageIO.read(path.toFile()) ?: error("Godot did not write a readable viewport PNG")
        check(image.width == options.width && image.height == options.height) { "Captured viewport size differs from the requested comparison size" }
        val colors = buildSet {
            for (y in 0 until image.height step maxOf(1, image.height / 50)) {
                for (x in 0 until image.width step maxOf(1, image.width / 50)) add(image.getRGB(x, y))
            }
        }
        check(colors.size > 16) { "Viewport capture appears blank or unrendered" }
        val receipt = buildJsonObject {
            provenance.forEach { (key, value) -> put(key, value) }
            put("presentation", mode)
            put("scenario", name)
            put("path", "$mode/$name.png")
            put("sha256", sha256(Files.readAllBytes(path)))
            put("width", image.width)
            put("height", image.height)
            put("godotVersion", renderer.godotVersion)
            put("backend", "Godot gl_compatibility / X11${if (options.xvfb) " / Xvfb" else ""}")
            put("authorityRevision", driver.revision.toString())
            put("authorityViewSha256", lastViewHash)
            put("seed", options.seed?.let(::JsonPrimitive) ?: JsonNull)
            put("reduceMotion", preferences.reduceMotion)
            put("textScale", options.textScale)
            put("diagnostics", captured.getValue("state").jsonObject.getValue("diagnostics"))
        }
        Files.writeString(renderer.output.resolve("$name.receipt.json"), receipt.toString())
        captures += receipt
        println("Captured $mode/$name.png")
    }

    private fun result(matchTrace: List<JsonObject>): JsonObject = buildJsonObject {
        put("presentation", mode)
        put("seed", options.seed?.let(::JsonPrimitive) ?: JsonNull)
        put("godotVersion", renderer.godotVersion)
        put("coverage", JsonArray(coverage.map(::JsonPrimitive)))
        put("bridgeEvents", bridgeEvents)
        put("viewerPlays", viewerPlays)
        put("viewerChallenges", viewerChallenges)
        put("roundsAdvanced", advances)
        put("probeRequests", renderer.requestCount)
        put("authorityTrace", JsonArray(matchTrace))
        put("authorityTraceSha256", sha256(JsonArray(matchTrace).toString().toByteArray(Charsets.UTF_8)))
        put("inputs", JsonArray(inputs))
        put("captures", JsonArray(captures))
    }

    private fun newDriver() = QualificationAuthorityDriver(
        options.seed?.let(::Random) ?: SecureComparisonRandom(), "comparison-${UUID.randomUUID()}",
    )

    private fun presentation(state: JsonObject) = state.getValue("presentation").jsonObject

    private fun eventType(document: String): String {
        val event = Json.parseToJsonElement(document).jsonObject
        return if (event.text("type") == "intent") event.getValue("payload").jsonObject.text("type") else event.text("type")
    }
}

private fun JsonObject.flag(key: String): Boolean = getValue(key).jsonPrimitive.boolean

/** Godot parses JSON numbers as double; 4 and 4.0 still describe the same public count. */
private fun sameJson(left: JsonElement?, right: JsonElement?): Boolean = when {
    left is JsonObject && right is JsonObject -> left.keys == right.keys && left.keys.all { sameJson(left[it], right[it]) }
    left is JsonArray && right is JsonArray -> left.size == right.size && left.indices.all { sameJson(left[it], right[it]) }
    left is JsonPrimitive && right is JsonPrimitive && !left.isString && !right.isString -> {
        val leftNumber = left.content.toBigDecimalOrNull()
        val rightNumber = right.content.toBigDecimalOrNull()
        if (leftNumber != null && rightNumber != null) leftNumber.compareTo(rightNumber) == 0 else left == right
    }
    else -> left == right
}

private class SecureComparisonRandom : Random() {
    private val random = SecureRandom()
    override fun nextBits(bitCount: Int): Int = if (bitCount == 0) 0 else random.nextInt().ushr(32 - bitCount)
}
