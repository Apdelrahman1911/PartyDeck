package dev.partydeck.app.platform

import android.content.Context
import android.media.AudioAttributes
import android.media.AudioFocusRequest
import android.media.AudioManager
import android.media.SoundPool
import android.os.Build
import android.os.Handler
import android.os.Looper
import android.os.SystemClock
import android.util.Log
import android.view.HapticFeedbackConstants
import android.view.View
import dev.partydeck.app.controller.AppSettings
import dev.partydeck.app.controller.Feedback
import dev.partydeck.app.controller.FeedbackCue
import dev.partydeck.resources.Res
import java.io.File
import java.io.IOException
import java.lang.ref.WeakReference
import java.util.concurrent.atomic.AtomicBoolean
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import org.jetbrains.compose.resources.ExperimentalResourceApi

/** Bounded, foreground-only effects; all native playback operations are confined to the main thread. */
class AndroidFeedback(context: Context) : Feedback {
    private val applicationContext = context.applicationContext
    private val mainHandler = Handler(Looper.getMainLooper())
    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.Main.immediate)
    private val closed = AtomicBoolean(false)
    private val foreground = AtomicBoolean(false)
    private val audioManager = applicationContext.getSystemService(AudioManager::class.java)
    private val audioAttributes = AudioAttributes.Builder()
        .setUsage(AudioAttributes.USAGE_GAME)
        .setContentType(AudioAttributes.CONTENT_TYPE_SONIFICATION)
        .build()
    private var viewReference = WeakReference<View>(null)
    private var soundPool: SoundPool? = null
    private val sampleIds = mutableMapOf<FeedbackCue, Int>()
    private val loadedSamples = mutableSetOf<Int>()
    private val streams = ArrayDeque<Int>(MAX_STREAMS)
    private var hasAudioFocus = false
    private var focusEndsAt = 0L
    private val finishPlayback = Runnable { stopPlayback() }
    private val focusRequest = AudioFocusRequest.Builder(AudioManager.AUDIOFOCUS_GAIN_TRANSIENT_MAY_DUCK)
        .setAudioAttributes(audioAttributes)
        .setOnAudioFocusChangeListener({ change ->
            if (change < 0) stopPlayback()
        }, mainHandler)
        .build()

    init {
        preload()
    }

    fun attachView(view: View) = onMain {
        if (!closed.get()) viewReference = WeakReference(view)
    }

    fun detachView(view: View) = onMain {
        if (viewReference.get() === view) viewReference.clear()
    }

    override fun setForeground(value: Boolean) {
        foreground.set(value)
        if (!value) onMain { stopPlayback() }
    }

    override fun play(cue: FeedbackCue, settings: AppSettings) {
        if (closed.get() || !foreground.get()) return
        onMain {
            if (closed.get() || !foreground.get()) return@onMain
            if (settings.hapticsEnabled) playHaptic(cue)
            if (settings.soundEnabled) playSound(cue)
        }
    }

    override fun close() {
        if (!closed.compareAndSet(false, true)) return
        foreground.set(false)
        scope.cancel()
        onMain {
            stopPlayback()
            viewReference.clear()
            soundPool?.release()
            soundPool = null
            sampleIds.clear()
            loadedSamples.clear()
        }
    }

    @OptIn(ExperimentalResourceApi::class)
    private fun preload() {
        scope.launch {
            val pool = try {
                SoundPool.Builder()
                    .setMaxStreams(MAX_STREAMS)
                    .setAudioAttributes(audioAttributes)
                    .build()
            } catch (failure: RuntimeException) {
                Log.w(TAG, "Audio effects are unavailable on this device", failure)
                return@launch
            }
            soundPool = pool
            pool.setOnLoadCompleteListener { _, sampleId, status ->
                onMain {
                    if (closed.get()) return@onMain
                    if (status == 0) loadedSamples.add(sampleId)
                    else Log.w(TAG, "An audio effect failed to decode (status $status)")
                }
            }
            for (clip in clips) {
                try {
                    val file = withContext(Dispatchers.IO) {
                        val directory = File(applicationContext.cacheDir, "partydeck_audio")
                        if (!directory.isDirectory && !directory.mkdirs()) {
                            throw IOException("Audio cache directory is unavailable")
                        }
                        File(directory, clip.fileName).also {
                            it.writeBytes(Res.readBytes("files/audio/${clip.fileName}"))
                        }
                    }
                    if (closed.get()) return@launch
                    val sampleId = pool.load(file.absolutePath, 1)
                    if (sampleId != 0) sampleIds[clip.cue] = sampleId
                    else Log.w(TAG, "An audio effect could not be loaded: ${clip.cue}")
                } catch (cancelled: CancellationException) {
                    throw cancelled
                } catch (failure: Exception) {
                    Log.w(TAG, "An audio effect is unavailable: ${clip.cue}", failure)
                }
            }
        }
    }

    private fun playSound(cue: FeedbackCue) {
        val pool = soundPool ?: return
        val sampleId = sampleIds[cue]?.takeIf(loadedSamples::contains) ?: return
        if (!hasAudioFocus) {
            hasAudioFocus = audioManager.requestAudioFocus(focusRequest) == AudioManager.AUDIOFOCUS_REQUEST_GRANTED
        }
        if (!hasAudioFocus) return
        val stream = pool.play(sampleId, 1f, 1f, 1, 0, 1f)
        if (stream != 0) {
            if (streams.size == MAX_STREAMS) streams.removeFirst()
            streams.addLast(stream)
        }
        // Clip lengths are generated with the assets; include a short decoder tail before releasing focus.
        val duration = clips.first { it.cue == cue }.durationMillis + AUDIO_TAIL_MILLIS
        focusEndsAt = maxOf(focusEndsAt, SystemClock.uptimeMillis() + duration)
        mainHandler.removeCallbacks(finishPlayback)
        mainHandler.postAtTime(finishPlayback, focusEndsAt)
    }

    private fun playHaptic(cue: FeedbackCue) {
        val view = viewReference.get()?.takeIf { it.isAttachedToWindow && it.hasWindowFocus() } ?: return
        val effect = when (cue) {
            FeedbackCue.CLICK, FeedbackCue.CARD_PLAY -> HapticFeedbackConstants.CONTEXT_CLICK
            FeedbackCue.CHALLENGE, FeedbackCue.LIGHT_OUT -> if (Build.VERSION.SDK_INT >= 30) {
                HapticFeedbackConstants.REJECT
            } else {
                HapticFeedbackConstants.LONG_PRESS
            }
            FeedbackCue.ROUND_END, FeedbackCue.WIN -> if (Build.VERSION.SDK_INT >= 30) {
                HapticFeedbackConstants.CONFIRM
            } else {
                HapticFeedbackConstants.CONTEXT_CLICK
            }
        }
        view.performHapticFeedback(effect)
    }

    private fun stopPlayback() {
        mainHandler.removeCallbacks(finishPlayback)
        streams.forEach { soundPool?.stop(it) }
        streams.clear()
        focusEndsAt = 0L
        if (hasAudioFocus) {
            hasAudioFocus = false
            audioManager.abandonAudioFocusRequest(focusRequest)
        }
    }

    private inline fun onMain(crossinline action: () -> Unit) {
        if (Looper.myLooper() == Looper.getMainLooper()) action()
        else mainHandler.post { action() }
    }

    private data class Clip(val cue: FeedbackCue, val fileName: String, val durationMillis: Long)

    private companion object {
        const val TAG = "PartyDeckFeedback"
        const val MAX_STREAMS = 4
        const val AUDIO_TAIL_MILLIS = 40L
        val clips = listOf(
            Clip(FeedbackCue.CLICK, "ui_tap.wav", 70),
            Clip(FeedbackCue.CARD_PLAY, "card_place.wav", 240),
            Clip(FeedbackCue.CHALLENGE, "challenge.wav", 480),
            Clip(FeedbackCue.ROUND_END, "safe.wav", 640),
            Clip(FeedbackCue.LIGHT_OUT, "light_out.wav", 520),
            Clip(FeedbackCue.WIN, "victory.wav", 1280),
        )
    }
}
