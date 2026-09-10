package dev.partydeck.app.godot

import dev.partydeck.app.controller.EmbeddedPresentationHost
import dev.partydeck.app.controller.GameplayPresentation
import dev.partydeck.app.controller.LifecycleBoundEmbeddedGameSession
import dev.partydeck.games.ENGINE_BRIDGE_PROTOCOL_VERSION
import dev.partydeck.games.EmbeddedGameFactory
import dev.partydeck.games.EmbeddedGameSession
import dev.partydeck.games.EngineCommand
import dev.partydeck.games.EngineEvent
import dev.partydeck.games.EngineLaunch
import dev.partydeck.games.PartyDeckGames
import dev.partydeck.godot.bridge.LastLightWireCodec
import dev.partydeck.godot.bridge.PresentationMode
import dev.partydeck.godot.bridge.PresentationPreferences
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.NonCancellable
import kotlinx.coroutines.channels.Channel
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.flow
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import kotlinx.coroutines.withContext
import kotlinx.coroutines.withTimeoutOrNull
import kotlin.coroutines.EmptyCoroutineContext

internal data class IosGodotLifecycle(
    val presentationId: String,
    val generation: Long,
    val isForeground: Boolean,
    val isBackgrounded: Boolean,
)

/** One registered native owner, one disposable presentation, and no additional authority/event gate. */
internal class IosGodotPresentationHost(
    private val onLifecycle: (String) -> Unit,
    private val onClosing: (String) -> Unit,
    private val onExit: (String) -> Unit,
    private val onUseCompose: (String) -> Unit,
) : EmbeddedPresentationHost {
    private val mutableAvailable = MutableStateFlow(emptySet<GameplayPresentation>())
    override val available = mutableAvailable.asStateFlow()
    private var registration: Registration? = null
    private var active: NativeSession? = null
    private var hostForeground = false
    private var hostBackgrounded = false
    private var quarantined = false
    private var closed = false

    fun install(port: IosGodotNativePort): IosGodotRegistration? {
        requireIosGodotMainThread()
        if (closed || quarantined || registration != null || active != null) return null
        val installed = Registration(port)
        registration = installed
        return IosGodotRegistration(
            publish = { twoD, threeD ->
                if (registration === installed && !closed) {
                    installed.offered = buildSet {
                        if (twoD) add(GameplayPresentation.GODOT_2D)
                        if (threeD) add(GameplayPresentation.GODOT_3D)
                    }
                    publishAvailability()
                }
            },
            detach = {
                if (registration === installed) {
                    registration = null
                    publishAvailability()
                    active?.beginClose()
                }
            },
        )
    }

    override fun createFactory(
        presentation: GameplayPresentation,
        preferences: PresentationPreferences,
    ): EmbeddedGameFactory? {
        requireIosGodotMainThread()
        if (presentation !in available.value) return null
        val mode = when (presentation) {
            GameplayPresentation.GODOT_2D -> PresentationMode.TWO_D
            GameplayPresentation.GODOT_3D -> PresentationMode.THREE_D
            GameplayPresentation.COMPOSE -> return null
        }
        return object : EmbeddedGameFactory {
            override val engineId = "godot-${mode.wireName}"
            override val protocolVersion = ENGINE_BRIDGE_PROTOCOL_VERSION
            override val supportedGames = setOf(PartyDeckGames.lastLight.id)
            override suspend fun open(launch: EngineLaunch): EmbeddedGameSession = openNative(
                presentation, mode, preferences, launch,
            )
        }
    }

    /** Called before controller lifecycle setters so queued commands capture the new native epoch. */
    fun updateLifecycle(isForeground: Boolean, isBackgrounded: Boolean) {
        requireIosGodotMainThread()
        hostForeground = isForeground
        hostBackgrounded = isBackgrounded
        active?.takeUnless { it.closing }?.updateLifecycle(isForeground, isBackgrounded)
    }

    fun currentLifecycle(): IosGodotLifecycle? {
        requireIosGodotMainThread()
        return active?.takeUnless { it.closing }?.lifecycle
    }

    fun close() {
        requireIosGodotMainThread()
        if (closed) return
        closed = true
        registration = null
        publishAvailability()
        active?.beginClose()
    }

    private suspend fun openNative(
        presentation: GameplayPresentation,
        mode: PresentationMode,
        preferences: PresentationPreferences,
        launch: EngineLaunch,
    ): EmbeddedGameSession {
        var acquired: NativeSession? = null
        try {
            return withContext(Dispatchers.Main.immediate) {
                check(!closed && !quarantined && active == null && presentation in available.value) {
                    "The iOS renderer is unavailable"
                }
                val installed = checkNotNull(registration)
                // The common shell remains the sound/haptics owner.
                val document = LastLightWireCodec.encodeLaunch(launch, mode, preferences.copy(soundEnabled = false))
                val session = NativeSession(installed, launch.presentationId)
                acquired = session
                active = session
                session.prepare(document)
                session
            }
        } catch (failure: Exception) {
            withContext(NonCancellable + Dispatchers.Main.immediate) {
                try {
                    acquired?.close()
                } catch (cleanup: Exception) {
                    failure.addSuppressed(cleanup)
                }
            }
            throw failure
        }
    }

    private fun publishAvailability() {
        mutableAvailable.value = if (closed || quarantined || active?.closing == true) emptySet()
        else registration?.offered.orEmpty()
    }

    private fun finished(session: NativeSession, success: Boolean) {
        if (!success) quarantined = true
        if (active === session) active = null
        publishAvailability()
    }

    private class Registration(val port: IosGodotNativePort) {
        var offered = emptySet<GameplayPresentation>()
    }

    private inner class NativeSession(
        private val installed: Registration,
        val presentationId: String,
    ) : LifecycleBoundEmbeddedGameSession, IosGodotNativeCallbacks {
        private val queue = Channel<EngineEvent>(MAX_QUEUED_EVENTS)
        private val deliveryMutex = Mutex()
        private val closeResult = CompletableDeferred<Boolean>()
        private var operation: NativeOperation? = null
        private var failure: Exception? = null
        private var lifecycleNotifications = 0L
        private var readyConfirmed = false
        private var closeCompleted = false
        var lifecycle: IosGodotLifecycle? = null
            private set
        var closing = false
            private set

        override val lifecycleGeneration: Long
            get() {
                requireIosGodotMainThread()
                return checkNotNull(lifecycle).generation
            }

        override val events: Flow<EngineEvent> = flow {
            for (event in queue) {
                failure?.let { throw it }
                if (closing) return@flow
                emit(event)
            }
            failure?.let { throw it }
        }

        suspend fun prepare(document: String) {
            val prepared = awaitNative { completion ->
                installed.port.prepare(presentationId, document, hostForeground, hostBackgrounded, this, completion)
            }
            check(prepared && isCurrent() && lifecycle != null) { "The iOS renderer did not prepare its lifecycle" }
        }

        override suspend fun send(command: EngineCommand) = send(command, lifecycleGeneration)

        override suspend fun send(command: EngineCommand, lifecycleGeneration: Long) {
            withContext(Dispatchers.Main.immediate) {
                deliveryMutex.withLock {
                    check(isCurrent()) { "The iOS presentation is closed" }
                    if (lifecycleGeneration != this@NativeSession.lifecycleGeneration) return@withLock
                    val document = LastLightWireCodec.encodeCommand(presentationId, command)
                    val confirmReady = !readyConfirmed
                    val delivered = awaitNative { completion ->
                        installed.port.deliver(presentationId, document, lifecycleGeneration, confirmReady, completion)
                    }
                    if (delivered) {
                        if (confirmReady) readyConfirmed = true
                    } else if (isCurrent() && lifecycleGeneration == this@NativeSession.lifecycleGeneration) {
                        fail("The iOS renderer rejected a current delivery")
                        throw checkNotNull(failure)
                    }
                    // Rejected obsolete deliveries do not consume Ready confirmation or end play.
                }
            }
        }

        fun updateLifecycle(isForeground: Boolean, isBackgrounded: Boolean) {
            val before = lifecycleNotifications
            val accepted = try {
                installed.port.updateLifecycle(presentationId, isForeground, isBackgrounded)
            } catch (_: Exception) {
                false
            }
            if (isCurrent() && (!accepted || lifecycleNotifications == before)) {
                fail("The iOS renderer did not acknowledge its lifecycle synchronously")
            }
        }

        override fun event(document: String) {
            requireIosGodotMainThread()
            if (!isCurrent()) return
            val event = try {
                LastLightWireCodec.decodeEvent(document)
            } catch (_: IllegalArgumentException) {
                fail("The iOS renderer sent an invalid event")
                return
            }
            if (!queue.trySend(event).isSuccess) fail("The iOS renderer event queue overflowed")
        }

        override fun lifecycleChanged(generation: Long, isForeground: Boolean, isBackgrounded: Boolean) {
            requireIosGodotMainThread()
            if (!isCurrent()) return
            val previous = lifecycle
            val changed = previous != null &&
                (previous.isForeground != isForeground || previous.isBackgrounded != isBackgrounded)
            if (generation < 0 || generation < (previous?.generation ?: 0) ||
                (changed && generation == previous.generation) || lifecycleNotifications == Long.MAX_VALUE
            ) {
                fail("The iOS renderer supplied an invalid lifecycle generation")
                return
            }
            lifecycle = IosGodotLifecycle(presentationId, generation, isForeground, isBackgrounded)
            lifecycleNotifications++
            onLifecycle(presentationId)
        }

        override fun exitRequested() {
            requireIosGodotMainThread()
            if (isCurrent()) onExit(presentationId)
        }

        override fun useCompose() {
            requireIosGodotMainThread()
            if (isCurrent()) onUseCompose(presentationId)
        }

        override fun failed() {
            requireIosGodotMainThread()
            if (isCurrent()) fail("The iOS renderer was lost")
        }

        private fun isCurrent() = !closing && !closed && active === this && registration === installed

        private suspend fun awaitNative(invoke: (IosGodotNativeCompletion) -> Unit): Boolean {
            check(operation == null) { "An iOS native operation is already pending" }
            val pending = NativeOperation()
            operation = pending
            return try {
                invoke(pending)
                pending.result.await()
            } finally {
                pending.invalidate()
                if (operation === pending) operation = null
            }
        }

        private fun fail(message: String) {
            if (failure == null) failure = IllegalStateException(message)
            beginClose()
        }

        fun beginClose(): CompletableDeferred<Boolean> {
            requireIosGodotMainThread()
            if (closing) return closeResult
            closing = true
            publishAvailability()
            queue.close(failure)
            while (queue.tryReceive().isSuccess) { /* Drop events from the disposed lifetime. */ }
            operation?.complete(false)
            try {
                installed.port.close(presentationId, object : IosGodotNativeCompletion {
                    override fun complete(success: Boolean) {
                        requireIosGodotMainThread()
                        finishClose(success)
                    }
                })
            } catch (_: Exception) {
                finishClose(false)
            }
            onClosing(presentationId)
            return closeResult
        }

        override suspend fun close() {
            withContext(Dispatchers.Main.immediate) {
                val result = beginClose()
                try {
                    if (withTimeoutOrNull(NATIVE_CLOSE_TIMEOUT_MS) { result.await() } != true) {
                        finishClose(false)
                        error("The iOS renderer did not confirm deferred cleanup")
                    }
                } catch (cancelled: CancellationException) {
                    finishClose(false)
                    throw cancelled
                }
            }
        }

        private fun finishClose(success: Boolean) {
            if (closeCompleted) return
            closeCompleted = true
            // Waiters may resume immediately on Main; publish native release before resuming them.
            finished(this, success)
            closeResult.complete(success)
        }
    }

    private class NativeOperation : IosGodotNativeCompletion {
        val result = CompletableDeferred<Boolean>()
        private var valid = true

        override fun complete(success: Boolean) {
            requireIosGodotMainThread()
            if (!valid) return
            valid = false
            result.complete(success)
        }

        fun invalidate() {
            valid = false
            result.cancel()
        }
    }

    private companion object {
        const val MAX_QUEUED_EVENTS = 16 // Each codec-validated event is at most 4 KiB.
        const val NATIVE_CLOSE_TIMEOUT_MS = 3_000L
    }
}

/** The pinned Darwin Main.immediate dispatcher tests the current CFRunLoop before dispatching. */
internal fun requireIosGodotMainThread() {
    check(!Dispatchers.Main.immediate.isDispatchNeeded(EmptyCoroutineContext)) {
        "iOS Godot port calls and callbacks require the main thread"
    }
}
