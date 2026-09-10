package dev.partydeck.godot.compare

import android.app.Activity
import android.app.ActivityManager
import android.content.Intent
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.os.Process
import android.provider.Settings
import android.view.ViewGroup
import android.widget.Button
import android.widget.CheckBox
import android.widget.LinearLayout
import android.widget.ScrollView
import android.widget.TextView
import androidx.core.content.edit
import dev.partydeck.godot.bridge.PresentationMode

/** Native chooser. It never loads, initializes, or looks up a Godot singleton. */
class ComparisonActivity : Activity() {
    private val main = Handler(Looper.getMainLooper())
    private lateinit var twoD: Button
    private lateinit var threeD: Button
    private lateinit var status: TextView
    private lateinit var motion: CheckBox
    private lateinit var sound: CheckBox
    private lateinit var reference: CheckBox
    private var resumed = false
    private var opening = false
    private var showFailed = false
    private val refreshProcesses = object : Runnable {
        override fun run() {
            if (!resumed) return
            val running = getSystemService(ActivityManager::class.java).runningAppProcesses
            // An unavailable process list is not evidence that the previous engine died.
            val ownProcessVisible = running?.any { it.pid == Process.myPid() } == true
            val engineExists = running?.any { it.uid == Process.myUid() && it.processName == "$packageName:godot" } == true
            val available = ownProcessVisible && !engineExists && !opening
            twoD.isEnabled = available
            threeD.isEnabled = available
            status.setText(when {
                opening -> R.string.chooser_launching
                !available -> R.string.chooser_waiting
                showFailed -> R.string.chooser_failed
                else -> R.string.chooser_ready
            })
            if (!available) main.postDelayed(this, 150)
        }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val preferences = getSharedPreferences(PREFERENCES, MODE_PRIVATE)
        val page = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(dp(24), dp(28), dp(24), dp(24))
            addView(label(getString(R.string.comparison_title), 34f))
            addView(label(getString(R.string.comparison_intro)).apply {
                setPadding(0, dp(16), 0, dp(24))
            })
        }
        motion = CheckBox(this).apply {
            id = R.id.reduce_motion
            setText(R.string.reduce_motion)
            minHeight = dp(48)
            val systemReduced = Settings.Global.getFloat(contentResolver, Settings.Global.ANIMATOR_DURATION_SCALE, 1f) == 0f
            isChecked = preferences.getBoolean("reduceMotion", systemReduced)
            setOnCheckedChangeListener { _, checked -> preferences.edit { putBoolean("reduceMotion", checked) } }
        }
        sound = CheckBox(this).apply {
            id = R.id.sound_enabled
            setText(R.string.enable_sound)
            minHeight = dp(48)
            isChecked = preferences.getBoolean("soundEnabled", true)
            setOnCheckedChangeListener { _, checked -> preferences.edit { putBoolean("soundEnabled", checked) } }
        }
        page.addView(motion)
        page.addView(sound)
        reference = CheckBox(this).apply {
            id = R.id.reference_scenario
            setText(R.string.reference_scenario)
            minHeight = dp(48)
            // An explicit per-run choice; normal interactive matches always use secure randomness.
            isChecked = false
        }
        page.addView(reference)
        page.addView(label(getString(R.string.reference_scenario_description), 14f).apply {
            setPadding(0, 0, 0, dp(12))
        })
        twoD = button(R.string.launch_2d, R.id.launch_2d) { launch(PresentationMode.TWO_D) }
        threeD = button(R.string.launch_3d, R.id.launch_3d) { launch(PresentationMode.THREE_D) }
        page.addView(twoD, LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT))
        page.addView(threeD, LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT))
        status = label(getString(R.string.chooser_ready)).apply {
            id = R.id.chooser_status
            accessibilityLiveRegion = TextView.ACCESSIBILITY_LIVE_REGION_POLITE
            setPadding(0, dp(16), 0, dp(12))
        }
        page.addView(status)
        page.addView(label(getString(R.string.native_scope), 14f))
        page.addView(button(R.string.native_notices, R.id.native_notices) {
            startActivity(Intent(this, NoticesActivity::class.java))
        })
        val scroll = ScrollView(this).apply { addView(page) }
        val root = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setBackgroundColor(getColor(R.color.comparison_ink))
            addView(scroll, LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT))
        }
        setContentView(root)
        applySafeInsets(root)
    }

    override fun onResume() {
        super.onResume()
        resumed = true
        opening = false
        main.removeCallbacks(refreshProcesses)
        refreshProcesses.run()
    }

    override fun onPause() {
        resumed = false
        main.removeCallbacks(refreshProcesses)
        super.onPause()
    }

    @Deprecated("Used for the simple native qualification Activity result, with no engine in this process.")
    override fun onActivityResult(requestCode: Int, resultCode: Int, data: Intent?) {
        super.onActivityResult(requestCode, resultCode, data)
        if (requestCode == REQUEST_GAME) {
            opening = false
            showFailed = resultCode != RESULT_OK
        }
    }

    private fun launch(mode: PresentationMode) {
        if (!resumed || opening || !twoD.isEnabled || !threeD.isEnabled) return
        opening = true
        showFailed = false
        twoD.isEnabled = false
        threeD.isEnabled = false
        status.setText(R.string.chooser_launching)
        val launch = Intent(this, GodotGameActivity::class.java)
            .putExtra(EXTRA_MODE, mode.wireName)
            .putExtra(EXTRA_REDUCE_MOTION, motion.isChecked)
            .putExtra(EXTRA_SOUND, sound.isChecked)
            .putExtra(EXTRA_REFERENCE_SCENARIO, reference.isChecked)
        @Suppress("DEPRECATION")
        startActivityForResult(launch, REQUEST_GAME)
    }

    companion object {
        internal const val EXTRA_MODE = "dev.partydeck.godot.compare.MODE"
        internal const val EXTRA_REDUCE_MOTION = "dev.partydeck.godot.compare.REDUCE_MOTION"
        internal const val EXTRA_SOUND = "dev.partydeck.godot.compare.SOUND"
        internal const val EXTRA_REFERENCE_SCENARIO = "dev.partydeck.godot.compare.REFERENCE_SCENARIO"
        private const val PREFERENCES = "comparison-preferences"
        private const val REQUEST_GAME = 1
    }
}
