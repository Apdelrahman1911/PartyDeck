package dev.partydeck.session

import dev.partydeck.core.LastLightEngine
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonElement
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlin.random.Random
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFalse
import kotlin.test.assertIs
import kotlin.test.assertNotNull
import kotlin.test.assertNull
import kotlin.test.assertTrue

/** Independent tests of security boundaries, beyond normal game-flow acceptance. */
class SecurityAdversarialTest {
    @Test
    fun everyEncodedRecipientViewExcludesOtherHandsTokensAndUnchallengedDiscards() {
        val table = Table()
        table.start()
        val allInitialCardIds = table.peers.flatMap { table.view(it).game!!.yourHand.map { card -> card.id } }.toSet()
        table.peers.forEach { peer ->
            val view = table.view(peer)
            assertPrivateMessage(ServerMessage.Snapshot(table.id, view), table, allInitialCardIds)
        }

        val firstActor = table.actor()
        val hiddenAcceptedCard = table.view(firstActor).game!!.yourHand.first().id
        val firstPlay = table.send(firstActor, ClientIntent.PlayCards(listOf(hiddenAcceptedCard)))
        assertEquals(null, firstPlay.receipt().error)
        firstPlay.deliveries.forEach { assertPrivateMessage(it.message, table, allInitialCardIds) }
        table.peers.forEach { peer ->
            val claim = table.view(peer).game!!.latestClaim
            assertEquals(1, claim?.cardCount)
        }

        val secondActor = table.actor()
        val challengedCard = table.view(secondActor).game!!.yourHand.first().id
        assertEquals(null, table.send(secondActor, ClientIntent.PlayCards(listOf(challengedCard))).receipt().error)
        val challenge = table.send(table.actor(), ClientIntent.Challenge)
        assertEquals(null, challenge.receipt().error)
        challenge.deliveries.forEach { delivery ->
            assertPrivateMessage(delivery.message, table, allInitialCardIds)
            assertFalse(hiddenAcceptedCard in stringValues(encoded(delivery.message)))
        }
        table.peers.forEach { peer ->
            assertEquals(listOf(challengedCard), table.view(peer).game!!.roundOutcome!!.revealedCards.map { it.id })
        }
    }

    @Test
    fun unauthorizedPeersReceiveOnlyFixedAdmissionErrors() {
        val table = Table()
        table.start()
        val intruder = SessionPeer("intruder")
        val attempts = listOf(
            ClientMessage.Join(table.id, "f".repeat(64), "Intruder"),
            ClientMessage.Resume(table.id, table.welcome(table.peers[1]).playerId, table.welcome(table.peers[2]).reconnectToken),
            ClientMessage.Command(table.id, 1, table.view(table.host).revision, ClientIntent.EndSession),
            ClientMessage.Command("previous-room", 1, 0, ClientIntent.EndSession),
        )
        for (message in attempts) {
            val dispatch = table.authority.handle(intruder, message)
            assertEquals(listOf(intruder.connectionId), dispatch.closeConnections)
            assertIs<ServerMessage.AdmissionRejected>(dispatch.deliveries.single().message)
            assertNull(table.authority.viewFor(intruder))
            assertPrivateMessage(dispatch.deliveries.single().message, table, emptySet())
        }
    }

    @Test
    fun resumeRevokesOldSocketAndLateDisconnectCannotRemoveReplacement() {
        val table = Table()
        table.start()
        val oldPeer = table.peers[1]
        val oldWelcome = table.welcome(oldPeer)
        val oldHand = table.view(oldPeer).game!!.yourHand
        val replacement = SessionPeer("replacement")
        val resumed = table.authority.handle(
            replacement,
            ClientMessage.Resume(table.id, oldWelcome.playerId, oldWelcome.reconnectToken),
        )
        val welcome = assertIs<ServerMessage.Welcome>(resumed.deliveries.first().message)
        assertEquals(oldWelcome.playerId, welcome.view.selfPlayerId)
        assertEquals(oldHand, welcome.view.game!!.yourHand)
        assertEquals(listOf(oldPeer.connectionId), resumed.closeConnections)
        assertNull(table.authority.viewFor(oldPeer))
        val resumedRevision = welcome.view.revision

        val obsoleteCommand = table.authority.handle(
            oldPeer,
            ClientMessage.Command(table.id, 100, resumedRevision, ClientIntent.EndSession),
        )
        assertEquals(SessionError.NOT_ADMITTED, assertIs<ServerMessage.AdmissionRejected>(obsoleteCommand.deliveries.single().message).error)
        assertEquals(SessionDispatch(), table.authority.disconnect(oldPeer))
        assertEquals(resumedRevision, table.authority.viewFor(replacement)!!.revision)
        assertTrue(table.authority.viewFor(replacement)!!.players.single { it.id == oldWelcome.playerId }.isConnected)

        val privilegeAttempt = table.authority.handle(
            replacement,
            ClientMessage.Command(table.id, welcome.nextCommandId, resumedRevision, ClientIntent.EndSession),
        )
        assertEquals(SessionError.NOT_HOST, privilegeAttempt.receipt().error)
        assertEquals(SessionPhase.GAME, table.view(table.host).phase)
    }

