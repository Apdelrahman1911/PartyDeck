package dev.partydeck.session

import dev.partydeck.core.Card
import dev.partydeck.core.CardRank
import dev.partydeck.core.GamePhase
import dev.partydeck.core.LastLightEngine
import kotlin.random.Random
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFalse
import kotlin.test.assertIs
import kotlin.test.assertNotNull
import kotlin.test.assertNull
import kotlin.test.assertTrue

/** Independent integration tests through authenticated peers and public session messages. */
class AuthorityAdversarialTest {
    @Test
    fun everyTableSizeCompletesThroughIntentsWithIndividualViewsAndMonotonicRevisions() {
        for (size in 2..6) {
            for (seed in 0 until 4) {
                val table = Table(size, ObservedRandom(seed * 17 + size))
                table.start()
                var latestSelection: List<Card>? = null
                var challenges = 0
                var actions = 0
                while (table.game().phase != GamePhase.FINISHED) {
                    val before = table.view()
                    val game = assertNotNull(before.game)
                    val previousRevision = before.revision
                    val sent = if (game.phase == GamePhase.ROUND_ENDED) {
                        assertTrue(before.controls.canAdvanceRound)
                        latestSelection = null
                        table.send(table.hostId, ClientIntent.AdvanceRound)
                    } else {
                        val actor = assertNotNull(game.turnPlayerId)
                        val own = table.game(actor)
                        if (own.availableActions.canChallenge && (actions % 3 == 0 || own.forcedChallenge)) {
                            val result = table.send(actor, ClientIntent.Challenge)
                            val outcome = assertNotNull(table.game().roundOutcome)
                            val cards = assertNotNull(latestSelection)
                            assertEquals(cards, outcome.revealedCards)
                            assertEquals(cards.none { it.rank != game.tableRank && it.rank != CardRank.WILD }, outcome.truthful)
                            assertEquals(actor, outcome.challengerId)
                            assertEquals(assertNotNull(game.latestClaim).playerId, outcome.claimantId)
                            assertEquals(if (outcome.truthful) actor else outcome.claimantId, outcome.penalizedPlayerId)
                            challenges++
                            result
                        } else {
                            assertTrue(own.availableActions.canPlay)
                            latestSelection = own.yourHand.take(own.availableActions.maxPlayableCards)
                            table.send(actor, ClientIntent.PlayCards(latestSelection.map { it.id }))
                        }
                    }
                    assertAccepted(sent)
                    assertEquals(previousRevision + 1, table.view().revision)
                    table.assertIndividuallyAddressedSnapshots(sent.dispatch)
                    val views = table.connectedViews()
                    val handIds = views.values.flatMap { assertNotNull(it.game).yourHand }.map { it.id }
                    assertEquals(handIds.size, handIds.toSet().size, "A private card appeared in several players' hands")
                    for ((id, view) in views) {
                        assertEquals(id, view.selfPlayerId)
                        assertEquals(id, assertNotNull(view.game).viewerId)
                        assertEquals(table.view().revision, view.revision)
                        if (id != table.hostId) {
                            assertFalse(view.controls.canAdvanceRound)
                            assertFalse(view.controls.canReturnToLobby)
                        }
                    }
                    actions++
                    assertTrue(challenges <= 6 * size - 1, "Session did not finish within the penalty bound")
                    assertTrue(actions <= (6 * size - 1) * (5 * size + 1), "Session stopped progressing")
                }
                val final = table.game()
                assertEquals(final.players.single { !it.eliminated }.id, final.winnerId)
                assertTrue(challenges > 0)
                assertTrue(table.view().controls.canReturnToLobby)
                assertFalse(table.view().controls.canAdvanceRound)
            }
        }
    }

