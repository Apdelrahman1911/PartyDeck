package dev.partydeck.app

import dev.partydeck.app.controller.AppScreen
import dev.partydeck.app.controller.AppSettings
import dev.partydeck.app.controller.ConnectionStatus
import dev.partydeck.app.controller.Feedback
import dev.partydeck.app.controller.FeedbackCue
import dev.partydeck.app.controller.PartyDeckController
import dev.partydeck.app.controller.PlatformServices
import dev.partydeck.app.controller.SettingsStore
import dev.partydeck.core.AvailableActions
import dev.partydeck.core.Card
import dev.partydeck.core.CardRank
import dev.partydeck.core.GamePhase
import dev.partydeck.core.GameView
import dev.partydeck.core.LastLightRules
import dev.partydeck.core.RoundOutcome
import dev.partydeck.session.ClientIntent
import dev.partydeck.session.ClientMessage
import dev.partydeck.session.ServerMessage
import dev.partydeck.session.SessionCodec
import dev.partydeck.session.SessionControls
import dev.partydeck.session.SessionEndReason
import dev.partydeck.session.SessionPhase
import dev.partydeck.session.SessionView
import dev.partydeck.session.WireDecodeResult
import dev.partydeck.transport.ConnectionState
import dev.partydeck.transport.JvmLanTransportFactory
import dev.partydeck.transport.LanConnection
import dev.partydeck.transport.LanEndpoint
import dev.partydeck.transport.LanHost
import dev.partydeck.transport.LanInvitation
import dev.partydeck.transport.LanTransport
import dev.partydeck.transport.LanTransportFactory
import java.net.ConnectException
import java.net.InetSocketAddress
import java.net.Socket
import java.security.SecureRandom
import java.util.concurrent.CopyOnWriteArrayList
import java.util.concurrent.atomic.AtomicBoolean
import java.util.concurrent.atomic.AtomicInteger
import java.util.concurrent.atomic.AtomicReference
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.CoroutineExceptionHandler
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.NonCancellable
import kotlinx.coroutines.TimeoutCancellationException
import kotlinx.coroutines.coroutineScope
import kotlinx.coroutines.currentCoroutineContext
import kotlinx.coroutines.delay
import kotlinx.coroutines.ensureActive
import kotlinx.coroutines.flow.map
import kotlinx.coroutines.flow.onEach
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.withContext
import kotlinx.coroutines.withTimeout
import kotlin.random.Random
import kotlin.random.asKotlinRandom
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertNotNull
import kotlin.test.assertNull
import kotlin.test.assertTrue

/**
 * Real controller -> protocol -> JSSE/TLS -> remote controller integration. No alternate rules,
 * authority, framing, certificate verifier, or transport driver is supplied by these tests.
 *
 * Verified API references (2026-09-09):
 * https://kotlinlang.org/api/kotlinx.coroutines/kotlinx-coroutines-core/kotlinx.coroutines/run-blocking.html
 * https://kotlinlang.org/api/kotlinx.coroutines/kotlinx-coroutines-core/kotlinx.coroutines/with-timeout.html
 * https://kotlinlang.org/api/kotlinx.coroutines/kotlinx-coroutines-core/kotlinx.coroutines.flow/on-each.html
 * https://docs.oracle.com/en/java/javase/21/docs/api/java.base/java/security/SecureRandom.html
 * https://kotlinlang.org/api/core/kotlin-stdlib/kotlin.random/as-kotlin-random.html
 *
 * runBlocking supplies a serial owner event loop; production native TLS still uses real IO threads.
 * All waits use real time because production dispatchers and sockets do not use virtual test time.
 */
class LanMultiplayerIntegrationTest {
    @Test
    fun sixRealTlsSeatsFinishRematchAndRehostUsingTheSameControllers() = runBlocking {
        withRealTable(seatCount = LastLightRules.MAX_PLAYERS, timeoutMillis = 120_000) { table ->
            table.playSixSeatsToWinner()
            table.rematchAndRehost()
        }
    }

    /** Opt-in measurements reuse the real fixture; only the rules RNG is seeded. */
    internal suspend fun measureSixSeatTls(
        seed: Int,
        idleMillis: Long,
        onInterval: (TlsPayloadInterval) -> Unit,
    ) = coroutineScope {
        require(idleMillis in 1..(Long.MAX_VALUE - 120_000))
        withRealTable(
            seatCount = LastLightRules.MAX_PLAYERS,
            timeoutMillis = 120_000 + idleMillis,
            gameSeed = seed,
        ) { table ->
            val idleBefore = table.settledPayloads()
            val idleRevision = table.host.session().revision
            val idleStarted = System.nanoTime()
            delay(idleMillis)
            val idleAfter = table.settledPayloads()
            val idleElapsed = System.nanoTime() - idleStarted
            assertEquals(idleRevision, table.host.session().revision, "Idle changed authority state")
            onInterval(TlsPayloadInterval(
                TlsMeasurementPhase.IDLE, idleElapsed, idleRevision, idleRevision, 0,
                idleAfter.zip(idleBefore) { after, before -> after - before },
            ))

            val activeBefore = table.settledPayloads()
            val activeRevision = table.host.session().revision
            val activeStarted = System.nanoTime()
            val acceptedCommands = table.playSixSeatsToWinner()
            val activeAfter = table.settledPayloads()
            val activeElapsed = System.nanoTime() - activeStarted
            assertEquals(acceptedCommands.toLong(), table.host.session().revision - activeRevision)
            onInterval(TlsPayloadInterval(
                TlsMeasurementPhase.ACTIVE, activeElapsed, activeRevision, table.host.session().revision,
                acceptedCommands, activeAfter.zip(activeBefore) { after, before -> after - before },
            ))
        }
    }

