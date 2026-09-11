package dev.partydeck.app

import dev.partydeck.core.GameAction
import dev.partydeck.core.GameDecision
import dev.partydeck.core.GamePhase
import dev.partydeck.core.GameState
import dev.partydeck.core.LastLightEngine
import dev.partydeck.core.LastLightRules
import dev.partydeck.core.PlayerIdentity
import dev.partydeck.session.ClientIntent
import dev.partydeck.session.ClientMessage
import dev.partydeck.session.HostAuthority
import dev.partydeck.session.HostSessionConfig
import dev.partydeck.session.ServerMessage
import dev.partydeck.session.SessionCodec
import dev.partydeck.session.SessionDispatch
import dev.partydeck.session.SessionPeer
import dev.partydeck.session.SessionView
import dev.partydeck.session.WireDecodeResult
import java.nio.file.Files
import java.nio.file.Path
import java.nio.file.StandardOpenOption
import java.time.Instant
import kotlinx.coroutines.runBlocking
import kotlin.random.Random

/** Explicit measurement entry point; ordinary JVM tests never invoke it. See the usage document. */
object JvmRuleNetworkMeasurements {
    @JvmStatic
    fun main(args: Array<String>) {
        if (args.contentEquals(arrayOf("--help"))) {
            println("--output=NEW_DIRECTORY [--seed=20260910] [--warmups=2] [--samples=5] [--idle-ms=1000]")
            return
        }
        val options = MeasurementOptions.parse(args)
        Files.createDirectories(options.output.parent)
        Files.createDirectory(options.output)
        val report = MeasurementReport(options)
        var completed = false
        try {
            for (trial in options.trials()) AuthorityCodecTrial(trial, report).run()
            runBlocking {
                for (trial in options.trials()) {
                    val intervals = mutableListOf<TlsPayloadInterval>()
                    LanMultiplayerIntegrationTest().measureSixSeatTls(options.seed, options.idleMillis) { interval ->
                        intervals += interval
                        report.tls(trial, interval)
                    }
                    check(intervals.map { it.phase } == listOf(TlsMeasurementPhase.IDLE, TlsMeasurementPhase.ACTIVE)) {
                        "TLS fixture did not report both requested intervals"
                    }
                    report.completedTls(trial, intervals.last().acceptedCommandCount)
                }
            }
            completed = true
        } finally {
            // Preserve partial raw rows on failure; metadata never calls a partial run complete.
            report.write(completed)
        }
        println("JVM rule/codec and six-seat TLS application-payload measurements written to ${options.output}")
    }
}

private data class MeasurementOptions(
    val output: Path,
    val seed: Int,
    val warmups: Int,
    val samples: Int,
    val idleMillis: Long,
) {
    fun trials(): List<Trial> = List(warmups) { Trial("warmup", it, seed) } +
        List(samples) { Trial("sample", it, seed) }

    companion object {
        fun parse(args: Array<String>): MeasurementOptions {
            val values = linkedMapOf<String, String>()
            for (arg in args) {
                require(arg.startsWith("--") && '=' in arg) { "Expected --option=value; use --help" }
                val name = arg.substring(2).substringBefore('=')
                require(name in setOf("output", "seed", "warmups", "samples", "idle-ms")) { "Unknown measurement option" }
                require(values.put(name, arg.substringAfter('=')) == null) { "Duplicate measurement option" }
            }
            val output = Path.of(requireNotNull(values["output"]) { "--output=NEW_DIRECTORY is required" })
                .toAbsolutePath().normalize()
            val options = MeasurementOptions(
                output,
                values["seed"]?.toInt() ?: 20260910,
                values["warmups"]?.toInt() ?: 2,
                values["samples"]?.toInt() ?: 5,
                values["idle-ms"]?.toLong() ?: 1_000,
            )
            require(options.warmups >= 0 && options.samples > 0) { "Warmups must be nonnegative and samples positive" }
            require(options.idleMillis > 0) { "Idle duration must be positive" }
            require(options.output.parent != null) { "Output needs a parent directory" }
            return options
        }
    }
}

private data class Trial(val kind: String, val index: Int, val seed: Int)
private data class Timed<T>(val value: T, val elapsedNs: Long)

private inline fun <T> timed(block: () -> T): Timed<T> {
    val started = System.nanoTime()
    val value = block()
    val elapsed = System.nanoTime() - started
    return Timed(value, elapsed)
}

private enum class Operation { INITIAL, JOIN, READY, START_GAME, PLAY_ONE, CHALLENGE, ADVANCE_ROUND }

