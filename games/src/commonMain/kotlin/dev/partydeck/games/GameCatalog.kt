package dev.partydeck.games

import dev.partydeck.core.LastLightRules
import kotlin.jvm.JvmInline

/** A stable identifier; display names may change or be localized independently. */
@JvmInline
value class GameId(val value: String) {
    init {
        requireStableIdentifier(value)
    }

    override fun toString(): String = value
}

sealed interface GamePresentation {
    data object Compose : GamePresentation

    /** Describes a real game whose platform factory must be installed before launch. */
    data class Embedded(
        val engineId: String,
        val protocolVersion: Int = ENGINE_BRIDGE_PROTOCOL_VERSION,
    ) : GamePresentation {
        init {
            requireStableIdentifier(engineId)
            require(protocolVersion > 0) { "An engine bridge version must be positive." }
        }
    }
}

data class GameDescriptor(
    val id: GameId,
    val title: String,
    val tagline: String,
    val minPlayers: Int,
    val maxPlayers: Int,
    val presentation: GamePresentation,
) {
    init {
        require(title.isNotBlank() && tagline.isNotBlank()) { "A catalog entry needs display copy." }
        require(minPlayers > 0 && maxPlayers >= minPlayers) { "Invalid game player limits." }
    }
}

/** Metadata only: constructing or browsing the catalog never starts a renderer. */
class GameCatalog(games: List<GameDescriptor>) {
    val games: List<GameDescriptor> = games.toList()
    private val byId = this.games.associateBy(GameDescriptor::id)

    init {
        require(byId.size == this.games.size) { "Game identifiers must be unique." }
    }

    fun find(id: GameId): GameDescriptor? = byId[id]

    fun availableGames(engines: EmbeddedGameRegistry = EmbeddedGameRegistry.Empty): List<GameDescriptor> =
        games.filter { engines.resolve(it) !is EngineResolution.Unavailable }
}

/** Only implemented games belong here. No Godot runtime is bundled in this release. */
object PartyDeckGames {
    val lastLight = GameDescriptor(
        id = GameId("last-light"),
        title = "Last Light",
        tagline = "Keep a straight face. Keep your light.",
        minPlayers = LastLightRules.MIN_PLAYERS,
        maxPlayers = LastLightRules.MAX_PLAYERS,
        presentation = GamePresentation.Compose,
    )

    val catalog = GameCatalog(listOf(lastLight))
}

internal fun requireStableIdentifier(value: String) {
    require(value.length in 1..64 && value.all { it in 'a'..'z' || it in '0'..'9' || it == '-' }) {
        "Identifiers use 1–64 lowercase ASCII letters, digits, or hyphens."
    }
}
