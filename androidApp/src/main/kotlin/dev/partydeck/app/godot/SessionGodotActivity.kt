package dev.partydeck.app.godot

import android.annotation.SuppressLint
import android.app.Activity
import android.app.ActivityManager
import android.app.Application
import android.content.Context
import android.content.Intent
import android.content.res.Configuration
import android.os.Build
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.os.Process
import android.os.SystemClock
import android.util.Log
import android.view.Gravity
import android.view.KeyEvent
import android.view.MotionEvent
import android.view.View
import android.view.ViewGroup
import android.view.WindowInsets
import android.view.WindowManager
import android.widget.Button
import android.widget.FrameLayout
import android.widget.LinearLayout
import android.widget.TextView
import androidx.activity.OnBackPressedCallback
import androidx.fragment.app.FragmentActivity
import dev.partydeck.app.R
import dev.partydeck.games.ENGINE_BRIDGE_PROTOCOL_VERSION
import dev.partydeck.games.MAX_ENGINE_PAYLOAD_BYTES
import dev.partydeck.godot.android.PartyDeckBridgePlugin
import dev.partydeck.godot.android.waitForRendererExit
import dev.partydeck.godot.bridge.LastLightWireCodec
import org.godotengine.godot.Godot
import org.godotengine.godot.GodotFragment
import org.godotengine.godot.GodotHost
import org.godotengine.godot.plugin.GodotPlugin
import org.json.JSONException
import org.json.JSONObject
import java.lang.ref.WeakReference
import java.util.concurrent.atomic.AtomicBoolean

/**
 * A disposable renderer in the private :godot process. The bound shell owns the session,
 * recipient projection, Ready acceptance and event gate; this host owns native privacy.
 */
