package dev.partydeck.session

import dev.partydeck.core.GamePhase
import dev.partydeck.core.GameRejection
import dev.partydeck.core.LastLightEngine
import dev.partydeck.core.LastLightRules
import kotlin.random.Random
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFalse
import kotlin.test.assertIs
import kotlin.test.assertNotNull
import kotlin.test.assertNull
import kotlin.test.assertTrue

class HostAuthorityTest {
    @Test
    fun invitationReadinessRosterAndHostGatesProtectStarting() {
        val table = TestTable(guests = 0)
        val intruder = SessionPeer("intruder")
        val invalid = table.authority.handle(intruder, ClientMessage.Join(table.id, "b".repeat(64), "Guest"))
        assertEquals(SessionError.INVALID_CREDENTIALS, invalid.admissionError())
        assertNull(table.authority.viewFor(intruder))
        assertEquals(0L, table.view(table.host).revision)
        assertEquals(SessionError.NOT_ENOUGH_PLAYERS, table.send(table.host, ClientIntent.StartGame).receipt().error)

        val first = table.join("  Mina  ")
        assertEquals("Mina", table.view(first).players.single { it.id == table.view(first).selfPlayerId }.displayName)
        assertEquals(SessionError.PLAYERS_NOT_READY, table.send(table.host, ClientIntent.StartGame).receipt().error)
        table.send(first, ClientIntent.SetReady(true))
        assertTrue(table.view(table.host).controls.canStartGame)

        val second = table.join("Noor")
        assertFalse(table.view(first).players.single { it.id == table.view(first).selfPlayerId }.isReady)
        assertFalse(table.view(table.host).controls.canStartGame)
        table.readyGuests()
        assertEquals(SessionError.NOT_HOST, table.send(second, ClientIntent.StartGame).receipt().error)
        assertTrue(table.send(table.host, ClientIntent.StartGame).receipt().accepted)
        assertEquals(SessionPhase.GAME, table.view(first).phase)
        assertEquals(SessionError.WRONG_PHASE, table.send(table.host, ClientIntent.KickPlayer(table.view(first).selfPlayerId)).receipt().error)
        assertEquals(GameRejection.ROUND_NOT_ENDED, table.send(table.host, ClientIntent.AdvanceRound).receipt().gameError)
        assertEquals(SessionError.NOT_HOST, table.send(first, ClientIntent.EndSession).receipt().error)
    }

    @Test
    fun joinsAreIdempotentBoundedAndUseUsableDisplayNames() {
        val table = TestTable(guests = 0)
        for (badName in listOf("", " \t ", "A".repeat(25), "Sam\nLee", "\u202eAlice", "\u200b\u200d", "\ud800")) {
            val result = table.authority.handle(SessionPeer("bad-name"), ClientMessage.Join(table.id, table.secret, badName))
            assertEquals(SessionError.INVALID_NAME, result.admissionError())
        }
        val unicodePeer = table.join("ليلى 🌙")
        val before = table.view(unicodePeer)
        val repeated = table.authority.handle(unicodePeer, ClientMessage.Join(table.id, table.secret, "Another name"))
        val welcome = assertIs<ServerMessage.Welcome>(repeated.deliveries.single().message)
        assertEquals(before, welcome.view)
        assertEquals(table.welcomes.getValue(unicodePeer.connectionId).reconnectToken, welcome.reconnectToken)
        repeat(LastLightRules.MAX_PLAYERS - 2) { table.join("Guest $it") }
        val full = table.authority.handle(SessionPeer("extra"), ClientMessage.Join(table.id, table.secret, "Extra"))
        assertEquals(SessionError.LOBBY_FULL, full.admissionError())
        assertEquals(LastLightRules.MAX_PLAYERS, table.view(table.host).players.size)
    }