    @Test
    fun realTlsGuestsPlayPrivateHandsResolveAChallengeRedealAndReleaseTheListener() = runBlocking {
        withRealTable { table ->
            val initial = table.sessions()
            val initialHands = initial.associate { it.selfPlayerId to assertNotNull(it.game).yourHand }
            assertEquals(3, initialHands.size)
            assertTrue(initialHands.values.all { it.size == 5 })
            assertEquals(15, initialHands.values.flatten().map { it.id }.toSet().size)
            assertTrue(initial.all { it.players == initial.first().players })
            table.assertPrivateWireViews(initialHands, roundNumber = 1)

            // Every seat submits one of its received cards, proving the private ownership mapping
            // actually works across both remote links rather than only looking plausible in UI.
            val claims = List(3) { table.playOneCard() }
            assertEquals(3, claims.map { it.playerId }.toSet().size)
            assertTrue(table.sessions().all { assertNotNull(it.game).yourHand.size == 4 })
            table.assertPrivateWireViews(initialHands, roundNumber = 1)

            val finalClaim = claims.last()
            val challenger = table.currentActor()
            val challengerId = challenger.session().selfPlayerId
            val truthful = finalClaim.card.rank == CardRank.WILD || finalClaim.card.rank == finalClaim.tableRank
            val expectedLoser = if (truthful) challengerId else finalClaim.playerId
            table.perform("challenge reaches every recipient") { challenger.controller.challenge() }
            val ended = table.sessions()
            val outcome = assertNotNull(ended.first().game?.roundOutcome)

            // Three players guarantee a redeal remains possible even if the first penalty burns out.
            assertTrue(ended.all { it.game?.phase == GamePhase.ROUND_ENDED })
            assertTrue(ended.all { it.game?.roundOutcome == outcome })
            assertEquals(listOf(finalClaim.card), outcome.revealedCards)
            assertEquals(finalClaim.playerId, outcome.claimantId)
            assertEquals(challengerId, outcome.challengerId)
            assertEquals(truthful, outcome.truthful)
            assertEquals(expectedLoser, outcome.penalizedPlayerId)
            assertEquals(1, outcome.penaltyAttempt)
            assertTrue(table.host.session().controls.canAdvanceRound)
            table.assertPrivateWireViews(initialHands, roundNumber = 1)

            table.perform("host explicitly starts the next round") { table.host.controller.nextRound() }
            val next = table.sessions()
            val oldIds = initialHands.values.flatten().map { it.id }.toSet()
            for (view in next) {
                val game = assertNotNull(view.game)
                val self = game.players.single { it.id == view.selfPlayerId }
                assertEquals(GamePhase.PLAYING, game.phase)
                assertEquals(2, game.roundNumber)
                assertEquals(if (self.eliminated) 0 else 5, game.yourHand.size)
                assertTrue(game.yourHand.none { it.id in oldIds })
                assertEquals(outcome, game.roundOutcome)
                assertNull(game.latestClaim)
            }
            assertEquals(
                ended.first().game?.players?.map { it.penaltyAttempts },
                next.first().game?.players?.map { it.penaltyAttempts },
            )

            val leaving = table.guests.last()
            val leavingId = leaving.session().selfPlayerId
            val leavingWasActive = next.first().game!!.players.single { it.id == leavingId }.eliminated.not()
            leaving.controller.leaveSession()
            table.until("guest leaves and closes its real transport") {
                leaving.controller.state.value.session == null && leaving.transport.allClosed() &&
                    table.host.session().players.single { it.id == leavingId }.isConnected.not()
            }
            assertEquals(AppScreen.HOME, leaving.controller.state.value.screen)
            assertEquals(leavingWasActive, leavingId in table.host.session().pausedPlayerIds)
            assertTrue(leaving.transport.commands.any { it.intent == ClientIntent.Leave })

            table.host.controller.leaveSession()
            val remainingGuest = table.guests.first()
            table.until("host termination reaches the remaining guest") {
                table.host.controller.state.value.session == null && table.host.transport.allClosed() &&
                    remainingGuest.controller.state.value.connection.status == ConnectionStatus.DISCONNECTED &&
                    remainingGuest.controller.state.value.session?.phase == SessionPhase.ENDED
            }
            assertNull(table.host.controller.state.value.invitation)
            table.assertListenerClosed()
            remainingGuest.controller.leaveSession()
            table.until("remaining guest releases its transport") { remainingGuest.transport.allClosed() }
        }
    }

