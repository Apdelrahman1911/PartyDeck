package dev.partydeck.godot.compare

import android.app.Activity
import android.app.ActivityManager
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
import android.view.View
import android.view.ViewGroup
import android.view.WindowManager
import android.widget.Button
import android.widget.FrameLayout
import android.widget.LinearLayout
import android.widget.TextView
import androidx.activity.OnBackPressedCallback
import androidx.core.view.isVisible
import androidx.fragment.app.FragmentActivity
import dev.partydeck.core.GameAction
import dev.partydeck.core.GamePhase
import dev.partydeck.games.EngineEventBody
import dev.partydeck.godot.bridge.BridgeDecision
import dev.partydeck.godot.bridge.BridgeInput
import dev.partydeck.godot.bridge.BridgeRejection
import dev.partydeck.godot.bridge.LastLightWireCodec
import dev.partydeck.godot.bridge.PresentationMode
import dev.partydeck.godot.bridge.PresentationPreferences
import dev.partydeck.godot.bridge.QualificationAuthorityDriver
import org.godotengine.godot.Godot
import org.godotengine.godot.GodotFragment
import org.godotengine.godot.GodotHost
import org.godotengine.godot.plugin.GodotPlugin
import org.json.JSONObject
import java.security.SecureRandom
import java.util.UUID
import java.util.concurrent.atomic.AtomicBoolean
import kotlin.random.Random

/**
 * Isolated local-practice qualification host. Every authority call belongs to the Android
 * main thread; the real Godot render thread sees only versioned recipient-safe documents.
 * No production session/transport or network secret crosses into this process.
 */