class SessionGodotActivity : FragmentActivity(), GodotHost, PartyDeckBridgePlugin.Listener,
    GodotRendererConnection.Listener {
    private val main = Handler(Looper.getMainLooper())
    private var connection: GodotRendererConnection? = null
    private var engine: Godot? = null
    private var plugin: PartyDeckBridgePlugin? = null
    private var pendingLaunch: String? = null
    private var presentationId: String? = null
    private var closeDocument: String? = null
    private var launchAdmitted = false
    private var engineAttached = false
    private var ownsProcess = false
    private var closing = false
    private var destroying = false
    private var started = false
    private var resumed = false
    private var focused = false
    private var readyAccepted = false
    private var hostForeground = false
    private var foregroundDelivered = false
    private var foregroundDrawn = false
    private var privacyGeneration = 0L
    private var rendererRunning: Boolean? = null
    private var backDownTime: Long? = null
    private var initialSurfaceSize: Pair<Int, Int>? = null
    private lateinit var initialConfiguration: Configuration
    private lateinit var engineContainer: SessionEngineContainer
    private lateinit var cover: TextView
    private lateinit var status: TextView
    private lateinit var standardTable: Button
    private lateinit var leaveTable: Button

    private val startupTimeout = Runnable { if (!readyAccepted && !closing) fallBack() }
    private val foregroundDrawTimeout = Runnable {
        if (localInteractive() && hostForeground && !foregroundDrawn) fallBack()
    }
    private val closeFallback = Runnable { destroyEngine() }

    override fun onCreate(savedInstanceState: Bundle?) {
        // A native singleton is never restored into a second Activity or reused in this process.
        super.onCreate(null)
        if (!isOwnGodotProcess()) {
            finish()
            return
        }
        if (savedInstanceState != null || !PROCESS_CLAIMED.compareAndSet(false, true)) {
            val owner = processOwner?.get()
            owner?.fallBack()
            finish()
            if (owner == null) main.postDelayed(::terminateOwnProcess, 100)
            return
        }
        ownsProcess = true
        processOwner = WeakReference(this)
        initialConfiguration = Configuration(resources.configuration)
        if (Build.VERSION.SDK_INT >= 33) setRecentsScreenshotEnabled(false)
        else window.addFlags(WindowManager.LayoutParams.FLAG_SECURE)
        createNativeContent()
        onBackPressedDispatcher.addCallback(this, object : OnBackPressedCallback(true) {
            override fun handleOnBackPressed() { closeTable(ReturnAction.LEAVE) }
        })
        connection = GodotRendererConnection(this, this)
        main.postDelayed(startupTimeout, 30_000)
        if (connection?.bind(intent) != true) fallBack()
    }

    override fun onLaunchDocument(document: String): Boolean {
        checkMainThread()
        if (closing || !ownsProcess || launchAdmitted || engine != null) return false
        // This is a broker-created launch, not renderer input. Read only native attachment
        // metadata; recipient data and the renderer event sequence stay with the common owner.
        val launch = try {
            require(PartyDeckBridgePlugin.withinUtf8Limit(document, MAX_ENGINE_PAYLOAD_BYTES))
            JSONObject(document).also {
                require(it.opt("type") == "launch")
                require(it.opt("protocolVersion") == ENGINE_BRIDGE_PROTOCOL_VERSION)
                require(it.opt("gameId") == "last-light")
                require(it.opt("presentationMode") == "2d" || it.opt("presentationMode") == "3d")
                require(it.getJSONObject("preferences").opt("soundEnabled") == false)
            }
        } catch (_: JSONException) {
            fallBack()
            return false
        } catch (_: IllegalArgumentException) {
            fallBack()
            return false
        }
        val id = launch.opt("presentationId") as? String ?: run {
            fallBack()
            return false
        }
        val terminal = try {
            LastLightWireCodec.encodeClose(id)
        } catch (_: IllegalArgumentException) {
            fallBack()
            return false
        }
        presentationId = id
        closeDocument = terminal
        pendingLaunch = document
        launchAdmitted = true
        bootstrapIfPossible()
        return !closing
    }

    override fun onCommandDocument(
        document: String,
        acceptReady: Boolean,
        afterDelivery: () -> Unit,
    ): Boolean {
        checkMainThread()
        if (closing) return false
        val bridge = plugin ?: return false
        val command = try {
            require(PartyDeckBridgePlugin.withinUtf8Limit(document, MAX_ENGINE_PAYLOAD_BYTES))
            JSONObject(document).also {
                require(it.opt("presentationId") == presentationId)
                require(it.opt("protocolVersion") == ENGINE_BRIDGE_PROTOCOL_VERSION)
                require(it.opt("type") == "view" || it.opt("type") == "foreground")
                if (it.opt("type") == "foreground") require(it.opt("isForeground") is Boolean)
            }
        } catch (_: JSONException) {
            fallBack()
            return false
        } catch (_: IllegalArgumentException) {
            fallBack()
            return false
        }
        if (acceptReady) {
            if (readyAccepted) return false
            readyAccepted = true
            main.removeCallbacks(startupTimeout)
            bridge.acceptReady()
        } else if (!readyAccepted) return false

        // The connection admits only commands stamped for its current published lifecycle;
        // an older foreground grant cannot acquire a new epoch merely by arriving late here.
        val foregroundCommand = command.opt("type") == "foreground"
        if (foregroundCommand) {
            conceal()
            hostForeground = command.getBoolean("isForeground")
        }
        val generation = privacyGeneration
        updateRenderScheduling()
        return bridge.send(document) {
            // Only this render-thread delivery callback acknowledges the broker command.
            afterDelivery()
            if (foregroundCommand && canDrawForeground(generation)) {
                foregroundDelivered = true
                bridge.afterForegroundDraw {
                    if (canDrawForeground(generation) && foregroundDelivered) {
                        foregroundDrawn = true
                        uncover(generation)
                    }
                }
                main.postDelayed(foregroundDrawTimeout, 10_000)
                updateRenderScheduling()
            }
        }
    }

    override fun onRendererEvent(document: String) {
        checkMainThread()
        if (!closing && connection?.sendRendererEvent(document) != true) fallBack()
    }

    override fun onRendererDiagnostics(document: String) = Unit

    override fun onBridgeFailure(code: String) { if (!closing) fallBack() }

    override fun onNativeSetup() { if (!closing) updateRenderScheduling() }

    override fun onNativeMainLoop() { if (!closing) updateRenderScheduling() }

    override fun onCloseRequested() { closeTable(ReturnAction.HOST) }

    override fun onConnectionLost() { closeTable(ReturnAction.HOST) }

    override fun getActivity(): Activity = this

    override fun getGodot(): Godot {
        check(ownsProcess && launchAdmitted && !closing)
        return engine ?: Godot.getInstance(applicationContext).also { engine = it }
    }

    override fun getCommandLine(): List<String> = listOf(
        "--main-pack", "res://partydeck-last-light.pck",
        "--rendering-method", "gl_compatibility", "--xr-mode", "off",
    )

    override fun getHostPlugins(engine: Godot): Set<GodotPlugin> {
        val bridge = plugin ?: PartyDeckBridgePlugin(
            engine, checkNotNull(pendingLaunch), resources.displayMetrics.density.toDouble(), this,
        ).also {
            it.setInputEnabled(false)
            plugin = it
        }
        return setOf(bridge)
    }

    override fun onGodotForceQuit(instance: Godot) {
        main.post { if (!closing) fallBack() }
    }

    override fun onGodotForceQuit(godotInstanceId: Int): Boolean = false

    override fun onGodotRestartRequested(instance: Godot) {
        main.post { if (!closing) fallBack() }
    }

    override fun onNewGodotInstanceRequested(args: Array<String>): Int = -1

    override fun onStart() {
        super.onStart()
        started = true
        bootstrapIfPossible()
        localLifecycleChanged(forceRendererState = true)
    }

    override fun onPostResume() {
        // FragmentActivity resumes its Fragments here, after Activity.onResume. Reapply our
        // stricter focus/foreground policy after GodotFragment's own render resume callbacks.
        super.onPostResume()
        resumed = true
        bootstrapIfPossible()
        localLifecycleChanged(forceRendererState = true)
    }

    override fun onPause() {
        resumed = false
        localLifecycleChanged()
        super.onPause()
    }

    override fun onStop() {
        started = false
        localLifecycleChanged()
        super.onStop()
    }

    override fun onWindowFocusChanged(hasFocus: Boolean) {
        if (!hasFocus) {
            focused = false
            localLifecycleChanged()
        }
        super.onWindowFocusChanged(hasFocus)
        if (hasFocus && !focused) {
            focused = true
            localLifecycleChanged()
        }
    }

    // Android's public Activity hook runs before Window/child dispatch. Core 1.18.0
    // restricts its intermediate ComponentActivity class, inherited by this hook.
    // Physical Back must reach this owner before Godot; predictive Back remains on
    // the OnBackPressedDispatcher callback registered in onCreate.
    @SuppressLint("RestrictedApi", "GestureBackNavigation")
    override fun dispatchKeyEvent(event: KeyEvent): Boolean {
        // Godot's SurfaceView consumes key events, including hardware Back. Keep native
        // Back on the same shell-owned leave-confirmation path as the accessible button.
        if (event.keyCode != KeyEvent.KEYCODE_BACK) return super.dispatchKeyEvent(event)
        when (event.action) {
            KeyEvent.ACTION_DOWN -> if (localInteractive() && event.repeatCount == 0) {
                backDownTime = event.downTime
            }
            KeyEvent.ACTION_UP -> {
                val owned = backDownTime == event.downTime
                backDownTime = null
                if (owned && localInteractive() && !event.isCanceled) closeTable(ReturnAction.LEAVE)
            }
        }
        return true
    }

    override fun onConfigurationChanged(newConfig: Configuration) {
        if (::initialConfiguration.isInitialized && (
                newConfig.orientation != initialConfiguration.orientation ||
                    newConfig.screenWidthDp != initialConfiguration.screenWidthDp ||
                    newConfig.screenHeightDp != initialConfiguration.screenHeightDp ||
                    newConfig.densityDpi != initialConfiguration.densityDpi ||
                    newConfig.fontScale != initialConfiguration.fontScale ||
                    newConfig.layoutDirection != initialConfiguration.layoutDirection
                )) fallBack()
        super.onConfigurationChanged(newConfig)
    }

    override fun onNewIntent(intent: Intent) {
        // A second handoff must not replace the recipient or reuse the consumed singleton.
        fallBack()
        super.onNewIntent(intent)
    }

    override fun onDestroy() {
        if (ownsProcess && !destroying) {
            closeTable(ReturnAction.STANDARD)
            // Do not let Fragment removal reach SurfaceView's untimed detach wait first.
            destroyEngine(finishActivity = false)
        }
        super.onDestroy()
    }

    private fun bootstrapIfPossible() {
        if (!ownsProcess || closing || !started || !launchAdmitted || engineAttached ||
            supportFragmentManager.isStateSaved || isFinishing || isDestroyed) return
        engineAttached = true
        try {
            supportFragmentManager.beginTransaction()
                .add(engineContainer.id, GodotFragment(), "partydeck-session-godot")
                .commitNow()
            pendingLaunch = null
            engine?.renderView?.view?.setZOrderOnTop(false)
            updateRenderScheduling(force = true)
        } catch (_: RuntimeException) {
            fallBack()
        } catch (_: LinkageError) {
            fallBack()
        }
    }

    private fun localLifecycleChanged(forceRendererState: Boolean = false) {
        if (!::cover.isInitialized) return
        // Even a gain keeps the old buffer concealed until the shell grants this lifecycle.
        conceal()
        updateRenderScheduling(force = forceRendererState)
        connection?.reportLifecycle(started = started, resumed = resumed, focused = focused)
    }

    private fun localInteractive(): Boolean = started && resumed && focused && !closing

    private fun canDrawForeground(generation: Long): Boolean =
        generation == privacyGeneration && readyAccepted && hostForeground && localInteractive()

    private fun conceal() {
        plugin?.setInputEnabled(false)
        foregroundDelivered = false
        foregroundDrawn = false
        main.removeCallbacks(foregroundDrawTimeout)
        backDownTime = null
        // Exhaustion is terminal: never let an old delivery generation become current again.
        if (privacyGeneration != Long.MAX_VALUE) privacyGeneration += 1
        else if (!closing) {
            closeTable(ReturnAction.STANDARD)
            return
        }
        if (!::cover.isInitialized) return
        cover.visibility = View.VISIBLE
        engineContainer.importantForAccessibility = View.IMPORTANT_FOR_ACCESSIBILITY_NO_HIDE_DESCENDANTS
        val hadEngineFocus = engineContainer.hasFocus()
        engine?.renderView?.view?.releasePointerCapture()
        engineContainer.disableInput()
        if (hadEngineFocus) cover.requestFocus()
        if (!closing) status.setText(if (readyAccepted) R.string.private_hand_cover else R.string.godot_opening_table)
    }

    private fun uncover(generation: Long) {
        if (!canDrawForeground(generation) || !foregroundDelivered || !foregroundDrawn) return
        main.removeCallbacks(foregroundDrawTimeout)
        initialSurfaceSize = initialSurfaceSize ?: engineContainer.width.takeIf { it > 0 }?.let {
            it to engineContainer.height
        }
        engineContainer.enableInput(generation)
        plugin?.setInputEnabled(true)
        // This visual surface has no mobile accessibility adapter. The native toolbar
        // returns to the complete standard-table controls on the same session.
        engineContainer.importantForAccessibility = View.IMPORTANT_FOR_ACCESSIBILITY_NO_HIDE_DESCENDANTS
        cover.visibility = View.GONE
        status.setText(R.string.godot_table_ready)
    }

    private fun updateRenderScheduling(force: Boolean = false) {
        val renderer = engine?.renderView ?: return
        // Bootstrap must draw under the opaque cover to produce Ready. After acceptance,
        // rendering resumes only after effective foreground has reached the native scene.
        val run = localInteractive() && (!readyAccepted || (hostForeground && foregroundDelivered))
        if (!force && rendererRunning == run) return
        rendererRunning = run
        // Godot 4.7.2: GodotFragment is primaryHost, so engine.onPause(this Activity) would
        // not pause it. These public render-view calls also handle focus-only interruptions.
        // The GL event queue still drains while drawing is stopped, allowing command ACKs.
        if (run) {
            renderer.onActivityStarted()
            renderer.onActivityResumed()
        } else {
            renderer.onActivityPaused()
            renderer.onActivityStopped()
        }
    }

    private fun fallBack() { closeTable(ReturnAction.STANDARD) }

    private fun closeTable(action: ReturnAction) {
        checkMainThread()
        if (closing || !ownsProcess) return
        closing = true
        hostForeground = false
        conceal()
        updateRenderScheduling()
        main.removeCallbacks(startupTimeout)
        if (::standardTable.isInitialized) {
            standardTable.isEnabled = false
            leaveTable.isEnabled = false
            status.setText(R.string.godot_closing_table)
        }
        // The broker's separate closing flag denies input. Publish actual visibility facts
        // so the shell can distinguish a closing visible child from actual OS background.
        connection?.reportLifecycle(started = started, resumed = resumed, focused = focused)
        when (action) {
            ReturnAction.STANDARD -> connection?.requestStandardTable()
            ReturnAction.LEAVE -> connection?.requestExit()
            ReturnAction.HOST -> Unit
        }
        // Privacy and input invalidation precede IPC. Neither shell ACK nor render progress
        // may hold the Activity open indefinitely when initialization or delivery fails.
        main.postDelayed(closeFallback, 250)
        val document = closeDocument
        val bridge = plugin
        if (document != null && bridge != null) bridge.close(document) { destroyEngine() }
        else destroyEngine()
    }

    private fun destroyEngine(finishActivity: Boolean = true) {
        checkMainThread()
        if (destroying || !ownsProcess) return
        destroying = true
        main.removeCallbacks(closeFallback)
        main.removeCallbacks(startupTimeout)
        main.removeCallbacks(foregroundDrawTimeout)
        plugin?.dispose()
        pendingLaunch = null
        closeDocument = null
        val currentEngine = engine
        val renderer = currentEngine?.renderView
        val exited = try {
            currentEngine == null || (renderer != null && waitForRendererExit(
                timeoutMillis = 1_500,
                nowMillis = SystemClock::elapsedRealtime,
                requestExitAndWait = renderer::blockingExitRenderer,
            ))
        } catch (_: RuntimeException) {
            false
        } catch (_: LinkageError) {
            false
        }
        // Only a true renderer-exit result proves its thread has stopped. Godot termination
        // and force-quit callbacks can run before this wait returns. Requested wait budgets
        // do not bound time spent acquiring Godot's native/GL monitor.
        if (!exited) {
            Log.e(TAG, "Native renderer exit was not confirmed; ending the owned Godot process")
            connection?.dispose()
            connection = null
            terminateOwnProcess()
            return
        }
        var cleaned = true
        try {
            currentEngine?.destroyAndKillProcess()
        } catch (_: RuntimeException) {
            cleaned = false
        } catch (_: LinkageError) {
            cleaned = false
        }
        engine = null
        plugin = null
        val completeClose: () -> Unit = {
            connection?.dispose()
            connection = null
            if (finishActivity && !isFinishing) finish()
            main.postDelayed(::terminateOwnProcess, 100)
        }
        val closingConnection = connection
        // Early Leave can precede service connection. Retain the binding for its bounded
        // HELLO/Exit/NativeClosed notification after the native renderer is already stopped.
        if (cleaned && closingConnection != null) closingConnection.reportNativeClosed(completeClose)
        else completeClose()
    }

    private fun isOwnGodotProcess(): Boolean {
        val expected = "$packageName:godot"
        return if (Build.VERSION.SDK_INT >= 28) Application.getProcessName() == expected
        else getSystemService(ActivityManager::class.java).runningAppProcesses
            ?.any { it.pid == Process.myPid() && it.processName == expected } == true
    }

    private fun terminateOwnProcess() {
        // Never terminate the shell or a PID received through the handoff/renderer.
        if (isOwnGodotProcess()) Process.killProcess(Process.myPid())
    }

    private fun createNativeContent() {
        status = label(R.string.godot_opening_table, 16f).apply {
            accessibilityLiveRegion = View.ACCESSIBILITY_LIVE_REGION_POLITE
            // Reserve room for the longer concealed status at large text sizes. A status
            // change must not itself resize the established native viewport.
            minLines = 2
            setPadding(dp(16), dp(8), dp(16), 0)
        }
        standardTable = nativeButton(R.string.godot_standard_table) { closeTable(ReturnAction.STANDARD) }.apply {
            contentDescription = getString(R.string.godot_standard_table_accessibility)
        }
        leaveTable = nativeButton(R.string.godot_leave_table) { closeTable(ReturnAction.LEAVE) }
        val buttons = LinearLayout(this).apply {
            orientation = LinearLayout.HORIZONTAL
            setPadding(dp(8), 0, dp(8), 0)
            addView(standardTable, LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f))
            addView(leaveTable, LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f))
        }
        engineContainer = SessionEngineContainer(this) { engine?.renderView?.view?.requestFocus() }.apply {
            id = View.generateViewId()
            importantForAccessibility = View.IMPORTANT_FOR_ACCESSIBILITY_NO_HIDE_DESCENDANTS
            addOnLayoutChangeListener { _, left, top, right, bottom, _, _, _, _ ->
                val size = (right - left) to (bottom - top)
                val initial = initialSurfaceSize
                if (!closing && initial != null && size != initial) fallBack()
            }
        }
        cover = label(R.string.private_hand_cover, 20f).apply {
            gravity = Gravity.CENTER
            setPadding(dp(24), dp(24), dp(24), dp(24))
            setBackgroundColor(getColor(R.color.partydeck_ink))
            isClickable = true
            isFocusable = true
            importantForAccessibility = View.IMPORTANT_FOR_ACCESSIBILITY_YES
        }
        val stage = FrameLayout(this).apply {
            addView(engineContainer, FrameLayout.LayoutParams(-1, -1))
            addView(cover, FrameLayout.LayoutParams(-1, -1))
        }
        val content = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setBackgroundColor(getColor(R.color.partydeck_ink))
            addView(status)
            addView(buttons)
            addView(stage, LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, 0, 1f))
        }
        setContentView(content)
        content.setOnApplyWindowInsetsListener { target, insets ->
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
        content.requestApplyInsets()
    }

    private fun label(textResource: Int, sizeSp: Float) = TextView(this).apply {
        setText(textResource)
        textSize = sizeSp
        setTextColor(getColor(R.color.partydeck_paper))
    }

    private fun nativeButton(textResource: Int, action: () -> Unit) = Button(this).apply {
        setText(textResource)
        textSize = 16f
        isAllCaps = false
        minHeight = dp(48)
        setSingleLine(false)
        setOnClickListener { action() }
    }

    private fun dp(value: Int): Int = (value * resources.displayMetrics.density).toInt()

    private fun checkMainThread() = check(Looper.myLooper() == Looper.getMainLooper())

    private enum class ReturnAction { STANDARD, LEAVE, HOST }

    companion object {
        private const val TAG = "PartyDeckGodot"
        private val PROCESS_CLAIMED = AtomicBoolean(false)
        private var processOwner: WeakReference<SessionGodotActivity>? = null
    }
}

