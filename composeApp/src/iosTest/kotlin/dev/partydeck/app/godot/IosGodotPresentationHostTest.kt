@file:OptIn(kotlinx.coroutines.ExperimentalCoroutinesApi::class)

package dev.partydeck.app.godot

import dev.partydeck.app.controller.AppSettings
import dev.partydeck.app.controller.Feedback
import dev.partydeck.app.controller.FeedbackCue
import dev.partydeck.app.controller.GameplayPresentation
import dev.partydeck.app.controller.LifecycleBoundEmbeddedGameSession
import dev.partydeck.app.controller.PartyDeckController
import dev.partydeck.app.controller.PlatformServices
import dev.partydeck.app.controller.PresentationLifecycle
import dev.partydeck.app.controller.SettingsStore
import dev.partydeck.core.LastLightEngine
import dev.partydeck.core.PlayerIdentity
import dev.partydeck.games.ENGINE_BRIDGE_PROTOCOL_VERSION
import dev.partydeck.games.EngineCommand
import dev.partydeck.games.EngineEvent
import dev.partydeck.games.EngineEventBody
import dev.partydeck.games.EngineLaunch
import dev.partydeck.games.PartyDeckGames
import dev.partydeck.godot.bridge.LastLightWireCodec
import dev.partydeck.godot.bridge.PresentationControls
import dev.partydeck.godot.bridge.PresentationMode
import dev.partydeck.godot.bridge.PresentationPreferences
import dev.partydeck.transport.LanTransport
import dev.partydeck.transport.LanTransportFactory
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.CoroutineStart
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.async
import kotlinx.coroutines.flow.collect
import kotlinx.coroutines.flow.take
import kotlinx.coroutines.flow.toList
import kotlinx.coroutines.test.TestScope
import kotlinx.coroutines.test.UnconfinedTestDispatcher
import kotlinx.coroutines.test.advanceTimeBy
import kotlinx.coroutines.test.resetMain
import kotlinx.coroutines.test.runCurrent
import kotlinx.coroutines.test.runTest
import kotlinx.coroutines.test.setMain
import kotlin.random.Random
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertFalse
import kotlin.test.assertIs
import kotlin.test.assertNotEquals
import kotlin.test.assertNotNull
import kotlin.test.assertNull
import kotlin.test.assertTrue

/** Callback/lifetime checks; these do not qualify UIKit, Swift export, or a running Godot engine. */
class IosGodotPresentationHostTest {
    @Test
    fun registrationAndFactoriesAreInertAndEarlyReadyIsRetainedForTheCommonGate() = mainTest {
        val fixture = Fixture(advertise = false)
        assertTrue(fixture.host.available.value.isEmpty())
        assertNull(fixture.host.createFactory(GameplayPresentation.GODOT_2D, PresentationPreferences()))
        assertTrue(fixture.port.preparations.isEmpty())
        fixture.registration.setAvailability(twoD = true, threeD = true)
        val preferences = PresentationPreferences(reduceMotion = true, soundEnabled = true, textScale = 1.5)
        val factory = assertNotNull(fixture.host.createFactory(GameplayPresentation.GODOT_3D, preferences))
        assertEquals("godot-3d", factory.engineId)
        assertEquals(setOf(PartyDeckGames.lastLight.id), factory.supportedGames)
        assertTrue(fixture.port.preparations.isEmpty())

        val launch = launch("early-ready")
        val session = factory.open(launch)
        assertEquals(
            LastLightWireCodec.encodeLaunch(launch, PresentationMode.THREE_D, preferences.copy(soundEnabled = false)),
            fixture.port.preparations.single().document,
        )
        assertTrue(fixture.port.deliveries.isEmpty(), "Prepare cannot confirm Ready on the shell's behalf")
        fixture.port.preparations.single().ready()
        val events = session.events.take(2).toList()
        assertEquals(listOf(EngineEventBody.Ready, EngineEventBody.Ready), events.map { it.body })
        assertEquals(listOf(0L, 0L), events.map { it.sequence }, "The common gate owns duplicate filtering")
        session.close()
        fixture.host.close()
    }

