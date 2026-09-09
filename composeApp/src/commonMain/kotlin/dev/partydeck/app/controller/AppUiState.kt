package dev.partydeck.app.controller

import dev.partydeck.session.SessionView

enum class AppScreen { HOME, HOST, JOIN, SESSION, SETTINGS, HOW_TO }

enum class SessionMode { LAN_HOST, LAN_CLIENT, PRACTICE }

enum class ConnectionStatus {
    IDLE,
    STARTING_HOST,
    CONNECTING,
    CONNECTED,
    RECONNECTING,
    DISCONNECTED,
}

data class ConnectionUiState(
    val status: ConnectionStatus = ConnectionStatus.IDLE,
    val mode: SessionMode? = null,
    val retryAttempt: Int = 0,
)

/** A shareable admission invite. Player-specific reconnect credentials are kept out of UI state. */
data class HostInvitation(
    val joinAddress: String,
    val displayAddress: String,
)

enum class PendingAction {
    HOST,
    JOIN,
    READY,
    START_GAME,
    PLAY_CARDS,
    CHALLENGE,
    NEXT_ROUND,
    RETURN_TO_LOBBY,
    KICK_PLAYER,
}

enum class UiProblemCode {
    INVALID_NAME,
    INVALID_INVITE,
    CONNECTION_FAILED,
    CONNECTION_LOST,
    LOCAL_NETWORK_PERMISSION_DENIED,
    HOST_UNAVAILABLE,
    SESSION_ENDED,
    SESSION_FULL,
    JOIN_REJECTED,
    VERSION_MISMATCH,
    ACTION_REJECTED,
    STALE_ACTION,
    SETTINGS_UNAVAILABLE,
    COPY_UNAVAILABLE,
    SHARING_UNAVAILABLE,
    SCANNING_UNAVAILABLE,
    INTERNAL_ERROR,
}

enum class RecoveryAction { DISMISS, RETRY_CONNECTION, EDIT_INVITE, RETURN_HOME }

/** Stable codes are mapped to localizable copy by the UI, never to raw network exception text. */
data class UiProblem(
    val occurrenceId: Long,
    val code: UiProblemCode,
    val recovery: RecoveryAction = RecoveryAction.DISMISS,
)

enum class UiNoticeCode { INVITATION_COPIED }

data class UiNotice(val occurrenceId: Long, val code: UiNoticeCode)

data class AppUiState(
    val screen: AppScreen = AppScreen.HOME,
    val displayName: String = "Guest",
    val joinAddress: String = "",
    val settings: AppSettings = AppSettings(),
    val systemReduceMotion: Boolean = false,
    val isForeground: Boolean = true,
    val isBackgrounded: Boolean = false,
    val privacyEpoch: Long = 0,
    val canScanInvitation: Boolean = false,
    val isScanningInvitation: Boolean = false,
    val connection: ConnectionUiState = ConnectionUiState(),
    val session: SessionView? = null,
    val invitation: HostInvitation? = null,
    val pendingAction: PendingAction? = null,
    val problem: UiProblem? = null,
    val notice: UiNotice? = null,
    val leaveConfirmationRequested: Boolean = false,
) {
    val effectiveReduceMotion: Boolean
        get() = settings.reduceMotion || systemReduceMotion

    val isPractice: Boolean
        get() = connection.mode == SessionMode.PRACTICE

    val canSendSessionAction: Boolean
        get() = isForeground && !isBackgrounded && session != null &&
            connection.status == ConnectionStatus.CONNECTED &&
            pendingAction == null
}
