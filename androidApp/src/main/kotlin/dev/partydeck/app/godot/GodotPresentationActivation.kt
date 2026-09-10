package dev.partydeck.app.godot

import android.content.Context
import android.content.pm.PackageManager
import dev.partydeck.app.controller.GameplayPresentation

/** Build-packaged exposure only; malformed metadata leaves the production renderer choices closed. */
internal object GodotPresentationActivation {
    private const val PROFILE = "dev.partydeck.GODOT_ACTIVATION_PROFILE"
    private const val MODES = "dev.partydeck.GODOT_PRESENTATION_MODES"
    private val modeOrder = listOf("2d", "3d")

    fun read(context: Context): Set<GameplayPresentation> = try {
        // The int flag overload also supports the app's API 26 minimum.
        @Suppress("DEPRECATION")
        val metadata = context.packageManager.getApplicationInfo(context.packageName, PackageManager.GET_META_DATA).metaData
        fromPackagedMetadata(metadata?.getString(PROFILE), metadata?.getString(MODES))
    } catch (_: PackageManager.NameNotFoundException) {
        emptySet()
    } catch (_: RuntimeException) {
        emptySet()
    }

    internal fun fromPackagedMetadata(profile: String?, modesCsv: String?): Set<GameplayPresentation> {
        if (profile !in setOf("shipping", "qualification") || modesCsv == null) return emptySet()
        if (modesCsv.isEmpty()) return emptySet()
        val modes = modesCsv.split(',')
        if (modes.any { it !in modeOrder } || modes.distinct().size != modes.size ||
            modeOrder.filter { it in modes }.joinToString(",") != modesCsv
        ) return emptySet()
        return modes.mapTo(linkedSetOf()) {
            when (it) {
                "2d" -> GameplayPresentation.GODOT_2D
                "3d" -> GameplayPresentation.GODOT_3D
                else -> error("Mode validation must precede presentation mapping.")
            }
        }
    }
}