    @Test
    fun evenPossessionOfLocalHostTokenCannotRemotelyReplaceAuthority() {
        val table = Table()
        val hostWelcome = table.welcome(table.host)
        val result = table.authority.handle(
            SessionPeer("remote-host-impersonator"),
            ClientMessage.Resume(table.id, hostWelcome.playerId, hostWelcome.reconnectToken),
        )
        assertEquals(SessionError.INVALID_CREDENTIALS, assertIs<ServerMessage.AdmissionRejected>(result.deliveries.single().message).error)
        assertNotNull(table.authority.viewFor(table.host))
    }

    @Test
    fun evictionAndConflictingIdsCannotResetReplayProtection() {
        val table = Table(replayCacheSize = 2)
        val guest = table.peers[1]
        val command = ClientMessage.Command(table.id, 1, table.view(guest).revision, ClientIntent.SetReady(true))
        val firstReceipt = table.authority.handle(guest, command).receipt()
        val afterFirst = table.view(guest)
        assertEquals(firstReceipt, table.authority.handle(guest, command).receipt())
        assertEquals(afterFirst, table.view(guest))
        assertEquals(
            SessionError.COMMAND_ID_CONFLICT,
            table.authority.handle(guest, command.copy(intent = ClientIntent.SetReady(false))).receipt().error,
        )
        listOf(2L to false, 3L to true).forEach { (id, ready) ->
            assertEquals(null, table.authority.handle(
                guest, ClientMessage.Command(table.id, id, table.view(guest).revision, ClientIntent.SetReady(ready)),
            ).receipt().error)
        }
        val beforeReplay = table.view(guest)
        assertEquals(SessionError.COMMAND_TOO_OLD, table.authority.handle(guest, command).receipt().error)
        assertEquals(beforeReplay, table.view(guest))

        val token = table.welcome(guest)
        val replacement = SessionPeer("replay-after-resume")
        table.authority.handle(replacement, ClientMessage.Resume(table.id, token.playerId, token.reconnectToken))
        assertEquals(SessionError.COMMAND_TOO_OLD, table.authority.handle(replacement, command).receipt().error)
    }

    @Test
    fun highCommandIdsNeverWrapToPermitAnOldCommand() {
        val table = Table()
        val guest = table.peers[1]
        for (invalid in listOf(0L, -1L, Long.MIN_VALUE, Long.MAX_VALUE)) {
            val result = table.authority.handle(
                guest, ClientMessage.Command(table.id, invalid, table.view(guest).revision, ClientIntent.SetReady(true)),
            )
            assertEquals(SessionError.INVALID_COMMAND_ID, result.receipt().error)
        }
        assertEquals(null, table.authority.handle(
            guest, ClientMessage.Command(table.id, Long.MAX_VALUE - 1, table.view(guest).revision, ClientIntent.SetReady(true)),
        ).receipt().error)
        assertEquals(SessionError.COMMAND_TOO_OLD, table.authority.handle(
            guest, ClientMessage.Command(table.id, 1, table.view(guest).revision, ClientIntent.SetReady(false)),
        ).receipt().error)
        val token = table.welcome(guest)
        val result = table.authority.handle(SessionPeer("last-id-resume"), ClientMessage.Resume(table.id, token.playerId, token.reconnectToken))
        assertTrue(assertIs<ServerMessage.Welcome>(result.deliveries.first().message).nextCommandId > 0)
    }

    @Test
    fun kickAndSessionTerminationInvalidateCredentials() {
        val table = Table()
        val removed = table.peers[1]
        val token = table.welcome(removed)
        val kick = table.send(table.host, ClientIntent.KickPlayer(token.playerId))
        assertEquals(null, kick.receipt().error)
        assertNull(table.authority.viewFor(removed))
        val resume = table.authority.handle(SessionPeer("removed-resume"), ClientMessage.Resume(table.id, token.playerId, token.reconnectToken))
        assertEquals(SessionError.INVALID_CREDENTIALS, assertIs<ServerMessage.AdmissionRejected>(resume.deliveries.single().message).error)
        table.send(table.host, ClientIntent.EndSession)
        table.peers.forEach { assertNull(table.authority.viewFor(it)) }
        assertEquals(SessionDispatch(), table.authority.initialDispatch())
    }