/**
 * Serial six-seat authority workload. A second real engine with the same seed measures bare rule
 * calls and verifies each recipient view. It never substitutes for HostAuthority's own engine.
 * Only successfully decoded remote inputs/outputs are used to drive subsequent real actions.
 */
private class AuthorityCodecTrial(private val trial: Trial, private val report: MeasurementReport) {
    private val peers = List(SEATS) { SessionPeer("measurement-peer-$it") }
    private val names = listOf("Host Ada", "Guest Bo", "Guest Cy", "Guest Dee", "Guest Eli", "Guest Fay")
    private val sessionId = "0".repeat(32)
    private val admissionSecret = "e".repeat(64)
    private var credentialNumber = 0L
    private val authority = HostAuthority(
        HostSessionConfig(sessionId, admissionSecret, names.first(), peers.first()),
        LastLightEngine(Random(trial.seed)),
        secureToken = { (++credentialNumber).toString(16).padStart(64, '0') },
    )
    private val referenceRules = LastLightEngine(Random(trial.seed))
    private var referenceState: GameState? = null
    private val views = arrayOfNulls<SessionView>(SEATS)
    private val nextCommandIds = LongArray(SEATS) { 1L }
    private var step = 0

    fun run() {
        val initial = timed { authority.initialDispatch() }
        deliver(Operation.INITIAL, actor = 0, revisionBefore = 0, dispatch = initial, ruleNs = null, input = null)
        for (seat in 1 until SEATS) {
            exchange(seat, ClientMessage.Join(sessionId, admissionSecret, names[seat]), Operation.JOIN)
        }
        // A join resets readiness, so all five admissions precede readiness commands.
        for (seat in 1 until SEATS) command(seat, ClientIntent.SetReady(true), Operation.READY)
        check(view(0).controls.canStartGame) { "Six-seat table did not become ready" }
        command(0, ClientIntent.StartGame, Operation.START_GAME)
        var gameCommands = 1
        // Match the real TLS fixture's initial orbit: each admitted seat submits a received card.
        val initialActors = mutableSetOf<Int>()
        repeat(SEATS) {
            val actor = currentActor()
            check(initialActors.add(actor)) { "Initial orbit repeated a seat" }
            playOne(actor)
            gameCommands++
        }
        while (view(0).game?.phase != GamePhase.FINISHED) {
            // After the initial orbit, each round has one play, one challenge and at most one
            // redeal. Challenges consume the finite six-seat/six-light penalty budget. This
            // bounds rules progress, not performance or elapsed time.
            check(gameCommands < 3 * LastLightRules.MAX_PLAYERS * LastLightRules.FUSE_LIGHTS + SEATS - 1) {
                "Legal workload exceeded the finite penalty budget"
            }
            val game = checkNotNull(view(0).game)
            if (game.phase == GamePhase.ROUND_ENDED) {
                check(view(0).controls.canAdvanceRound)
                command(0, ClientIntent.AdvanceRound, Operation.ADVANCE_ROUND)
            } else {
                val actor = currentActor()
                val ownGame = checkNotNull(view(actor).game)
                if (ownGame.availableActions.canChallenge) {
                    command(actor, ClientIntent.Challenge, Operation.CHALLENGE)
                } else {
                    playOne(actor)
                }
            }
            gameCommands++
        }
        val finished = checkNotNull(view(0).game)
        check(finished.winnerId != null && finished.players.count { !it.eliminated } == 1)
        check(views.all { received ->
            received?.game?.let { it.phase == GamePhase.FINISHED && it.winnerId == finished.winnerId } == true
        })
        report.completedAuthority(trial, step, gameCommands)
    }

    private fun view(seat: Int): SessionView = checkNotNull(views[seat]) { "Recipient has no accepted snapshot" }

    private fun currentActor(): Int {
        val turn = checkNotNull(view(0).game?.turnPlayerId)
        return views.indexOfFirst { it?.selfPlayerId == turn }.also {
            check(it >= 0) { "No recipient owns the current turn" }
        }
    }

    private fun playOne(actor: Int) {
        val game = checkNotNull(view(actor).game)
        check(game.availableActions.canPlay && game.yourHand.isNotEmpty())
        command(actor, ClientIntent.PlayCards(listOf(game.yourHand.first().id)), Operation.PLAY_ONE)
    }

    private fun command(actor: Int, intent: ClientIntent, operation: Operation) {
        val command = ClientMessage.Command(sessionId, nextCommandIds[actor]++, view(actor).revision, intent)
        exchange(actor, command, operation)
    }

