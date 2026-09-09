package dev.partydeck.transport

import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.serialization.Serializable

/** One independently owned transport lifetime; never share an instance between controllers. */
interface LanTransportFactory {
    fun create(): LanTransport
}

interface LanTransport {
    val discoveredHosts: StateFlow<List<DiscoveredHost>>
    val discoveryState: StateFlow<DiscoveryState>

    suspend fun startDiscovery()
    suspend fun stopDiscovery()
    suspend fun host(displayName: String): LanHost

    /** The complete SHA-256 certificate pin comes from the trusted invitation, never discovery. */
    suspend fun connect(endpoint: LanEndpoint, certificateSha256: String): LanConnection

    /** Terminal and idempotent. Closes discovery, listeners, pending operations and connections. */
    suspend fun close()
}

interface LanHost {
    val info: HostInfo

    /** A bounded, single-consumer stream. Application admission must precede game messages. */
    val incomingConnections: Flow<LanConnection>

    suspend fun close()
}

interface LanConnection {
    /** An opaque connection lifetime identifier, not a player ID or persistent device identity. */
    val id: String
    val state: StateFlow<ConnectionState>

    /** Ordered messages, each at most [MAX_FRAME_BYTES]; consume from one coroutine. */
    val incoming: Flow<ByteArray>

    /** Completes on a local transport write. Remote application acknowledgement is separate. */
    suspend fun send(bytes: ByteArray)
    suspend fun close()
}

/** A direct LAN address, with optional Bonjour identity for rediscovery after address changes. */
@Serializable
data class LanEndpoint(
    val host: String,
    val port: Int,
    val serviceName: String? = null,
) {
    init {
        require(host.length <= 253 && host.none { it.isWhitespace() || it.isISOControl() })
        require(host.isNotBlank() || !serviceName.isNullOrBlank())
        require(port in 1..65535)
        require(serviceName == null || (serviceName.isNotBlank() && serviceName.encodeToByteArray().size <= 63))
    }
}

data class HostInfo(
    val displayName: String,
    val serviceName: String,
    val endpoints: List<LanEndpoint>,
    val certificateSha256: String,
)

/** Discovery is a public, unauthenticated hint and cannot supply a trusted certificate pin. */
data class DiscoveredHost(
    val serviceName: String,
    val displayName: String,
    val endpoint: LanEndpoint,
)

sealed interface DiscoveryState {
    data object Idle : DiscoveryState
    data object Searching : DiscoveryState
    data class Failed(val failure: TransportFailure) : DiscoveryState
}

sealed interface ConnectionState {
    data object Connected : ConnectionState
    data object Closed : ConnectionState
    data class Failed(val failure: TransportFailure) : ConnectionState
}

enum class TransportFailureCode {
    PERMISSION_DENIED,
    UNAVAILABLE,
    AUTHENTICATION_FAILED,
    TIMED_OUT,
    BUSY,
    CLOSED,
    MESSAGE_TOO_LARGE,
    INVALID_FRAME,
    IO_ERROR,
}

data class TransportFailure(val code: TransportFailureCode, val message: String)

class TransportException(val failure: TransportFailure) : Exception(failure.message)

const val MAX_FRAME_BYTES: Int = 65_536
const val BONJOUR_SERVICE_TYPE: String = "_partydeck._tcp"
