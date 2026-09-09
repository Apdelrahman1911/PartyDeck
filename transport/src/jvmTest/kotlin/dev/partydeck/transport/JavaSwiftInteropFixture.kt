package dev.partydeck.transport

import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.async
import kotlinx.coroutines.cancelAndJoin
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.withTimeout
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.put
import java.nio.file.AtomicMoveNotSupportedException
import java.nio.file.Files
import java.nio.file.Path
import java.nio.file.StandardCopyOption.ATOMIC_MOVE
import java.nio.file.StandardCopyOption.REPLACE_EXISTING
import kotlin.system.exitProcess
import kotlin.test.Test
import kotlin.test.assertContentEquals
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith

/**
 * A CI-owned JVM peer for NativeTransportTests' real Swift Network.framework driver.
 * Launch outside Gradle/XCTest; see docs/research/jvm-swift-interop.md for the wire contract.
 * This lives only on the JVM test classpath and never enters a shipping application.
 */
object JavaSwiftInteropFixture {
    @JvmStatic
    fun main(args: Array<String>) {
        require(args.size == 2) { "Usage: JavaSwiftInteropFixture <manifest-path> <result-path>" }
        val manifestPath = Path.of(args[0]).toAbsolutePath().normalize()
        val resultPath = Path.of(args[1]).toAbsolutePath().normalize()
        require(manifestPath != resultPath) { "Manifest and result paths must differ" }
        var stage = "preparing-output"
        try {
            Files.deleteIfExists(manifestPath)
            Files.deleteIfExists(resultPath)
            val result = runBlocking {
                serveInterop(
                    onReady = { writeAtomically(manifestPath, it.json()) },
                    onStage = {
                        stage = it
                        println("PartyDeck interop: $it")
                    },
                )
            }
            stage = "writing-result"
            writeAtomically(resultPath, result.json())
            println("PartyDeck interop: PASS (both host directions, payloads acknowledged, peers closed)")
        } catch (error: Exception) {
            val result = buildJsonObject {
                put("version", 1)
                put("status", "FAIL")
                put("stage", stage)
                put("error", "${error.javaClass.simpleName}: ${error.message.orEmpty()}")
            }
            try {
                writeAtomically(resultPath, result)
            } catch (writeFailure: Exception) {
                error.addSuppressed(writeFailure)
            }
            System.err.println("PartyDeck interop: FAIL at $stage")
            error.printStackTrace(System.err)
            exitProcess(1)
        }
    }
}

private const val PROTOCOL = "PARTYDECK-INTEROP-1"
private const val REVERSE_OK = "$PROTOCOL-REVERSE-OK"
private const val FORWARD_OK = "$PROTOCOL-OK"
private const val COMPLETE = "$PROTOCOL-COMPLETE"
private const val LARGE_PAYLOAD_BYTES = 65_536
private const val SMALL_PAYLOAD_BYTES = 20_000
private const val STARTUP_TIMEOUT_MILLIS = 20 * 60 * 1_000L
private const val EXCHANGE_TIMEOUT_MILLIS = 120_000L

private data class InteropManifest(val port: Int, val certificateSha256: String) {
    fun json() = buildJsonObject {
        put("version", 1)
        put("port", port)
        put("certificateSha256", certificateSha256)
    }
}

private data class InteropResult(val forwardTerminalState: String, val reverseTerminalState: String) {
    fun json() = buildJsonObject {
        put("version", 1)
        put("status", "PASS")
        put("forwardBytesReceived", LARGE_PAYLOAD_BYTES)
        put("forwardBytesSent", SMALL_PAYLOAD_BYTES)
        put("reverseBytesSent", SMALL_PAYLOAD_BYTES)
        put("reverseBytesReceived", LARGE_PAYLOAD_BYTES)
        put("forwardTerminalState", forwardTerminalState)
        put("reverseTerminalState", reverseTerminalState)
    }
}