    @Test
    fun parserRejectsDuplicateDecodedKeysAtEveryMessageLevel() {
        val json = validCommand()
        val attacks = listOf(
            json.replace("\"protocolVersion\":1", "\"protocolVersion\":1,\"protocolVersion\":1"),
            json.replace("\"protocolVersion\":1", "\"protocolVersion\":2,\"\\u0070rotocolVersion\":1"),
            json.replace("\"type\":\"command\"", "\"type\":\"join\",\"\\u0074ype\":\"command\""),
            json.replace("\"commandId\":1", "\"commandId\":1,\"\\u0063ommandId\":2"),
            json.replace("\"type\":\"set_ready\"", "\"type\":\"end_session\",\"\\u0074ype\":\"set_ready\""),
            json.replace("\"ready\":true", "\"ready\":false,\"\\u0072eady\":true"),
            json.replace("\"sessionId\":\"room\"", "\"sessionId\":\"room\",\"sessionId\":\"room\""),
        )
        attacks.forEach { assertMalformed(it.encodeToByteArray()) }
    }

    @Test
    fun parserRejectsMalformedUnicodeSyntaxVersionsAndNumericOverflow() {
        val valid = validCommand()
        val malformed = listOf(
            "", "[]", "null", "{}", valid + "{}", "\ufeff$valid",
            valid.replace("\"commandId\":1", "\"commandId\":01"),
            valid.replace("\"commandId\":1", "\"commandId\":+1"),
            valid.replace("\"commandId\":1", "\"commandId\":9223372036854775808"),
            valid.replace("\"expectedRevision\":0", "\"expectedRevision\":-9223372036854775809"),
            valid.replace("\"protocolVersion\":1", "\"protocolVersion\":\"1\""),
            valid.replace("\"protocolVersion\":1", "\"protocolVersion\":1.0"),
            valid.replace(",\"protocolVersion\":1", ""),
            valid.dropLast(1) + ",}",
            valid.replace("\"room\"", "\"ro\\uD800om\""),
            valid.replace("\"room\"", "\"ro\\uDC00om\""),
            valid.replace("\"room\"", "\"ro\u0000om\""),
            valid.replace("\"room\"", "\"ro\\x41om\""),
            valid.replace("\"intent\":", "\"playerId\":\"p0\",\"intent\":"),
            valid.replace("\"command\"", "\"unknown_command\""),
        )
        malformed.forEach { assertMalformed(it.encodeToByteArray()) }
        val invalidUtf8 = listOf(
            byteArrayOf(0x80.toByte()), byteArrayOf(0xc0.toByte(), 0xaf.toByte()),
            byteArrayOf(0xc2.toByte()), byteArrayOf(0xed.toByte(), 0xa0.toByte(), 0x80.toByte()),
            byteArrayOf(0xf4.toByte(), 0x90.toByte(), 0x80.toByte(), 0x80.toByte()),
        )
        invalidUtf8.forEach(::assertMalformed)
        assertEquals(SessionError.UNSUPPORTED_VERSION, assertIs<WireDecodeResult.Failure>(
            SessionCodec.decodeClient(valid.replace("\"protocolVersion\":1", "\"protocolVersion\":2").encodeToByteArray()),
        ).error)
    }

    @Test
    fun parserBoundsDepthCollectionsAndTotalBytesWithoutEchoingSecrets() {
        val valid = validCommand()
        val deep = "[".repeat(1_000) + "0" + "]".repeat(1_000)
        assertMalformed(valid.replace("\"ready\":true", "\"ready\":$deep").encodeToByteArray())
        val manyCards = (1..65).joinToString(",") { "\"r1-c$it\"" }
        val tooManySelection = valid.replace("\"type\":\"set_ready\",\"ready\":true", "\"type\":\"play_cards\",\"cardIds\":[$manyCards]")
        assertMalformed(tooManySelection.encodeToByteArray())
        val tooManyFields = (1..33).joinToString(",") { "\"field$it\":0" }
        assertMalformed("{$tooManyFields}".encodeToByteArray())
        assertMalformed(valid.replace("\"room\"", "\"${"s".repeat(1_100)}\"").encodeToByteArray())
        assertEquals(SessionError.PAYLOAD_TOO_LARGE, assertIs<WireDecodeResult.Failure>(
            SessionCodec.decodeClient(ByteArray(MAX_WIRE_BYTES + 1) { ' '.code.toByte() }),
        ).error)
        val marker = "secret-must-not-appear-in-diagnostics"
        val failure = assertIs<WireDecodeResult.Failure>(SessionCodec.decodeClient("{\"$marker\":bad}".encodeToByteArray()))
        assertFalse(failure.toString().contains(marker))
    }

