package dev.partydeck.transport

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.async
import kotlinx.coroutines.cancelAndJoin
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.take
import kotlinx.coroutines.flow.toList
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.withContext
import kotlinx.coroutines.withTimeout
import java.net.InetSocketAddress
import java.net.ServerSocket
import java.net.Socket
import java.net.SocketException
import javax.net.ssl.SSLSocket
import kotlin.test.Test
import kotlin.test.assertContentEquals
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertFalse
import kotlin.test.assertIs

/** Real JSSE sockets complement the common callback tests and controller integration tests. */
class JavaTlsTransportTest {
    @Test
    fun completePinProtectsOrderedMaximumSizeFramesAndPeerClosure(): Unit = runBlocking {
        withTimeout(15_000) {
            val hosting = JvmLanTransportFactory().create()
            val joining = JvmLanTransportFactory().create()
            try {
                val host = hosting.host("TLS frame test")
                val client = joining.connect(loopback(host), host.info.certificateSha256)
                val server = host.incomingConnections.first()
                val messages = listOf(
                    "first".encodeToByteArray(),
                    ByteArray(MAX_FRAME_BYTES) { (it % 251).toByte() },
                    "last".encodeToByteArray(),
                )
                val received = async { server.incoming.take(messages.size).toList() }
                messages.forEach { client.send(it) }
                received.await().zip(messages).forEach { (actual, expected) -> assertContentEquals(expected, actual) }

                val reply = "accepted".encodeToByteArray()
                server.send(reply)
                assertContentEquals(reply, client.incoming.first())
                client.close()
                server.state.first { it != ConnectionState.Connected }
                assertEquals(ConnectionState.Closed, client.state.value)
                host.close()
                withContext(Dispatchers.IO) {
                    assertFailsWith<SocketException> {
                        Socket().use { it.connect(InetSocketAddress("127.0.0.1", host.info.endpoints.first().port), 1_000) }
                    }
                }
            } finally {
                joining.close()
                hosting.close()
            }
        }
    }

    @Test
    fun changedPinIsRejectedBeforeReturningAConnection(): Unit = runBlocking {
        withTimeout(15_000) {
            val hosting = JvmLanTransportFactory().create()
            val joining = JvmLanTransportFactory().create()
            try {
                val host = hosting.host("TLS pin test")
                val correct = host.info.certificateSha256
                val incorrect = (if (correct.first() == '0') "1" else "0") + correct.drop(1)
                val failure = assertFailsWith<TransportException> { joining.connect(loopback(host), incorrect) }
                assertEquals(TransportFailureCode.AUTHENTICATION_FAILED, failure.failure.code)

                // A rejected guest must leave the listener usable for a correctly pinned one.
                joining.connect(loopback(host), correct).close()
            } finally {
                joining.close()
                hosting.close()
            }
        }
    }

    @Test
    fun cachedDiscoveryCanReplaceAnUnreachableAddressButNotAnAuthenticationFailure(): Unit = runBlocking {
        withTimeout(15_000) {
            val hosting = JvmLanTransportFactory().create()
            val otherHosting = JvmLanTransportFactory().create()
            var joining: LanTransport? = null
            try {
                val host = hosting.host("TLS discovery target")
                val otherHost = otherHosting.host("Different TLS identity")
                val discovered = loopback(host).copy(serviceName = host.info.serviceName)
                val discovery = object : JavaLanDiscovery by ManualJavaDiscovery() {
                    override fun lookup(serviceName: String): LanEndpoint? =
                        discovered.takeIf { it.serviceName == serviceName }
                }
                val client = CallbackLanTransport(JavaLanDriver(discovery, allowLoopbackFallback = true))
                joining = client
                val unusedPort = withContext(Dispatchers.IO) { ServerSocket(0).use { it.localPort } }

                // A current public NSD address can recover a stale endpoint, using the same pin.
                client.connect(
                    LanEndpoint("127.0.0.1", unusedPort, host.info.serviceName),
                    host.info.certificateSha256,
                ).close()

                // A live endpoint that presents another certificate is a terminal rejection,
                // even when discovery could supply a correctly pinned alternative afterward.
                val rejected = assertFailsWith<TransportException> {
                    client.connect(
                        loopback(otherHost).copy(serviceName = host.info.serviceName),
                        host.info.certificateSha256,
                    )
                }
                assertEquals(TransportFailureCode.AUTHENTICATION_FAILED, rejected.failure.code)
            } finally {
                joining?.close()
                otherHosting.close()
                hosting.close()
            }
        }
    }