class GodotGameActivity : FragmentActivity(), GodotHost, PartyDeckBridgePlugin.Listener {
    private val main = Handler(Looper.getMainLooper())
    private val forceQuitObserved = AtomicBoolean(false)
    private val terminatingObserved = AtomicBoolean(false)
    private val facts = JSONObject()
    private var evidenceRevision = 0L
    private var engine: Godot? = null
    private var plugin: PartyDeckBridgePlugin? = null
    private lateinit var authority: QualificationAuthorityDriver
    private lateinit var launchDocument: String
    private lateinit var mode: PresentationMode
    private lateinit var evidence: EvidenceRecorder
    private lateinit var stage: FrameLayout
    private lateinit var cover: TextView
    private lateinit var status: TextView
    private lateinit var refresh: Button
    private lateinit var initialConfiguration: Configuration
    private var resumed = false
    private var focused = false
    private var foreground = false
    private var foregroundDelivered = false
    private var foregroundEpoch = 0L
    private var ready = false
    private var closing = false
    private var destroying = false
    private var finalEvidence = false
    private var isolatedProcess = false
    private var diagnosticRequest = 0L
    private var diagnosticSequence = -1L
    private var requestInFlight: String? = null
    private var lastDiagnosticRequestAt = 0L
    private var receivedEvents = 0L
    private var receivedIntents = 0L
    private var acceptedIntents = 0L
    private var rejectedEvents = 0L
    private var authorityRejections = 0L
    private var botActions = 0L
    private var submittedCommands = 0L
    private val requestDiagnostics = Runnable { requestFreshDiagnostics() }
    private val diagnosticsTimeout = Runnable {
        if (!closing && requestInFlight != null) {
            plugin?.cancelDiagnosticsRequest()
            requestInFlight = null
            facts.put("diagnosticsTimedOut", true)
            recordEvidence()
        }
    }
    private val startupTimeout = Runnable { if (!ready && !closing) fail("renderer_ready_timeout") }
    private val closeFallback = Runnable {
        if (!destroying) {
            facts.put("closeSignalAcknowledged", false)
            destroyEngine()
        }
    }
    private val botTurn = Runnable {
        if (foreground && ready && !closing) {
            try {
                for (step in authority.advanceOtherPlayers()) {
                    if (step.documents.isNotEmpty()) botActions += 1
                    step.documents.forEach(::send)
                }
                recordEvidence()
                scheduleDiagnostics()
            } catch (_: RuntimeException) { fail("practice_authority_failed") }
        }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        // Matches are transient. Never restore a Fragment/native singleton across Activity
        // recreation: a fresh engine requires a fresh process, per Godot's own host source.
        super.onCreate(null)
        isolatedProcess = getSystemService(ActivityManager::class.java).runningAppProcesses
            ?.any { it.pid == Process.myPid() && it.processName == "$packageName:godot" } == true
        if (!isolatedProcess || savedInstanceState != null || !HOST_CLAIMED.compareAndSet(false, true)) {
            setResult(RESULT_CANCELED)
            finish()
            if (isolatedProcess) main.postDelayed({ Process.killProcess(Process.myPid()) }, 150)
            return
        }
        mode = PresentationMode.entries.firstOrNull {
            it.wireName == intent.getStringExtra(ComparisonActivity.EXTRA_MODE)
        } ?: run {
            setResult(RESULT_CANCELED)
            finish()
            main.postDelayed({ Process.killProcess(Process.myPid()) }, 150)
            return
        }
        initialConfiguration = Configuration(resources.configuration)
        if (Build.VERSION.SDK_INT >= 33) setRecentsScreenshotEnabled(false)
        else window.addFlags(WindowManager.LayoutParams.FLAG_SECURE)
        createNativeContent()
        onBackPressedDispatcher.addCallback(this, object : OnBackPressedCallback(true) {
            override fun handleOnBackPressed() { closeTable("native_back") }
        })
        val referenceScenario = intent.getBooleanExtra(ComparisonActivity.EXTRA_REFERENCE_SCENARIO, false)
        val secure = SecureRandom()
        val random = if (referenceScenario) Random(2) else object : Random() {
            override fun nextBits(bitCount: Int): Int = if (bitCount == 0) 0 else secure.nextInt().ushr(32 - bitCount)
        }
        authority = QualificationAuthorityDriver(random, UUID.randomUUID().toString())
        launchDocument = authority.launchDocument(mode, PresentationPreferences(
            reduceMotion = intent.getBooleanExtra(ComparisonActivity.EXTRA_REDUCE_MOTION, false),
            soundEnabled = intent.getBooleanExtra(ComparisonActivity.EXTRA_SOUND, true),
            textScale = resources.configuration.fontScale.toDouble().coerceIn(1.0, 2.0),
        ))
        evidence = EvidenceRecorder(filesDir) { if (!closing) fail("evidence_io_failed") }
        facts.put("schemaVersion", 1)
            .put("presentationId", authority.presentationId)
            .put("mode", mode.wireName)
            .put("randomness", if (referenceScenario) "reference_seed_2" else "platform_secure_random")
            .put("displayDensity", resources.displayMetrics.density.toDouble())
            .put("enginePid", Process.myPid())
            .put("taskId", taskId)
            .put("startedElapsedRealtimeMs", SystemClock.elapsedRealtime().toString())
            .put("lifecycle", "opening")
            .put("setupCompleted", false)
            .put("mainLoopStarted", false)
            .put("readyAccepted", false)
            .put("bridgeClosed", false)
            .put("nativeDestroyRequested", false)
            .put("nativeDestroyReturned", false)
            .put("nativeTerminating", false)
            .put("nativeForceQuitCallback", false)
            .put("processExitRequested", false)
            .put("diagnosticsRequested", "0")
            .put("diagnosticsTimedOut", false)
            .put("capturePolicy", if (Build.VERSION.SDK_INT >= 33) "recents_disabled" else "secure_window")
        // Authority rejects background input immediately, even before the scene connects.
        authority.setForeground(false)
        recordEvidence()
        supportFragmentManager.beginTransaction()
            .add(R.id.engine_container, GodotFragment(), "partydeck-godot")
            .commitNow()
        main.postDelayed(startupTimeout, 30_000)
    }

