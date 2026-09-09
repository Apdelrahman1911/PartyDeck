package dev.partydeck.games

import kotlinx.coroutines.flow.Flow

const val ENGINE_BRIDGE_PROTOCOL_VERSION: Int = 1
const val MAX_ENGINE_PAYLOAD_BYTES: Int = 65_536

/**
 * An immutable, bounded document in a game adapter's versioned schema.
 * The adapter must encode a recipient-safe view or player intent, never authoritative
 * state or credentials. This boundary bounds storage; the adapter validates its schema.
 */
data class EnginePayload(val schemaId: String, val document: String) {
    init {
        requireStableIdentifier(schemaId)
        require(document.length <= MAX_ENGINE_PAYLOAD_BYTES) { "Engine payload exceeds the size limit." }
        require(document.encodeToByteArray().size <= MAX_ENGINE_PAYLOAD_BYTES) {
            "Engine payload exceeds the UTF-8 byte limit."
        }
    }
}

/** Unique for each presentation lifetime; this is not a network admission credential. */
data class EngineLaunch(
    val gameId: GameId,
    val presentationId: String,
    val initialView: EnginePayload,
    val initialRevision: Long,
    val protocolVersion: Int = ENGINE_BRIDGE_PROTOCOL_VERSION,
) {
    init {
        require(presentationId.isNotBlank() && presentationId.length <= 128) { "Invalid presentation identifier." }
        require(initialRevision >= 0) { "A view revision cannot be negative." }
        require(protocolVersion == ENGINE_BRIDGE_PROTOCOL_VERSION) { "Unsupported engine bridge protocol." }
    }
}

/** Coarse updates only. Local animations and the render loop stay inside the renderer. */
sealed interface EngineCommand {
    data class ShowView(val revision: Long, val payload: EnginePayload) : EngineCommand {
        init {
            require(revision >= 0) { "A view revision cannot be negative." }
        }
    }

    data class SetForeground(val isForeground: Boolean) : EngineCommand
}

sealed interface EngineEventBody {
    data object Ready : EngineEventBody

    /** The shell maps this to a validated authority intent; it never trusts engine outcomes. */
    data class PlayerIntent(val expectedRevision: Long, val payload: EnginePayload) : EngineEventBody {
        init {
            require(expectedRevision >= 0) { "An intent revision cannot be negative." }
        }
    }

    /** A presentation exit request, not an authoritative game result. */
    data object ExitRequested : EngineEventBody

    data class Failed(val reason: EngineFailure) : EngineEventBody
}

enum class EngineFailure { INITIALIZATION_FAILED, INVALID_PAYLOAD, RENDERER_LOST, INTERNAL_ERROR }

data class EngineEvent(
    val presentationId: String,
    val protocolVersion: Int,
    val sequence: Long,
    val body: EngineEventBody,
)

/**
 * Implemented only by a qualified platform renderer. The first release installs none.
 * Creating a factory must not start an engine; open is called only on game entry.
 */
interface EmbeddedGameFactory {
    val engineId: String
    val protocolVersion: Int
    val supportedGames: Set<GameId>

    suspend fun open(launch: EngineLaunch): EmbeddedGameSession
}

interface EmbeddedGameSession {
    /**
     * One bounded, ordered stream. Retain the initial Ready/Failed event until the shell
     * subscribes. The shell serializes events through EngineEventGate before handling them.
     */
    val events: Flow<EngineEvent>

    /** Platform implementations dispatch to the appropriate engine thread. */
    suspend fun send(command: EngineCommand)

    /** Idempotent; stops rendering/audio and releases native view, callbacks and resources. */
    suspend fun close()
}

sealed interface EngineResolution {
    data object NotRequired : EngineResolution
    data class Available(val factory: EmbeddedGameFactory) : EngineResolution
    data class Unavailable(val reason: EngineUnavailableReason) : EngineResolution
}

enum class EngineUnavailableReason { NOT_INSTALLED, UNSUPPORTED_PROTOCOL, UNSUPPORTED_GAME }

/** Capability lookup has no engine lifecycle side effects. */
class EmbeddedGameRegistry(factories: List<EmbeddedGameFactory>) {
    private val byId = factories.associateBy(EmbeddedGameFactory::engineId)

    init {
        require(byId.size == factories.size) { "Engine identifiers must be unique." }
        factories.forEach {
            requireStableIdentifier(it.engineId)
            require(it.protocolVersion > 0) { "An engine bridge version must be positive." }
        }
    }

    fun resolve(game: GameDescriptor): EngineResolution {
        val presentation = game.presentation
        if (presentation is GamePresentation.Compose) return EngineResolution.NotRequired
        presentation as GamePresentation.Embedded
        val factory = byId[presentation.engineId]
            ?: return EngineResolution.Unavailable(EngineUnavailableReason.NOT_INSTALLED)
        if (presentation.protocolVersion != ENGINE_BRIDGE_PROTOCOL_VERSION || factory.protocolVersion != presentation.protocolVersion) {
            return EngineResolution.Unavailable(EngineUnavailableReason.UNSUPPORTED_PROTOCOL)
        }
        if (game.id !in factory.supportedGames) {
            return EngineResolution.Unavailable(EngineUnavailableReason.UNSUPPORTED_GAME)
        }
        return EngineResolution.Available(factory)
    }

    companion object {
        val Empty = EmbeddedGameRegistry(emptyList())
    }
}
