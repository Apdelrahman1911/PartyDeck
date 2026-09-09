package dev.partydeck.session

import dev.partydeck.core.GameView
import dev.partydeck.core.PlayerId
import kotlinx.serialization.Serializable

@Serializable
enum class SessionPhase { LOBBY, GAME, ENDED }

@Serializable
data class LobbyPlayer(
    val id: PlayerId,
    val displayName: String,
    val isReady: Boolean,
    val isConnected: Boolean,
)

@Serializable
data class SessionControls(
    val canStartGame: Boolean = false,
    val canAdvanceRound: Boolean = false,
    val canReturnToLobby: Boolean = false,
)

/** The entire visible state for one admitted player. Credentials never belong here. */
@Serializable
data class SessionView(
    val sessionId: String,
    val revision: Long,
    val selfPlayerId: PlayerId,
    val hostPlayerId: PlayerId,
    val phase: SessionPhase,
    val players: List<LobbyPlayer>,
    val game: GameView? = null,
    val pausedPlayerIds: List<PlayerId> = emptyList(),
    val controls: SessionControls = SessionControls(),
)
