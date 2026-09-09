package dev.partydeck.transport

import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.CoroutineDispatcher
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.NonCancellable
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.TimeoutCancellationException
import kotlinx.coroutines.cancel
import kotlinx.coroutines.channels.Channel
import kotlinx.coroutines.currentCoroutineContext
import kotlinx.coroutines.delay
import kotlinx.coroutines.ensureActive
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.receiveAsFlow
import kotlinx.coroutines.launch
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import kotlinx.coroutines.withContext
import kotlinx.coroutines.withTimeout
import kotlin.time.TimeSource

/** Shared lifecycle/framing adapter around a real native TLS and DNS-SD driver. */
class CallbackLanTransport internal constructor(
    private val driver: NativeLanDriver,
    private val config: TransportConfiguration,
    private val dispatcher: CoroutineDispatcher,
) : LanTransport {
    /** Explicit overload is also the stable Swift construction boundary. */
    constructor(driver: NativeLanDriver) : this(
        driver,
        TransportConfiguration(),
        Dispatchers.Default.limitedParallelism(1),
    )

    private val scope = CoroutineScope(SupervisorJob() + dispatcher)
    private val events = Channel<NativeEvent>(128)
    private val terminated = MutableStateFlow(false)
    private val nativePeers = MutableStateFlow<Map<String, NativePeerAdmission>>(emptyMap())
    private val latestDiscovery = MutableStateFlow<DiscoverySnapshot?>(null)
    private val discoveryRefreshQueued = MutableStateFlow(false)
    private val mutableHosts = MutableStateFlow<List<DiscoveredHost>>(emptyList())
    private val mutableDiscovery = MutableStateFlow<DiscoveryState>(DiscoveryState.Idle)
    override val discoveredHosts = mutableHosts.asStateFlow()
    override val discoveryState = mutableDiscovery.asStateFlow()

    // These collections are only accessed on the serial dispatcher, including native events.
    private var nextOperation = 0L
    private var pendingHost: PendingHost? = null
    private var activeHost: Host? = null
    private var discoveryId: String? = null
    private var discoveryStarted: CompletableDeferred<Unit>? = null
    private val pendingConnections = mutableMapOf<String, PendingConnection>()
    private val connections = mutableMapOf<String, Connection>()
    private val pendingWrites = mutableMapOf<String, PendingWrite>()

    init {
        driver.attach(Observer())
        scope.launch {
            for (event in events) {
                if (!terminated.value) handle(event)
            }
        }
    }

    override suspend fun startDiscovery(): Unit = withContext(dispatcher) {
        ensureOpen()
        if (discoveryId != null) {
            discoveryStarted?.await()
            return@withContext
        }
        val operationId = operationId()
        val result = CompletableDeferred<Unit>()
        discoveryId = operationId
        discoveryStarted = result
        var started = false
        try {
            driver.startDiscovery(operationId)
            await(result, "Discovery did not start")
            started = true
        } finally {
            if (!started && discoveryId == operationId) {
                driver.stopDiscovery(operationId)
                discoveryId = null
                discoveryStarted = null
                if (mutableDiscovery.value !is DiscoveryState.Failed) {
                    mutableDiscovery.value = DiscoveryState.Idle
                }
            }
        }
    }

    override suspend fun stopDiscovery(): Unit = withContext(NonCancellable + dispatcher) {
        discoveryId?.let(driver::stopDiscovery)
        discoveryId = null
        discoveryStarted?.completeExceptionally(closedException())
        discoveryStarted = null
        mutableHosts.value = emptyList()
        mutableDiscovery.value = DiscoveryState.Idle
    }

    override suspend fun host(displayName: String): LanHost {
        var acquired: Host? = null
        try {
            return withContext(dispatcher) {
                ensureOpen()
                require(displayName.isNotBlank() && displayName.encodeToByteArray().size <= 80 &&
                    displayName.none { it.isISOControl() }) { "Invalid host name" }
                if (activeHost != null || pendingHost != null) {
                    throw failure(TransportFailureCode.BUSY, "This transport is already hosting")
                }
                val pending = PendingHost(operationId())
                pendingHost = pending
                var claimed = false
                try {
                    driver.startHost(pending.id, displayName)
                    val host = await(pending.result, "Hosting did not start")
                    currentCoroutineContext().ensureActive()
                    acquired = host
                    claimed = true
                    host
                } finally {
                    if (pendingHost === pending) pendingHost = null
                    if (!claimed) {
                        driver.stopHost(pending.id)
                        pending.host?.let { closeHost(it, null) }
                    }
                }
            }
        } catch (cancelled: CancellationException) {
            // withContext also has prompt cancellation when dispatching its result to the caller.
            withContext(NonCancellable + dispatcher) { acquired?.let { closeHost(it, null) } }
            throw cancelled
        }
    }

    override suspend fun connect(endpoint: LanEndpoint, certificateSha256: String): LanConnection {
        var acquired: Connection? = null
        try {
            return withContext(dispatcher) {
                ensureOpen()
                require(isSha256Hex(certificateSha256)) { "A complete certificate fingerprint is required" }
                if (connections.size + pendingConnections.size >= MAX_NATIVE_CONNECTIONS) {
                    throw failure(TransportFailureCode.BUSY, "Too many connections")
                }
                val pending = PendingConnection(operationId())
                pendingConnections[pending.id] = pending
                var claimed = false
                try {
                    driver.connect(pending.id, endpoint, certificateSha256)
                    val connection = await(pending.result, "The host did not respond")
                    currentCoroutineContext().ensureActive()
                    acquired = connection
                    claimed = true
                    connection
                } finally {
                    pendingConnections.remove(pending.id)
                    if (!claimed) {
                        driver.cancelConnect(pending.id)
                        pending.connection?.let { closeConnection(it, null) }
                    }
                }
            }
        } catch (cancelled: CancellationException) {
            withContext(NonCancellable + dispatcher) { acquired?.let { closeConnection(it, null) } }
            throw cancelled
        }
    }

    override suspend fun close(): Unit = withContext(NonCancellable + dispatcher) {
        shutdown(null)
    }

    private fun ensureOpen() {
        if (terminated.value) throw closedException()
    }

    private fun operationId(): String = "operation-${++nextOperation}"

    private suspend fun <T> await(result: CompletableDeferred<T>, message: String): T = try {
        withTimeout(config.operationTimeoutMillis) { result.await() }
    } catch (_: TimeoutCancellationException) {
        throw failure(TransportFailureCode.TIMED_OUT, message)
    }

    private fun publish(event: NativeEvent): Boolean {
        if (terminated.value) return false
        if (events.trySend(event).isSuccess) return true
        // Only lifecycle events use this path. Byte events have per-peer credits and cannot
        // occupy more than 64 slots; peer registration and in-flight operations are bounded.
        // Preserve a terminal/completion callback instead of terminating every other player.
        scope.launch { events.send(event) }
        return true
    }

    private fun registerNativePeer(id: String): Boolean {
        while (true) {
            val current = nativePeers.value
            if (id in current || current.size >= MAX_NATIVE_CONNECTIONS) return false
            if (nativePeers.compareAndSet(current, current + (id to NativePeerAdmission()))) return true
        }
    }

    private fun reserveByteEvent(id: String): Boolean {
        while (true) {
            val current = nativePeers.value
            val peer = current[id] ?: return false
            if (peer.terminal || peer.queuedChunks >= 8) return false
            if (nativePeers.compareAndSet(current, current + (id to peer.copy(queuedChunks = peer.queuedChunks + 1)))) return true
        }
    }

    private fun releaseByteEvent(id: String) {
        while (true) {
            val current = nativePeers.value
            val peer = current[id] ?: return
            if (nativePeers.compareAndSet(current, current + (id to peer.copy(queuedChunks = (peer.queuedChunks - 1).coerceAtLeast(0))))) return
        }
    }

    private fun markNativeTerminal(id: String): Boolean {
        while (true) {
            val current = nativePeers.value
            val peer = current[id] ?: return false
            if (peer.terminal) return false
            if (nativePeers.compareAndSet(current, current + (id to peer.copy(terminal = true)))) return true
        }
    }

    private fun releaseNativePeer(id: String) {
        while (true) {
            val current = nativePeers.value
            if (id !in current || nativePeers.compareAndSet(current, current - id)) return
        }
    }

    private fun rejectNativePeer(id: String, reason: TransportFailure) {
        if (markNativeTerminal(id)) publish(NativeEvent.ConnectionClosed(id, reason))
        driver.closeConnection(id)
    }

    private fun handle(event: NativeEvent) {
        when (event) {
            is NativeEvent.HostReady -> {
                val pending = pendingHost
                if (pending?.id != event.id) {
                    if (activeHost?.id != event.id) driver.stopHost(event.id)
                    return
                }
                if (!isSha256Hex(event.info.certificateSha256) || event.info.endpoints.isEmpty()) {
                    pending.result.completeExceptionally(failure(TransportFailureCode.UNAVAILABLE, "No usable host address"))
                    driver.stopHost(event.id)
                    return
                }
                val host = Host(event.id, event.info)
                pending.host = host
                activeHost = host
                pending.result.complete(host)
            }
            is NativeEvent.HostFailed -> {
                pendingHost?.takeIf { it.id == event.id }?.result?.completeExceptionally(TransportException(event.failure))
                activeHost?.takeIf { it.id == event.id }?.let { closeHost(it, event.failure) }
            }
            is NativeEvent.Incoming -> {
                val host = activeHost
                if (host?.id != event.hostId || connections.size >= MAX_NATIVE_CONNECTIONS || event.connectionId in connections) {
                    releaseNativePeer(event.connectionId)
                    driver.closeConnection(event.connectionId)
                    return
                }
                val connection = Connection(event.connectionId, event.hostId)
                connections[connection.id] = connection
                if (!host.incoming.trySend(connection).isSuccess) {
                    closeConnection(connection, TransportFailure(TransportFailureCode.BUSY, "Too many pending players"))
                }
            }
            is NativeEvent.Connected -> {
                val pending = pendingConnections[event.id]
                if (pending == null || connections.size >= MAX_NATIVE_CONNECTIONS || event.connectionId in connections) {
                    releaseNativePeer(event.connectionId)
                    driver.closeConnection(event.connectionId)
                    pending?.result?.completeExceptionally(failure(TransportFailureCode.BUSY, "Too many connections"))
                    return
                }
                val connection = Connection(event.connectionId, null)
                connections[connection.id] = connection
                pending.connection = connection
                pending.result.complete(connection)
            }
            is NativeEvent.ConnectFailed ->
                pendingConnections[event.id]?.result?.completeExceptionally(TransportException(event.failure))
            is NativeEvent.Bytes -> try {
                connections[event.id]?.receive(event.bytes)
            } finally {
                releaseByteEvent(event.id)
            }
            is NativeEvent.ConnectionClosed -> {
                connections[event.id]?.let { connection ->
                    val reason = if (event.failure == null && connection.decoder.hasPartialFrame) {
                        TransportFailure(TransportFailureCode.INVALID_FRAME, "The connection ended during a message")
                    } else event.failure
                    closeConnection(connection, reason, notifyDriver = false)
                }
                releaseNativePeer(event.id)
            }
            is NativeEvent.Sent -> {
                val write = pendingWrites[event.id] ?: return
                if (event.failure == null) write.result.complete(Unit)
                else {
                    write.result.completeExceptionally(TransportException(event.failure))
                    connections[write.connectionId]?.let { closeConnection(it, event.failure) }
                }
            }
            is NativeEvent.DiscoveryStarted -> if (discoveryId == event.id) {
                mutableDiscovery.value = DiscoveryState.Searching
                discoveryStarted?.complete(Unit)
                discoveryStarted = null
            }
            NativeEvent.DiscoveryRefresh -> {
                discoveryRefreshQueued.value = false
                latestDiscovery.value?.let { update ->
                    if (discoveryId == update.id) mutableHosts.value = update.hosts
                }
            }
            is NativeEvent.DiscoveryFailed -> if (discoveryId == event.id) {
                mutableDiscovery.value = DiscoveryState.Failed(event.failure)
                mutableHosts.value = emptyList()
                discoveryStarted?.completeExceptionally(TransportException(event.failure))
                discoveryStarted = null
                discoveryId = null
                driver.stopDiscovery(event.id)
            }
        }
    }

    private fun closeHost(host: Host, reason: TransportFailure?) {
        if (host.closed) return
        host.closed = true
        if (activeHost === host) activeHost = null
        driver.stopHost(host.id)
        connections.values.filter { it.hostId == host.id }.forEach { closeConnection(it, reason) }
        host.incoming.close(reason?.let(::TransportException))
    }

    private fun closeConnection(connection: Connection, reason: TransportFailure?, notifyDriver: Boolean = true) {
        if (connections.remove(connection.id) !== connection) return
        releaseNativePeer(connection.id)
        if (notifyDriver) driver.closeConnection(connection.id)
        connection.finish(reason)
        pendingWrites.values.filter { it.connectionId == connection.id }.forEach {
            it.result.completeExceptionally(reason?.let(::TransportException) ?: closedException())
        }
    }

    private fun shutdown(reason: TransportFailure?) {
        if (!terminated.compareAndSet(expect = false, update = true)) return
        val closeError = try {
            driver.close()
            null
        } catch (_: Exception) {
            TransportFailure(TransportFailureCode.IO_ERROR, "Network resources could not be closed cleanly")
        }
        val failure = reason ?: closeError
        val exception = failure?.let(::TransportException) ?: closedException()
        discoveryId = null
        discoveryStarted?.completeExceptionally(exception)
        discoveryStarted = null
        mutableHosts.value = emptyList()
        mutableDiscovery.value = failure?.let { DiscoveryState.Failed(it) } ?: DiscoveryState.Idle
        pendingHost?.result?.completeExceptionally(exception)
        pendingHost = null
        activeHost?.let {
            it.closed = true
            it.incoming.close(failure?.let(::TransportException))
        }
        activeHost = null
        pendingConnections.values.forEach { it.result.completeExceptionally(exception) }
        pendingConnections.clear()
        pendingWrites.values.forEach { it.result.completeExceptionally(exception) }
        pendingWrites.clear()
        connections.values.forEach { it.finish(failure) }
        connections.clear()
        nativePeers.value = emptyMap()
        latestDiscovery.value = null
        events.close()
        scope.cancel()
        if (closeError != null && reason == null) throw TransportException(closeError)
    }

    private inner class Host(val id: String, override val info: HostInfo) : LanHost {
        val incoming = Channel<LanConnection>(MAX_NATIVE_CONNECTIONS)
        override val incomingConnections = incoming.receiveAsFlow()
        var closed = false

        override suspend fun close(): Unit = withContext(NonCancellable + dispatcher) {
            closeHost(this@Host, null)
        }
    }

    private inner class Connection(override val id: String, val hostId: String?) : LanConnection {
        val decoder = FrameDecoder()
        private val received = Channel<ByteArray>(16)
        private val mutableState = MutableStateFlow<ConnectionState>(ConnectionState.Connected)
        override val state = mutableState.asStateFlow()
        override val incoming = received.receiveAsFlow()
        private val writeMutex = Mutex()
        private var lastReceived = TimeSource.Monotonic.markNow()
        private val keepalive = scope.launch {
            while (true) {
                delay(config.heartbeatIntervalMillis)
                if (lastReceived.elapsedNow().inWholeMilliseconds >= config.idleTimeoutMillis) {
                    closeConnection(this@Connection, TransportFailure(TransportFailureCode.TIMED_OUT, "The peer stopped responding"))
                    break
                }
                try {
                    write(FrameCodec.encode(ByteArray(0)))
                } catch (_: TransportException) {
                    // write() already closed the connection and exposed its typed failure.
                    break
                }
            }
        }

        override suspend fun send(bytes: ByteArray) {
            if (bytes.isEmpty()) throw failure(TransportFailureCode.INVALID_FRAME, "Application messages cannot be empty")
            if (bytes.size > MAX_FRAME_BYTES) throw failure(TransportFailureCode.MESSAGE_TOO_LARGE, "Message exceeds the transport limit")
            val frame = FrameCodec.encode(bytes)
            withContext(dispatcher) { write(frame) }
        }

        private suspend fun write(frame: ByteArray): Unit = writeMutex.withLock {
            if (mutableState.value != ConnectionState.Connected) throw closedException()
            val operationId = operationId()
            val pending = PendingWrite(id)
            pendingWrites[operationId] = pending
            try {
                driver.send(id, operationId, frame)
                withTimeout(config.writeTimeoutMillis) { pending.result.await() }
            } catch (_: TimeoutCancellationException) {
                val reason = TransportFailure(TransportFailureCode.TIMED_OUT, "The peer is not accepting messages")
                closeConnection(this@Connection, reason)
                throw TransportException(reason)
            } catch (cancelled: CancellationException) {
                // A cancelled stream write may have sent a prefix; never reuse that connection.
                closeConnection(this@Connection, null)
                throw cancelled
            } catch (error: TransportException) {
                closeConnection(this@Connection, error.failure)
                throw error
            } catch (_: Exception) {
                val reason = TransportFailure(TransportFailureCode.IO_ERROR, "The message could not be sent")
                closeConnection(this@Connection, reason)
                throw TransportException(reason)
            } finally {
                pendingWrites.remove(operationId)
            }
        }

        fun receive(bytes: ByteArray) {
            try {
                decoder.accept(bytes) { payload ->
                    lastReceived = TimeSource.Monotonic.markNow()
                    if (payload.isEmpty()) true
                    else if (received.trySend(payload).isSuccess) true
                    else {
                        closeConnection(this, TransportFailure(TransportFailureCode.IO_ERROR, "The peer sent messages faster than they could be processed"))
                        false
                    }
                }
            } catch (error: TransportException) {
                closeConnection(this, error.failure)
            }
        }

        fun finish(reason: TransportFailure?) {
            mutableState.value = reason?.let { ConnectionState.Failed(it) } ?: ConnectionState.Closed
            keepalive.cancel()
            received.close(reason?.let(::TransportException))
        }

        override suspend fun close(): Unit = withContext(NonCancellable + dispatcher) {
            closeConnection(this@Connection, null)
        }
    }

    private inner class Observer : NativeLanObserver {
        override fun onHostReady(operationId: String, info: HostInfo) { publish(NativeEvent.HostReady(operationId, info)) }
        override fun onHostFailed(operationId: String, code: TransportFailureCode, message: String) {
            publish(NativeEvent.HostFailed(operationId, TransportFailure(code, message)))
        }
        override fun onIncomingConnection(hostId: String, connectionId: String) {
            if (!registerNativePeer(connectionId) || !publish(NativeEvent.Incoming(hostId, connectionId))) {
                if (terminated.value) releaseNativePeer(connectionId)
                driver.closeConnection(connectionId)
            }
        }
        override fun onConnected(operationId: String, connectionId: String) {
            if (registerNativePeer(connectionId)) {
                if (!publish(NativeEvent.Connected(operationId, connectionId))) {
                    releaseNativePeer(connectionId)
                    driver.closeConnection(connectionId)
                }
            } else {
                driver.closeConnection(connectionId)
                publish(NativeEvent.ConnectFailed(operationId, TransportFailure(TransportFailureCode.BUSY, "Too many pending connections")))
            }
        }
        override fun onConnectFailed(operationId: String, code: TransportFailureCode, message: String) {
            publish(NativeEvent.ConnectFailed(operationId, TransportFailure(code, message)))
        }
        override fun onConnectionBytes(connectionId: String, bytes: ByteArray): Boolean {
            if (bytes.size > NATIVE_READ_CHUNK_BYTES) {
                rejectNativePeer(connectionId, TransportFailure(TransportFailureCode.INVALID_FRAME, "Invalid native read size"))
                return false
            }
            if (!reserveByteEvent(connectionId)) {
                rejectNativePeer(connectionId, TransportFailure(TransportFailureCode.IO_ERROR, "The peer exceeded its receive allowance"))
                return false
            }
            if (events.trySend(NativeEvent.Bytes(connectionId, bytes.copyOf())).isSuccess) return true
            releaseByteEvent(connectionId)
            rejectNativePeer(connectionId, TransportFailure(TransportFailureCode.IO_ERROR, "The peer's receive queue is full"))
            return false
        }
        override fun onConnectionClosed(connectionId: String, code: TransportFailureCode?, message: String?) {
            if (markNativeTerminal(connectionId)) {
                publish(NativeEvent.ConnectionClosed(connectionId, code?.let { TransportFailure(it, message ?: "Connection failed") }))
            }
        }
        override fun onSendComplete(operationId: String, code: TransportFailureCode?, message: String?) {
            publish(NativeEvent.Sent(operationId, code?.let { TransportFailure(it, message ?: "Write failed") }))
        }
        override fun onDiscoveryStarted(operationId: String) { publish(NativeEvent.DiscoveryStarted(operationId)) }
        override fun onDiscoveryChanged(operationId: String, hosts: List<DiscoveredHost>) {
            latestDiscovery.value = DiscoverySnapshot(operationId, hosts.take(64).toList())
            if (discoveryRefreshQueued.compareAndSet(expect = false, update = true)) publish(NativeEvent.DiscoveryRefresh)
        }
        override fun onDiscoveryFailed(operationId: String, code: TransportFailureCode, message: String) {
            publish(NativeEvent.DiscoveryFailed(operationId, TransportFailure(code, message)))
        }
    }

    private class PendingHost(val id: String) {
        val result = CompletableDeferred<Host>()
        var host: Host? = null
    }
    private class PendingConnection(val id: String) {
        val result = CompletableDeferred<Connection>()
        var connection: Connection? = null
    }
    private class PendingWrite(val connectionId: String) { val result = CompletableDeferred<Unit>() }
    private data class NativePeerAdmission(val queuedChunks: Int = 0, val terminal: Boolean = false)
}

