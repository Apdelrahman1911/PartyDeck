package dev.partydeck.transport

import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.CoroutineStart
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import java.io.Closeable
import java.io.IOException
import java.net.Inet4Address
import java.net.InetSocketAddress
import java.net.NetworkInterface
import java.net.ServerSocket
import java.net.Socket
import java.net.SocketTimeoutException
import java.security.cert.CertificateException
import java.util.Collections
import java.util.UUID
import java.util.concurrent.atomic.AtomicBoolean
import javax.net.ssl.SSLException
import javax.net.ssl.SSLHandshakeException
import javax.net.ssl.SSLSocket

/**
 * Native JSSE implementation shared by Android and the optional JVM launcher.
 * A raw socket is retained solely to abort blocked TLS I/O on cancellation; application bytes
 * are always read and written through SSLSocket, after a successful TLS handshake.
 */
internal class JavaLanDriver(
    private val discovery: JavaLanDiscovery,
    private val allowLoopbackFallback: Boolean,
    private val handshakeTimeoutMillis: Long = NATIVE_HANDSHAKE_TIMEOUT_MS.toLong(),
) : NativeLanDriver {
    private val lock = Any()
    private val io = CoroutineScope(SupervisorJob() + Dispatchers.IO)
    private var closed = false
    private var observer: NativeLanObserver? = null
    private var host: HostHandle? = null
    private val connections = mutableMapOf<String, ConnectionHandle>()

    override fun attach(observer: NativeLanObserver) {
        synchronized(lock) {
            check(this.observer == null) { "Driver is already attached" }
            this.observer = observer
        }
        discovery.attach(observer)
    }

    override fun startHost(operationId: String, displayName: String) {
        val handle = synchronized(lock) {
            if (closed || host != null) {
                observer?.onHostFailed(operationId, TransportFailureCode.BUSY, "The host listener is unavailable")
                return
            }
            HostHandle(operationId, displayName).also { host = it }
        }
        io.launch {
            var listener: ServerSocket? = null
            try {
                val identity = JavaTlsIdentity.generate()
                listener = ServerSocket().apply {
                    reuseAddress = false
                    bind(InetSocketAddress(0), MAX_NATIVE_CONNECTIONS)
                }
                val serviceName = "partydeck-${UUID.randomUUID().toString().replace("-", "").take(12)}"
                val endpoints = localEndpoints(listener.localPort, serviceName, allowLoopbackFallback)
                if (endpoints.isEmpty()) throw IOException("No local network address")
                val accepted = synchronized(lock) {
                    if (closed || host !== handle) false
                    else {
                        handle.listener = listener
                        handle.identity = identity
                        true
                    }
                }
                if (!accepted) {
                    closeResource(listener)?.let { throw it }
                    return@launch
                }
                fun ready(actualName: String) {
                    if (!handle.ready.compareAndSet(false, true)) return
                    val info = HostInfo(displayName, actualName, endpoints.map { it.copy(serviceName = actualName) }, identity.certificateSha256)
                    synchronized(lock) {
                        if (closed || host !== handle) return
                        observer?.onHostReady(operationId, info)
                        io.launch { acceptConnections(handle) }
                    }
                }
                // Advertising is optional for reachability: failed multicast still has a direct invitation.
                discovery.advertise(operationId, displayName, serviceName, listener.localPort, ::ready)
                io.launch {
                    delay(2_000)
                    ready(serviceName)
                }
            } catch (error: Exception) {
                listener?.let(::closeResource)
                val notify = synchronized(lock) {
                    if (host === handle) { host = null; !closed } else false
                }
                discovery.stopAdvertising(operationId)
                if (notify) observer?.onHostFailed(operationId, mapFailure(error), "The game could not start on this network")
            }
        }
    }

    private fun acceptConnections(hostHandle: HostHandle) {
        val listener = hostHandle.listener ?: return
        try {
            while (synchronized(lock) { !closed && host === hostHandle }) {
                val raw = listener.accept()
                val connection = synchronized(lock) {
                    if (closed || host !== hostHandle || connections.size >= MAX_NATIVE_CONNECTIONS) null
                    else ConnectionHandle(UUID.randomUUID().toString(), raw, null, hostHandle.id).also { connections[it.id] = it }
                }
                if (connection == null) {
                    closeResource(raw)
                    continue
                }
                startHandshakeDeadline(connection)
                io.launch {
                    try {
                        val tls = checkNotNull(hostHandle.identity).context.socketFactory.createSocket(
                            raw, raw.inetAddress.hostAddress, raw.port, true,
                        ) as SSLSocket
                        if (!adoptTls(connection, tls)) return@launch
                        configureTlsSocket(tls, client = false)
                        tls.startHandshake()
                        tls.soTimeout = 0
                        val ready = synchronized(lock) {
                            if (connections[connection.id] !== connection || closed || host !== hostHandle) false
                            else {
                                connection.ready = true
                                connection.handshakeDeadline?.cancel()
                                connection.handshakeDeadline = null
                                observer?.onIncomingConnection(hostHandle.id, connection.id)
                                true
                            }
                        }
                        if (ready) read(connection, tls)
                        else disconnect(connection, null)
                    } catch (error: Exception) {
                        disconnect(connection, TransportFailure(mapFailure(error), "The secure connection failed"))
                    }
                }
            }
        } catch (error: Exception) {
            val notify = synchronized(lock) { !closed && host === hostHandle }
            if (notify) {
                observer?.onHostFailed(hostHandle.id, mapFailure(error), "The host listener stopped")
                stopHost(hostHandle.id)
            }
        }
    }

    override fun stopHost(hostId: String) {
        val stopped = synchronized(lock) {
            host?.takeIf { it.id == hostId }?.also { host = null }
        }
        discovery.stopAdvertising(hostId)
        stopped?.listener?.let(::closeResource)
        val owned = synchronized(lock) { connections.values.filter { it.hostId == hostId } }
        owned.forEach { disconnect(it, null) }
    }

    override fun connect(operationId: String, endpoint: LanEndpoint, certificateSha256: String) {
        val handle = synchronized(lock) {
            if (closed || connections.size >= MAX_NATIVE_CONNECTIONS) {
                observer?.onConnectFailed(operationId, TransportFailureCode.BUSY, "Too many connections")
                return
            }
            ConnectionHandle(UUID.randomUUID().toString(), Socket(), operationId, null).also { connections[it.id] = it }
        }
        startHandshakeDeadline(handle)
        io.launch {
            try {
                val discovered = endpoint.serviceName?.let(discovery::lookup)
                val candidates = listOfNotNull(endpoint.takeIf { it.host.isNotBlank() }, discovered).distinct()
                if (candidates.isEmpty()) {
                    disconnect(handle, TransportFailure(TransportFailureCode.UNAVAILABLE, "This game is no longer visible; use a current invitation"))
                    return@launch
                }
                val context = JavaTlsIdentity.clientContext(certificateSha256)
                for ((index, candidate) in candidates.withIndex()) {
                    try {
                        val raw = synchronized(lock) {
                            if (connections[handle.id] !== handle || closed) return@launch
                            if (index > 0) handle.raw = Socket()
                            handle.raw
                        }
                        raw.connect(InetSocketAddress(candidate.host, candidate.port), 4_000)
                        val tls = context.socketFactory.createSocket(raw, candidate.host, candidate.port, true) as SSLSocket
                        if (!adoptTls(handle, tls)) return@launch
                        configureTlsSocket(tls, client = true)
                        tls.startHandshake()
                        tls.soTimeout = 0
                        val ready = synchronized(lock) {
                            if (connections[handle.id] !== handle || closed) false
                            else {
                                handle.ready = true
                                handle.handshakeDeadline?.cancel()
                                handle.handshakeDeadline = null
                                observer?.onConnected(operationId, handle.id)
                                true
                            }
                        }
                        if (ready) read(handle, tls)
                        else disconnect(handle, null)
                        return@launch
                    } catch (error: Exception) {
                        val reason = mapFailure(error)
                        if (index + 1 == candidates.size || reason == TransportFailureCode.AUTHENTICATION_FAILED) throw error
                        closeResource(handle.raw)?.let { error.addSuppressed(it) }
                        handle.tls?.let(::closeResource)?.let { error.addSuppressed(it) }
                        synchronized(lock) { handle.tls = null }
                    }
                }
            } catch (error: Exception) {
                val code = mapFailure(error)
                val message = if (code == TransportFailureCode.AUTHENTICATION_FAILED) {
                    "The host identity did not match the invitation"
                } else "The host could not be reached"
                disconnect(handle, TransportFailure(code, message))
            }
        }
    }

    private fun read(handle: ConnectionHandle, tls: SSLSocket) {
        try {
            val input = tls.inputStream
            val buffer = ByteArray(NATIVE_READ_CHUNK_BYTES)
            while (true) {
                val count = input.read(buffer)
                if (count < 0) break
                if (count == 0) continue
                if (observer?.onConnectionBytes(handle.id, buffer.copyOf(count)) != true) {
                    disconnect(handle, TransportFailure(TransportFailureCode.IO_ERROR, "The receive queue is full"))
                    return
                }
            }
            disconnect(handle, null)
        } catch (error: Exception) {
            disconnect(handle, TransportFailure(mapFailure(error), "The connection was interrupted"))
        }
    }

    override fun cancelConnect(operationId: String) {
        synchronized(lock) { connections.values.firstOrNull { it.operationId == operationId } }?.let { disconnect(it, null) }
    }

    override fun send(connectionId: String, operationId: String, bytes: ByteArray) {
        val handle = synchronized(lock) { connections[connectionId]?.takeIf { it.ready } }
        if (handle == null) {
            observer?.onSendComplete(operationId, TransportFailureCode.CLOSED, "The connection is closed")
            return
        }
        io.launch {
            try {
                val output = checkNotNull(handle.tls).outputStream
                output.write(bytes)
                output.flush()
                observer?.onSendComplete(operationId, null, null)
            } catch (error: Exception) {
                val code = mapFailure(error)
                observer?.onSendComplete(operationId, code, "The message could not be sent")
                disconnect(handle, TransportFailure(code, "The connection was interrupted"))
            }
        }
    }

    override fun closeConnection(connectionId: String) {
        synchronized(lock) { connections[connectionId] }?.let { disconnect(it, null) }
    }

    private fun adoptTls(handle: ConnectionHandle, tls: SSLSocket): Boolean {
        val accepted = synchronized(lock) {
            if (connections[handle.id] !== handle || closed) false
            else { handle.tls = tls; true }
        }
        if (!accepted) closeResource(tls)?.let { throw it }
        return accepted
    }

    private fun startHandshakeDeadline(handle: ConnectionHandle) {
        // SO_TIMEOUT bounds one blocking read, not an entire TLS handshake. An absolute
        // timer also releases an accepted slot when an untrusted peer only trickles bytes.
        val deadline = io.launch(start = CoroutineStart.LAZY) {
            delay(handshakeTimeoutMillis)
            disconnect(
                handle,
                TransportFailure(TransportFailureCode.TIMED_OUT, "The secure connection did not become ready"),
                onlyBeforeReady = true,
            )
        }
        val owned = synchronized(lock) {
            if (connections[handle.id] !== handle || closed || handle.ready) false
            else { handle.handshakeDeadline = deadline; true }
        }
        if (owned) deadline.start() else deadline.cancel()
    }

    private fun disconnect(handle: ConnectionHandle, failure: TransportFailure?, onlyBeforeReady: Boolean = false) {
        val removed = synchronized(lock) {
            // Readiness and expiry compete under the same lock, so a stale deadline cannot
            // close a connection that already completed its handshake.
            if (onlyBeforeReady && handle.ready) false
            else connections.remove(handle.id, handle).also { removed ->
                if (removed) {
                    handle.handshakeDeadline?.cancel()
                    handle.handshakeDeadline = null
                }
            }
        }
        if (!removed) return
        // Closing raw TCP first aborts blocked handshake/read/write work. The wrapper then
        // releases its TLS state without waiting for an unresponsive peer's close_notify.
        var cleanupFailure = closeResource(handle.raw)
        handle.tls?.let(::closeResource)?.let { tlsFailure ->
            if (cleanupFailure == null) cleanupFailure = tlsFailure
            else cleanupFailure.addSuppressed(tlsFailure)
        }
        val reason = failure ?: cleanupFailure?.let { TransportFailure(TransportFailureCode.IO_ERROR, "Connection cleanup failed") }
        if (handle.ready) observer?.onConnectionClosed(handle.id, reason?.code, reason?.message)
        else handle.operationId?.let {
            observer?.onConnectFailed(it, reason?.code ?: TransportFailureCode.CLOSED, reason?.message ?: "Connection cancelled")
        }
    }

    override fun startDiscovery(operationId: String) { discovery.start(operationId) }
    override fun stopDiscovery(operationId: String) { discovery.stop(operationId) }

    override fun close() {
        val currentHost: HostHandle?
        val currentConnections: List<ConnectionHandle>
        synchronized(lock) {
            if (closed) return
            closed = true
            currentHost = host
            host = null
            currentConnections = connections.values.toList()
        }
        var cleanupFailure = currentHost?.listener?.let(::closeResource)
        try {
            discovery.close()
        } catch (error: Exception) {
            if (cleanupFailure == null) cleanupFailure = IOException("Discovery cleanup failed", error)
            else cleanupFailure.addSuppressed(error)
        }
        currentConnections.forEach { disconnect(it, null) }
        io.cancel()
        cleanupFailure?.let { throw IllegalStateException("Transport cleanup failed", it) }
    }

    private class HostHandle(val id: String, val displayName: String) {
        var listener: ServerSocket? = null
        var identity: JavaTlsIdentity? = null
        val ready = AtomicBoolean(false)
    }

    private class ConnectionHandle(val id: String, var raw: Socket, val operationId: String?, val hostId: String?) {
        var tls: SSLSocket? = null
        var ready = false
        var handshakeDeadline: Job? = null
    }
}