    private fun exchange(actor: Int, message: ClientMessage, operation: Operation) {
        val revisionBefore = view(0).revision
        val encoded = if (actor == 0) null else timed { SessionCodec.encodeClient(message) }
        val decoded = encoded?.let { timed { SessionCodec.decodeClient(it.value) } }
        val acceptedInput = when (val result = decoded?.value) {
            null -> message
            is WireDecodeResult.Success -> {
                check(result.value == message) { "Client codec changed a generated input" }
                result.value
            }
            is WireDecodeResult.Failure -> error("Generated client payload was rejected by SessionCodec")
        }
        val input = MessageMeasurement(
            "client_to_host", actor, clientKind(message), encoded?.value?.size,
            encoded?.elapsedNs, decoded?.elapsedNs,
        )
        val ruleNs = (acceptedInput as? ClientMessage.Command)?.let { measureRules(actor, it.intent) }
        val result = timed { authority.handle(peers[actor], acceptedInput) }
        if (message is ClientMessage.Command) {
            val receipts = result.value.deliveries.mapNotNull { (it.message as? ServerMessage.Receipt)?.receipt }
            check(receipts.size == 1 && receipts.single().accepted && receipts.single().commandId == message.commandId) {
                "Real authority rejected or failed to acknowledge a generated legal command"
            }
        }
        deliver(operation, actor, revisionBefore, result, ruleNs, input)
        check(view(0).revision == revisionBefore + 1) { "A generated command did not change exactly one revision" }
    }

    private fun measureRules(actor: Int, intent: ClientIntent): Long? {
        if (intent == ClientIntent.StartGame) {
            val roster = view(0).players.map { PlayerIdentity(it.id, it.displayName) }
            val measured = timed { referenceRules.start(roster) }
            referenceState = measured.value
            return measured.elapsedNs
        }
        val state = referenceState ?: return null
        val measured = when (intent) {
            is ClientIntent.PlayCards -> {
                val action = GameAction.Play(view(actor).selfPlayerId, intent.cardIds)
                timed { referenceRules.apply(state, action) }
            }
            ClientIntent.Challenge -> {
                val action = GameAction.Challenge(view(actor).selfPlayerId)
                timed { referenceRules.apply(state, action) }
            }
            ClientIntent.AdvanceRound -> timed { referenceRules.advanceRound(state) }
            else -> return null
        }
        referenceState = (measured.value as? GameDecision.Applied)?.state
            ?: error("Reference rules rejected the real authority workload")
        return measured.elapsedNs
    }

    private fun deliver(
        operation: Operation,
        actor: Int,
        revisionBefore: Long,
        dispatch: Timed<SessionDispatch>,
        ruleNs: Long?,
        input: MessageMeasurement?,
    ) {
        check(dispatch.value.closeConnections.isEmpty()) { "Legal workload unexpectedly closed a recipient" }
        val routed = ArrayList<RoutedMessage>(dispatch.value.deliveries.size)
        val fanoutStarted = System.nanoTime()
        for (delivery in dispatch.value.deliveries) {
            val seat = peers.indexOfFirst { it.connectionId == delivery.connectionId }
            check(seat >= 0) { "Authority emitted a delivery for an unknown recipient" }
            val encoded = if (seat == 0) null else timed { SessionCodec.encodeServer(delivery.message) }
            val decoded = encoded?.let { timed { SessionCodec.decodeServer(it.value) } }
            routed += RoutedMessage(seat, delivery.message, encoded?.value?.size, encoded?.elapsedNs, decoded)
        }
        val fanoutNs = System.nanoTime() - fanoutStarted
        // Consume every decoder result and compare it with the actual authority payload outside
        // the fan-out stopwatch. Neither messages nor views are printed or written to a report.
        for (delivery in routed) {
            val message = when (val result = delivery.decoded?.value) {
                null -> delivery.original
                is WireDecodeResult.Success -> {
                    check(result.value == delivery.original) { "Server codec changed a recipient payload" }
                    result.value
                }
                is WireDecodeResult.Failure -> error("Authority payload was rejected by SessionCodec")
            }
            when (message) {
                is ServerMessage.Welcome -> {
                    views[delivery.seat] = message.view
                    nextCommandIds[delivery.seat] = message.nextCommandId
                }
                is ServerMessage.Snapshot -> views[delivery.seat] = message.view
                is ServerMessage.Receipt -> check(message.receipt.accepted)
                else -> error("Unexpected server message in the legal workload")
            }
        }
        val revisionAfter = view(0).revision
        for (seat in views.indices) {
            val received = views[seat] ?: continue
            check(received.selfPlayerId == "p$seat" && received.revision == revisionAfter)
            check(received == authority.viewFor(peers[seat])) { "Recipient did not converge with its authority view" }
            referenceState?.let { state ->
                val expected = timed { referenceRules.viewFor(state, received.selfPlayerId) }
                check(received.game == expected.value) { "Recipient view diverged from independently executed rules" }
                report.ruleView(trial, step, operation, seat, expected.elapsedNs)
            }
        }
        input?.let { report.message(trial, step, operation, it) }
        for (delivery in routed) {
            report.message(
                trial, step, operation,
                MessageMeasurement(
                    "host_to_recipient", delivery.seat, serverKind(delivery.original), delivery.bytes,
                    delivery.encodeNs, delivery.decoded?.elapsedNs,
                ),
            )
        }
        report.step(
            trial, step++, operation, actor, revisionBefore, revisionAfter, ruleNs, dispatch.elapsedNs, fanoutNs,
            routed.count { it.seat == 0 }, routed.count { it.seat != 0 },
            routed.sumOf { if (it.seat == 0) 0L else checkNotNull(it.bytes).toLong() },
            if (actor == 0) 0 else input?.bytes ?: 0,
        )
    }