    @Test
    fun interruptedRealTlsLinkResumesTheSamePrivateTurnAndUsesAFreshCommandId() = runBlocking {
        withRealTable { table ->
            val guest = table.guests.first()
            val guestId = guest.session().selfPlayerId
            repeat(2) {
                if (table.currentActor() !== guest) table.playOneCard()
            }
            assertEquals(guestId, table.currentActor().session().selfPlayerId)
            val before = guest.session()
            val beforeGame = assertNotNull(before.game)
            val privateHand = beforeGame.yourHand
            val oldLink = guest.transport.connections.single()
            val commandCount = guest.transport.commands.size
            val previousCommandId = guest.transport.commands.maxOf { it.id }
            val gate = guest.transport.holdNewConnections()

            // Close an actual established TLS link, then hold only subsequent connect attempts.
            // No synthetic snapshot, authority state, or successful connection is injected.
            oldLink.close()
            table.until("host pauses while the real client link is absent") {
                guestId in table.host.session().pausedPlayerIds &&
                    guest.controller.state.value.connection.status != ConnectionStatus.CONNECTED &&
                    table.devices.filter { it !== guest }.all { guestId in it.session().pausedPlayerIds }
            }
            val pausedHost = table.host.session()
            assertEquals(beforeGame.turnPlayerId, pausedHost.game?.turnPlayerId)
            assertEquals(beforeGame.latestClaim, pausedHost.game?.latestClaim)
            assertEquals(privateHand, guest.controller.state.value.session?.game?.yourHand)
            assertTrue(table.devices.filter { it !== guest }.all {
                it.session().game?.availableActions?.let { actions -> !actions.canPlay && !actions.canChallenge } == true
            })
            assertEquals(commandCount, guest.transport.commands.size)

            gate.complete(Unit)
            table.awaitSynchronized("same seat resumes through a new pinned TLS connection", minimumRevision = before.revision + 2)
            val resumed = guest.session()
            assertEquals(before.selfPlayerId, resumed.selfPlayerId)
            assertEquals(before.sessionId, resumed.sessionId)
            assertEquals(privateHand, resumed.game?.yourHand)
            assertEquals(beforeGame.turnPlayerId, resumed.game?.turnPlayerId)
            assertEquals(beforeGame.latestClaim, resumed.game?.latestClaim)
            assertEquals(beforeGame.players, resumed.game?.players)
            assertTrue(resumed.pausedPlayerIds.isEmpty())
            assertEquals(2, guest.transport.connections.size)
            assertTrue(guest.transport.connections.last().id != oldLink.id)
            assertTrue(oldLink.state.value != ConnectionState.Connected)
            assertEquals(listOf("join", "resume"), guest.transport.hellos.toList())
            assertEquals(commandCount, guest.transport.commands.size, "Reconnect replayed a gameplay command")

            val selected = privateHand.first()
            table.perform("resumed player submits exactly one new action") {
                guest.controller.playCards(listOf(selected.id))
            }
            val sent = guest.transport.commands.drop(commandCount).single()
            assertTrue(sent.id > previousCommandId)
            assertEquals(resumed.revision, sent.expectedRevision)
            assertEquals(ClientIntent.PlayCards(listOf(selected.id)), sent.intent)
            assertEquals(privateHand.filterNot { it.id == selected.id }, guest.session().game?.yourHand)
            assertEquals(resumed.revision + 1, guest.session().revision)
            assertEquals(guestId, table.host.session().game?.latestClaim?.playerId)
        }
    }

    private suspend fun CoroutineScope.withRealTable(
        seatCount: Int = 3,
        timeoutMillis: Long = 45_000,
        gameSeed: Int? = null,
        block: suspend (RealTable) -> Unit,
    ) {
        val table = RealTable(this, seatCount, gameSeed)
        try {
            withTimeout(timeoutMillis) {
                table.start()
                block(table)
                table.assertNoAsyncFailures()
            }
        } finally {
            withContext(NonCancellable) { table.close() }
        }
    }

    private class RealTable(parentScope: CoroutineScope, seatCount: Int, gameSeed: Int?) {
        private val failures = CopyOnWriteArrayList<Throwable>()
        private val owner = CoroutineScope(parentScope.coroutineContext + CoroutineExceptionHandler { _, error -> failures.add(error) })
        val devices = listOf("Host Ada", "Guest Bo", "Guest Cy", "Guest Dee", "Guest Eli", "Guest Fay")
            .take(seatCount).map { Device(it, owner, gameSeed) }
        val host = devices.first()
        val guests = devices.drop(1)
        private val privacy = if (seatCount == LastLightRules.MAX_PLAYERS) RecipientAudit(devices) else null
        private var listenerEndpoint: LanEndpoint? = null

        suspend fun start() {
            for (device in devices) {
                until("${device.name} preferences load") { device.controller.state.value.displayName == device.name }
                device.controller.setDisplayName(device.name)
            }
            host.controller.navigate(AppScreen.HOST)
            host.controller.host()
            awaitSynchronized("real TLS host is ready", participants = listOf(host))
            val text = assertNotNull(host.controller.state.value.invitation).joinAddress
            val invitation = LanInvitation.decode(text)
            listenerEndpoint = invitation.endpoint
            assertEquals(host.session().sessionId, invitation.sessionId)
            assertEquals(64, invitation.certificateSha256.length)
            for ((index, guest) in guests.withIndex()) {
                guest.controller.navigate(AppScreen.JOIN)
                guest.controller.setJoinAddress(text)
                guest.controller.join()
                awaitSynchronized("guest ${index + 1} is admitted", participants = devices.take(index + 2))
                assertEquals(invitation.sessionId, guest.session().sessionId)
                assertNull(guest.controller.state.value.invitation)
            }
            assertTrue(sessions().all { it.players.size == devices.size && it.phase == SessionPhase.LOBBY })
            privacy?.record(sessions())
            readyAndStart()
        }