private suspend fun serveInterop(
    startupTimeoutMillis: Long = STARTUP_TIMEOUT_MILLIS,
    exchangeTimeoutMillis: Long = EXCHANGE_TIMEOUT_MILLIS,
    onReady: (InteropManifest) -> Unit,
    onStage: (String) -> Unit = {},
): InteropResult {
    check(MAX_FRAME_BYTES == LARGE_PAYLOAD_BYTES) { "Update both fixture peers when the transport limit changes" }
    val transport = JvmLanTransportFactory().create()
    try {
        onStage("starting-jvm-listener")
        val host = transport.host("JVM Swift TLS fixture")
        onReady(InteropManifest(host.info.endpoints.first().port, host.info.certificateSha256))
        onStage("waiting-for-swift-client")
        // Xcode can compile the app after this process publishes its ready manifest.
        val forward = withTimeout(startupTimeoutMillis) { host.incomingConnections.first() }
        return withTimeout(exchangeTimeoutMillis) {
            onStage("receiving-swift-listener")
            val callback = parseCallback(forward.incoming.first())
            onStage("receiving-forward-payload")
            requirePayload(forward.incoming.first(), pattern(LARGE_PAYLOAD_BYTES, 31, 7), "forward request")

            onStage("connecting-to-swift-listener")
            // The control record cannot redirect this test process to an arbitrary network host.
            val reverse = transport.connect(LanEndpoint("127.0.0.1", callback.port), callback.certificateSha256)
            onStage("exchanging-reverse-payloads")
            reverse.send(pattern(SMALL_PAYLOAD_BYTES, 17, 3))
            requirePayload(reverse.incoming.first(), pattern(LARGE_PAYLOAD_BYTES, 13, 11), "reverse reply")
            reverse.send(REVERSE_OK.encodeToByteArray())
            onStage("waiting-for-reverse-close")
            val reverseTerminal = awaitPeerClose(reverse)

            onStage("sending-forward-reply")
            forward.send(pattern(SMALL_PAYLOAD_BYTES, 19, 5))
            requirePayload(forward.incoming.first(), FORWARD_OK.encodeToByteArray(), "forward acknowledgement")
            forward.send(COMPLETE.encodeToByteArray())
            onStage("waiting-for-forward-close")
            val forwardTerminal = awaitPeerClose(forward)
            InteropResult(forwardTerminal, reverseTerminal)
        }
    } finally {
        // PASS is returned only after the actual native listener and all owned peers are closed.
        transport.close()
    }
}

private fun parseCallback(payload: ByteArray): InteropManifest {
    require(payload.size <= 128) { "Oversized fixture control record" }
    val fields = payload.decodeToString(throwOnInvalidSequence = true).split('\n')
    require(fields.size == 3 && fields[0] == PROTOCOL) { "Invalid fixture control record" }
    require(fields[1].matches(Regex("[1-9][0-9]{0,4}"))) { "Invalid callback port" }
    val port = fields[1].toInt()
    require(port in 1..65_535) { "Invalid callback port" }
    require(fields[2].matches(Regex("[0-9a-f]{64}"))) { "Callback requires a complete lowercase certificate pin" }
    return InteropManifest(port, fields[2])
}

private fun pattern(size: Int, multiplier: Int, offset: Int) =
    ByteArray(size) { ((it * multiplier + offset) % 251).toByte() }

private fun requirePayload(actual: ByteArray, expected: ByteArray, label: String) {
    check(actual.contentEquals(expected)) {
        "Unexpected $label: received ${actual.size} bytes, expected ${expected.size} bytes with exact content"
    }
}

private suspend fun awaitPeerClose(connection: LanConnection): String =
    when (val terminal = connection.state.first { it != ConnectionState.Connected }) {
        ConnectionState.Closed -> "Closed"
        is ConnectionState.Failed -> {
            // Network.framework cancellation may arrive as EOF or a TLS/socket reset. An idle
            // deadline or malformed frame is not evidence that Swift reached its close step.
            check(terminal.failure.code in setOf(TransportFailureCode.IO_ERROR, TransportFailureCode.UNAVAILABLE)) {
                "Unexpected terminal state: ${terminal.failure.code}"
            }
            "Failed:${terminal.failure.code}"
        }
        ConnectionState.Connected -> error("A connected peer is not terminal")
    }