    @Test
    fun cancellationDuringPrepareAwaitsNativeCloseAndIgnoresTheOldPrepareCompletion() = mainTest {
        val fixture = Fixture()
        fixture.port.completePrepare = false
        fixture.port.completeClose = false
        val opening = async(start = CoroutineStart.UNDISPATCHED) { fixture.open("cancelled-prepare") }
        val old = fixture.port.preparations.single()
        opening.cancel()
        runCurrent()
        assertEquals("cancelled-prepare", fixture.port.closures.single().id)
        assertFalse(opening.isCompleted, "Cancellation must wait for the acquired native handle")
        assertTrue(fixture.host.available.value.isEmpty())
        old.completion.complete(true)
        runCurrent()
        assertFalse(opening.isCompleted)

        fixture.port.closures.single().completion.complete(true)
        runCurrent()
        assertFailsWith<CancellationException> { opening.await() }
        fixture.port.completePrepare = true
        fixture.port.completeClose = true
        val replacement = fixture.open("after-cancellation")
        old.completion.complete(false)
        old.callbacks.failed()
        assertEquals(1, fixture.port.closures.size)
        replacement.close()
        fixture.host.close()
    }

    @Test
    fun failedOrIncompletePrepareReleasesAcquiredResourcesBeforeReturningFailure() = mainTest {
        for (kind in 0..2) {
            val fixture = Fixture()
            fixture.port.completeClose = false
            fixture.port.prepareSuccess = kind != 0
            fixture.port.reportInitialLifecycle = kind != 1
            fixture.port.throwDuringPrepare = kind == 2
            val opening = async(start = CoroutineStart.UNDISPATCHED) { runCatching { fixture.open("bad-prepare-$kind") } }
            assertFalse(opening.isCompleted)
            assertEquals(1, fixture.port.closures.size)
            fixture.port.closures.single().completion.complete(true)
            runCurrent()
            assertIs<IllegalStateException>(opening.await().exceptionOrNull())
            assertTrue(GameplayPresentation.GODOT_2D in fixture.host.available.value)
            fixture.host.close()
        }
    }

    @Test
    fun deferredClosePublishesAvailabilityBeforeTheControllerResumesAPendingModeSwitch() = mainTest {
        val port = ControlledPort().apply { completeClose = false }
        lateinit var controller: PartyDeckController
        val host = IosGodotPresentationHost(
            onLifecycle = { controller.refreshPresentationLifecycle(it) },
            onClosing = {},
            onExit = { controller.requestPresentationExit(it) },
            onUseCompose = { controller.useComposePresentation() },
        )
        host.updateLifecycle(true, false)
        assertNotNull(host.install(port)).setAvailability(twoD = true, threeD = true)
        controller = PartyDeckController(TestServices(), NoTransport, CoroutineScope(backgroundScope.coroutineContext + Dispatchers.Main.immediate), host)
        try {
            controller.startPractice()
            runCurrent()
            assertTrue(controller.selectPresentation(GameplayPresentation.GODOT_2D))
            runCurrent()
            val old = port.preparations.single()
            val sessionId = controller.state.value.session?.sessionId
            assertEquals(PresentationLifecycle.ACTIVE, controller.state.value.presentation.lifecycle)
            assertTrue(controller.selectPresentation(GameplayPresentation.GODOT_3D))
            runCurrent()
            assertEquals(PresentationLifecycle.CLOSING, controller.state.value.presentation.lifecycle)
            assertEquals(1, port.preparations.size)
            assertTrue(host.available.value.isEmpty())

            port.closures.single().completion.complete(true)
            runCurrent()
            assertEquals(2, port.preparations.size, "A resumed close waiter must see a released host")
            val current = port.preparations.last()
            assertNotEquals(old.id, current.id)
            assertEquals(GameplayPresentation.GODOT_3D, controller.state.value.presentation.selected)
            assertEquals(PresentationLifecycle.ACTIVE, controller.state.value.presentation.lifecycle)
            assertEquals(sessionId, controller.state.value.session?.sessionId)

            old.ready()
            old.lifecycle(8, false, true)
            old.callbacks.exitRequested()
            old.callbacks.useCompose()
            old.callbacks.failed()
            port.closures.first().completion.complete(false)
            runCurrent()
            assertEquals(current.id, controller.state.value.presentation.presentationId)
            assertFalse(controller.state.value.leaveConfirmationRequested)
            assertEquals(1, port.closures.size)
            assertTrue(GameplayPresentation.GODOT_3D in host.available.value)
        } finally {
            port.completeClose = true
            port.closures.forEach { it.completion.complete(true) }
            controller.close()
            runCurrent()
            controller.awaitClosed()
            host.close()
        }
    }