internal fun localEndpoints(port: Int, serviceName: String, allowLoopbackFallback: Boolean): List<LanEndpoint> {
    val interfaces = NetworkInterface.getNetworkInterfaces()?.let(Collections::list).orEmpty()
    val addresses = interfaces.filter { it.isUp && !it.isLoopback }.flatMap { Collections.list(it.inetAddresses) }
        .filter { !it.isLoopbackAddress && !it.isAnyLocalAddress && !it.isMulticastAddress && !it.isLinkLocalAddress }
        .sortedBy { if (it is Inet4Address) 0 else 1 }
        .mapNotNull { it.hostAddress }
        .distinct()
    return if (addresses.isEmpty() && allowLoopbackFallback) listOf(LanEndpoint("127.0.0.1", port, serviceName))
    else addresses.map { LanEndpoint(it, port, serviceName) }
}

private fun closeResource(resource: Closeable): IOException? = try {
    resource.close()
    null
} catch (error: IOException) {
    error
}

private fun mapFailure(error: Exception): TransportFailureCode = when (error) {
    is SecurityException -> TransportFailureCode.PERMISSION_DENIED
    is SocketTimeoutException -> TransportFailureCode.TIMED_OUT
    is SSLHandshakeException, is CertificateException -> TransportFailureCode.AUTHENTICATION_FAILED
    is SSLException -> TransportFailureCode.IO_ERROR
    is IOException -> TransportFailureCode.UNAVAILABLE
    else -> TransportFailureCode.IO_ERROR
}