    private data class RoutedMessage(
        val seat: Int,
        val original: ServerMessage,
        val bytes: Int?,
        val encodeNs: Long?,
        val decoded: Timed<WireDecodeResult<ServerMessage>>?,
    )

    private companion object { const val SEATS = 6 }
}

private data class MessageMeasurement(
    val direction: String,
    val seat: Int,
    val kind: String,
    val bytes: Int?,
    val encodeNs: Long?,
    val decodeNs: Long?,
)

private fun clientKind(message: ClientMessage): String = when (message) {
    is ClientMessage.Join -> "join"
    is ClientMessage.Resume -> "resume"
    is ClientMessage.Command -> "command"
}

private fun serverKind(message: ServerMessage): String = when (message) {
    is ServerMessage.Welcome -> "welcome"
    is ServerMessage.Snapshot -> "snapshot"
    is ServerMessage.Receipt -> "receipt"
    is ServerMessage.AdmissionRejected -> "admission_rejected"
    is ServerMessage.Ended -> "ended"
}

/** Fixed-schema numeric/category output only. No DTO, exception, credential or card serialization. */
private class MeasurementReport(private val options: MeasurementOptions) {
    private val startedAt = Instant.now().toString()
    private val steps = Csv(
        "run_kind,run_index,seed,step,operation,actor_seat,revision_before,revision_after,reference_rule_ns," +
            "authority_handle_ns,serial_codec_fanout_ns,host_local_deliveries,remote_deliveries," +
            "remote_server_payload_bytes,remote_client_payload_bytes",
    )
    private val messages = Csv(
        "run_kind,run_index,seed,step,operation,direction,seat,route,message_kind,payload_bytes,encode_ns,decode_ns",
    )
    private val ruleViews = Csv("run_kind,run_index,seed,step,operation,seat,reference_rule_view_ns")
    private val tls = Csv(
        "run_kind,run_index,seed,phase,seat,elapsed_ns,revision_before,revision_after,accepted_commands," +
            "sent_messages,sent_payload_bytes,received_messages,received_payload_bytes",
    )
    private val completions = Csv("run_kind,run_index,seed,suite,authority_steps,game_commands")
    private var authorityTrials = 0
    private var tlsTrials = 0
    private var tlsIntervals = 0

    fun message(trial: Trial, step: Int, operation: Operation, message: MessageMeasurement) {
        messages.add(
            trial.kind, trial.index, trial.seed, step, operation.name, message.direction, message.seat,
            if (message.seat == 0) "host_local_object" else "remote_codec", message.kind,
            message.bytes, message.encodeNs, message.decodeNs,
        )
    }

    fun ruleView(trial: Trial, step: Int, operation: Operation, seat: Int, elapsedNs: Long) {
        ruleViews.add(trial.kind, trial.index, trial.seed, step, operation.name, seat, elapsedNs)
    }

    fun step(
        trial: Trial, step: Int, operation: Operation, actor: Int, before: Long, after: Long,
        ruleNs: Long?, authorityNs: Long, fanoutNs: Long, localDeliveries: Int, remoteDeliveries: Int,
        serverBytes: Long, clientBytes: Int,
    ) {
        steps.add(
            trial.kind, trial.index, trial.seed, step, operation.name, actor, before, after,
            ruleNs, authorityNs, fanoutNs, localDeliveries, remoteDeliveries, serverBytes, clientBytes,
        )
    }