    @Test
    fun failedOrTimedOutCloseQuarantinesTheOwnerDespiteLateSuccess() = mainTest {
        for (timeout in listOf(false, true)) {
            val fixture = Fixture()
            fixture.port.completeClose = false
            val session = fixture.open("failed-close-$timeout")
            val factory = assertNotNull(fixture.host.createFactory(GameplayPresentation.GODOT_2D, PresentationPreferences()))
            val closing = async(start = CoroutineStart.UNDISPATCHED) { runCatching { session.close() } }
            assertFalse(closing.isCompleted)
            assertTrue(fixture.host.available.value.isEmpty())
            assertFailsWith<IllegalStateException> { factory.open(launch("too-early")) }
            if (timeout) advanceTimeBy(3_001) else fixture.port.closures.single().completion.complete(false)
            runCurrent()
            assertIs<IllegalStateException>(closing.await().exceptionOrNull())
            fixture.registration.close()
            fixture.port.closures.single().completion.complete(true)
            assertNull(fixture.host.install(ControlledPort()))
            assertTrue(fixture.host.available.value.isEmpty())
            assertEquals(1, fixture.port.preparations.size)
            fixture.host.close()
        }
    }

    @Test
    fun nativeLifecycleIsVisibleBeforeTheCallbackAndObsoleteCommandsCannotConsumeReady() = mainTest {
        val fixture = Fixture()
        val session = fixture.open("lifecycle-order")
        val epoch = 9_007_199_254_740_993L
        fixture.port.preparations.single().lifecycle(epoch, true, false)
        assertEquals(epoch, fixture.observedLifecycles.last().generation)
        assertEquals(epoch, session.lifecycleGeneration)
        session.send(EngineCommand.SetForeground(true), 0)
        assertTrue(fixture.port.deliveries.isEmpty())

        // A conservative shell grant is valid even while native interactivity is true.
        session.send(EngineCommand.SetForeground(false), epoch)
        val first = fixture.port.deliveries.single()
        assertEquals(epoch, first.generation)
        assertTrue(first.confirmReady)
        assertEquals(LastLightWireCodec.encodeCommand("lifecycle-order", EngineCommand.SetForeground(false)), first.document)
        session.send(EngineCommand.SetForeground(true), epoch)
        assertFalse(fixture.port.deliveries.last().confirmReady)
        session.close()
        fixture.host.close()
    }

    @Test
    fun aSupersededStalledDeliveryAndQueuedOldCommandLeaveReadyForTheFreshGeneration() = mainTest {
        val fixture = Fixture()
        fixture.port.completeDelivery = false
        val session = fixture.open("stalled-delivery")
        val first = async(start = CoroutineStart.UNDISPATCHED) { session.send(EngineCommand.SetForeground(true), 0) }
        val queuedOld = async(start = CoroutineStart.UNDISPATCHED) { session.send(EngineCommand.SetForeground(true), 0) }
        val obsolete = fixture.port.deliveries.single()
        fixture.port.preparations.single().lifecycle(1, true, false)
        val fresh = async(start = CoroutineStart.UNDISPATCHED) { session.send(EngineCommand.SetForeground(true), 1) }
        obsolete.completion.complete(false)
        runCurrent()
        first.await()
        queuedOld.await()
        assertEquals(2, fixture.port.deliveries.size)
        val current = fixture.port.deliveries.last()
        assertEquals(1, current.generation)
        assertTrue(current.confirmReady)
        assertFalse(fresh.isCompleted)
        obsolete.completion.complete(true)
        assertFalse(fresh.isCompleted)
        current.completion.complete(true)
        runCurrent()
        fresh.await()
        fixture.port.completeDelivery = true
        session.send(EngineCommand.SetForeground(true), 1)
        assertFalse(fixture.port.deliveries.last().confirmReady)
        assertTrue(fixture.port.closures.isEmpty())
        session.close()
        fixture.host.close()
    }

    @Test
    fun currentDeliveryRejectionEndsThePresentationAndDiscardsBufferedEvents() = mainTest {
        val fixture = Fixture()
        fixture.port.deliverySuccess = false
        val session = fixture.open("rejected-delivery")
        assertFailsWith<IllegalStateException> { session.send(EngineCommand.SetForeground(true), 0) }
        val observed = mutableListOf<EngineEvent>()
        assertFailsWith<IllegalStateException> { session.events.collect { observed += it } }
        assertTrue(observed.isEmpty())
        assertEquals(1, fixture.port.closures.size)
        session.close()
        fixture.host.close()
    }