    @Test
    fun anExactDuplicateReturnsItsOriginalReceiptAlongsideTheCurrentSnapshot() {
        val random = ObservedRandom(119)
        val table = Table(3, random)
        table.start()
        val actor = assertNotNull(table.game().turnPlayerId)
        val firstPlay = table.send(actor, ClientIntent.PlayCards(table.game(actor).yourHand.take(1).map { it.id }))
        assertAccepted(firstPlay)
        assertAccepted(table.send(assertNotNull(table.game().turnPlayerId), ClientIntent.Challenge))
        assertAccepted(table.send(table.hostId, ClientIntent.AdvanceRound))
        val currentViews = table.connectedViews()
        val draws = random.draws

        val duplicate = table.authority.handle(table.peer(actor), firstPlay.command)
        assertEquals(firstPlay.receipt, receipt(duplicate))
        val snapshot = duplicate.deliveries.map { it.message }.filterIsInstance<ServerMessage.Snapshot>().single()
        assertEquals(currentViews.getValue(actor), snapshot.view)
        assertTrue(snapshot.view.revision > firstPlay.receipt.revision)
        assertEquals(setOf(table.peer(actor).connectionId), duplicate.deliveries.map { it.connectionId }.toSet())
        assertEquals(currentViews, table.connectedViews())
        assertEquals(draws, random.draws)

        val conflict = table.authority.handle(table.peer(actor), firstPlay.command.copy(intent = ClientIntent.Challenge))
        assertEquals(SessionError.COMMAND_ID_CONFLICT, receipt(conflict).error)
        assertEquals(currentViews, table.connectedViews())
        assertEquals(draws, random.draws)
    }

    @Test
    fun staleRequestsConsumeTheirIdsAndResumeRecoversTheCounterWithoutReplayingTheGame() {
        val random = ObservedRandom(331)
        val table = Table(3, random)
        table.start()
        if (table.game().turnPlayerId == table.hostId) {
            assertAccepted(table.send(table.hostId, ClientIntent.PlayCards(table.game(table.hostId).yourHand.take(1).map { it.id })))
        }
        val actor = assertNotNull(table.game().turnPlayerId)
        assertTrue(actor != table.hostId)
        val priorRevision = table.view().revision
        assertAccepted(table.send(actor, ClientIntent.PlayCards(table.game(actor).yourHand.take(1).map { it.id })))
        val expectedViews = table.connectedViews()
        val draws = random.draws
        val stale = table.send(actor, ClientIntent.Challenge, expectedRevision = priorRevision)
        assertEquals(SessionError.STALE_REVISION, stale.receipt.error)
        assertNull(stale.receipt.gameError)
        assertEquals(expectedViews, table.connectedViews())
        assertEquals(draws, random.draws)

        val oldPeer = table.peer(actor)
        val privateHand = table.game(actor).yourHand
        table.authority.disconnect(oldPeer)
        assertTrue(actor in table.view().pausedPlayerIds)
        val welcome = table.resume(actor, "resumed-stale-player")
        assertEquals(stale.command.commandId + 1, welcome.nextCommandId)
        assertEquals(privateHand, assertNotNull(welcome.view.game).yourHand)
        assertTrue(table.view().pausedPlayerIds.isEmpty())
        assertEquals(draws, random.draws)

        val beforeDuplicate = table.connectedViews()
        val duplicate = table.authority.handle(table.peer(actor), stale.command)
        assertEquals(stale.receipt, receipt(duplicate))
        assertEquals(beforeDuplicate, table.connectedViews())
        assertEquals(draws, random.draws)
        val beforeLateDisconnect = table.connectedViews()
        assertTrue(table.authority.disconnect(oldPeer).deliveries.isEmpty())
        assertEquals(beforeLateDisconnect, table.connectedViews())

        var interveningPlays = 0
        while (table.game().turnPlayerId != actor) {
            val current = assertNotNull(table.game().turnPlayerId)
            assertAccepted(table.send(current, ClientIntent.PlayCards(table.game(current).yourHand.take(1).map { it.id })))
            interveningPlays++
            assertTrue(interveningPlays < 3)
        }
        val resumedAction = table.send(actor, ClientIntent.PlayCards(table.game(actor).yourHand.take(1).map { it.id }))
        assertEquals(welcome.nextCommandId, resumedAction.command.commandId)
        assertAccepted(resumedAction)
        assertEquals(draws, random.draws)
    }