        private suspend fun readyAndStart() {
            for (guest in guests) perform("${guest.name} becomes ready") { guest.controller.setReady(true) }
            assertTrue(host.session().controls.canStartGame)
            assertTrue(guests.none { it.session().controls.canStartGame })
            perform("host starts the real shared game") { host.controller.startGame() }
            assertTrue(sessions().all { it.phase == SessionPhase.GAME && it.game?.phase == GamePhase.PLAYING })
        }

        suspend fun playSixSeatsToWinner(): Int {
            assertEquals(LastLightRules.MAX_PLAYERS, devices.size)
            val firstOrbit = List(devices.size) { playOneCard() }
            assertEquals(devices.size, firstOrbit.map { it.playerId }.toSet().size)
            assertTrue(sessions().all { it.game?.yourHand?.size == LastLightRules.HAND_SIZE - 1 })
            var acceptedCommands = devices.size
            val commandBound = devices.size + devices.size * LastLightRules.FUSE_LIGHTS * 3
            while (host.session().game?.phase != GamePhase.FINISHED) {
                assertTrue(acceptedCommands < commandBound, "Legal match exceeded its finite fuse budget")
                if (host.session().game?.phase == GamePhase.ROUND_ENDED) {
                    assertTrue(host.session().controls.canAdvanceRound)
                    perform("host advances the ended round") { host.controller.nextRound() }
                } else {
                    val actor = currentActor()
                    if (assertNotNull(actor.session().game).availableActions.canChallenge) {
                        perform("current recipient challenges the last claim") { actor.controller.challenge() }
                    } else {
                        playOneCard()
                    }
                }
                acceptedCommands++
            }
            val finished = assertNotNull(host.session().game)
            val survivor = finished.players.single { !it.eliminated }
            assertEquals(devices.size - 1, finished.players.count { it.eliminated })
            assertEquals(survivor.id, finished.winnerId)
            assertTrue(sessions().all {
                val game = it.game
                game?.phase == GamePhase.FINISHED && game.winnerId == survivor.id &&
                    game.availableActions == AvailableActions()
            })
            assertTrue(host.session().controls.canReturnToLobby)
            settledPayloads()
            return acceptedCommands
        }

        suspend fun rematchAndRehost() {
            val originalSession = host.session().sessionId
            val originalBindings = sessions().map { it.selfPlayerId }
            val originalInvitation = assertNotNull(host.controller.state.value.invitation).joinAddress
            val originalConnections = devices.map { it.transport.connections.toList() }
            assertTrue(guests.all { it.transport.hellos.toList() == listOf("join") })
            assertEquals(guests.size, originalConnections.first().size)
            assertTrue(originalConnections.drop(1).all { it.size == 1 })

            perform("winner returns all seats to the lobby") { host.controller.returnToLobby() }
            assertTrue(sessions().all { it.phase == SessionPhase.LOBBY && it.game == null })
            assertEquals(originalBindings, sessions().map { it.selfPlayerId })
            assertTrue(sessions().all { it.sessionId == originalSession })
            assertTrue(host.session().players.single { it.id == host.session().selfPlayerId }.isReady)
            assertTrue(host.session().players.filter { it.id != host.session().selfPlayerId }.none { it.isReady })
            assertTrue(sessions().none { it.controls.canStartGame })
            readyAndStart()
            assertEquals(originalBindings, sessions().map { it.selfPlayerId })
            assertTrue(sessions().all { it.sessionId == originalSession })
            assertEquals(devices.size, List(devices.size) { playOneCard().playerId }.toSet().size)

            endSessionAndReturnHome()
            assertTrue(originalConnections.flatten().all { it.state.value != ConnectionState.Connected })
            start()
            assertTrue(host.session().sessionId != originalSession, "Rehosting reused a session identity")
            assertTrue(host.controller.state.value.invitation?.joinAddress != originalInvitation,
                "Rehosting reused an invitation")
            assertEquals(guests.size * 2, host.transport.connections.size)
            for (guest in guests) {
                assertEquals(2, guest.transport.connections.size)
                assertEquals(listOf("join", "join"), guest.transport.hellos.toList())
            }
            assertEquals(devices.size, List(devices.size) { playOneCard().playerId }.toSet().size)
            endSessionAndReturnHome()
        }

        private suspend fun endSessionAndReturnHome() {
            settledPayloads()
            val endingSession = host.session().sessionId
            host.controller.leaveSession()
            until("host termination reaches all five authenticated guests") {
                host.controller.state.value.session == null && host.transport.allClosed() && guests.all {
                    it.controller.state.value.connection.status == ConnectionStatus.DISCONNECTED &&
                        it.controller.state.value.session?.phase == SessionPhase.ENDED &&
                        it.transport.ended.any { message ->
                            message.sessionId == endingSession && message.reason == SessionEndReason.HOST_ENDED
                        }
                }
            }
            assertNull(host.controller.state.value.invitation)
            guests.forEach { it.controller.leaveSession() }
            until("all six devices return Home and release their transports") {
                devices.all {
                    it.controller.state.value.screen == AppScreen.HOME &&
                        it.controller.state.value.session == null && it.transport.allClosed() &&
                        it.transport.connections.all { connection -> connection.state.value != ConnectionState.Connected }
                }
            }
            privacy?.verifyWireViews()
            assertListenerClosed()
        }

