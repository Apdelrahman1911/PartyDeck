package dev.partydeck.app

import android.Manifest
import android.app.Activity
import android.content.Intent
import android.content.pm.PackageManager
import android.graphics.Color
import android.graphics.Typeface
import android.graphics.drawable.GradientDrawable
import android.os.Bundle
import android.os.Build
import android.provider.Settings
import android.text.TextUtils
import android.util.Log
import android.util.Size
import android.view.Gravity
import android.view.Surface
import android.view.View
import android.view.WindowManager
import android.widget.Button
import android.widget.FrameLayout
import android.widget.LinearLayout
import android.widget.ScrollView
import android.widget.TextView
import androidx.activity.ComponentActivity
import androidx.activity.SystemBarStyle
import androidx.activity.enableEdgeToEdge
import androidx.activity.result.contract.ActivityResultContracts
import androidx.camera.core.Camera
import androidx.camera.core.CameraSelector
import androidx.camera.core.ImageAnalysis
import androidx.camera.core.Preview
import androidx.camera.core.TorchState
import androidx.camera.core.resolutionselector.ResolutionSelector
import androidx.camera.core.resolutionselector.ResolutionStrategy
import androidx.camera.lifecycle.ProcessCameraProvider
import androidx.camera.view.PreviewView
import androidx.core.content.ContextCompat
import androidx.core.net.toUri
import androidx.core.view.ViewCompat
import androidx.core.view.WindowInsetsCompat
import androidx.lifecycle.Lifecycle
import dev.partydeck.app.scanner.QrInvitationAnalyzer
import dev.partydeck.app.scanner.ScannerOverlay
import java.util.concurrent.Executors

/** Camera permission is requested only after the user chooses Scan on the Join screen. */
class InvitationScannerActivity : ComponentActivity() {
    private lateinit var previewView: PreviewView
    private lateinit var overlay: ScannerOverlay
    private lateinit var instructions: LinearLayout
    private lateinit var title: TextView
    private lateinit var message: TextView
    private lateinit var action: Button
    private lateinit var light: Button
    private val worker = Executors.newSingleThreadExecutor()
    private var cameraProvider: ProcessCameraProvider? = null
    private var imageAnalysis: ImageAnalysis? = null
    private var analyzer: QrInvitationAnalyzer? = null
    private var camera: Camera? = null
    private var cameraStarting = false
    private var torchEnabled = false
    private var permissionRequested = false

    private val cameraPermission = registerForActivityResult(ActivityResultContracts.RequestPermission()) { granted ->
        if (granted) startCamera() else showPermissionExplanation()
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge(
            statusBarStyle = SystemBarStyle.dark(Color.TRANSPARENT),
            navigationBarStyle = SystemBarStyle.dark(Color.TRANSPARENT),
        )
        if (Build.VERSION.SDK_INT >= 33) setRecentsScreenshotEnabled(false)
        else window.addFlags(WindowManager.LayoutParams.FLAG_SECURE)
        setResult(Activity.RESULT_CANCELED)
        createContent()
        permissionRequested = savedInstanceState?.getBoolean(PERMISSION_REQUESTED) ?: false
        if (hasCameraPermission()) {
            previewView.post { startCamera() }
        } else if (permissionRequested) {
            showPermissionExplanation()
        } else {
            requestCameraPermission()
        }
    }

    override fun onStart() {
        super.onStart()
        analyzer?.setActive(true)
    }

    override fun onResume() {
        super.onResume()
        if (hasCameraPermission() && !cameraStarting) previewView.post { startCamera() }
    }

    override fun onStop() {
        analyzer?.setActive(false)
        super.onStop()
    }

    override fun onSaveInstanceState(outState: Bundle) {
        outState.putBoolean(PERMISSION_REQUESTED, permissionRequested)
        super.onSaveInstanceState(outState)
    }

    override fun onDestroy() {
        releaseCamera()
        worker.shutdown()
        super.onDestroy()
    }