    @Test
    fun theHostCanAdvanceAfterEliminationAndDisconnectedEliminatedGuestsDoNotPauseSurvivors() {
        val table = Table(4, FixedOpeningRandom(4))
        table.start()
        assertEquals(table.hostId, table.game().turnPlayerId)
        val hostBluff = table.game(table.hostId).yourHand.first {
            it.rank != CardRank.WILD && it.rank != table.game().tableRank
        }
        assertAccepted(table.send(table.hostId, ClientIntent.PlayCards(listOf(hostBluff.id))))
        assertAccepted(table.send(assertNotNull(table.game().turnPlayerId), ClientIntent.Challenge))
        assertTrue(table.game().players.single { it.id == table.hostId }.eliminated)
        assertTrue(table.game().yourHand.isEmpty())
        assertTrue(table.view().controls.canAdvanceRound)
        val guest = table.ids.first { it != table.hostId }
        val forbidden = table.send(guest, ClientIntent.AdvanceRound)
        assertEquals(SessionError.NOT_HOST, forbidden.receipt.error)
        assertAccepted(table.send(table.hostId, ClientIntent.AdvanceRound))

        val nextOpener = assertNotNull(table.game().turnPlayerId)
        val bluff = table.game(nextOpener).yourHand.first {
            it.rank != CardRank.WILD && it.rank != table.game().tableRank
        }
        assertAccepted(table.send(nextOpener, ClientIntent.PlayCards(listOf(bluff.id))))
        assertAccepted(table.send(assertNotNull(table.game().turnPlayerId), ClientIntent.Challenge))
        assertTrue(table.game().players.single { it.id == nextOpener }.eliminated)
        assertEquals(GamePhase.ROUND_ENDED, table.game().phase)
        table.authority.disconnect(table.peer(nextOpener))
        assertTrue(table.view().pausedPlayerIds.isEmpty())
        assertTrue(table.view().controls.canAdvanceRound)
        assertAccepted(table.send(table.hostId, ClientIntent.AdvanceRound))
        val survivor = assertNotNull(table.game().turnPlayerId)
        assertTrue(table.game(survivor).availableActions.canPlay)
        assertAccepted(table.send(survivor, ClientIntent.PlayCards(table.game(survivor).yourHand.take(1).map { it.id })))
    }

    @Test
    fun aDisconnectedEmptyHandClaimantPausesTheCompulsoryChallengeUntilResume() {
        val random = ObservedRandom(510, FixedOpeningRandom(3))
        val table = Table(3, random)
        table.start()
        var plays = 0
        while (!table.game().forcedChallenge) {
            val actor = assertNotNull(table.game().turnPlayerId)
            assertAccepted(table.send(actor, ClientIntent.PlayCards(table.game(actor).yourHand.take(3).map { it.id })))
            plays++
            assertTrue(plays < 15)
        }
        val claim = assertNotNull(table.game().latestClaim)
        val challenger = assertNotNull(table.game().turnPlayerId)
        assertTrue(claim.playerId != table.hostId)
        assertTrue(table.game(claim.playerId).yourHand.isEmpty())
        val draws = random.draws
        table.authority.disconnect(table.peer(claim.playerId))
        assertEquals(listOf(claim.playerId), table.view().pausedPlayerIds)
        assertEquals(claim, table.game().latestClaim)
        assertFalse(table.game(challenger).availableActions.canChallenge)
        assertFalse(table.game(challenger).availableActions.canPlay)
        val pausedViews = table.connectedViews()
        val rejected = table.send(challenger, ClientIntent.Challenge)
        assertEquals(SessionError.PLAYERS_DISCONNECTED, rejected.receipt.error)
        assertEquals(pausedViews, table.connectedViews())
        assertEquals(draws, random.draws)

        val welcome = table.resume(claim.playerId, "resumed-empty-claimant")
        assertTrue(assertNotNull(welcome.view.game).yourHand.isEmpty())
        assertEquals(claim, table.game().latestClaim)
        assertEquals(challenger, table.game().turnPlayerId)
        assertTrue(table.game(challenger).availableActions.canChallenge)
        assertAccepted(table.send(challenger, ClientIntent.Challenge))
        assertEquals(claim.playerId, assertNotNull(table.game().roundOutcome).claimantId)
        assertEquals(1, table.game().players.sumOf { it.penaltyAttempts })
        assertEquals(draws, random.draws)
    }