    @Test
    fun completeMatchCanReturnToLobbyAndRematchWithoutResettingRevision() {
        val table = TestTable(guests = 2, seed = 11)
        table.start()
        var actions = 0
        while (table.view(table.host).game?.phase != GamePhase.FINISHED) {
            assertTrue(actions++ < 512, "A finite fuse match must finish")
            val hostView = table.view(table.host)
            if (hostView.game?.phase == GamePhase.ROUND_ENDED) {
                assertTrue(table.send(table.host, ClientIntent.AdvanceRound).receipt().accepted)
            } else {
                val turnId = assertNotNull(hostView.game?.turnPlayerId)
                val actor = table.peers.single { table.view(it).selfPlayerId == turnId }
                val view = assertNotNull(table.view(actor).game)
                val intent = if (view.availableActions.canChallenge) ClientIntent.Challenge
                else ClientIntent.PlayCards(listOf(view.yourHand.first().id))
                assertTrue(table.send(actor, intent).receipt().accepted)
            }
        }
        val finalView = table.view(table.host)
        assertNotNull(finalView.game?.winnerId)
        assertTrue(table.send(table.host, ClientIntent.ReturnToLobby).receipt().accepted)
        val lobby = table.view(table.host)
        assertEquals(SessionPhase.LOBBY, lobby.phase)
        assertNull(lobby.game)
        assertTrue(lobby.revision > finalView.revision)
        assertFalse(lobby.controls.canStartGame)
        assertTrue(lobby.players.filter { it.id != lobby.hostPlayerId }.none { it.isReady })
        table.readyGuests()
        assertTrue(table.send(table.host, ClientIntent.StartGame).receipt().accepted)
        assertEquals(1, table.view(table.host).game?.roundNumber)
        assertTrue(table.view(table.host).revision > lobby.revision)
    }

    @Test
    fun activeLeaveRevokesItsCredentialAndReturnRemovesTheAbandonedSeat() {
        val table = TestTable(guests = 2)
        table.start()
        val leaving = table.peers[1]
        val welcome = table.welcomes.getValue(leaving.connectionId)
        val leave = table.send(leaving, ClientIntent.Leave)
        assertEquals(listOf(leaving.connectionId), leave.closeConnections)
        assertIs<ServerMessage.Ended>(leave.deliveries.last().message)
        assertNull(table.authority.viewFor(leaving))
        assertEquals(listOf(welcome.playerId), table.view(table.host).pausedPlayerIds)

        val impostor = SessionPeer("new-connection")
        val resume = table.authority.handle(impostor, ClientMessage.Resume(table.id, welcome.playerId, welcome.reconnectToken))
        assertEquals(SessionError.INVALID_CREDENTIALS, resume.admissionError())
        assertTrue(table.send(table.host, ClientIntent.ReturnToLobby).receipt().accepted)
        assertFalse(table.view(table.host).players.any { it.id == welcome.playerId })
        assertTrue(table.view(table.host).pausedPlayerIds.isEmpty())
    }

    @Test
    fun snapshotsAndWelcomesNeverIncludeAnotherPlayersPrivateCardsOrCredentials() {
        val table = TestTable(guests = 5)
        table.start()
        val views = table.peers.associateWith(table::view)
        for ((peer, view) in views) {
            val bytes = SessionCodec.encodeServer(ServerMessage.Snapshot(table.id, view))
            val text = bytes.decodeToString()
            assertEquals(ServerMessage.Snapshot(table.id, view), assertIs<WireDecodeResult.Success<ServerMessage>>(SessionCodec.decodeServer(bytes)).value)
            for ((other, otherView) in views) {
                if (other != peer) {
                    assertTrue(assertNotNull(otherView.game).yourHand.none { text.contains("\"${it.id}\"") })
                }
                assertFalse(text.contains(table.welcomes.getValue(other.connectionId).reconnectToken))
            }
            assertFalse(text.contains(table.secret))
            for (privateField in listOf("burnoutStep", "undealtCards", "discardedCards", "pendingPlay")) {
                assertFalse(text.contains("\"$privateField\""))
            }
            assertEquals(view.selfPlayerId, view.game?.viewerId)
            assertEquals(LastLightRules.HAND_SIZE, view.game?.yourHand?.size)
        }
    }