    private fun createContent() {
        val root = FrameLayout(this).apply { setBackgroundColor(INK) }
        previewView = PreviewView(this).apply { scaleType = PreviewView.ScaleType.FILL_CENTER }
        overlay = ScannerOverlay(this)
        root.addView(previewView, fillParent())
        root.addView(overlay, fillParent())
        val controls = FrameLayout(this)
        root.addView(controls, fillParent())
        ViewCompat.setOnApplyWindowInsetsListener(controls) { view, insets ->
            val safe = insets.getInsets(WindowInsetsCompat.Type.systemBars() or WindowInsetsCompat.Type.displayCutout())
            view.setPadding(safe.left + dp(24), safe.top + dp(12), safe.right + dp(24), safe.bottom + dp(24))
            insets
        }

        val header = LinearLayout(this).apply {
            orientation = LinearLayout.HORIZONTAL
            gravity = Gravity.CENTER_VERTICAL
        }
        val brand = label(R.string.scanner_brand, 13f).apply {
            letterSpacing = .18f
            setTypeface(typeface, Typeface.BOLD)
            maxLines = 1
            ellipsize = TextUtils.TruncateAt.END
        }
        header.addView(brand, LinearLayout.LayoutParams(0, dp(48), 1f))
        header.addView(button(R.string.scanner_cancel, primary = false).apply { setOnClickListener { finish() } })
        controls.addView(header, FrameLayout.LayoutParams(FrameLayout.LayoutParams.MATCH_PARENT, dp(48), Gravity.TOP))

        instructions = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(dp(20), dp(20), dp(20), dp(16))
            background = rounded(0xF0191526.toInt())
        }
        title = label(R.string.scanner_title, 24f).apply { setTypeface(typeface, Typeface.BOLD) }
        ViewCompat.setAccessibilityHeading(title, true)
        message = label(R.string.scanner_instruction, 16f).apply {
            setTextColor(0xFFD5D0DF.toInt())
            setPadding(0, dp(8), 0, dp(16))
        }
        instructions.addView(title)
        instructions.addView(message)
        action = button(R.string.scanner_allow_camera, primary = true).apply { visibility = View.GONE }
        light = button(R.string.scanner_light_on, primary = false).apply {
            visibility = View.GONE
            setOnClickListener {
                val activeCamera = camera ?: return@setOnClickListener
                val change = activeCamera.cameraControl.enableTorch(!torchEnabled)
                change.addListener({
                    try {
                        change.get()
                    } catch (failure: Exception) {
                        Log.w(TAG, "The camera light is unavailable", failure)
                    }
                }, ContextCompat.getMainExecutor(this@InvitationScannerActivity))
            }
        }
        instructions.addView(action, LinearLayout.LayoutParams(LinearLayout.LayoutParams.MATCH_PARENT, dp(48)))
        instructions.addView(light, LinearLayout.LayoutParams(LinearLayout.LayoutParams.MATCH_PARENT, dp(48)))
        val instructionFrame = FrameLayout(this).apply {
            addView(instructions, FrameLayout.LayoutParams(FrameLayout.LayoutParams.MATCH_PARENT, FrameLayout.LayoutParams.WRAP_CONTENT, Gravity.BOTTOM))
        }
        val instructionScroll = ScrollView(this).apply {
            isFillViewport = true
            isVerticalScrollBarEnabled = false
            addView(instructionFrame, FrameLayout.LayoutParams(FrameLayout.LayoutParams.MATCH_PARENT, FrameLayout.LayoutParams.WRAP_CONTENT))
        }
        controls.addView(instructionScroll, fillParent().apply { topMargin = dp(64) })
        setContentView(root)
        ViewCompat.requestApplyInsets(controls)
    }

    private fun startCamera() {
        if (cameraStarting || isFinishing || isDestroyed || !hasCameraPermission()) return
        cameraStarting = true
        showScanning()
        val providerFuture = ProcessCameraProvider.getInstance(this)
        providerFuture.addListener({
            if (isFinishing || isDestroyed) return@addListener
            try {
                val provider = providerFuture.get()
                cameraProvider = provider
                val rotation = previewView.display?.rotation ?: Surface.ROTATION_0
                val preview = Preview.Builder().setTargetRotation(rotation).build().apply {
                    setSurfaceProvider(previewView.surfaceProvider)
                }
                val frameAnalyzer = QrInvitationAnalyzer(
                    onInvitation = { invitation -> runOnUiThread {
                        if (!isFinishing && !isDestroyed && lifecycle.currentState.isAtLeast(Lifecycle.State.STARTED)) {
                            setResult(Activity.RESULT_OK, Intent().putExtra(EXTRA_INVITATION, invitation))
                            finish()
                        }
                    } },
                    onOtherCode = { runOnUiThread { if (!isDestroyed) message.setText(R.string.scanner_wrong_code) } },
                    onFailure = { runOnUiThread { if (!isDestroyed) showCameraFailure() } },
                )
                analyzer = frameAnalyzer
                frameAnalyzer.setActive(lifecycle.currentState.isAtLeast(Lifecycle.State.STARTED))
                val analysis = ImageAnalysis.Builder()
                    .setTargetRotation(rotation)
                    .setBackpressureStrategy(ImageAnalysis.STRATEGY_KEEP_ONLY_LATEST)
                    .setResolutionSelector(ResolutionSelector.Builder()
                        .setResolutionStrategy(ResolutionStrategy(Size(1280, 720), ResolutionStrategy.FALLBACK_RULE_CLOSEST_LOWER_THEN_HIGHER))
                        .build())
                    .build().apply { setAnalyzer(worker, frameAnalyzer) }
                imageAnalysis = analysis
                val selector = if (provider.hasCamera(CameraSelector.DEFAULT_BACK_CAMERA)) {
                    CameraSelector.DEFAULT_BACK_CAMERA
                } else {
                    CameraSelector.DEFAULT_FRONT_CAMERA
                }
                camera = provider.bindToLifecycle(this, selector, preview, analysis).also { activeCamera ->
                    light.visibility = if (activeCamera.cameraInfo.hasFlashUnit()) View.VISIBLE else View.GONE
                    activeCamera.cameraInfo.torchState.observe(this) { state ->
                        torchEnabled = state == TorchState.ON
                        light.setText(if (torchEnabled) R.string.scanner_light_off else R.string.scanner_light_on)
                    }
                }
            } catch (failure: Exception) {
                Log.w(TAG, "The invitation camera is unavailable", failure)
                showCameraFailure()
            }
        }, ContextCompat.getMainExecutor(this))
    }

    private fun releaseCamera() {
        analyzer?.close()
        imageAnalysis?.clearAnalyzer()
        camera?.cameraInfo?.torchState?.removeObservers(this)
        cameraProvider?.unbindAll()
        analyzer = null
        imageAnalysis = null
        camera = null
        cameraStarting = false
    }

    private fun showScanning() {
        previewView.visibility = View.VISIBLE
        overlay.visibility = View.VISIBLE
        title.setText(R.string.scanner_title)
        message.setText(R.string.scanner_instruction)
        action.visibility = View.GONE
        light.visibility = View.GONE
        positionInstructions(Gravity.BOTTOM)
    }

    private fun showPermissionExplanation() {
        releaseCamera()
        showExplanation(R.string.scanner_permission_title, R.string.scanner_permission_body)
        if (shouldShowRequestPermissionRationale(Manifest.permission.CAMERA)) {
            action.setText(R.string.scanner_allow_camera)
            action.setOnClickListener { requestCameraPermission() }
        } else {
            action.setText(R.string.scanner_open_settings)
            action.setOnClickListener {
                startActivity(Intent(Settings.ACTION_APPLICATION_DETAILS_SETTINGS, "package:$packageName".toUri()))
            }
        }
    }

    private fun showCameraFailure() {
        releaseCamera()
        showExplanation(R.string.scanner_unavailable_title, R.string.scanner_unavailable_body)
        action.setText(R.string.scanner_retry)
        action.setOnClickListener { startCamera() }
    }

    private fun showExplanation(heading: Int, body: Int) {
        previewView.visibility = View.GONE
        overlay.visibility = View.GONE
        title.setText(heading)
        message.setText(body)
        light.visibility = View.GONE
        action.visibility = View.VISIBLE
        positionInstructions(Gravity.CENTER)
    }

    private fun positionInstructions(gravity: Int) {
        instructions.layoutParams = (instructions.layoutParams as FrameLayout.LayoutParams).apply { this.gravity = gravity }
    }

    private fun requestCameraPermission() {
        permissionRequested = true
        cameraPermission.launch(Manifest.permission.CAMERA)
    }

    private fun hasCameraPermission() = ContextCompat.checkSelfPermission(this, Manifest.permission.CAMERA) == PackageManager.PERMISSION_GRANTED

    private fun label(text: Int, size: Float) = TextView(this).apply {
        setText(text)
        textSize = size
        setTextColor(PAPER)
        gravity = Gravity.CENTER_VERTICAL
    }

    private fun button(text: Int, primary: Boolean) = Button(this).apply {
        setText(text)
        isAllCaps = false
        textSize = 15f
        minimumHeight = dp(48)
        minHeight = dp(48)
        setPadding(dp(16), 0, dp(16), 0)
        setTextColor(if (primary) INK else PAPER)
        backgroundTintList = null
        background = rounded(if (primary) PAPER else 0xFF302A3F.toInt())
    }

    private fun rounded(color: Int) = GradientDrawable().apply {
        setColor(color)
        cornerRadius = dp(16).toFloat()
    }

    private fun dp(value: Int) = (resources.displayMetrics.density * value).toInt()
    private fun fillParent() = FrameLayout.LayoutParams(FrameLayout.LayoutParams.MATCH_PARENT, FrameLayout.LayoutParams.MATCH_PARENT)

    companion object {
        const val EXTRA_INVITATION = "dev.partydeck.app.extra.INVITATION"
        private const val PERMISSION_REQUESTED = "camera_permission_requested"
        private const val TAG = "PartyDeckScanner"
        private const val INK = 0xFF191526.toInt()
        private const val PAPER = 0xFFF4F0E8.toInt()
    }
}