    private fun createNativeContent() {
        status = label(getString(R.string.engine_loading, mode.wireName.uppercase()), 16f).apply {
            id = R.id.host_status
            accessibilityLiveRegion = View.ACCESSIBILITY_LIVE_REGION_POLITE
            setPadding(dp(12), dp(8), dp(12), 0)
        }
        val buttons = LinearLayout(this).apply {
            orientation = LinearLayout.HORIZONTAL
            addView(button(R.string.exit_game, R.id.exit_game) { closeTable("native_close") },
                LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f))
            refresh = button(R.string.refresh_diagnostics, R.id.refresh_diagnostics) { scheduleDiagnostics() }
            refresh.isEnabled = false
            addView(refresh, LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f))
        }
        val container = FrameLayout(this).apply { id = R.id.engine_container }
        cover = label(getString(R.string.privacy_cover), 20f).apply {
            id = R.id.privacy_cover
            gravity = Gravity.CENTER
            setPadding(dp(24), dp(24), dp(24), dp(24))
            setBackgroundColor(getColor(R.color.comparison_ink))
            isClickable = true
            isFocusable = true
            importantForAccessibility = View.IMPORTANT_FOR_ACCESSIBILITY_YES
        }
        stage = FrameLayout(this).apply {
            addView(container, FrameLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT))
            addView(cover, FrameLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT))
        }
        val root = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setBackgroundColor(getColor(R.color.comparison_ink))
            addView(status)
            addView(buttons)
            addView(stage, LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, 0, 1f))
        }
        setContentView(root)
        applySafeInsets(root)
    }

    override fun getActivity(): Activity = this

    override fun getGodot(): Godot = engine ?: Godot.getInstance(applicationContext).also { engine = it }

    override fun getCommandLine(): List<String> = listOf(
        "--main-pack", "res://partydeck-last-light.pck", "--rendering-method", "gl_compatibility",
        "--xr-mode", "off",
    )

    override fun getHostPlugins(engine: Godot): Set<GodotPlugin> {
        val bridge = plugin ?: PartyDeckBridgePlugin(engine, launchDocument,
            resources.displayMetrics.density.toDouble(), this).also { plugin = it }
        return setOf(bridge)
    }

    override fun onGodotForceQuit(instance: Godot) {
        forceQuitObserved.set(true)
        main.post { if (!closing) closeTable("native_force_quit") }
    }

    override fun onGodotForceQuit(godotInstanceId: Int) = false

    override fun onGodotRestartRequested(instance: Godot) {
        main.post { if (!closing) closeTable("restart_requested") }
    }

    override fun onNewGodotInstanceRequested(args: Array<String>): Int = -1

    override fun onNativeSetup() {
        if (closing) return
        facts.put("setupCompleted", true)
        recordEvidence()
    }

    override fun onNativeMainLoop() {
        if (closing) return
        facts.put("mainLoopStarted", true)
        recordEvidence()
    }

    override fun onRendererEvent(document: String) {
        if (closing) return
        check(Looper.myLooper() == Looper.getMainLooper())
        receivedEvents += 1
        val event = try { LastLightWireCodec.decodeEvent(document) } catch (_: IllegalArgumentException) { null }
        val playerIntent = event?.body is EngineEventBody.PlayerIntent
        if (playerIntent) receivedIntents += 1
        try {
            val step = authority.handleEvent(document)
            when (val decision = step.decision) {
                is BridgeDecision.Rejected -> {
                    rejectedEvents += 1
                    facts.put("lastBridgeRejection", decision.reason.name)
                    if (decision.reason in setOf(BridgeRejection.INVALID_DOCUMENT, BridgeRejection.WRONG_PRESENTATION,
                            BridgeRejection.UNSUPPORTED_PROTOCOL)) {
                        fail("invalid_renderer_document")
                        return
                    }
                    if (playerIntent && ready) send(authority.refreshView())
                }
                is BridgeDecision.Accepted -> {
                    val input = decision.input
                    if (playerIntent) {
                        facts.put("lastIntentType", when (input) {
                            is BridgeInput.Action -> if (input.action is GameAction.Play) "play" else "challenge"
                            BridgeInput.AdvanceRound -> "advance_round"
                            BridgeInput.ReturnToLobby -> "return_to_lobby"
                            else -> "unknown"
                        })
                        if (step.authorityRejection == null) acceptedIntents += 1
                    }
                    if (step.authorityRejection != null) {
                        authorityRejections += 1
                        facts.put("lastAuthorityRejection", step.authorityRejection?.name)
                        send(authority.refreshView())
                    }
                    when (input) {
                        BridgeInput.Ready -> {
                            ready = true
                            facts.put("readyAccepted", true)
                            main.removeCallbacks(startupTimeout)
                            plugin?.acceptReady()
                            sendForeground(foreground)
                            updatePrivacy()
                        }
                        BridgeInput.ExitRequested -> { closeTable("renderer_exit"); return }
                        BridgeInput.ReturnToLobby -> { closeTable("return_to_chooser"); return }
                        is BridgeInput.Failed -> { fail("renderer_${input.reason.name.lowercase()}"); return }
                        else -> Unit
                    }
                    step.documents.forEach(::send)
                }
            }
            recordEvidence()
            scheduleDiagnostics()
            scheduleBots()
        } catch (_: RuntimeException) { fail("authority_or_bridge_failed") }
    }

    override fun onRendererDiagnostics(document: String) {
        if (closing) return
        val expected = requestInFlight ?: return
        val diagnostic = RendererDiagnostics.decode(document, authority.presentationId, mode.wireName)
        if (diagnostic == null) {
            fail("invalid_renderer_diagnostics")
            return
        }
        if (diagnostic.getString("requestId") != expected) {
            facts.put("staleDiagnosticsRejected", true)
            recordEvidence()
            return
        }
        requestInFlight = null
        plugin?.cancelDiagnosticsRequest()
        main.removeCallbacks(diagnosticsTimeout)
        val sequence = diagnostic.getString("sequence").toLong()
        if (sequence <= diagnosticSequence || diagnostic.getString("revision") != authority.revision.toString()) {
            facts.put("staleDiagnosticsRejected", true)
            recordEvidence()
            scheduleDiagnostics()
            return
        }
        diagnosticSequence = sequence
        facts.put("diagnostics", diagnostic).put("diagnosticsTimedOut", false)
        recordEvidence()
    }

    override fun onBridgeFailure(code: String) { if (!closing) fail(code) }

    override fun onResume() {
        super.onResume()
        resumed = true
        updatePrivacy()
    }

    override fun onPause() {
        resumed = false
        updatePrivacy() // Native opaque cover + authority rejection precede Godot/Fragment pause.
        super.onPause()
    }

    override fun onWindowFocusChanged(hasFocus: Boolean) {
        if (!hasFocus) {
            focused = false
            updatePrivacy()
        }
        super.onWindowFocusChanged(hasFocus)
        if (hasFocus) {
            focused = true
            updatePrivacy()
        }
    }

    override fun onConfigurationChanged(newConfig: Configuration) {
        if (::initialConfiguration.isInitialized &&
            (newConfig.orientation != initialConfiguration.orientation ||
                newConfig.screenWidthDp != initialConfiguration.screenWidthDp ||
                newConfig.screenHeightDp != initialConfiguration.screenHeightDp ||
                newConfig.densityDpi != initialConfiguration.densityDpi)) {
            // Upstream explicitly does not support automatic engine surface resizing.
            closeTable("window_configuration_changed")
        }
        super.onConfigurationChanged(newConfig)
    }

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        // A second launch cannot replace the recipient or initialize another engine.
        if (!closing) closeTable("duplicate_launch")
    }

    override fun onDestroy() {
        if (::authority.isInitialized && !destroying) {
            closing = true
            foreground = false
            authority.close()
            plugin?.dispose()
            facts.put("bridgeClosed", true).put("closeReason", "activity_destroyed")
            destroyEngine(finishActivity = false)
        }
        super.onDestroy()
    }

    private fun updatePrivacy() {
        if (!::cover.isInitialized) return
        val next = resumed && focused && !closing
        if (next != foreground || !next) foregroundDelivered = false
        val conceal = !next || !ready || !foregroundDelivered
        cover.visibility = if (conceal) View.VISIBLE else View.GONE
        findViewById<View>(R.id.engine_container).importantForAccessibility = if (conceal) {
            View.IMPORTANT_FOR_ACCESSIBILITY_NO_HIDE_DESCENDANTS
        } else View.IMPORTANT_FOR_ACCESSIBILITY_AUTO
        refresh.isEnabled = next && ready
        if (next != foreground && ::authority.isInitialized && !closing) {
            foreground = next
            sendForeground(next)
            if (next) {
                scheduleDiagnostics()
                scheduleBots()
            } else {
                main.removeCallbacks(botTurn)
                main.removeCallbacks(requestDiagnostics)
                main.removeCallbacks(diagnosticsTimeout)
                requestInFlight = null
                plugin?.cancelDiagnosticsRequest()
            }
        } else foreground = next
        if (::evidence.isInitialized && !closing) {
            facts.put("lifecycle", if (next && ready) "active" else if (!next) "background" else "opening")
            recordEvidence()
        }
    }

    private fun send(document: String) {
        if (closing) return
        if (plugin?.send(document) == true) submittedCommands += 1
    }

    private fun sendForeground(value: Boolean) {
        foregroundEpoch += 1
        val epoch = foregroundEpoch
        val document = authority.setForeground(value)
        if (plugin?.send(document) {
                if (!closing && foreground && ready && value && foregroundEpoch == epoch) {
                    plugin?.afterForegroundDraw {
                        if (!closing && foreground && ready && foregroundEpoch == epoch) {
                            foregroundDelivered = true
                            updatePrivacy()
                        }
                    }
                }
            } == true) submittedCommands += 1
    }

    private fun scheduleBots() {
        main.removeCallbacks(botTurn)
        if (foreground && ready && !closing) main.postDelayed(botTurn, 700)
    }

    private fun scheduleDiagnostics() {
        if (!ready || closing || !foreground) return
        main.removeCallbacks(requestDiagnostics)
        val remaining = (lastDiagnosticRequestAt + 500 - SystemClock.elapsedRealtime()).coerceAtLeast(100)
        main.postDelayed(requestDiagnostics, remaining)
    }

    private fun requestFreshDiagnostics() {
        if (closing || !ready || !foreground || requestInFlight != null) return
        if (diagnosticRequest == Long.MAX_VALUE) { fail("diagnostic_counter_exhausted"); return }
        diagnosticRequest += 1
        val request = diagnosticRequest.toString()
        requestInFlight = request
        lastDiagnosticRequestAt = SystemClock.elapsedRealtime()
        if (plugin?.requestDiagnostics(request) != true) {
            requestInFlight = null
            return
        }
        facts.put("diagnosticsRequested", request)
        main.removeCallbacks(diagnosticsTimeout)
        main.postDelayed(diagnosticsTimeout, 2_000)
        recordEvidence()
    }

    private fun fail(code: String) {
        if (closing) return
        facts.put("failureCode", code)
        status.setText(R.string.engine_failed)
        closeTable("failure")
    }

    private fun closeTable(reason: String) {
        if (closing || !::authority.isInitialized) return
        closing = true
        foreground = false
        foregroundDelivered = false
        foregroundEpoch += 1
        main.removeCallbacks(botTurn)
        main.removeCallbacks(requestDiagnostics)
        main.removeCallbacks(diagnosticsTimeout)
        main.removeCallbacks(startupTimeout)
        updatePrivacy()
        refresh.isEnabled = false
        status.setText(R.string.engine_closing)
        facts.put("lifecycle", "closing").put("closeReason", reason).put("bridgeClosed", true)
        val closeDocument = authority.close()
        recordEvidence()
        // A paused/not-yet-started render thread may never consume Close. Native privacy and
        // bridge invalidation are synchronous; upstream destruction follows after this bound.
        main.postDelayed(closeFallback, 250)
        plugin?.close(closeDocument) {
            facts.put("closeSignalAcknowledged", true)
            destroyEngine()
        }
    }

    private fun destroyEngine(finishActivity: Boolean = true) {
        if (destroying) return
        destroying = true
        main.removeCallbacks(closeFallback)
        plugin?.dispose()
        facts.put("nativeDestroyRequested", engine != null)
        recordEvidence()
        val start = SystemClock.elapsedRealtime()
        val renderer = engine?.renderView
        // The upstream timed GL wait may wake before its mExited flag is set. Confirm
        // exit with the public API before onDestroy's single-wait fallback can misfire.
        val rendererExited = renderer != null && waitForRendererExit(
            timeoutMillis = 1_500,
            nowMillis = SystemClock::elapsedRealtime,
            requestExitAndWait = renderer::blockingExitRenderer,
        )
        if (engine != null && !rendererExited) {
            if (!facts.has("failureCode")) facts.put("failureCode", "native_renderer_exit_unconfirmed")
            Log.e(EvidenceRecorder.TAG, "Renderer exit was not confirmed before native host cleanup")
            recordEvidence()
        }
        engine?.destroyAndKillProcess { terminatingObserved.set(true) }
        facts.put("nativeDestroyReturned", engine != null)
            .put("nativeDestroyElapsedMs", (SystemClock.elapsedRealtime() - start).toString())
            .put("nativeTerminating", terminatingObserved.get() || plugin?.nativeTerminating?.get() == true)
            .put("nativeForceQuitCallback", forceQuitObserved.get())
        setResult(if (facts.has("failureCode")) RESULT_CANCELED else RESULT_OK)
        if (finishActivity && !isFinishing) finish()
        facts.put("lifecycle", "process_exit_requested").put("processExitRequested", true)
        finalEvidence = true
        val finalDocument = evidenceDocument()
        evidence.finish(finalDocument) {
            // finish() has returned ownership of the task to the separate-process chooser.
            main.postDelayed({ terminateOwnEngineProcess() }, 100)
        }
        // IO failure must not leave a warm singleton available for a second launch.
        main.postDelayed({ terminateOwnEngineProcess() }, 1_500)
    }

    private fun terminateOwnEngineProcess() {
        if (!isolatedProcess) return
        Log.i(EvidenceRecorder.TAG, "Engine process exit requested")
        Process.killProcess(Process.myPid())
    }

    private fun recordEvidence() {
        if (!::evidence.isInitialized || finalEvidence) return
        if (!closing && ready) status.text = if (authority.revision == 0L) {
            getString(R.string.engine_ready, mode.wireName.uppercase())
        } else getString(R.string.engine_revision, mode.wireName.uppercase(), authority.revision.toString())
        evidence.record(evidenceDocument())
    }

    private fun evidenceDocument(): String {
        evidenceRevision += 1
        val view = authority.view
        val publicState = JSONObject()
            .put("phase", view.phase.name)
            .put("roundNumber", view.roundNumber)
            .put("viewerHandCount", view.yourHand.size)
            .put("canPlay", view.availableActions.canPlay)
            .put("canChallenge", view.availableActions.canChallenge)
            .put("canAdvanceRound", view.phase == GamePhase.ROUND_ENDED)
            .put("winnerPresent", view.winnerId != null)
        view.roundOutcome?.let {
            publicState.put("outcomeRoundNumber", it.roundNumber)
                .put("truthful", it.truthful).put("burnedOut", it.burnedOut)
        }
        facts.put("evidenceRevision", evidenceRevision.toString())
            .put("revision", authority.revision.toString())
            .put("foreground", foreground)
            .put("coverVisible", cover.isVisible)
            .put("foregroundFrameReady", foregroundDelivered)
            .put("receivedEvents", receivedEvents.toString())
            .put("receivedIntents", receivedIntents.toString())
            .put("acceptedIntents", acceptedIntents.toString())
            .put("rejectedEvents", rejectedEvents.toString())
            .put("authorityRejections", authorityRejections.toString())
            .put("botActions", botActions.toString())
            .put("submittedCommands", submittedCommands.toString())
            .put("publicState", publicState)
        engine?.renderView?.view?.let { surface ->
            val location = IntArray(2)
            surface.getLocationOnScreen(location)
            facts.put("engineSurface", JSONObject()
                .put("x", location[0]).put("y", location[1])
                .put("width", surface.width).put("height", surface.height))
        }
        return facts.toString()
    }

    companion object {
        private val HOST_CLAIMED = AtomicBoolean(false)
    }
}
