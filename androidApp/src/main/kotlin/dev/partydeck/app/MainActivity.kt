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
import dev.partydeck.app.platform.InvitationScannerHost
import kotlinx.coroutines.launch

class MainActivity : ComponentActivity(), InvitationScannerHost {
    private lateinit var owner: PartyDeckAndroidViewModel
    private lateinit var privacy: SessionPrivacyGuard
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
                return PartyDeckAndroidViewModel(application) as T
            }
        })[PartyDeckAndroidViewModel::class.java]
        owner.services.attachActivity(this)
        updateInteractivity()
        privacy = SessionPrivacyGuard(this)
        privacy.setPrivateSession(owner.controller.state.value.session != null)

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
        if (owner.services.isAttachedActivity(this)) owner.controller.setBackgrounded(false)
    }

    override fun onResume() {
        super.onResume()
        activityResumed = true
        activityFocused = hasWindowFocus()
        if (owner.services.isAttachedActivity(this)) {
            owner.controller.setSystemReduceMotion(!ValueAnimator.areAnimatorsEnabled())
        }
        privacy.setResumed(true)
        privacy.setFocused(activityFocused)
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
        if (::privacy.isInitialized) privacy.setFocused(hasFocus)
        updateInteractivity()
    }

    override fun onStop() {
        activityResumed = false
        updateInteractivity()
        // A replacement Activity keeps the same session; rotation is not OS backgrounding.
        if (!isChangingConfigurations && owner.services.isAttachedActivity(this)) {
            owner.controller.setBackgrounded(true)
        }
        super.onStop()
    }

    override fun onDestroy() {
        owner.services.detachActivity(this)
        super.onDestroy()
    }

    override fun launchInvitationScanner() {
        scanner.launch(Intent(this, InvitationScannerActivity::class.java))
    }

    private fun updateInteractivity() {
        if (::owner.isInitialized && owner.services.isAttachedActivity(this)) {
            owner.controller.setForeground(activityResumed && activityFocused)
        }
    }
}
