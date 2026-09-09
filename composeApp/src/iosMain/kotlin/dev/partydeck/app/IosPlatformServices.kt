@file:OptIn(kotlinx.cinterop.ExperimentalForeignApi::class, org.jetbrains.compose.resources.ExperimentalResourceApi::class)

package dev.partydeck.app

import dev.partydeck.app.controller.AppSettings
import dev.partydeck.app.controller.Feedback
import dev.partydeck.app.controller.FeedbackCue
import dev.partydeck.app.controller.PlatformServices
import dev.partydeck.app.controller.SettingsStore
import dev.partydeck.resources.Res
import kotlinx.cinterop.addressOf
import kotlinx.cinterop.convert
import kotlinx.cinterop.usePinned
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import platform.Foundation.NSUserDefaults
import platform.Security.SecRandomCopyBytes
import platform.Security.errSecSuccess
import platform.Security.kSecRandomDefault
import kotlin.random.Random

internal class IosPlatformServices(private val nativeActions: IosNativeActions) : PlatformServices {
    override val settingsStore: SettingsStore = IosSettingsStore()
    override val feedback: Feedback = IosFeedback(nativeActions.feedback)
    override val canScanInvitation: Boolean get() = nativeActions.canScanInvitation

    override fun copyText(value: String) {
        check(nativeActions.copyText(value)) { "Clipboard is unavailable" }
    }

    override fun shareText(value: String) {
        check(nativeActions.shareText(value)) { "Sharing is unavailable" }
    }

    override fun scanInvitation(onResult: (String?) -> Unit) {
        val presented = nativeActions.scanInvitation(object : IosScanResult {
            private var delivered = false

            override fun complete(value: String?) {
                if (delivered) return
                delivered = true
                onResult(value)
            }
        })
        check(presented) { "Invitation scanning is unavailable" }
    }

    override fun gameRandom(): Random = IosSecureRandom()

    override fun secureToken(): String {
        val bytes = secureBytes(32)
        return try {
            buildString(64) {
                bytes.forEach { byte ->
                    val value = byte.toInt() and 0xff
                    append(HEX[value ushr 4])
                    append(HEX[value and 15])
                }
            }
        } finally {
            bytes.fill(0)
        }
    }

    private companion object {
        const val HEX = "0123456789abcdef"
    }
}

/** UserDefaults owns its persistence scheduling; synchronous disk flushes are unnecessary. */
private class IosSettingsStore : SettingsStore {
    private val defaults = NSUserDefaults.standardUserDefaults

    override suspend fun load(): AppSettings = withContext(Dispatchers.Default) {
        AppSettings(
            displayName = defaults.stringForKey(NAME) ?: "Guest",
            soundEnabled = boolean(SOUND, fallback = true),
            hapticsEnabled = boolean(HAPTICS, fallback = true),
            reduceMotion = boolean(MOTION, fallback = false),
        )
    }

    override suspend fun save(settings: AppSettings): Unit = withContext(Dispatchers.Default) {
        defaults.setObject(settings.displayName, forKey = NAME)
        defaults.setBool(settings.soundEnabled, forKey = SOUND)
        defaults.setBool(settings.hapticsEnabled, forKey = HAPTICS)
        defaults.setBool(settings.reduceMotion, forKey = MOTION)
    }

    private fun boolean(key: String, fallback: Boolean): Boolean =
        if (defaults.objectForKey(key) == null) fallback else defaults.boolForKey(key)

    private companion object {
        const val NAME = "partydeck.preferences.v1.displayName"
        const val SOUND = "partydeck.preferences.v1.sound"
        const val HAPTICS = "partydeck.preferences.v1.haptics"
        const val MOTION = "partydeck.preferences.v1.reduceMotion"
    }
}

/** Every draw uses fresh OS randomness, including draws after an observed card or penalty. */
private class IosSecureRandom : Random() {
    override fun nextBits(bitCount: Int): Int {
        require(bitCount in 0..32)
        if (bitCount == 0) return 0
        val bytes = secureBytes(4)
        val word = ((bytes[0].toInt() and 0xff) shl 24) or
            ((bytes[1].toInt() and 0xff) shl 16) or
            ((bytes[2].toInt() and 0xff) shl 8) or
            (bytes[3].toInt() and 0xff)
        return if (bitCount == 32) word else word ushr (32 - bitCount)
    }
}

private fun secureBytes(count: Int): ByteArray {
    val bytes = ByteArray(count)
    val status = bytes.usePinned { pinned ->
        SecRandomCopyBytes(kSecRandomDefault, count.convert(), pinned.addressOf(0))
    }
    check(status == errSecSuccess) { "Secure random generation is unavailable" }
    return bytes
}

/** URI lookup is cheap; the Swift implementation loads and prepares audio off the feedback path. */
private class IosFeedback(private val native: IosNativeFeedback) : Feedback {
    private var closed = false

    init {
        FeedbackCue.entries.forEach { cue ->
            val key = cue.assetKey()
            native.prepare(key, Res.getUri("files/audio/$key.wav"))
        }
    }

    override fun play(cue: FeedbackCue, settings: AppSettings) {
        if (!closed) native.play(cue.assetKey(), settings.soundEnabled, settings.hapticsEnabled)
    }

    override fun setForeground(value: Boolean) {
        if (!closed) native.setForeground(value)
    }

    override fun close() {
        if (closed) return
        closed = true
        native.close()
    }

    private fun FeedbackCue.assetKey(): String = when (this) {
        FeedbackCue.CLICK -> "ui_tap"
        FeedbackCue.CARD_PLAY -> "card_place"
        FeedbackCue.CHALLENGE -> "challenge"
        FeedbackCue.ROUND_END -> "safe"
        FeedbackCue.LIGHT_OUT -> "light_out"
        FeedbackCue.WIN -> "victory"
    }
}
