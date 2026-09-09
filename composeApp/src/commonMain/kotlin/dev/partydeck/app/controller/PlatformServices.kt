package dev.partydeck.app.controller

import kotlin.random.Random

/** Small preferences which may survive application restarts. Session secrets are never stored here. */
data class AppSettings(
    val displayName: String = "Guest",
    val soundEnabled: Boolean = true,
    val hapticsEnabled: Boolean = true,
    val reduceMotion: Boolean = false,
)

interface SettingsStore {
    suspend fun load(): AppSettings
    suspend fun save(settings: AppSettings)
}

enum class FeedbackCue {
    CLICK,
    CARD_PLAY,
    CHALLENGE,
    ROUND_END,
    LIGHT_OUT,
    WIN,
}

interface Feedback {
    fun play(cue: FeedbackCue, settings: AppSettings)
    fun setForeground(value: Boolean)
    fun close()
}

/** The native owner supplies services and closes the controller when ownership permanently ends. */
interface PlatformServices {
    val settingsStore: SettingsStore
    val feedback: Feedback
    val canScanInvitation: Boolean
    val showsCopyConfirmation: Boolean get() = false

    /** Called only for an explicit user copy action. Implementations should mark secrets sensitive. */
    fun copyText(value: String)

    /** Opens the native sharing flow for an explicit user action. */
    fun shareText(value: String)

    /** Null is cancellation or permission denial. Scanning never joins a session by itself. */
    fun scanInvitation(onResult: (String?) -> Unit)

    /** Every output must come from the platform CSPRNG, not a seeded deterministic generator. */
    fun gameRandom(): Random

    /** Exactly 32 secure random bytes, encoded as 64 lowercase hexadecimal characters. */
    fun secureToken(): String
}