    @Test
    fun validEscapesWhitespaceAndSupplementaryCharactersDoNotConfusePreflight() {
        val message = ClientMessage.Join("room", "a".repeat(64), "Ada \"[]{}\" 🌟")
        val decoded = SessionCodec.decodeClient(" \n\t".encodeToByteArray() + SessionCodec.encodeClient(message) + "\r ".encodeToByteArray())
        assertEquals(message, assertIs<WireDecodeResult.Success<ClientMessage>>(decoded).value)
    }

    private fun assertMalformed(bytes: ByteArray) {
        assertEquals(SessionError.MALFORMED_MESSAGE, assertIs<WireDecodeResult.Failure>(SessionCodec.decodeClient(bytes)).error)
    }

    private fun validCommand(): String =
        "{\"type\":\"command\",\"sessionId\":\"room\",\"commandId\":1,\"expectedRevision\":0,\"intent\":{\"type\":\"set_ready\",\"ready\":true},\"protocolVersion\":1}"

    private fun assertPrivateMessage(message: ServerMessage, table: Table, allCardIds: Set<String>) {
        val tree = encoded(message)
        val strings = stringValues(tree)
        val keys = fieldNames(tree)
        assertTrue(keys.intersect(setOf("burnoutStep", "undealtCards", "discardedCards", "pendingPlay", "random", "seed")).isEmpty())
        assertFalse(table.admissionSecret in strings)
        val view = when (message) {
            is ServerMessage.Welcome -> message.view
            is ServerMessage.Snapshot -> message.view
            else -> null
        }
        val allowedCards = view?.game?.let { game ->
            game.yourHand.map { it.id }.toSet() + game.roundOutcome?.revealedCards.orEmpty().map { it.id }
        }.orEmpty()
        assertTrue((strings intersect allCardIds).all { it in allowedCards })
        table.welcomes.values.forEach { welcome ->
            val permitted = message is ServerMessage.Welcome && message.playerId == welcome.playerId
            if (!permitted) assertFalse(welcome.reconnectToken in strings)
        }
    }

    private fun encoded(message: ServerMessage): JsonElement =
        Json.parseToJsonElement(SessionCodec.encodeServer(message).decodeToString())

    private fun stringValues(element: JsonElement): Set<String> = when (element) {
        is JsonObject -> element.values.flatMap(::stringValues).toSet()
        is JsonArray -> element.flatMap(::stringValues).toSet()
        is JsonPrimitive -> if (element.isString) setOf(element.content) else emptySet()
    }

    private fun fieldNames(element: JsonElement): Set<String> = when (element) {
        is JsonObject -> element.keys + element.values.flatMap(::fieldNames)
        is JsonArray -> element.flatMap(::fieldNames).toSet()
        is JsonPrimitive -> emptySet()
    }

    private fun SessionDispatch.receipt(): CommandReceipt =
        deliveries.mapNotNull { (it.message as? ServerMessage.Receipt)?.receipt }.single()

    private class Table(replayCacheSize: Int = 64) {
        val id = "room"
        val admissionSecret = "a".repeat(64)
        val host = SessionPeer("host-local")
        val peers = listOf(host, SessionPeer("guest-a"), SessionPeer("guest-b"))
        private var tokenCounter = 1
        val authority = HostAuthority(
            HostSessionConfig(id, admissionSecret, "Host", host, replayCacheSize),
            LastLightEngine(Random(0x51cafe)),
        ) { (tokenCounter++).toString(16).padStart(64, '0') }
        val welcomes = linkedMapOf<String, ServerMessage.Welcome>()
        private val nextCommandIds = mutableMapOf<String, Long>()

        init {
            welcomes[host.connectionId] = authority.initialDispatch().deliveries.single().message as ServerMessage.Welcome
            peers.drop(1).forEachIndexed { index, peer ->
                val dispatch = authority.handle(peer, ClientMessage.Join(id, admissionSecret, "Guest ${index + 1}"))
                welcomes[peer.connectionId] = dispatch.deliveries.first().message as ServerMessage.Welcome
            }
        }

        fun welcome(peer: SessionPeer): ServerMessage.Welcome = welcomes.getValue(peer.connectionId)
        fun view(peer: SessionPeer): SessionView = checkNotNull(authority.viewFor(peer))
        fun actor(): SessionPeer = peers.single { welcome(it).playerId == view(host).game!!.turnPlayerId }
        fun send(peer: SessionPeer, intent: ClientIntent): SessionDispatch {
            val next = nextCommandIds[peer.connectionId] ?: 1L
            nextCommandIds[peer.connectionId] = next + 1
            return authority.handle(peer, ClientMessage.Command(id, next, view(peer).revision, intent))
        }
        fun start() {
            peers.drop(1).forEach { send(it, ClientIntent.SetReady(true)) }
            send(host, ClientIntent.StartGame)
            check(view(host).phase == SessionPhase.GAME)
        }
    }
}
