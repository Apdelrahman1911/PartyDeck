package dev.partydeck.transport

/**
 * Platform I/O boundary. Methods return promptly; results arrive at [NativeLanObserver].
 *
 * Native implementations perform TLS before announcing a connection. Incoming TLS has no
 * client-certificate identity; the session layer must admit the client. Outgoing TLS must
 * reject any leaf certificate whose complete SHA-256 digest differs from the supplied pin.
 *
 * Callbacks may arrive on a native I/O queue. Each connection must report ready before bytes,
 * preserve byte order, and stop reading when [NativeLanObserver.onConnectionBytes] returns false.
 * A driver owns at most [MAX_NATIVE_CONNECTIONS] accepted/connecting sockets, including handshakes.
 */
interface NativeLanDriver {
    fun attach(observer: NativeLanObserver)
    fun startHost(operationId: String, displayName: String)
    fun stopHost(hostId: String)
    fun startDiscovery(operationId: String)
    fun stopDiscovery(operationId: String)
    fun connect(operationId: String, endpoint: LanEndpoint, certificateSha256: String)
    fun cancelConnect(operationId: String)
    fun send(connectionId: String, operationId: String, bytes: ByteArray)
    fun closeConnection(connectionId: String)
    fun close()
}

/** A callback-only interface deliberately suitable for direct Swift implementation. */
interface NativeLanObserver {
    fun onHostReady(operationId: String, info: HostInfo)
    fun onHostFailed(operationId: String, code: TransportFailureCode, message: String)
    fun onIncomingConnection(hostId: String, connectionId: String)
    fun onConnected(operationId: String, connectionId: String)
    fun onConnectFailed(operationId: String, code: TransportFailureCode, message: String)

    /** False means the receiver rejected the bytes; the native connection must close. */
    fun onConnectionBytes(connectionId: String, bytes: ByteArray): Boolean

    fun onConnectionClosed(connectionId: String, code: TransportFailureCode?, message: String?)
    fun onSendComplete(operationId: String, code: TransportFailureCode?, message: String?)
    fun onDiscoveryStarted(operationId: String)
    fun onDiscoveryChanged(operationId: String, hosts: List<DiscoveredHost>)
    fun onDiscoveryFailed(operationId: String, code: TransportFailureCode, message: String)
}

const val MAX_NATIVE_CONNECTIONS: Int = 8
const val NATIVE_READ_CHUNK_BYTES: Int = 16_384
const val NATIVE_HANDSHAKE_TIMEOUT_MS: Int = 10_000
