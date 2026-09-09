package dev.partydeck.app

import dev.partydeck.app.controller.AppSettings
import dev.partydeck.app.controller.Feedback
import dev.partydeck.app.controller.FeedbackCue
import dev.partydeck.app.controller.PlatformServices
import dev.partydeck.app.controller.SettingsStore
import dev.partydeck.resources.Res
import java.awt.Desktop
import java.awt.Toolkit
import java.awt.datatransfer.StringSelection
import java.io.ByteArrayInputStream
import java.net.URI
import java.net.URLEncoder
import java.security.SecureRandom
import java.util.prefs.Preferences
import javax.sound.sampled.AudioSystem
import javax.sound.sampled.Clip
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import kotlin.random.Random
import kotlin.random.asKotlinRandom

/** Optional desktop services; the mobile applications supply their own native implementations. */
class JvmPlatformServices(parentScope: CoroutineScope) : PlatformServices {
    private val secureRandom = SecureRandom()
    override val settingsStore: SettingsStore = JvmSettingsStore()
    override val feedback: Feedback = JvmFeedback(parentScope)
    override val canScanInvitation: Boolean = false

    override fun scanInvitation(onResult: (String?) -> Unit) = onResult(null)

    override fun gameRandom(): Random = secureRandom.asKotlinRandom()

    override fun secureToken(): String = ByteArray(32).also(secureRandom::nextBytes).joinToString("") {
        (it.toInt() and 255).toString(16).padStart(2, '0')
    }

    override fun copyText(value: String) {
        Toolkit.getDefaultToolkit().systemClipboard.setContents(StringSelection(value), null)
    }

    override fun shareText(value: String) {
        check(Desktop.isDesktopSupported() && Desktop.getDesktop().isSupported(Desktop.Action.MAIL)) {
            "System sharing is unavailable; use Copy invitation."
        }
        val body = URLEncoder.encode(value, Charsets.UTF_8).replace("+", "%20")
        Desktop.getDesktop().mail(URI.create("mailto:?subject=PartyDeck%20invitation&body=$body"))
    }
}

private class JvmSettingsStore : SettingsStore {
    private val preferences = Preferences.userRoot().node("dev/partydeck/settings")

    override suspend fun load(): AppSettings = withContext(Dispatchers.IO) {
        AppSettings(
            displayName = preferences.get("displayName", "Guest"),
            soundEnabled = preferences.getBoolean("soundEnabled", true),
            hapticsEnabled = preferences.getBoolean("hapticsEnabled", true),
            reduceMotion = preferences.getBoolean("reduceMotion", false),
        )
    }

    override suspend fun save(settings: AppSettings): Unit = withContext(Dispatchers.IO) {
        preferences.put("displayName", settings.displayName)
        preferences.putBoolean("soundEnabled", settings.soundEnabled)
        preferences.putBoolean("hapticsEnabled", settings.hapticsEnabled)
        preferences.putBoolean("reduceMotion", settings.reduceMotion)
        preferences.flush()
    }
}

private class JvmFeedback(parentScope: CoroutineScope) : Feedback {
    private val scope = CoroutineScope(parentScope.coroutineContext + SupervisorJob(parentScope.coroutineContext[Job]))
    private val lock = Any()
    private val clips = mutableMapOf<FeedbackCue, Clip>()
    private var foreground = true
    private var closed = false
    private var audioAvailable = true

    override fun play(cue: FeedbackCue, settings: AppSettings) {
        if (!settings.soundEnabled) return
        scope.launch(Dispatchers.IO) {
            val file = when (cue) {
                FeedbackCue.CLICK -> "ui_tap"
                FeedbackCue.CARD_PLAY -> "card_place"
                FeedbackCue.CHALLENGE -> "challenge"
                FeedbackCue.ROUND_END -> "safe"
                FeedbackCue.LIGHT_OUT -> "light_out"
                FeedbackCue.WIN -> "victory"
            }
            if (synchronized(lock) { closed || !foreground || !audioAvailable }) return@launch
            val bytes = Res.readBytes("files/audio/$file.wav")
            synchronized(lock) {
                if (closed || !foreground || !audioAvailable) return@synchronized
                try {
                    val clip = clips[cue] ?: AudioSystem.getClip().also { candidate ->
                        try {
                            AudioSystem.getAudioInputStream(ByteArrayInputStream(bytes)).use(candidate::open)
                            clips[cue] = candidate
                        } catch (failure: Exception) {
                            candidate.close()
                            throw failure
                        }
                    }
                    clips.values.forEach(Clip::stop)
                    clip.framePosition = 0
                    clip.start()
                } catch (_: javax.sound.sampled.LineUnavailableException) {
                    disableAudio()
                } catch (_: IllegalArgumentException) {
                    disableAudio()
                }
            }
        }
    }

    private fun disableAudio() {
        audioAvailable = false
        clips.values.forEach(Clip::close)
        clips.clear()
        System.err.println("PartyDeck: this desktop has no available audio output; visual feedback remains active.")
    }

    override fun setForeground(value: Boolean) = synchronized(lock) {
        foreground = value
        if (!value) clips.values.forEach(Clip::stop)
    }

    override fun close() {
        synchronized(lock) {
            if (closed) return
            closed = true
            clips.values.forEach(Clip::close)
            clips.clear()
        }
        scope.cancel()
    }
}