internal data class TransportConfiguration(
    val operationTimeoutMillis: Long = 12_000,
    val writeTimeoutMillis: Long = 5_000,
    val heartbeatIntervalMillis: Long = 5_000,
    val idleTimeoutMillis: Long = 20_000,
)

private fun closedException() = failure(TransportFailureCode.CLOSED, "The connection is closed")
private fun failure(code: TransportFailureCode, message: String) = TransportException(TransportFailure(code, message))

private sealed interface NativeEvent {
    data class HostReady(val id: String, val info: HostInfo) : NativeEvent
    data class HostFailed(val id: String, val failure: TransportFailure) : NativeEvent
    data class Incoming(val hostId: String, val connectionId: String) : NativeEvent
    data class Connected(val id: String, val connectionId: String) : NativeEvent
    data class ConnectFailed(val id: String, val failure: TransportFailure) : NativeEvent
    data class Bytes(val id: String, val bytes: ByteArray) : NativeEvent
    data class ConnectionClosed(val id: String, val failure: TransportFailure?) : NativeEvent
    data class Sent(val id: String, val failure: TransportFailure?) : NativeEvent
    data class DiscoveryStarted(val id: String) : NativeEvent
    data object DiscoveryRefresh : NativeEvent
    data class DiscoveryFailed(val id: String, val failure: TransportFailure) : NativeEvent
}

private data class DiscoverySnapshot(val id: String, val hosts: List<DiscoveredHost>)
