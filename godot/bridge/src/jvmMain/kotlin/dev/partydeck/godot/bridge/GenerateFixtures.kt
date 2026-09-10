package dev.partydeck.godot.bridge

import dev.partydeck.core.GamePhase
import dev.partydeck.games.ENGINE_BRIDGE_PROTOCOL_VERSION
import dev.partydeck.games.EngineCommand
import dev.partydeck.games.EngineEvent
import dev.partydeck.games.EngineEventBody
import dev.partydeck.games.EngineLaunch
import dev.partydeck.games.GameId
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.put
import java.nio.file.Files
import java.nio.file.Path
import java.security.MessageDigest
import kotlin.random.Random

/** Reproducible public/private-recipient projections from real authority operations. */
object GenerateFixtures {
    private const val FIXTURE_SEED = 2
    private const val PRESENTATION_ID = "last-light-generated-fixture-v1"

    @JvmStatic
    fun main(args: Array<String>) {
        require(args.size == 1) { "Usage: GenerateFixtures <output-directory>" }
        val output = Path.of(args.single()).toAbsolutePath().normalize()
        Files.createDirectories(output)
        val documents = linkedMapOf<String, String>()
        val driver = QualificationAuthorityDriver(Random(FIXTURE_SEED), PRESENTATION_ID)
        var sequence = 0L
        var humanPlays = 0
        var humanChallenges = 0

        fun emitIntent(intent: RendererIntent): Pair<String, QualificationStep> {
            val document = LastLightWireCodec.encodeEvent(EngineEvent(
                PRESENTATION_ID, ENGINE_BRIDGE_PROTOCOL_VERSION, ++sequence,
                EngineEventBody.PlayerIntent(driver.revision, LastLightWireCodec.intentPayload(intent)),
            ))
            val step = driver.handleEvent(document)
            check(step.decision is BridgeDecision.Accepted && step.authorityRejection == null) { "Fixture action was rejected." }
            when (intent) {
                is RendererIntent.Play -> humanPlays++
                RendererIntent.Challenge -> humanChallenges++
                else -> Unit
            }
            return document to step
        }

        fun preview(prefix: String) {
            val view = driver.view
            val controls = PresentationControls(true, true, view.phase == GamePhase.ROUND_ENDED, view.phase == GamePhase.FINISHED)
            val launch = EngineLaunch(GameId("last-light"), PRESENTATION_ID, LastLightWireCodec.viewPayload(view, controls), driver.revision)
            for (mode in PresentationMode.entries) {
                documents["$prefix-${mode.wireName}.json"] = LastLightWireCodec.encodeLaunch(launch, mode)
            }
        }

        preview("launch")
        val ready = LastLightWireCodec.encodeEvent(EngineEvent(PRESENTATION_ID, 1, sequence, EngineEventBody.Ready))
        documents["ready.json"] = ready
        check(driver.handleEvent(ready).decision == BridgeDecision.Accepted(BridgeInput.Ready))
        val (play, played) = emitIntent(RendererIntent.Play(listOf(driver.view.yourHand.first().id)))
        documents["play.json"] = play
        documents["after-play.json"] = played.documents.single()
        val firstBots = driver.advanceOtherPlayers()
        check(driver.view.phase == GamePhase.ROUND_ENDED)
        documents["round-ended.json"] = firstBots.last().documents.single()
        preview("round-ended-launch")
        val (advance, advanced) = emitIntent(RendererIntent.AdvanceRound)
        documents["advance-round.json"] = advance
        documents["round-playing.json"] = advanced.documents.single()

        var steps = 0
        while (driver.view.phase != GamePhase.FINISHED) {
            check(++steps <= 300) { "Fixture authority did not reach a winner within its budget." }
            val view = driver.view
            when {
                view.phase == GamePhase.ROUND_ENDED -> emitIntent(RendererIntent.AdvanceRound)
                view.viewerId != view.turnPlayerId -> check(driver.advanceOtherPlayers().isNotEmpty())
                view.availableActions.canChallenge -> emitIntent(RendererIntent.Challenge)
                view.availableActions.canPlay -> emitIntent(RendererIntent.Play(listOf(view.yourHand.first().id)))
                else -> error("No projected action can advance the fixture.")
            }
        }
        preview("finished-launch")
        documents["finished.json"] = LastLightWireCodec.encodeCommand(
            PRESENTATION_ID,
            EngineCommand.ShowView(driver.revision, LastLightWireCodec.viewPayload(driver.view, PresentationControls(true, true, false, true))),
        )
        documents["return-to-lobby.json"] = emitIntent(RendererIntent.ReturnToLobby).first
        documents["close.json"] = driver.close()

        for ((name, document) in documents) Files.writeString(output.resolve(name), "$document\n")
        val manifest = buildJsonObject {
            put("version", 1)
            put("generator", "dev.partydeck.godot.bridge.GenerateFixtures")
            put("authority", "LastLightEngine.start/viewFor/apply/advanceRound")
            put("purpose", "isolated renderer qualification; not multiplayer evidence")
            put("seed", FIXTURE_SEED)
            put("viewerId", driver.viewerId)
            put("finalRevision", driver.revision.toString())
            put("finalRound", driver.view.roundNumber)
            put("viewerPlayEvents", humanPlays)
            put("viewerChallengeEvents", humanChallenges)
            put("sha256", buildJsonObject {
                documents.keys.forEach { name ->
                    val digest = MessageDigest.getInstance("SHA-256").digest(Files.readAllBytes(output.resolve(name)))
                    put(name, digest.joinToString("") { it.toUByte().toString(16).padStart(2, '0') })
                }
            })
        }
        Files.writeString(output.resolve("fixture-manifest.json"), "$manifest\n")
        println("Generated ${documents.size} authority-derived renderer documents; viewer plays=$humanPlays, challenges=$humanChallenges, final round=${driver.view.roundNumber}.")
        println("Fixture seed/provenance is in the tooling manifest; it is never sent as a renderer view or intent.")
    }
}
