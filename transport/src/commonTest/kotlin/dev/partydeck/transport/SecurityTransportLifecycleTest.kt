package dev.partydeck.transport

import kotlinx.coroutines.CoroutineDispatcher
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.async
import kotlinx.coroutines.cancel
import kotlinx.coroutines.flow.take
import kotlinx.coroutines.flow.toList
import kotlinx.coroutines.launch
import kotlinx.coroutines.test.StandardTestDispatcher
import kotlinx.coroutines.test.TestScope
import kotlinx.coroutines.test.runCurrent
import kotlinx.coroutines.test.runTest
import kotlin.coroutines.CoroutineContext
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFalse
import kotlin.test.assertTrue

/** Deterministic ownership/flood tests, independent of the operating system's TLS implementation. */
@OptIn(ExperimentalCoroutinesApi::class)
class SecurityTransportLifecycleTest {
    @Test
    fun oneUnadmittedPeerCannotStopTheListenerOrAnotherPeerByFloodingCallbacks() = runTest {
        val driver = RecordingDriver()
        val transport = CallbackLanTransport(driver, configuration(), StandardTestDispatcher(testScheduler))
        try {
            val starting = async { transport.host("Table") }
            runCurrent()
            val host = starting.await()
            val hostId = driver.openHosts.single()
            driver.accept(hostId, "flooding-peer")
            driver.accept(hostId, "honest-peer")
            runCurrent()
            val accepted = host.incomingConnections.take(2).toList()
            val honest = accepted.single { it.id == "honest-peer" }

            // No admission credential is necessary to reach this native TLS callback boundary.
            // Burst callbacks before the serial adapter can drain them, as a native read loop can.
            repeat(80) {
                if ("flooding-peer" in driver.openConnections) {
                    if (!driver.observer.onConnectionBytes("flooding-peer", ByteArray(NATIVE_READ_CHUNK_BYTES))) {
                        driver.closeConnection("flooding-peer")
                    }
                }
            }
            runCurrent()
            assertEquals(0, driver.wholeDriverCloses, "A peer receive overflow must not close the entire transport")
            assertTrue(hostId in driver.openHosts)
            assertEquals(ConnectionState.Connected, honest.state.value)
        } finally {
            transport.close()
        }
    }

    @Test
    fun cancelledConnectReturnClosesTheNativeConnectionBeforeCallerClaimsIt() = runTest {
        assertPromptCancellationOwnership(hosting = false)
    }

    @Test
    fun cancelledHostReturnClosesTheNativeListenerBeforeCallerClaimsIt() = runTest {
        assertPromptCancellationOwnership(hosting = true)
    }

    private suspend fun TestScope.assertPromptCancellationOwnership(hosting: Boolean) {
        val driver = RecordingDriver()
        val transport = CallbackLanTransport(driver, configuration(), StandardTestDispatcher(testScheduler))
        val callerDispatcher = PausedDispatcher()
        val callerScope = CoroutineScope(SupervisorJob() + callerDispatcher)
        var delivered = false
        val caller = callerScope.launch {
            if (hosting) transport.host("Table")
            else transport.connect(LanEndpoint("127.0.0.1", 12345), PIN)
            delivered = true
        }
        try {
            callerDispatcher.runAll()
            runCurrent()
            if (!hosting) {
                driver.completeConnect("new-connection")
                runCurrent()
            }
            // The inner dispatcher acquired the resource and queued its result on the caller.
            assertTrue(callerDispatcher.hasWork)
            assertFalse(delivered)
            assertTrue(if (hosting) driver.openHosts.isNotEmpty() else driver.openConnections.isNotEmpty())

            caller.cancel()
            callerDispatcher.runAll()
            runCurrent()
            // Cleanup crosses back from the transport dispatcher before the caller can finish.
            callerDispatcher.runAll()
            assertTrue(caller.isCompleted)
            assertFalse(delivered)
            assertTrue(
                if (hosting) driver.openHosts.isEmpty() else driver.openConnections.isEmpty(),
                "A resource discarded by withContext prompt cancellation must still be closed",
            )
        } finally {
            callerScope.cancel()
            callerDispatcher.runAll()
            transport.close()
        }
    }

    private class PausedDispatcher : CoroutineDispatcher() {
        private val work = ArrayDeque<Runnable>()
        val hasWork: Boolean get() = work.isNotEmpty()

        override fun dispatch(context: CoroutineContext, block: Runnable) { work.addLast(block) }
        fun runAll() { while (work.isNotEmpty()) work.removeFirst().run() }
    }

    private class RecordingDriver : NativeLanDriver {
        lateinit var observer: NativeLanObserver
        val openHosts = mutableSetOf<String>()
        val openConnections = mutableSetOf<String>()
        var wholeDriverCloses = 0
        private var pendingConnect: String? = null

        override fun attach(observer: NativeLanObserver) { this.observer = observer }
        override fun startHost(operationId: String, displayName: String) {
            openHosts.add(operationId)
            observer.onHostReady(operationId, HostInfo(displayName, "room", listOf(LanEndpoint("127.0.0.1", 12345)), PIN))
        }
        override fun stopHost(hostId: String) { openHosts.remove(hostId) }
        override fun startDiscovery(operationId: String) { observer.onDiscoveryStarted(operationId) }
        override fun stopDiscovery(operationId: String) = Unit
        override fun connect(operationId: String, endpoint: LanEndpoint, certificateSha256: String) { pendingConnect = operationId }
        override fun cancelConnect(operationId: String) {
            if (pendingConnect == operationId) pendingConnect = null
        }
        override fun send(connectionId: String, operationId: String, bytes: ByteArray) {
            observer.onSendComplete(operationId, null, null)
        }
        override fun closeConnection(connectionId: String) {
            if (openConnections.remove(connectionId)) observer.onConnectionClosed(connectionId, null, null)
        }
        override fun close() {
            wholeDriverCloses++
            openHosts.clear()
            openConnections.clear()
            pendingConnect = null
        }

        fun completeConnect(connectionId: String) {
            val operationId = checkNotNull(pendingConnect)
            pendingConnect = null
            openConnections.add(connectionId)
            observer.onConnected(operationId, connectionId)
        }
        fun accept(hostId: String, connectionId: String) {
            openConnections.add(connectionId)
            observer.onIncomingConnection(hostId, connectionId)
        }
    }

    private fun configuration() = TransportConfiguration(
        operationTimeoutMillis = 1_000,
        writeTimeoutMillis = 1_000,
        heartbeatIntervalMillis = 1_000_000,
        idleTimeoutMillis = 2_000_000,
    )

    private companion object { const val PIN = "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb" }
}
