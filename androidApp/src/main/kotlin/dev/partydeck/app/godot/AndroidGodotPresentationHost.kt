package dev.partydeck.app.godot

import android.content.Context
import android.content.Intent
import android.os.Looper
import android.util.Base64
import dev.partydeck.app.controller.EmbeddedPresentationHost
import dev.partydeck.app.controller.GameplayPresentation
import dev.partydeck.games.EmbeddedGameFactory
import dev.partydeck.games.EmbeddedGameSession
import dev.partydeck.games.ENGINE_BRIDGE_PROTOCOL_VERSION
import dev.partydeck.games.EngineLaunch
import dev.partydeck.games.GameId
import dev.partydeck.godot.bridge.LastLightWireCodec
import dev.partydeck.godot.bridge.PresentationMode
import dev.partydeck.godot.bridge.PresentationPreferences
import java.security.SecureRandom
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.NonCancellable
import kotlinx.coroutines.currentCoroutineContext
import kotlinx.coroutines.ensureActive
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.withContext

/** Retained shell attachment. Factories are inert and contain only mode and display preferences. */
class AndroidGodotPresentationHost(
    context: Context,
    listener: Listener,
    qualifiedPresentations: Set<GameplayPresentation>,
) : EmbeddedPresentationHost {
    interface Listener {
        fun launchRenderer(intent: Intent): Boolean
        /** Exact elapsedRealtime deadline for the bounded opening visibility lease. */
        fun onOpening(presentationId: String, deadlineMillis: Long)
        fun onLifecycle(presentationId: String, state: GodotRendererLifecycle)
        fun onClosing(presentationId: String)
        fun onClosed(presentationId: String)
        fun onExitRequested(presentationId: String)
        fun onStandardTableRequested(presentationId: String)
    }

    private val context = context.applicationContext
    private var listener: Listener? = listener
    private val qualified = qualifiedPresentations.filter { it != GameplayPresentation.COMPOSE }.toSet()
    private val offered = MutableStateFlow(emptySet<GameplayPresentation>())
    override val available = offered.asStateFlow()
    private var active: GodotPresentationSession? = null
    private var closed = false

    init { checkMain(); GodotSessionRegistry.observe(this) }

    override fun createFactory(
        presentation: GameplayPresentation,
        preferences: PresentationPreferences,
    ): EmbeddedGameFactory? {
        checkMain()
        if (closed || presentation !in qualified || preferences.soundEnabled) return null
        val mode = when (presentation) {
            GameplayPresentation.GODOT_2D -> PresentationMode.TWO_D
            GameplayPresentation.GODOT_3D -> PresentationMode.THREE_D
            GameplayPresentation.COMPOSE -> return null
        }
        return Factory(mode, preferences)
    }

    /** ViewModel disposal immediately invalidates callbacks and initiates bounded retirement. */
    fun close() {
        checkMain()
        if (closed) return
        closed = true
        listener = null
        GodotSessionRegistry.removeObserver(this)
        offered.value = emptySet()
        active?.detachOwner()
        active = null
    }

    internal fun registryAvailabilityChanged(vacant: Boolean) {
        checkMain()
        offered.value = if (!closed && vacant) qualified else emptySet()
    }

    internal fun lifecycle(session: GodotPresentationSession, state: GodotRendererLifecycle) {
        if (active === session && !closed) listener?.onLifecycle(session.identity.presentationId, state)
    }

    internal fun closing(session: GodotPresentationSession) {
        if (active === session && !closed) listener?.onClosing(session.identity.presentationId)
    }

    internal fun released(session: GodotPresentationSession) {
        if (active !== session) return
        active = null
        if (!closed) listener?.onClosed(session.identity.presentationId)
    }

    internal fun requestExit(session: GodotPresentationSession) {
        if (active === session && !closed) listener?.onExitRequested(session.identity.presentationId)
    }

    internal fun requestStandardTable(session: GodotPresentationSession) {
        if (active === session && !closed) listener?.onStandardTableRequested(session.identity.presentationId)
    }

    private inner class Factory(
        private val mode: PresentationMode,
        private val preferences: PresentationPreferences,
    ) : EmbeddedGameFactory {
        override val engineId = if (mode == PresentationMode.TWO_D) "godot-2d" else "godot-3d"
        override val protocolVersion = ENGINE_BRIDGE_PROTOCOL_VERSION
        override val supportedGames = setOf(GameId("last-light"))

        override suspend fun open(launch: EngineLaunch): EmbeddedGameSession {
            var created: GodotPresentationSession? = null
            try {
                return withContext(Dispatchers.Main.immediate) {
                    check(!closed && active == null && GodotSessionRegistry.vacant)
                    require(launch.gameId in supportedGames && launch.protocolVersion == protocolVersion)
                    val document = LastLightWireCodec.encodeLaunch(launch, mode, preferences)
                    val token = ByteArray(32).also { SecureRandom().nextBytes(it) }.let {
                        Base64.encodeToString(it, Base64.NO_PADDING or Base64.NO_WRAP or Base64.URL_SAFE)
                    }
                    val identity = GodotIpcIdentity(launch.presentationId, token)
                    require(identity.isValid() && GodotIpcContent(GodotIpcKind.LAUNCH, document).valid())
                    val session = GodotPresentationSession(identity, document, this@AndroidGodotPresentationHost)
                    created = session
                    if (!GodotSessionRegistry.register(session)) {
                        session.launchFailed()
                        throw GodotIpcException()
                    }
                    active = session
                    val deadline = session.startOpening()
                    listener?.onOpening(identity.presentationId, deadline)
                    currentCoroutineContext().ensureActive()
                    if (closed || session.isClosing) throw GodotIpcException()
                    val launched = try {
                        listener?.launchRenderer(GodotRendererConnection.launchIntent(context, identity)) == true
                    } catch (_: RuntimeException) {
                        // An exception after invoking a launcher is not proof that no Activity
                        // was dispatched. Preserve the retirement token until child death.
                        session.launched()
                        throw GodotIpcException()
                    }
                    if (!launched) {
                        session.launchFailed()
                        throw GodotIpcException()
                    }
                    session.launched()
                    session
                }
            } catch (cancelled: CancellationException) {
                withContext(NonCancellable + Dispatchers.Main.immediate) { created?.cancelOpen() }
                throw cancelled
            } catch (failure: Exception) {
                withContext(NonCancellable + Dispatchers.Main.immediate) { created?.cancelOpen() }
                throw failure
            }
        }
    }

    private fun checkMain() { check(Looper.myLooper() == Looper.getMainLooper()) }
}
