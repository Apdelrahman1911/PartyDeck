package dev.partydeck.app

import android.animation.ValueAnimator
import android.app.Activity
import android.content.Intent
import android.graphics.Color
import android.os.Bundle
import android.view.WindowManager
import androidx.activity.ComponentActivity
import androidx.activity.OnBackPressedCallback
import androidx.activity.SystemBarStyle
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.ui.Modifier
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.semantics.testTagsAsResourceId
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.lifecycleScope
import androidx.lifecycle.repeatOnLifecycle
import dev.partydeck.app.controller.AppScreen
import dev.partydeck.app.godot.GodotPresentationActivation
import dev.partydeck.app.platform.InvitationScannerHost
import kotlinx.coroutines.launch

class MainActivity : ComponentActivity(), InvitationScannerHost {
    private lateinit var owner: PartyDeckAndroidViewModel
    private lateinit var privacy: SessionPrivacyGuard
    private var shellAttachment: Long? = null
    private var activityStarted = false
    private var activityResumed = false
    private var activityFocused = false
    private val scanner = registerForActivityResult(ActivityResultContracts.StartActivityForResult()) { result ->
        val invitation = if (result.resultCode == Activity.RESULT_OK) {
            result.data?.getStringExtra(InvitationScannerActivity.EXTRA_INVITATION)
        } else {
            null
        }
        owner.services.deliverScanResult(invitation)
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge(
            statusBarStyle = SystemBarStyle.dark(Color.TRANSPARENT),
            navigationBarStyle = SystemBarStyle.dark(Color.TRANSPARENT),
        )
        owner = ViewModelProvider(this, object : ViewModelProvider.Factory {
            override fun <T : ViewModel> create(modelClass: Class<T>): T {
                require(modelClass == PartyDeckAndroidViewModel::class.java)
                @Suppress("UNCHECKED_CAST")
                return PartyDeckAndroidViewModel(
                    application,
                    qualifiedPresentations = GodotPresentationActivation.read(application),
                ) as T
            }
        })[PartyDeckAndroidViewModel::class.java]
        privacy = SessionPrivacyGuard(this)
        privacy.setPrivateSession(owner.controller.state.value.session != null)
        shellAttachment = owner.attachActivity(this)
        updateInteractivity()

        val back = object : OnBackPressedCallback(false) {
            override fun handleOnBackPressed() {
                if (!owner.controller.requestBack()) {
                    isEnabled = false
                    onBackPressedDispatcher.onBackPressed()
                }
            }
        }
        onBackPressedDispatcher.addCallback(this, back)
        lifecycleScope.launch {
            repeatOnLifecycle(Lifecycle.State.STARTED) {
                owner.controller.state.collect { state ->
                    back.isEnabled = state.screen != AppScreen.HOME
                    privacy.setPrivateSession(state.session != null)
                    if (state.session != null) {
                        window.addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
                    } else {
                        window.clearFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
                    }
                }
            }
        }
        setContent {
            PartyDeckApp(owner.controller, modifier = Modifier.semantics { testTagsAsResourceId = true })
        }
        privacy.attachCover()
    }

    override fun onStart() {
        super.onStart()
        activityStarted = true
        updateInteractivity()
    }

    override fun onResume() {
        super.onResume()
        activityResumed = true
        activityFocused = hasWindowFocus()
        if (owner.services.isAttachedActivity(this)) {
            owner.controller.setSystemReduceMotion(!ValueAnimator.areAnimatorsEnabled())
            owner.controller.setPresentationTextScale(resources.configuration.fontScale.toDouble())
        }
        updateInteractivity()
    }

    override fun onPause() {
        activityResumed = false
        privacy.setResumed(false)
        updateInteractivity()
        super.onPause()
    }

    override fun onWindowFocusChanged(hasFocus: Boolean) {
        super.onWindowFocusChanged(hasFocus)
        activityFocused = hasFocus
        if (::privacy.isInitialized && !hasFocus) privacy.setFocused(false)
        updateInteractivity()
    }

    override fun onUserLeaveHint() {
        if (::privacy.isInitialized) privacy.setFocused(false)
        shellAttachment?.let { owner.userLeavingActivity(this, it) }
        super.onUserLeaveHint()
    }

    override fun onStop() {
        activityStarted = false
        activityResumed = false
        activityFocused = false
        privacy.setResumed(false)
        shellAttachment?.let { owner.stopActivity(this, it, isChangingConfigurations) }
        super.onStop()
    }

    override fun onDestroy() {
        shellAttachment?.let { owner.detachActivity(this, it) }
        shellAttachment = null
        super.onDestroy()
    }

    override fun launchInvitationScanner() {
        scanner.launch(Intent(this, InvitationScannerActivity::class.java))
    }

    private fun updateInteractivity() {
        val identity = shellAttachment ?: return
        owner.updateActivityVisibility(this, identity, activityStarted, activityResumed, activityFocused)
    }

    internal fun onShellInteractivityChanged(identity: Long, interactive: Boolean) {
        if (shellAttachment != identity) return
        if (::privacy.isInitialized) {
            privacy.setPrivateSession(owner.controller.state.value.session != null)
            // Positive privacy permission comes only from the selected aggregate surface.
            // Negative native lifecycle callbacks cover synchronously before publication.
            privacy.setFocused(activityFocused && interactive)
            privacy.setResumed(activityResumed)
        }
    }
}