/** Tracks native gesture ownership independently of the bridge's renderer-event generation. */
private class SessionEngineContainer(context: Context, private val onTouchStart: () -> Unit) : FrameLayout(context) {
    private data class KeyIdentity(val deviceId: Int, val keyCode: Int, val scanCode: Int)
    private data class PressedKey(val event: KeyEvent, val generation: Long)

    private var inputEnabled = false
    private var inputGeneration = -1L
    private var enabledAt = Long.MAX_VALUE
    private var touchGeneration = -1L
    private var lastTouch: MotionEvent? = null
    private val pressedPointers = mutableSetOf<Int>()
    private val pressedKeys = mutableMapOf<KeyIdentity, PressedKey>()

    init { descendantFocusability = FOCUS_BLOCK_DESCENDANTS }

    fun disableInput() {
        inputEnabled = false
        inputGeneration = -1L
        enabledAt = Long.MAX_VALUE
        // The plugin gate is already disabled, so synthetic releases cannot submit actions.
        cancelPendingInputEvents()
        cancelTouch()
        val keys = pressedKeys.values.toList()
        pressedKeys.clear()
        for (key in keys) {
            val release = KeyEvent.changeAction(KeyEvent.changeTimeRepeat(
                key.event, SystemClock.uptimeMillis(), 0, key.event.flags or KeyEvent.FLAG_CANCELED,
            ), KeyEvent.ACTION_UP)
            super.dispatchKeyEvent(release)
        }
        clearFocus()
        descendantFocusability = FOCUS_BLOCK_DESCENDANTS
    }

