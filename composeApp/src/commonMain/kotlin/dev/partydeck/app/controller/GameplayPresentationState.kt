package dev.partydeck.app.controller

import dev.partydeck.games.EmbeddedGameFactory
import dev.partydeck.games.EmbeddedGameSession
import dev.partydeck.games.EngineCommand
import dev.partydeck.godot.bridge.PresentationPreferences
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow

/** A local display choice. It never changes a table's rules or network protocol. */
enum class GameplayPresentation {
    COMPOSE,
    GODOT_2D,
    GODOT_3D,
}

enum class PresentationLifecycle { COMPOSE, OPENING, ACTIVE, CLOSING }

enum class PresentationFallbackReason {
    UNAVAILABLE,
    INITIALIZATION_FAILED,
    RENDERER_LOST,
    INVALID_EVENT,
    DELIVERY_FAILED,
    PREFERENCES_CHANGED,
}

data class GameplayPresentationState(
    val selected: GameplayPresentation = GameplayPresentation.COMPOSE,
    val available: Set<GameplayPresentation> = setOf(GameplayPresentation.COMPOSE),
    val lifecycle: PresentationLifecycle = PresentationLifecycle.COMPOSE,
    val presentationId: String? = null,
    val fallbackReason: PresentationFallbackReason? = null,
) {
    val showsEmbedded: Boolean
        get() = lifecycle == PresentationLifecycle.OPENING || lifecycle == PresentationLifecycle.ACTIVE
}

/**
 * Supplied by the retained native owner. Advertise only installed, qualified presentations which
 * can open now. Losing availability prevents a future open; it does not end an existing engine.
 *
 * Creating a factory is inert. The factory captures these preferences and owns native attachment
 * only during [EmbeddedGameFactory.open]. Its engine ID must be godot-2d or godot-3d respectively.
 * The shell owns sound/haptics and supplies soundEnabled=false. Native open must release acquired
 * resources on cancellation, and session close must await its deferred native cleanup.
 *
 * The coordinator buffers views until it accepts Ready. Its first session.send is confirmation of
 * that Ready; the native factory may then release its command queue. Bootstrap may run behind an
 * opaque cover before confirmation. Never wait for that confirmation before producing Ready.
 */
interface EmbeddedPresentationHost {
    val available: StateFlow<Set<GameplayPresentation>>

    fun createFactory(
        presentation: GameplayPresentation,
        preferences: PresentationPreferences,
    ): EmbeddedGameFactory?

    companion object {
        val None: EmbeddedPresentationHost = object : EmbeddedPresentationHost {
            override val available = MutableStateFlow(emptySet<GameplayPresentation>()).asStateFlow()
            override fun createFactory(
                presentation: GameplayPresentation,
                preferences: PresentationPreferences,
            ): EmbeddedGameFactory? = null
        }
    }
}

/**
 * Optional native privacy barrier. The shell captures this generation when it queues a command,
 * before any suspension. A cross-process owner discards commands for an older native lifecycle.
 * Ready confirmation remains independent of whether the first queued command is still current.
 * Read and update the generation on the same owner dispatcher as the controller.
 */
interface LifecycleBoundEmbeddedGameSession : EmbeddedGameSession {
    val lifecycleGeneration: Long
    suspend fun send(command: EngineCommand, lifecycleGeneration: Long)
}
