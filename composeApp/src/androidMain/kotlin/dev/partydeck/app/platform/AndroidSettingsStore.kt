package dev.partydeck.app.platform

import android.content.Context
import dev.partydeck.app.controller.AppSettings
import dev.partydeck.app.controller.SettingsStore
import java.io.IOException
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import kotlinx.coroutines.withContext

/** Only presentation preferences belong here; admission and reconnect secrets stay in memory. */
internal class AndroidSettingsStore(context: Context) : SettingsStore {
    private val applicationContext = context.applicationContext
    private val access = Mutex()
    private val preferences by lazy {
        applicationContext.getSharedPreferences("partydeck_settings", Context.MODE_PRIVATE)
    }

    override suspend fun load(): AppSettings = access.withLock {
        withContext(Dispatchers.IO) {
            AppSettings(
                displayName = preferences.getString(DISPLAY_NAME, null) ?: AppSettings().displayName,
                soundEnabled = preferences.getBoolean(SOUND_ENABLED, true),
                hapticsEnabled = preferences.getBoolean(HAPTICS_ENABLED, true),
                reduceMotion = preferences.getBoolean(REDUCE_MOTION, false),
            )
        }
    }

    override suspend fun save(settings: AppSettings): Unit = access.withLock {
        withContext(Dispatchers.IO) {
            val saved = preferences.edit()
                .putString(DISPLAY_NAME, settings.displayName)
                .putBoolean(SOUND_ENABLED, settings.soundEnabled)
                .putBoolean(HAPTICS_ENABLED, settings.hapticsEnabled)
                .putBoolean(REDUCE_MOTION, settings.reduceMotion)
                .commit()
            if (!saved) throw IOException("PartyDeck settings could not be saved")
        }
    }

    private companion object {
        const val DISPLAY_NAME = "display_name"
        const val SOUND_ENABLED = "sound_enabled"
        const val HAPTICS_ENABLED = "haptics_enabled"
        const val REDUCE_MOTION = "reduce_motion"
    }
}