    fun enableInput(generation: Long) {
        inputGeneration = generation
        enabledAt = SystemClock.uptimeMillis()
        descendantFocusability = FOCUS_AFTER_DESCENDANTS
        inputEnabled = true
    }

    override fun dispatchTouchEvent(event: MotionEvent): Boolean {
        if (!inputEnabled || event.eventTime < enabledAt) return true
        val action = event.actionMasked
        if (action == MotionEvent.ACTION_DOWN) {
            // Reject the boundary millisecond too: an already queued DOWN may share the
            // clock tick in which the new generation became interactive.
            if (event.downTime <= enabledAt) return true
            cancelTouch()
            touchGeneration = inputGeneration
            pressedPointers.add(event.getPointerId(event.actionIndex))
            onTouchStart()
        } else {
            val previous = lastTouch ?: return true
            if (touchGeneration != inputGeneration || event.downTime != previous.downTime ||
                event.deviceId != previous.deviceId || event.source != previous.source) return true
            if (action == MotionEvent.ACTION_POINTER_DOWN) {
                pressedPointers.add(event.getPointerId(event.actionIndex))
            }
            if ((0 until event.pointerCount).any { event.getPointerId(it) !in pressedPointers }) return true
        }
        lastTouch?.recycle()
        lastTouch = MotionEvent.obtain(event)
        val handled = super.dispatchTouchEvent(event)
        when (action) {
            MotionEvent.ACTION_POINTER_UP -> pressedPointers.remove(event.getPointerId(event.actionIndex))
            MotionEvent.ACTION_UP, MotionEvent.ACTION_CANCEL -> clearTouch()
        }
        return handled
    }