        suspend fun settledPayloads(): List<ApplicationPayloadSnapshot> {
            awaitSynchronized("controller revisions settle before payload observation")
            var settled: List<ApplicationPayloadSnapshot>? = null
            until("successful sends and delivered payloads balance at all endpoints") {
                val snapshots = devices.map { it.transport.payloads.snapshot() }
                val hostPayloads = snapshots.first()
                val guestPayloads = snapshots.drop(1)
                val balanced = hostPayloads.sentMessages == guestPayloads.sumOf { it.receivedMessages } &&
                    hostPayloads.sentBytes == guestPayloads.sumOf { it.receivedBytes } &&
                    hostPayloads.receivedMessages == guestPayloads.sumOf { it.sentMessages } &&
                    hostPayloads.receivedBytes == guestPayloads.sumOf { it.sentBytes }
                if (balanced) settled = snapshots
                balanced
            }
            privacy?.verifyWireViews()
            return assertNotNull(settled)
        }

        fun sessions(): List<SessionView> = devices.map { it.session() }

        fun currentActor(): Device {
            val actor = assertNotNull(host.session().game?.turnPlayerId)
            return devices.single { it.session().selfPlayerId == actor }
        }

        suspend fun playOneCard(): PlayedClaim {
            val actor = currentActor()
            val game = assertNotNull(actor.session().game)
            assertTrue(game.availableActions.canPlay)
            val card = game.yourHand.first()
            val claim = PlayedClaim(actor.session().selfPlayerId, card, game.tableRank)
            perform("${actor.name} plays its received private card", playedClaim = claim) {
                actor.controller.playCards(listOf(card.id))
            }
            assertEquals(game.yourHand.size - 1, actor.session().game?.yourHand?.size)
            assertTrue(sessions().all { it.game?.latestClaim?.playerId == claim.playerId })
            return claim
        }

        suspend fun perform(label: String, playedClaim: PlayedClaim? = null, action: () -> Unit) {
            awaitSynchronized("ready before $label")
            val beforeViews = sessions()
            val before = host.session().revision
            val commandCounts = guests.map { it.transport.commands.size }
            val receiptCounts = guests.map { it.transport.receipts.size }
            action()
            awaitSynchronized(label, minimumRevision = before + 1)
            assertEquals(before + 1, host.session().revision, "One action changed more than one authority revision")
            devices.forEach { assertNull(it.controller.state.value.problem, "$label reported a UI problem") }
            if (privacy != null) {
                var remoteCommands = 0
                for ((index, guest) in guests.withIndex()) {
                    val commands = guest.transport.commands.toList().drop(commandCounts[index])
                    val receipts = guest.transport.receipts.toList().drop(receiptCounts[index])
                    remoteCommands += commands.size
                    assertTrue(commands.size <= 1 && receipts.size == commands.size,
                        "One accepted action must have one matching remote receipt")
                    commands.singleOrNull()?.let { command ->
                        val receipt = receipts.single()
                        assertEquals(before, command.expectedRevision)
                        assertEquals(guest.session().sessionId, receipt.sessionId)
                        assertEquals(command.id, receipt.receipt.commandId)
                        assertEquals(before + 1, receipt.receipt.revision)
                        assertTrue(receipt.receipt.accepted, "A generated legal command was rejected")
                    }
                }
                assertTrue(remoteCommands <= 1, "One action sent commands from more than one guest")
                privacy.record(sessions(), beforeViews, playedClaim)
            }
        }

        suspend fun awaitSynchronized(label: String, minimumRevision: Long = 0, participants: List<Device> = devices) {
            until(label) {
                val states = participants.map { it.controller.state.value }
                val views = states.mapNotNull { it.session }
                views.size == states.size && states.all {
                    it.connection.status == ConnectionStatus.CONNECTED && it.pendingAction == null
                } && views.all { it.revision >= minimumRevision } &&
                    views.map { it.revision }.distinct().size == 1 && views.map { it.sessionId }.distinct().size == 1
            }
        }

        suspend fun until(label: String, condition: suspend () -> Boolean) {
            try {
                withTimeout(15_000) {
                    while (!condition()) {
                        assertNoAsyncFailures()
                        delay(10)
                    }
                }
            } catch (timedOut: TimeoutCancellationException) {
                currentCoroutineContext().ensureActive()
                throw AssertionError("Timed out: $label. ${diagnostics()}", timedOut)
            }
        }

        fun assertPrivateWireViews(initialHands: Map<String, List<Card>>, roundNumber: Int) {
            for (guest in guests) {
                val owner = guest.session().selfPlayerId
                val allowedHand = initialHands.getValue(owner).toSet()
                val wireViews = guest.transport.receivedViews.filter { it.game?.roundNumber == roundNumber }
                assertTrue(wireViews.isNotEmpty(), "No real game snapshot arrived on the guest TLS link")
                for (view in wireViews) {
                    assertEquals(owner, view.selfPlayerId)
                    assertEquals(owner, view.game?.viewerId)
                    assertTrue(assertNotNull(view.game).yourHand.all { it in allowedHand }, "Another seat's hand reached this recipient")
                }
                assertEquals(0, guest.transport.decodeFailures.get(), "A production wire message violated the protocol")
            }
        }

