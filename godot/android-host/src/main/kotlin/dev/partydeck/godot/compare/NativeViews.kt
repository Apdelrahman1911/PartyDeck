package dev.partydeck.godot.compare

import android.app.Activity
import android.content.Context
import android.os.Build
import android.view.View
import android.view.WindowInsets
import android.widget.Button
import android.widget.TextView

internal fun Context.dp(value: Int): Int = (value * resources.displayMetrics.density).toInt()

internal fun Context.label(text: CharSequence, sizeSp: Float = 16f): TextView = TextView(this).apply {
    this.text = text
    textSize = sizeSp
    setTextColor(getColor(R.color.comparison_paper))
}

internal fun Context.button(resourceId: Int, viewId: Int, action: () -> Unit): Button = Button(this).apply {
    id = viewId
    setText(resourceId)
    isAllCaps = false
    minHeight = dp(48)
    setOnClickListener { action() }
}

/** Target 36 draws edge-to-edge; the native controls and Godot surface share the inset content. */
internal fun Activity.applySafeInsets(view: View) {
    view.setOnApplyWindowInsetsListener { target, insets ->
        if (Build.VERSION.SDK_INT >= 30) {
            val safe = insets.getInsets(WindowInsets.Type.systemBars() or WindowInsets.Type.displayCutout())
            target.setPadding(safe.left, safe.top, safe.right, safe.bottom)
        } else {
            @Suppress("DEPRECATION")
            target.setPadding(insets.systemWindowInsetLeft, insets.systemWindowInsetTop,
                insets.systemWindowInsetRight, insets.systemWindowInsetBottom)
        }
        insets
    }
    view.requestApplyInsets()
}