    override fun dispatchKeyEvent(event: KeyEvent): Boolean {
        if (!inputEnabled || event.eventTime < enabledAt) return true
        val identity = KeyIdentity(event.deviceId, event.keyCode, event.scanCode)
        val pressed = pressedKeys[identity]
        when (event.action) {
            KeyEvent.ACTION_DOWN -> {
                if (event.repeatCount == 0) {
                    if (event.downTime <= enabledAt) return true
                    pressedKeys[identity] = PressedKey(KeyEvent(event), inputGeneration)
                } else if (pressed?.generation != inputGeneration || pressed.event.downTime != event.downTime) {
                    return true
                }
            }
            KeyEvent.ACTION_UP -> {
                if (pressed?.generation != inputGeneration || pressed.event.downTime != event.downTime) return true
                pressedKeys.remove(identity)
            }
            else -> return true
        }
        return super.dispatchKeyEvent(event)
    }

    override fun dispatchKeyShortcutEvent(event: KeyEvent): Boolean {
        val pressed = pressedKeys[KeyIdentity(event.deviceId, event.keyCode, event.scanCode)]
        return if (!inputEnabled || pressed?.generation != inputGeneration ||
            pressed.event.downTime != event.downTime) true else super.dispatchKeyShortcutEvent(event)
    }