        suspend fun assertListenerClosed() {
            val endpoint = listenerEndpoint ?: return
            until("closed host port rejects new TCP connections") {
                withContext(Dispatchers.IO) {
                    try {
                        Socket().use { it.connect(InetSocketAddress(endpoint.host, endpoint.port), 250) }
                        false
                    } catch (_: ConnectException) {
                        true
                    }
                }
            }
        }

        fun assertNoAsyncFailures() {
            assertTrue(failures.isEmpty(), "Uncaught controller failure: ${failures.map { it.javaClass.simpleName }}")
        }

        suspend fun close() {
            devices.forEach {
                it.transport.releaseNewConnections()
                it.controller.close()
            }
            try {
                withTimeout(10_000) { devices.forEach { it.controller.awaitClosed() } }
                assertNoAsyncFailures()
                devices.forEach { device ->
                    assertTrue(device.transport.allClosed(), "${device.name} left an owned transport open")
                    assertTrue(device.transport.connections.all { it.state.value != ConnectionState.Connected })
                    assertTrue(device.services.feedbackClosed.get())
                }
                assertListenerClosed()
            } finally {
                // A failed cleanup assertion still releases real sockets so a failed test cannot
                // contaminate other suites. This runs only after controller cleanup was checked.
                devices.forEach { it.transport.closeRemainingTransports() }
            }
        }

        private fun diagnostics(): String = devices.joinToString("; ") {
            val state = it.controller.state.value
            "${it.name}: connection=${state.connection.status}, phase=${state.session?.phase}, " +
                "revision=${state.session?.revision}, pending=${state.pendingAction}, problem=${state.problem?.code}"
        }
    }

    /** Checks received projections and real submitted cards, without creating a second authority. */
    private class RecipientAudit(private val devices: List<Device>) {
        private data class RevisionKey(val sessionId: String, val revision: Long)
        private data class MatchKey(val sessionId: String, val startRevision: Long)
        private data class RoundKey(val match: MatchKey, val round: Int)
        private data class Roster(val firstFullRevision: Long, val owners: List<String>)

        private val rosters = mutableMapOf<String, Roster>()
        private val revisions = mutableMapOf<RevisionKey, Map<String, SessionView>>()
        private val dealtHands = mutableMapOf<RoundKey, Map<String, List<Card>>>()
        private val publicOutcomes = mutableMapOf<RoundKey, RoundOutcome>()
        private val wireCursors = IntArray(devices.size)
        private var match: MatchKey? = null
        private var pendingClaim: PlayedClaim? = null