    @Test
    fun leavingAndStartingARematchCannotResurrectOldCommandsOrOldReadiness() {
        val random = ObservedRandom(817)
        val table = Table(3, random)
        val originalStart = table.start()
        val firstMatchRevision = table.view().revision
        val oldCard = table.game(table.hostId).yourHand.first().id
        val leaving = table.ids.first { it != table.hostId }
        val remaining = table.ids.last()
        val left = table.send(leaving, ClientIntent.Leave)
        assertAccepted(left)
        assertTrue(table.peer(leaving).connectionId in left.dispatch.closeConnections)
        assertTrue(left.dispatch.deliveries.any { it.message is ServerMessage.Ended && it.message.reason == SessionEndReason.LEFT })
        assertEquals(listOf(leaving), table.view().pausedPlayerIds)
        assertAccepted(table.send(table.hostId, ClientIntent.ReturnToLobby))
        assertEquals(SessionPhase.LOBBY, table.view().phase)
        assertNull(table.view().game)
        assertEquals(setOf(table.hostId, remaining), table.view().players.map { it.id }.toSet())
        assertFalse(table.view().players.single { it.id == remaining }.isReady)
        assertFalse(table.view().controls.canStartGame)
        val beforeReplay = table.connectedViews()
        val draws = random.draws
        val duplicateStart = table.authority.handle(table.peer(table.hostId), originalStart.command)
        assertEquals(originalStart.receipt, receipt(duplicateStart))
        assertEquals(beforeReplay, table.connectedViews())
        assertEquals(draws, random.draws)

        assertAccepted(table.send(remaining, ClientIntent.SetReady(true)))
        assertAccepted(table.send(table.hostId, ClientIntent.StartGame))
        assertEquals(1, table.game().roundNumber)
        assertTrue(table.view().revision > firstMatchRevision)
        val beforeStale = table.connectedViews()
        val stale = table.send(table.hostId, ClientIntent.PlayCards(listOf(oldCard)), expectedRevision = firstMatchRevision)
        assertEquals(SessionError.STALE_REVISION, stale.receipt.error)
        assertEquals(beforeStale, table.connectedViews())
    }

    private class Table(size: Int, random: Random) {
        private val admissionSecret = "a".repeat(64)
        private val hostPeer = SessionPeer("host-peer")
        private var tokenCounter = 0
        val authority = HostAuthority(
            HostSessionConfig("authority-adversarial", admissionSecret, "Host", hostPeer),
            LastLightEngine(random),
        ) { (++tokenCounter).toString(16).padStart(64, '0') }
        val hostId: String = authority.hostPlayerId
        private val peers = linkedMapOf<String, SessionPeer>()
        private val tokens = mutableMapOf<String, String>()
        private val nextCommands = mutableMapOf<String, Long>()
        val ids: List<String> get() = peers.keys.toList()

        init {
            remember(hostPeer, welcome(authority.initialDispatch()))
            repeat(size - 1) { index ->
                val peer = SessionPeer("guest-$index")
                val dispatch = authority.handle(peer, ClientMessage.Join(authority.sessionId, admissionSecret, "Guest ${index + 1}"))
                remember(peer, welcome(dispatch))
            }
        }