    @Test
    fun invalidAndOverflowEventsClearTheQueueBeforeACollectorCanObserveReady() = mainTest {
        for (overflow in listOf(false, true)) {
            val fixture = Fixture()
            val session = fixture.open("bad-events-$overflow")
            val native = fixture.port.preparations.single()
            if (overflow) repeat(16) { native.ready(it + 1L) } else native.callbacks.event(" ".repeat(4_097))
            val observed = mutableListOf<EngineEvent>()
            assertFailsWith<IllegalStateException> { session.events.collect { observed += it } }
            assertTrue(observed.isEmpty())
            assertEquals(1, fixture.port.closures.size)
            session.close()
            fixture.host.close()
        }
    }

    @Test
    fun unacknowledgedOrInvalidNativeLifecycleFailsClosed() = mainTest {
        for (kind in 0..3) {
            val fixture = Fixture()
            val session = fixture.open("invalid-lifecycle-$kind")
            val native = fixture.port.preparations.single()
            when (kind) {
                0 -> {
                    fixture.port.acknowledgeLifecycle = false
                    fixture.host.updateLifecycle(true, false)
                }
                1 -> {
                    fixture.port.acceptLifecycle = false
                    fixture.host.updateLifecycle(false, true)
                }
                2 -> native.lifecycle(-1, true, false)
                3 -> native.lifecycle(0, false, true)
            }
            assertEquals(1, fixture.port.closures.size)
            assertFailsWith<IllegalStateException> { session.events.collect {} }
            session.close()
            fixture.host.close()
        }
    }

    @Test
    fun detachedRegistrationAndOldCallbacksCannotAffectAReplacementOwner() = mainTest {
        val fixture = Fixture()
        val first = fixture.open("first-registration")
        fixture.registration.close()
        first.close()
        val replacementPort = ControlledPort()
        val replacementRegistration = assertNotNull(fixture.host.install(replacementPort))
        replacementRegistration.setAvailability(twoD = false, threeD = true)
        val replacement = assertNotNull(fixture.host.createFactory(GameplayPresentation.GODOT_3D, PresentationPreferences()))
            .open(launch("second-registration"))
        val lifecycleCount = fixture.observedLifecycles.size
        fixture.registration.setAvailability(twoD = true, threeD = false)
        fixture.registration.close()
        val old = fixture.port.preparations.single()
        old.lifecycle(99, false, true)
        old.callbacks.exitRequested()
        old.callbacks.useCompose()
        old.callbacks.failed()
        old.ready()
        fixture.port.closures.single().completion.complete(false)
        assertEquals(lifecycleCount, fixture.observedLifecycles.size)
        assertTrue(fixture.exitRequests.isEmpty())
        assertTrue(fixture.composeRequests.isEmpty())
        assertEquals(setOf(GameplayPresentation.GODOT_3D), fixture.host.available.value)
        assertTrue(replacementPort.closures.isEmpty())
        replacement.close()
        fixture.host.close()
    }
}

private fun mainTest(block: suspend TestScope.() -> Unit) = runTest {
    Dispatchers.setMain(UnconfinedTestDispatcher(testScheduler))
    try { block() } finally { Dispatchers.resetMain() }
}

private class Fixture(advertise: Boolean = true) {
    val port = ControlledPort()
    val observedLifecycles = mutableListOf<IosGodotLifecycle>()
    val exitRequests = mutableListOf<String>()
    val composeRequests = mutableListOf<String>()
    val host: IosGodotPresentationHost = IosGodotPresentationHost(
        onLifecycle = { observedLifecycles += assertNotNull(currentLifecycle()) },
        onClosing = {}, onExit = { exitRequests += it }, onUseCompose = { composeRequests += it },
    )
    val registration = assertNotNull(host.install(port))

    init {
        host.updateLifecycle(true, false)
        if (advertise) registration.setAvailability(twoD = true, threeD = true)
    }

    private fun currentLifecycle(): IosGodotLifecycle? = host.currentLifecycle()

    suspend fun open(id: String): LifecycleBoundEmbeddedGameSession = assertIs(
        assertNotNull(host.createFactory(GameplayPresentation.GODOT_2D, PresentationPreferences())).open(launch(id)),
    )
}