        fun record(views: List<SessionView>, before: List<SessionView>? = null, playedClaim: PlayedClaim? = null) {
            val reference = views.first()
            val roster = rosters.getOrPut(reference.sessionId) {
                Roster(reference.revision, views.map { it.selfPlayerId })
            }
            assertEquals(devices.size, roster.owners.toSet().size)
            for ((index, view) in views.withIndex()) {
                assertEquals(roster.owners[index], view.selfPlayerId)
                assertEquals(devices[index].name, view.players.single { it.id == view.selfPlayerId }.displayName)
                assertTrue(view.players.all { it.isConnected } && view.pausedPlayerIds.isEmpty())
                assertTrue(publicProjection(view) == publicProjection(reference),
                    "Recipient snapshots disagree on public state")
                if (index != 0) assertEquals(SessionControls(), view.controls)
                view.game?.let { game ->
                    assertEquals(view.selfPlayerId, game.viewerId)
                    val self = game.players.single { it.id == view.selfPlayerId }
                    assertEquals(self.handCount, game.yourHand.size)
                    assertTrue(!self.eliminated || game.yourHand.isEmpty(), "Eliminated recipient retained a hand")
                    if (game.phase != GamePhase.PLAYING || game.turnPlayerId != view.selfPlayerId || self.eliminated) {
                        assertEquals(AvailableActions(), game.availableActions)
                    }
                }
            }

            val game = reference.game
            val previous = before?.first()?.game
            if (game == null) {
                assertEquals(SessionPhase.LOBBY, reference.phase)
                match = null
                pendingClaim = null
            } else {
                assertEquals(SessionPhase.GAME, reference.phase)
                if (previous == null) {
                    match = MatchKey(reference.sessionId, reference.revision)
                    assertEquals(GamePhase.PLAYING, game.phase)
                    assertEquals(1, game.roundNumber)
                    assertNull(game.latestClaim)
                    assertNull(game.roundOutcome)
                    assertNull(game.winnerId)
                    assertTrue(game.players.all { !it.eliminated && it.penaltyAttempts == 0 })
                }
                val currentMatch = assertNotNull(match)
                assertEquals(reference.sessionId, currentMatch.sessionId)
                val round = RoundKey(currentMatch, game.roundNumber)
                if (previous == null || previous.roundNumber != game.roundNumber) {
                    if (previous != null) {
                        assertEquals(GamePhase.ROUND_ENDED, previous.phase)
                        assertEquals(previous.roundNumber + 1, game.roundNumber)
                        assertEquals(GamePhase.PLAYING, game.phase)
                        assertNull(game.latestClaim)
                        val oldCards = dealtHands.getValue(RoundKey(currentMatch, previous.roundNumber))
                            .values.flatten().map { it.id }.toSet()
                        assertTrue(views.all { view -> view.game!!.yourHand.none { it.id in oldCards } },
                            "A redeal reused a previous round card")
                    }
                    val hands = views.associate { it.selfPlayerId to assertNotNull(it.game).yourHand }
                    for (view in views) {
                        val own = assertNotNull(view.game)
                        val eliminated = own.players.single { it.id == view.selfPlayerId }.eliminated
                        assertEquals(if (eliminated) 0 else LastLightRules.HAND_SIZE, own.yourHand.size)
                    }
                    val ids = hands.values.flatten().map { it.id }
                    assertEquals(ids.size, ids.toSet().size, "Dealt private hands overlap")
                    assertTrue(round !in dealtHands, "A fresh match/round reused an audit boundary")
                    dealtHands[round] = hands
                    pendingClaim = null
                } else {
                    val oldViews = assertNotNull(before).associateBy { it.selfPlayerId }
                    for (view in views) {
                        val own = assertNotNull(view.game)
                        val oldHand = assertNotNull(oldViews.getValue(view.selfPlayerId).game).yourHand
                        val expectedHand = when {
                            own.players.single { it.id == view.selfPlayerId }.eliminated -> emptyList()
                            playedClaim?.playerId == view.selfPlayerId -> oldHand.filterNot { it.id == playedClaim.card.id }
                            else -> oldHand
                        }
                        assertTrue(expectedHand == own.yourHand, "A received hand changed outside its accepted action")
                    }
                    if (playedClaim != null) {
                        val actor = assertNotNull(oldViews.getValue(playedClaim.playerId).game)
                        assertTrue(playedClaim.card in actor.yourHand, "Play did not use the actor's received card")
                        assertEquals(previous.turnPlayerId, playedClaim.playerId)
                        assertEquals(playedClaim.playerId, game.latestClaim?.playerId)
                        assertEquals(1, game.latestClaim?.cardCount)
                        pendingClaim = playedClaim
                    } else if (previous.phase == GamePhase.PLAYING && game.phase != GamePhase.PLAYING) {
                        val claim = assertNotNull(pendingClaim, "Challenge has no observed private-card submission")
                        val outcome = assertNotNull(game.roundOutcome)
                        val truthful = claim.card.rank == CardRank.WILD || claim.card.rank == claim.tableRank
                        val loser = if (truthful) previous.turnPlayerId else claim.playerId
                        assertEquals(game.roundNumber, outcome.roundNumber)
                        assertEquals(claim.tableRank, outcome.tableRank)
                        assertEquals(claim.playerId, outcome.claimantId)
                        assertEquals(previous.turnPlayerId, outcome.challengerId)
                        assertTrue(outcome.revealedCards == listOf(claim.card),
                            "Public outcome revealed cards outside the challenged claim")
                        assertEquals(truthful, outcome.truthful)
                        assertEquals(loser, outcome.penalizedPlayerId)
                        assertEquals(previous.players.single { it.id == loser }.penaltyAttempts + 1, outcome.penaltyAttempt)
                        publicOutcomes[round] = outcome
                        pendingClaim = null
                    }
                }
                for (view in views) {
                    val own = assertNotNull(view.game)
                    val allowed = dealtHands.getValue(round).getValue(view.selfPlayerId).toSet()
                    assertTrue(own.yourHand.all { it in allowed }, "Another seat's dealt cards reached this recipient")
                    own.roundOutcome?.let { outcome ->
                        assertTrue(publicOutcomes[RoundKey(currentMatch, outcome.roundNumber)] == outcome,
                            "Recipient received an unverified public reveal")
                    }
                }
            }
            revisions[RevisionKey(reference.sessionId, reference.revision)] = views.associateBy { it.selfPlayerId }
            verifyWireViews()
        }

        fun verifyWireViews() {
            for (index in 1 until devices.size) {
                val transport = devices[index].transport
                // Copy once, then advance only to that copy's size; concurrent arrivals stay pending.
                val received = transport.receivedViews.toList()
                for (view in received.drop(wireCursors[index])) {
                    val roster = assertNotNull(rosters[view.sessionId], "Wire snapshot belongs to an unknown session")
                    val owner = roster.owners[index]
                    assertEquals(owner, view.selfPlayerId)
                    val accepted = revisions[RevisionKey(view.sessionId, view.revision)]?.get(owner)
                    if (accepted == null) {
                        assertTrue(view.revision < roster.firstFullRevision &&
                            view.phase == SessionPhase.LOBBY && view.game == null,
                            "Wire snapshot has no accepted authority revision")
                    } else {
                        assertTrue(view == accepted, "Wire snapshot differs from its recipient's verified projection")
                    }
                }
                assertEquals(0, transport.decodeFailures.get(), "A real TLS payload violated the production codec")
                wireCursors[index] = received.size
            }
        }

        private fun publicProjection(view: SessionView): SessionView = view.copy(
            selfPlayerId = "",
            controls = SessionControls(),
            game = view.game?.copy(viewerId = null, yourHand = emptyList(), availableActions = AvailableActions()),
        )
    }

