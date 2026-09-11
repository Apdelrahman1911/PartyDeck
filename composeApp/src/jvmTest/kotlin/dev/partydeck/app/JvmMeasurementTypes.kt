package dev.partydeck.app

/** Successful application payloads observed outside the production TLS/framing implementation. */
internal class ApplicationPayloadMeter {
    private var sentMessages = 0L
    private var sentBytes = 0L
    private var receivedMessages = 0L
    private var receivedBytes = 0L

    /** Call only after the delegated application send succeeds. */
    fun sent(byteCount: Int) = synchronized(this) {
        require(byteCount >= 0)
        sentMessages++
        sentBytes += byteCount
    }

    /** Call when the delegated incoming flow delivers an application payload. */
    fun received(byteCount: Int) = synchronized(this) {
        require(byteCount >= 0)
        receivedMessages++
        receivedBytes += byteCount
    }

    fun snapshot(): ApplicationPayloadSnapshot = synchronized(this) {
        ApplicationPayloadSnapshot(sentMessages, sentBytes, receivedMessages, receivedBytes)
    }
}

internal data class ApplicationPayloadSnapshot(
    val sentMessages: Long,
    val sentBytes: Long,
    val receivedMessages: Long,
    val receivedBytes: Long,
) {
    operator fun minus(previous: ApplicationPayloadSnapshot): ApplicationPayloadSnapshot =
        ApplicationPayloadSnapshot(
            sentMessages - previous.sentMessages,
            sentBytes - previous.sentBytes,
            receivedMessages - previous.receivedMessages,
            receivedBytes - previous.receivedBytes,
        ).also {
            check(it.sentMessages >= 0 && it.sentBytes >= 0 && it.receivedMessages >= 0 && it.receivedBytes >= 0) {
                "Application payload counters moved backwards"
            }
        }
}

internal enum class TlsMeasurementPhase { IDLE, ACTIVE }

/**
 * One settled interval from the existing six-controller integration fixture. Entries are ordered
 * host first, then its five guests. These count payload bytes once at each observed endpoint;
 * adding sent and received bytes together would count the same delivery twice.
 */
internal data class TlsPayloadInterval(
    val phase: TlsMeasurementPhase,
    val elapsedNs: Long,
    val revisionBefore: Long,
    val revisionAfter: Long,
    val acceptedCommandCount: Int,
    val payloadDeltas: List<ApplicationPayloadSnapshot>,
) {
    init {
        require(elapsedNs >= 0)
        require(revisionBefore >= 0 && revisionAfter >= revisionBefore)
        require(acceptedCommandCount >= 0)
        require(payloadDeltas.size == 6)
    }
}