    override fun dispatchGenericMotionEvent(event: MotionEvent): Boolean =
        if (!ownsMotion(event)) true else super.dispatchGenericMotionEvent(event)

    override fun dispatchCapturedPointerEvent(event: MotionEvent): Boolean =
        if (!ownsMotion(event)) true else super.dispatchCapturedPointerEvent(event)

    private fun ownsMotion(event: MotionEvent): Boolean {
        if (!inputEnabled || event.eventTime < enabledAt) return false
        val buttonEvent = event.buttonState != 0 || event.actionMasked == MotionEvent.ACTION_BUTTON_PRESS ||
            event.actionMasked == MotionEvent.ACTION_BUTTON_RELEASE
        if (!buttonEvent) return true
        val touch = lastTouch ?: return false
        return touchGeneration == inputGeneration && touch.deviceId == event.deviceId &&
            touch.downTime == event.downTime
    }

    private fun cancelTouch() {
        lastTouch?.let {
            val cancel = MotionEvent.obtain(it)
            cancel.action = MotionEvent.ACTION_CANCEL
            super.dispatchTouchEvent(cancel)
            cancel.recycle()
        }
        clearTouch()
    }

    private fun clearTouch() {
        lastTouch?.recycle()
        lastTouch = null
        touchGeneration = -1L
        pressedPointers.clear()
    }
}
