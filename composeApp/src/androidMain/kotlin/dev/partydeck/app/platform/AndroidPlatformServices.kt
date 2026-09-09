package dev.partydeck.app.platform

import android.app.Activity
import android.content.ClipData
import android.content.ClipDescription
import android.content.ClipboardManager
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Build
import android.os.PersistableBundle
import dev.partydeck.app.controller.PlatformServices
import dev.partydeck.app.controller.SettingsStore
import dev.partydeck.app.shared.R
import java.lang.ref.WeakReference
import java.security.SecureRandom
import kotlin.random.Random
import kotlin.random.asKotlinRandom

/** The Activity owns the result launcher; this interface prevents a retained Activity callback. */
interface InvitationScannerHost {
    fun launchInvitationScanner()
}

class AndroidPlatformServices(context: Context) : PlatformServices {
    private val applicationContext = context.applicationContext
    private val tokenRandom = SecureRandom()
    private var activityReference = WeakReference<Activity>(null)
    private var scanResult: ((String?) -> Unit)? = null

    override val settingsStore: SettingsStore = AndroidSettingsStore(applicationContext)
    override val feedback = AndroidFeedback(applicationContext)
    override val canScanInvitation: Boolean
        get() = applicationContext.packageManager.hasSystemFeature(PackageManager.FEATURE_CAMERA_ANY)
    override val showsCopyConfirmation: Boolean
        get() = Build.VERSION.SDK_INT >= 33

    /** The current Activity is weakly attached, so a configuration change cannot leak the old window. */
    fun attachActivity(activity: Activity) {
        activityReference = WeakReference(activity)
        feedback.attachView(activity.window.decorView)
    }

    fun detachActivity(activity: Activity) {
        feedback.detachView(activity.window.decorView)
        if (activityReference.get() === activity) activityReference.clear()
    }

    fun isAttachedActivity(activity: Activity): Boolean = activityReference.get() === activity

    override fun copyText(value: String) {
        val clip = ClipData.newPlainText(applicationContext.getString(R.string.invitation_clipboard_label), value).apply {
            description.extras = PersistableBundle().apply {
                putBoolean(ClipDescription.EXTRA_IS_SENSITIVE, true)
            }
        }
        applicationContext.getSystemService(ClipboardManager::class.java).setPrimaryClip(clip)
    }

    override fun shareText(value: String) {
        val activity = requireForegroundActivity()
        val send = Intent(Intent.ACTION_SEND).apply {
            type = "text/plain"
            putExtra(Intent.EXTRA_TEXT, value)
        }
        activity.startActivity(Intent.createChooser(send, null))
    }

    override fun scanInvitation(onResult: (String?) -> Unit) {
        check(canScanInvitation) { "This device has no camera" }
        check(scanResult == null) { "An invitation scan is already in progress" }
        val owner = requireForegroundActivity() as? InvitationScannerHost
            ?: error("The invitation scanner is unavailable")
        scanResult = onResult
        try {
            owner.launchInvitationScanner()
        } catch (failure: Exception) {
            scanResult = null
            throw failure
        }
    }

    fun deliverScanResult(value: String?) {
        val callback = scanResult
        scanResult = null
        callback?.invoke(value?.takeIf { it.length <= MAX_INVITATION_LENGTH })
    }

    override fun gameRandom(): Random = SecureRandom().asKotlinRandom()

    override fun secureToken(): String {
        val bytes = ByteArray(32)
        tokenRandom.nextBytes(bytes)
        return buildString(64) {
            for (byte in bytes) {
                val value = byte.toInt() and 0xff
                append(HEX[value ushr 4])
                append(HEX[value and 0xf])
            }
        }
    }

    fun close() {
        scanResult = null
        activityReference.clear()
        feedback.close()
    }

    private fun requireForegroundActivity(): Activity = activityReference.get()
        ?.takeUnless { it.isFinishing || it.isDestroyed }
        ?: error("The current PartyDeck window is unavailable")

    private companion object {
        const val HEX = "0123456789abcdef"
        const val MAX_INVITATION_LENGTH = 2048
    }
}