    @Test
    fun malformedAndTruncatedTlsPayloadsCloseOnlyTheirConnection(): Unit = runBlocking {
        withTimeout(15_000) {
            val hosting = JvmLanTransportFactory().create()
            try {
                val host = hosting.host("TLS invalid frame test")
                val wireInputs = listOf(
                    // One byte beyond the shared maximum; the body must never be allocated.
                    byteArrayOf(0, 1, 0, 1),
                    // A complete header followed by only half of its declared payload.
                    byteArrayOf(0, 0, 0, 4, 11, 12),
                    // A truncated header is also an incomplete frame.
                    byteArrayOf(0, 0),
                )
                for (wire in wireInputs) {
                    val socket = pinnedSocket(host)
                    try {
                        val incoming = host.incomingConnections.first()
                        withContext(Dispatchers.IO) {
                            socket.outputStream.write(wire)
                            socket.outputStream.flush()
                            socket.close()
                        }
                        val terminal = incoming.state.first { it != ConnectionState.Connected }
                        assertEquals(TransportFailureCode.INVALID_FRAME, assertIs<ConnectionState.Failed>(terminal).failure.code)
                    } finally {
                        withContext(Dispatchers.IO) { socket.close() }
                    }
                }
            } finally {
                hosting.close()
            }
        }
    }

    @Test
    fun slowHandshakeHasAnAbsoluteDeadlineEvenWhileBytesKeepArriving(): Unit = runBlocking {
        withTimeout(12_000) {
            val hosting = CallbackLanTransport(
                JavaLanDriver(ManualJavaDiscovery(), allowLoopbackFallback = true, handshakeTimeoutMillis = 1_200),
            )
            val joining = JvmLanTransportFactory().create()
            try {
                val host = hosting.host("TLS slow peer test")
                val socket = withContext(Dispatchers.IO) { Socket("127.0.0.1", host.info.endpoints.first().port) }
                try {
                    withContext(Dispatchers.IO) {
                        // A TLS handshake record declaring 4 KiB. JSSE waits for the remainder;
                        // frequent progress keeps its individual 10 s reads from timing out.
                        socket.outputStream.write(byteArrayOf(22, 3, 3, 0x10, 0))
                        socket.outputStream.flush()
                    }
                    val trickle = launch(Dispatchers.IO) {
                        try {
                            while (isActive) {
                                socket.outputStream.write(0)
                                socket.outputStream.flush()
                                delay(40)
                            }
                        } catch (_: SocketException) {
                            // The expected absolute deadline can reset the TCP peer.
                        }
                    }
                    try {
                        awaitRemoteClose(socket)
                    } finally {
                        trickle.cancelAndJoin()
                    }
                    // A timed-out native handshake did not terminate the transport/listener.
                    joining.connect(loopback(host), host.info.certificateSha256).close()
                } finally {
                    withContext(Dispatchers.IO) { socket.close() }
                }
            } finally {
                joining.close()
                hosting.close()
            }
        }
    }

    @Test
    fun cancellingAConnectingCallerClosesItsActualBlockedTlsSocket(): Unit = runBlocking {
        withTimeout(10_000) {
            val joining = JvmLanTransportFactory().create()
            val listener = ServerSocket(0)
            try {
                var delivered = false
                val connecting = async {
                    joining.connect(LanEndpoint("127.0.0.1", listener.localPort), "0".repeat(64))
                    delivered = true
                }
                val accepted = withContext(Dispatchers.IO) { listener.accept() }
                try {
                    connecting.cancelAndJoin()
                    assertFalse(delivered)
                    awaitRemoteClose(accepted)
                } finally {
                    withContext(Dispatchers.IO) { accepted.close() }
                }
            } finally {
                withContext(Dispatchers.IO) { listener.close() }
                joining.close()
            }
        }
    }

    private fun loopback(host: LanHost) = LanEndpoint("127.0.0.1", host.info.endpoints.first().port)

    private suspend fun pinnedSocket(host: LanHost): SSLSocket = withContext(Dispatchers.IO) {
        (JavaTlsIdentity.clientContext(host.info.certificateSha256).socketFactory
            .createSocket("127.0.0.1", host.info.endpoints.first().port) as SSLSocket).also {
            configureTlsSocket(it, client = true)
            it.startHandshake()
        }
    }

    private suspend fun awaitRemoteClose(socket: Socket) = withContext(Dispatchers.IO) {
        // A test failure occurs well before the production 10 s per-read TLS timeout.
        socket.soTimeout = 3_500
        try {
            val input = socket.inputStream
            val buffer = ByteArray(1_024)
            while (input.read(buffer) >= 0) { /* Drain any already-sent handshake bytes. */ }
        } catch (_: SocketException) {
            // Either EOF or TCP reset proves that the owner released the remote socket.
        }
    }
}