private fun writeAtomically(path: Path, json: JsonObject) {
    Files.createDirectories(path.parent)
    val temporary = Files.createTempFile(path.parent, ".partydeck-interop-", ".json")
    try {
        Files.writeString(temporary, "$json\n")
        try {
            Files.move(temporary, path, ATOMIC_MOVE, REPLACE_EXISTING)
        } catch (_: AtomicMoveNotSupportedException) {
            Files.move(temporary, path, REPLACE_EXISTING)
        }
    } finally {
        Files.deleteIfExists(temporary)
    }
}

/** Validates fixture orchestration using real Java peers; this is not Swift execution evidence. */
class JavaSwiftInteropFixtureTest {
    @Test
    fun protocolExchangesBothDirectionsAndWaitsForPeerAcknowledgements(): Unit = runBlocking {
        withTimeout(20_000) {
            val ready = CompletableDeferred<InteropManifest>()
            val fixture = async { serveInterop(10_000, 10_000, onReady = { ready.complete(it) }) }
            val peer = JvmLanTransportFactory().create()
            try {
                val peerHost = peer.host("Fixture self-test peer")
                val manifest = ready.await()
                val forward = peer.connect(LanEndpoint("127.0.0.1", manifest.port), manifest.certificateSha256)
                forward.send("PARTYDECK-INTEROP-1\n${peerHost.info.endpoints.first().port}\n${peerHost.info.certificateSha256}".encodeToByteArray())
                forward.send(ByteArray(65_536) { ((it * 31 + 7) % 251).toByte() })

                val reverse = peerHost.incomingConnections.first()
                assertContentEquals(ByteArray(20_000) { ((it * 17 + 3) % 251).toByte() }, reverse.incoming.first())
                reverse.send(ByteArray(65_536) { ((it * 13 + 11) % 251).toByte() })
                assertEquals("PARTYDECK-INTEROP-1-REVERSE-OK", reverse.incoming.first().decodeToString())
                reverse.close()

                assertContentEquals(ByteArray(20_000) { ((it * 19 + 5) % 251).toByte() }, forward.incoming.first())
                forward.send("PARTYDECK-INTEROP-1-OK".encodeToByteArray())
                assertEquals("PARTYDECK-INTEROP-1-COMPLETE", forward.incoming.first().decodeToString())
                forward.close()
                val result = fixture.await().json()
                assertEquals("\"PASS\"", result["status"].toString())
                assertEquals("65536", result["forwardBytesReceived"].toString())
                assertEquals("65536", result["reverseBytesReceived"].toString())
            } finally {
                peer.close()
                fixture.cancelAndJoin()
            }
        }
    }

    @Test
    fun corruptedPayloadFailsTheFixtureBeforeReverseConnection(): Unit = runBlocking {
        withTimeout(20_000) {
            val ready = CompletableDeferred<InteropManifest>()
            val fixture = async {
                assertFailsWith<IllegalStateException> {
                    serveInterop(10_000, 10_000, onReady = { ready.complete(it) })
                }
            }
            val peer = JvmLanTransportFactory().create()
            try {
                val peerHost = peer.host("Corrupt fixture self-test peer")
                val manifest = ready.await()
                val forward = peer.connect(LanEndpoint("127.0.0.1", manifest.port), manifest.certificateSha256)
                forward.send("PARTYDECK-INTEROP-1\n${peerHost.info.endpoints.first().port}\n${peerHost.info.certificateSha256}".encodeToByteArray())
                val corrupt = ByteArray(65_536) { ((it * 31 + 7) % 251).toByte() }
                corrupt[32_768] = (corrupt[32_768].toInt() xor 1).toByte()
                forward.send(corrupt)
                assertEquals(
                    "Unexpected forward request: received 65536 bytes, expected 65536 bytes with exact content",
                    fixture.await().message,
                )
                forward.state.first { it != ConnectionState.Connected }
            } finally {
                peer.close()
                fixture.cancelAndJoin()
            }
        }
    }
}