        fun peer(id: String): SessionPeer = peers.getValue(id)
        fun view(id: String = hostId): SessionView = assertNotNull(authority.viewFor(peer(id)))
        fun game(id: String = hostId) = assertNotNull(view(id).game)
        fun connectedViews(): Map<String, SessionView> = peers.mapNotNull { (id, peer) -> authority.viewFor(peer)?.let { id to it } }.toMap()

        fun start(): Sent {
            for (id in ids.filter { it != hostId }) assertAccepted(send(id, ClientIntent.SetReady(true)))
            return send(hostId, ClientIntent.StartGame).also(::assertAccepted)
        }

        fun send(id: String, intent: ClientIntent, expectedRevision: Long = view().revision): Sent {
            val commandId = nextCommands.getValue(id)
            nextCommands[id] = commandId + 1
            val command = ClientMessage.Command(authority.sessionId, commandId, expectedRevision, intent)
            val dispatch = authority.handle(peer(id), command)
            return Sent(command, dispatch, receipt(dispatch))
        }

        fun resume(id: String, connectionId: String): ServerMessage.Welcome {
            val peer = SessionPeer(connectionId)
            val dispatch = authority.handle(peer, ClientMessage.Resume(authority.sessionId, id, tokens.getValue(id)))
            return welcome(dispatch).also { remember(peer, it) }
        }

        fun assertIndividuallyAddressedSnapshots(dispatch: SessionDispatch) {
            val snapshots = dispatch.deliveries.filter { it.message is ServerMessage.Snapshot }
            assertEquals(connectedViews().size, snapshots.size)
            assertEquals(snapshots.size, snapshots.map { it.connectionId }.toSet().size)
            for (delivery in snapshots) {
                val id = peers.entries.single { it.value.connectionId == delivery.connectionId }.key
                val snapshot = assertIs<ServerMessage.Snapshot>(delivery.message)
                assertEquals(view(id), snapshot.view)
                assertEquals(authority.sessionId, snapshot.sessionId)
                assertEquals(id, snapshot.view.selfPlayerId)
            }
        }

        private fun remember(peer: SessionPeer, welcome: ServerMessage.Welcome) {
            peers[welcome.playerId] = peer
            tokens[welcome.playerId] = welcome.reconnectToken
            nextCommands[welcome.playerId] = welcome.nextCommandId
        }
    }

    private data class Sent(val command: ClientMessage.Command, val dispatch: SessionDispatch, val receipt: CommandReceipt)

    private class ObservedRandom(seed: Int, private val source: Random = Random(seed)) : Random() {
        var draws = 0
            private set

        override fun nextBits(bitCount: Int): Int {
            draws++
            return source.nextBits(bitCount)
        }

        override fun nextInt(until: Int): Int {
            draws++
            return source.nextInt(until)
        }
    }

    /** Documented entropy contract: burnout steps, initial opener, rank, then shuffle bounds. */
    private class FixedOpeningRandom(private val players: Int) : Random() {
        private var boundedDraws = 0

        override fun nextInt(until: Int): Int {
            val draw = boundedDraws++
            return if (draw <= players + 1) 0 else until - 1
        }

        override fun nextBits(bitCount: Int): Int = error("This fixture expects the documented bounded-draw contract")
    }

    private companion object {
        fun receipt(dispatch: SessionDispatch): CommandReceipt =
            dispatch.deliveries.map { it.message }.filterIsInstance<ServerMessage.Receipt>().single().receipt

        fun welcome(dispatch: SessionDispatch): ServerMessage.Welcome =
            dispatch.deliveries.map { it.message }.filterIsInstance<ServerMessage.Welcome>().single()

        fun assertAccepted(sent: Sent) {
            assertNull(sent.receipt.error, "Rejected intent ${sent.command.intent}: ${sent.receipt}")
            assertNull(sent.receipt.gameError)
        }
    }
}
