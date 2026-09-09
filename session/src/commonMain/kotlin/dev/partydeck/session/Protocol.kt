package dev.partydeck.session

import dev.partydeck.core.CardId
import dev.partydeck.core.GameRejection
import dev.partydeck.core.PlayerId
import kotlinx.serialization.Required
import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

const val PROTOCOL_VERSION: Int = 1
const val MAX_WIRE_BYTES: Int = 65_536

@Serializable
sealed interface ClientIntent {
    @Serializable @SerialName("set_ready")
    data class SetReady(val ready: Boolean) : ClientIntent

    @Serializable @SerialName("start_game")
    data object StartGame : ClientIntent

    @Serializable @SerialName("play_cards")
    data class PlayCards(val cardIds: List<CardId>) : ClientIntent

    @Serializable @SerialName("challenge")
    data object Challenge : ClientIntent

    @Serializable @SerialName("advance_round")
    data object AdvanceRound : ClientIntent

    @Serializable @SerialName("return_to_lobby")
    data object ReturnToLobby : ClientIntent

    @Serializable @SerialName("kick_player")
    data class KickPlayer(val playerId: PlayerId) : ClientIntent

    @Serializable @SerialName("leave")
    data object Leave : ClientIntent

    @Serializable @SerialName("end_session")
    data object EndSession : ClientIntent
}

@Serializable
sealed interface ClientMessage {
    val protocolVersion: Int
    val sessionId: String

    @Serializable @SerialName("join")
    data class Join(
        override val sessionId: String,
        val admissionSecret: String,
        val displayName: String,
        @Required override val protocolVersion: Int = PROTOCOL_VERSION,
    ) : ClientMessage

    @Serializable @SerialName("resume")
    data class Resume(
        override val sessionId: String,
        val playerId: PlayerId,
        val reconnectToken: String,
        @Required override val protocolVersion: Int = PROTOCOL_VERSION,
    ) : ClientMessage

    @Serializable @SerialName("command")
    data class Command(
        override val sessionId: String,
        val commandId: Long,
        val expectedRevision: Long,
        val intent: ClientIntent,
        @Required override val protocolVersion: Int = PROTOCOL_VERSION,
    ) : ClientMessage
}

@Serializable
enum class SessionError {
    UNSUPPORTED_VERSION,
    WRONG_SESSION,
    MALFORMED_MESSAGE,
    PAYLOAD_TOO_LARGE,
    INVALID_CREDENTIALS,
    INVALID_NAME,
    LOBBY_FULL,
    NOT_ADMITTED,
    ALREADY_ADMITTED,
    SESSION_CLOSED,
    NOT_HOST,
    WRONG_PHASE,
    NOT_ENOUGH_PLAYERS,
    PLAYERS_NOT_READY,
    PLAYERS_DISCONNECTED,
    UNKNOWN_PLAYER,
    CANNOT_REMOVE_HOST,
    INVALID_COMMAND_ID,
    COMMAND_ID_CONFLICT,
    COMMAND_TOO_OLD,
    STALE_REVISION,
    ILLEGAL_GAME_ACTION,
    SESSION_EXHAUSTED,
}

@Serializable
data class CommandReceipt(
    val commandId: Long,
    val revision: Long,
    val error: SessionError? = null,
    val gameError: GameRejection? = null,
) {
    val accepted: Boolean get() = error == null
}

@Serializable
enum class SessionEndReason { HOST_ENDED, HOST_DISCONNECTED, REMOVED, LEFT }

@Serializable
sealed interface ServerMessage {
    val protocolVersion: Int
    val sessionId: String

    @Serializable @SerialName("welcome")
    data class Welcome(
        override val sessionId: String,
        val playerId: PlayerId,
        val reconnectToken: String,
        val nextCommandId: Long,
        val view: SessionView,
        @Required override val protocolVersion: Int = PROTOCOL_VERSION,
    ) : ServerMessage

    @Serializable @SerialName("snapshot")
    data class Snapshot(
        override val sessionId: String,
        val view: SessionView,
        @Required override val protocolVersion: Int = PROTOCOL_VERSION,
    ) : ServerMessage

    @Serializable @SerialName("receipt")
    data class Receipt(
        override val sessionId: String,
        val receipt: CommandReceipt,
        @Required override val protocolVersion: Int = PROTOCOL_VERSION,
    ) : ServerMessage

    @Serializable @SerialName("admission_rejected")
    data class AdmissionRejected(
        override val sessionId: String,
        val error: SessionError,
        @Required override val protocolVersion: Int = PROTOCOL_VERSION,
    ) : ServerMessage

    @Serializable @SerialName("session_ended")
    data class Ended(
        override val sessionId: String,
        val reason: SessionEndReason,
        @Required override val protocolVersion: Int = PROTOCOL_VERSION,
    ) : ServerMessage
}