    fun tls(trial: Trial, interval: TlsPayloadInterval) {
        for ((seat, delta) in interval.payloadDeltas.withIndex()) {
            tls.add(
                trial.kind, trial.index, trial.seed, interval.phase.name, seat, interval.elapsedNs,
                interval.revisionBefore, interval.revisionAfter, interval.acceptedCommandCount,
                delta.sentMessages, delta.sentBytes, delta.receivedMessages, delta.receivedBytes,
            )
        }
        tlsIntervals++
    }

    fun completedAuthority(trial: Trial, steps: Int, commands: Int) {
        completions.add(trial.kind, trial.index, trial.seed, "authority_codec", steps, commands)
        authorityTrials++
    }

    fun completedTls(trial: Trial, commands: Int) {
        completions.add(trial.kind, trial.index, trial.seed, "real_tls", null, commands)
        tlsTrials++
    }

    fun write(completed: Boolean) {
        steps.write(options.output.resolve("authority-steps.csv"))
        messages.write(options.output.resolve("codec-messages.csv"))
        ruleViews.write(options.output.resolve("rule-views.csv"))
        tls.write(options.output.resolve("tls-payload-intervals.csv"))
        completions.write(options.output.resolve("completed-trials.csv"))
        val metadata = Csv("key,value")
        val values = linkedMapOf(
            "schema_version" to "1",
            "completed" to completed.toString(),
            "started_utc" to startedAt,
            "finished_utc" to Instant.now().toString(),
            "seed" to options.seed.toString(),
            "seats" to "6",
            "remote_guests" to "5",
            "warmup_trials_per_suite" to options.warmups.toString(),
            "sample_trials_per_suite" to options.samples.toString(),
            "completed_authority_trials" to authorityTrials.toString(),
            "completed_tls_trials" to tlsTrials.toString(),
            "observed_tls_intervals" to tlsIntervals.toString(),
            "idle_requested_ms" to options.idleMillis.toString(),
            "java_version" to System.getProperty("java.version"),
            "java_vendor" to System.getProperty("java.vendor"),
            "java_vm_name" to System.getProperty("java.vm.name"),
            "java_vm_version" to System.getProperty("java.vm.version"),
            "kotlin_version" to KotlinVersion.CURRENT.toString(),
            "os_name" to System.getProperty("os.name"),
            "os_version" to System.getProperty("os.version"),
            "os_arch" to System.getProperty("os.arch"),
            "available_processors" to Runtime.getRuntime().availableProcessors().toString(),
            "max_heap_bytes" to Runtime.getRuntime().maxMemory().toString(),
            "clock" to "System.nanoTime elapsed nanoseconds; not CPU time",
            "policy" to "All six seats play one received card, then challenge when available, otherwise play first card; host advances ended rounds",
            "randomness" to "Fresh Kotlin Random(seed) per table; same seed for warmup and sample trials",
            "tls_security_randomness" to "Real SecureRandom credentials and TLS identities; only test game RNG is seeded",
            "reference_rule_scope" to "Separate real LastLightEngine call before HostAuthority.handle; do not add durations",
            "authority_scope" to "HostAuthority.handle (INITIAL uses initialDispatch), including real rules and recipient view construction",
            "fanout_scope" to "Serial in-memory remote encode/decode loop including routing/timer/record overhead; no sockets",
            "host_local_scope" to "Host commands and deliveries use objects; blank codec fields mean no bytes encoded",
            "tls_scope" to "Application payload at successful send and incoming over real TLS; one JVM with six controllers",
            "tls_exclusions" to "Setup/admission; keepalives; four-byte framing; TLS records/handshake; TCP/IP/socket bytes",
            "tls_duration_scope" to "Fixture idle/full-match elapsed time including controller work, convergence polling and assertions",
            "byte_accounting" to "Each delivery appears at sender and receiver; sum sent OR received, never both",
            "output_privacy" to "Fixed categories, counts and durations only; no cards, DTOs, credentials, hosts or environment dump",
            "qualification" to "Exploratory JVM workload measurements; no device-performance threshold or hardware qualification",
        )
        for ((key, value) in values) metadata.add(key, value)
        metadata.write(options.output.resolve("metadata.csv"))
    }

    private class Csv(header: String) {
        private val content = StringBuilder(header).append('\n')

        fun add(vararg values: Any?) {
            content.append(values.joinToString(",") { value ->
                value?.toString()?.let { "\"${it.replace("\"", "\"\"")}\"" } ?: ""
            }).append('\n')
        }

        fun write(path: Path) {
            Files.writeString(path, content, StandardOpenOption.CREATE_NEW, StandardOpenOption.WRITE)
        }
    }
}