    private class Device(val name: String, scope: CoroutineScope, gameSeed: Int?) {
        val services = SilentSecureServices(name, gameSeed)
        val transport = ObservedRealTransportFactory()
        val controller = PartyDeckController(services, transport, scope)
        fun session(): SessionView = assertNotNull(controller.state.value.session, "$name has no active session")
    }

    private data class PlayedClaim(val playerId: String, val card: Card, val tableRank: CardRank)
    private data class SentCommand(val id: Long, val expectedRevision: Long, val intent: ClientIntent)

    /** Transparent observers; every successful connection is returned by the production factory. */
    private class ObservedRealTransportFactory : LanTransportFactory {
        private val production = JvmLanTransportFactory()
        private val transports = CopyOnWriteArrayList<ObservedTransport>()
        private val gate = AtomicReference<CompletableDeferred<Unit>?>(null)
        val connections = CopyOnWriteArrayList<LanConnection>()
        val receivedViews = CopyOnWriteArrayList<SessionView>()
        val receipts = CopyOnWriteArrayList<ServerMessage.Receipt>()
        val ended = CopyOnWriteArrayList<ServerMessage.Ended>()
        val payloads = ApplicationPayloadMeter()
        val commands = CopyOnWriteArrayList<SentCommand>()
        val hellos = CopyOnWriteArrayList<String>()
        val decodeFailures = AtomicInteger()

        override fun create(): LanTransport = ObservedTransport(production.create()).also { transports.add(it) }
        fun allClosed(): Boolean = transports.all { it.closed.get() }
        fun holdNewConnections(): CompletableDeferred<Unit> = CompletableDeferred<Unit>().also { gate.set(it) }
        fun releaseNewConnections() { gate.getAndSet(null)?.complete(Unit) }

        suspend fun closeRemainingTransports() {
            transports.filterNot { it.closed.get() }.forEach { it.close() }
        }

        private inner class ObservedTransport(private val delegate: LanTransport) : LanTransport by delegate {
            val closed = AtomicBoolean()

            override suspend fun host(displayName: String): LanHost {
                val host = delegate.host(displayName)
                return object : LanHost by host {
                    override val incomingConnections = host.incomingConnections.map { observe(it, clientSide = false) }
                }
            }

            override suspend fun connect(endpoint: LanEndpoint, certificateSha256: String): LanConnection {
                gate.get()?.await()
                return observe(delegate.connect(endpoint, certificateSha256), clientSide = true)
            }

            override suspend fun close() {
                delegate.close()
                closed.set(true)
            }
        }

        private fun observe(delegate: LanConnection, clientSide: Boolean): LanConnection {
            val observed = object : LanConnection by delegate {
                override val incoming = delegate.incoming.onEach { bytes ->
                    payloads.received(bytes.size)
                    if (clientSide) when (val decoded = SessionCodec.decodeServer(bytes)) {
                        is WireDecodeResult.Success -> when (val message = decoded.value) {
                            is ServerMessage.Welcome -> receivedViews.add(message.view)
                            is ServerMessage.Snapshot -> receivedViews.add(message.view)
                            is ServerMessage.Receipt -> receipts.add(message)
                            is ServerMessage.Ended -> ended.add(message)
                            else -> Unit
                        }
                        is WireDecodeResult.Failure -> decodeFailures.incrementAndGet()
                    }
                }

                override suspend fun send(bytes: ByteArray) {
                    if (clientSide) when (val decoded = SessionCodec.decodeClient(bytes)) {
                        is WireDecodeResult.Success -> when (val message = decoded.value) {
                            is ClientMessage.Join -> hellos.add("join")
                            is ClientMessage.Resume -> hellos.add("resume")
                            is ClientMessage.Command -> commands.add(SentCommand(message.commandId, message.expectedRevision, message.intent))
                        }
                        is WireDecodeResult.Failure -> decodeFailures.incrementAndGet()
                    }
                    delegate.send(bytes)
                    payloads.sent(bytes.size)
                }
            }
            connections.add(observed)
            return observed
        }
    }

    /** Only opt-in measurements seed rule outcomes; credentials always retain a real CSPRNG. */
    private class SilentSecureServices(name: String, gameSeed: Int?) : PlatformServices {
        private val secure = SecureRandom()
        private val rulesRandom = gameSeed?.let { Random(it) } ?: secure.asKotlinRandom()
        private var stored = AppSettings(displayName = name, soundEnabled = false, hapticsEnabled = false)
        val feedbackClosed = AtomicBoolean()
        override val settingsStore = object : SettingsStore {
            override suspend fun load(): AppSettings = stored
            override suspend fun save(settings: AppSettings) { stored = settings }
        }
        override val feedback = object : Feedback {
            override fun play(cue: FeedbackCue, settings: AppSettings) = Unit
            override fun setForeground(value: Boolean) = Unit
            override fun close() { feedbackClosed.set(true) }
        }
        override val canScanInvitation = false
        override fun copyText(value: String) = Unit
        override fun shareText(value: String) = Unit
        override fun scanInvitation(onResult: (String?) -> Unit) = onResult(null)
        override fun gameRandom(): Random = rulesRandom
        override fun secureToken(): String = ByteArray(32).also(secure::nextBytes).joinToString("") {
            (it.toInt() and 255).toString(16).padStart(2, '0')
        }
    }
}
