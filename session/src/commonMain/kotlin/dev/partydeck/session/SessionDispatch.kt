package dev.partydeck.session

/**
 * A channel supplied by the trusted transport adapter, never decoded from a client payload.
 * TLS authenticates the host; admission and reconnect credentials authenticate a player's seat.
 */
data class SessionPeer(val connectionId: String)

data class Delivery(val connectionId: String, val message: ServerMessage)

data class SessionDispatch(
    val deliveries: List<Delivery> = emptyList(),
    val closeConnections: List<String> = emptyList(),
)

data class HostSessionConfig(
    val sessionId: String,
    val admissionSecret: String,
    val hostDisplayName: String,
    val hostPeer: SessionPeer,
    val replayCacheSize: Int = 64,
)