    @Test
    fun acceptedCommandRetainsAnIndependentCopyOfTheCardSelection() {
        val table = TestTable(guests = 1)
        table.start()
        val turnId = assertNotNull(table.view(table.host).game?.turnPlayerId)
        val actor = table.peers.single { table.view(it).selfPlayerId == turnId }
        val card = assertNotNull(table.view(actor).game).yourHand.first().id
        val selection = mutableListOf(card)
        val message = table.message(actor, ClientIntent.PlayCards(selection))
        val receipt = table.authority.handle(actor, message).receipt()
        assertTrue(receipt.accepted)
        val afterPlay = table.view(actor)
        selection.clear()
        val duplicate = table.authority.handle(actor, message.copy(intent = ClientIntent.PlayCards(listOf(card))))
        assertEquals(receipt, duplicate.receipt())
        assertEquals(afterPlay, table.view(actor))
    }

    @Test
    fun kickingAndHostLossRemoveAuthorityAccess() {
        val table = TestTable(guests = 2)
        val target = table.peers[1]
        val welcome = table.welcomes.getValue(target.connectionId)
        val kick = table.send(table.host, ClientIntent.KickPlayer(welcome.playerId))
        assertEquals(listOf(target.connectionId), kick.closeConnections)
        assertNull(table.authority.viewFor(target))
        assertEquals(SessionError.INVALID_CREDENTIALS, table.authority.handle(
            SessionPeer("resume-kicked"), ClientMessage.Resume(table.id, welcome.playerId, welcome.reconnectToken),
        ).admissionError())
        val ended = table.authority.disconnect(table.host)
        assertTrue(ended.deliveries.all { (it.message as ServerMessage.Ended).reason == SessionEndReason.HOST_DISCONNECTED })
        assertNull(table.authority.viewFor(table.host))
        assertEquals(SessionError.SESSION_CLOSED, table.authority.handle(
            SessionPeer("late-join"), ClientMessage.Join(table.id, table.secret, "Late"),
        ).admissionError())
    }

    private class TestTable(guests: Int = 1, seed: Int = 7) {
        val id = "authority-test-room"
        val secret = "a".repeat(64)
        val host = SessionPeer("local-host")
        private var tokenCounter = 0
        val authority = HostAuthority(
            HostSessionConfig(id, secret, "Host", host),
            LastLightEngine(Random(seed)),
            { (++tokenCounter).toString(16).padStart(64, '0') },
        )
        val peers = mutableListOf(host)
        val welcomes = mutableMapOf<String, ServerMessage.Welcome>()
        private val nextCommands = mutableMapOf<String, Long>()

        init {
            welcomes[host.connectionId] = authority.initialDispatch().deliveries.single().message as ServerMessage.Welcome
            repeat(guests) { join("Guest ${it + 1}") }
        }

        fun join(name: String): SessionPeer {
            val peer = SessionPeer("guest-${peers.size}")
            val dispatch = authority.handle(peer, ClientMessage.Join(id, secret, name))
            welcomes[peer.connectionId] = dispatch.deliveries.first().message as ServerMessage.Welcome
            peers += peer
            return peer
        }

        fun view(peer: SessionPeer): SessionView = assertNotNull(authority.viewFor(peer))

        fun message(peer: SessionPeer, intent: ClientIntent): ClientMessage.Command {
            val view = view(peer)
            val commandId = nextCommands.getOrElse(view.selfPlayerId) { 1L }
            nextCommands[view.selfPlayerId] = commandId + 1
            return ClientMessage.Command(id, commandId, view.revision, intent)
        }

        fun send(peer: SessionPeer, intent: ClientIntent): SessionDispatch = authority.handle(peer, message(peer, intent))

        fun readyGuests() {
            peers.drop(1).forEach { assertTrue(send(it, ClientIntent.SetReady(true)).receipt().accepted) }
        }

        fun start() {
            readyGuests()
            assertTrue(send(host, ClientIntent.StartGame).receipt().accepted)
        }
    }
}

private fun SessionDispatch.receipt(): CommandReceipt = deliveries.map { it.message }.filterIsInstance<ServerMessage.Receipt>().single().receipt
private fun SessionDispatch.admissionError(): SessionError = (deliveries.single().message as ServerMessage.AdmissionRejected).error
