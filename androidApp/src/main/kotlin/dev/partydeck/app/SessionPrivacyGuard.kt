package dev.partydeck.app

import android.app.Activity
import android.os.Build
import android.view.Gravity
import android.view.View
import android.view.ViewGroup
import android.view.WindowManager
import android.widget.TextView

/** Native privacy protection is applied before drawing, independently of Compose or network teardown. */
internal class SessionPrivacyGuard(private val activity: Activity) {
    private var privateSession = false
    private var resumed = false
    private var focused = false
    private var cover: View? = null
    private var composeContent: View? = null
    private var originalAccessibilityImportance = View.IMPORTANT_FOR_ACCESSIBILITY_AUTO

    init {
        if (Build.VERSION.SDK_INT >= 33) activity.setRecentsScreenshotEnabled(false)
    }

    fun attachCover() {
        val content = activity.findViewById<ViewGroup>(android.R.id.content)
        composeContent = content.getChildAt(0)
        originalAccessibilityImportance = composeContent?.importantForAccessibility ?: View.IMPORTANT_FOR_ACCESSIBILITY_AUTO
        cover = TextView(activity).apply {
            setBackgroundColor(activity.getColor(R.color.partydeck_ink))
            setTextColor(activity.getColor(R.color.partydeck_paper))
            setText(R.string.private_hand_cover)
            textSize = 18f
            gravity = Gravity.CENTER
            val padding = (24 * resources.displayMetrics.density).toInt()
            setPadding(padding, padding, padding, padding)
            isClickable = true
            importantForAccessibility = View.IMPORTANT_FOR_ACCESSIBILITY_YES
        }.also {
            activity.addContentView(it, ViewGroup.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT))
        }
        updateCover()
    }

    fun setPrivateSession(value: Boolean) {
        privateSession = value
        if (Build.VERSION.SDK_INT < 33) {
            if (value) activity.window.addFlags(WindowManager.LayoutParams.FLAG_SECURE)
            else activity.window.clearFlags(WindowManager.LayoutParams.FLAG_SECURE)
        }
        updateCover()
    }

    fun setResumed(value: Boolean) {
        resumed = value
        updateCover()
    }

    fun setFocused(value: Boolean) {
        focused = value
        updateCover()
    }

    private fun updateCover() {
        val conceal = privateSession && !(resumed && focused)
        cover?.visibility = if (conceal) View.VISIBLE else View.GONE
        composeContent?.importantForAccessibility = if (conceal) {
            View.IMPORTANT_FOR_ACCESSIBILITY_NO_HIDE_DESCENDANTS
        } else {
            originalAccessibilityImportance
        }
    }
}