/** Intentionally retains old callbacks/completions so tests can exercise obsolete native work. */
private class ControlledPort : IosGodotNativePort {
    val preparations = mutableListOf<Preparation>()
    val deliveries = mutableListOf<Delivery>()
    val closures = mutableListOf<Closure>()
    var completePrepare = true
    var prepareSuccess = true
    var reportInitialLifecycle = true
    var throwDuringPrepare = false
    var completeDelivery = true
    var deliverySuccess = true
    var completeClose = true
    var acceptLifecycle = true
    var acknowledgeLifecycle = true

    override fun prepare(
        presentationId: String, launchDocument: String, isForeground: Boolean, isBackgrounded: Boolean,
        callbacks: IosGodotNativeCallbacks, completion: IosGodotNativeCompletion,
    ) {
        val native = Preparation(presentationId, launchDocument, callbacks, completion, isForeground, isBackgrounded)
        preparations += native
        if (throwDuringPrepare) error("Native prepare failed")
        if (reportInitialLifecycle) native.lifecycle(0, isForeground, isBackgrounded)
        native.ready()
        if (completePrepare) completion.complete(prepareSuccess)
    }

    override fun updateLifecycle(presentationId: String, isForeground: Boolean, isBackgrounded: Boolean): Boolean {
        if (acceptLifecycle && acknowledgeLifecycle) {
            val native = preparations.last { it.id == presentationId }
            val changed = native.foreground != isForeground || native.backgrounded != isBackgrounded
            native.lifecycle(native.generation + if (changed) 1 else 0, isForeground, isBackgrounded)
        }
        return acceptLifecycle
    }

    override fun deliver(
        presentationId: String, commandDocument: String, lifecycleGeneration: Long, confirmReady: Boolean,
        completion: IosGodotNativeCompletion,
    ) {
        deliveries += Delivery(presentationId, commandDocument, lifecycleGeneration, confirmReady, completion)
        if (completeDelivery) completion.complete(deliverySuccess)
    }

    override fun close(presentationId: String, completion: IosGodotNativeCompletion) {
        closures += Closure(presentationId, completion)
        if (completeClose) completion.complete(true)
    }

    class Preparation(
        val id: String, val document: String, val callbacks: IosGodotNativeCallbacks,
        val completion: IosGodotNativeCompletion, var foreground: Boolean, var backgrounded: Boolean,
    ) {
        var generation = 0L
        fun ready(sequence: Long = 0) = callbacks.event(
            LastLightWireCodec.encodeEvent(EngineEvent(id, ENGINE_BRIDGE_PROTOCOL_VERSION, sequence, EngineEventBody.Ready)),
        )
        fun lifecycle(epoch: Long, foreground: Boolean, backgrounded: Boolean) {
            generation = epoch
            this.foreground = foreground
            this.backgrounded = backgrounded
            callbacks.lifecycleChanged(epoch, foreground, backgrounded)
        }
    }

    data class Delivery(
        val id: String, val document: String, val generation: Long, val confirmReady: Boolean,
        val completion: IosGodotNativeCompletion,
    )
    data class Closure(val id: String, val completion: IosGodotNativeCompletion)
}

private fun launch(id: String): EngineLaunch {
    val engine = LastLightEngine(Random(2))
    val state = engine.start(listOf(PlayerIdentity("one", "One"), PlayerIdentity("two", "Two")))
    return EngineLaunch(
        PartyDeckGames.lastLight.id, id,
        LastLightWireCodec.viewPayload(engine.viewFor(state, "one"), PresentationControls(true, false, false, true)), 0,
    )
}

private object NoTransport : LanTransportFactory {
    override fun create(): LanTransport = error("The presentation test uses the real practice authority")
}

private class TestServices : PlatformServices {
    override val settingsStore = object : SettingsStore {
        override suspend fun load() = AppSettings()
        override suspend fun save(settings: AppSettings) = Unit
    }
    override val feedback = object : Feedback {
        override fun play(cue: FeedbackCue, settings: AppSettings) = Unit
        override fun setForeground(value: Boolean) = Unit
        override fun close() = Unit
    }
    override val canScanInvitation = false
    private var token = 0L
    override fun gameRandom(): Random = Random(2)
    override fun secureToken(): String = (++token).toString(16).padStart(64, '0')
    override fun copyText(value: String) = Unit
    override fun shareText(value: String) = Unit
    override fun scanInvitation(onResult: (String?) -> Unit) = Unit
}
