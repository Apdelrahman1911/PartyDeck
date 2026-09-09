package dev.partydeck.games

import dev.partydeck.core.LastLightRules
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertIs
import kotlin.test.assertSame
import kotlin.test.assertTrue

class GameCatalogTest {
    @Test
    fun shippingCatalogContainsOnlyTheImplementedComposeGame() {
        val game = PartyDeckGames.catalog.availableGames().single()
        assertEquals(GameId("last-light"), game.id)
        assertSame(PartyDeckGames.lastLight, game)
        assertEquals(LastLightRules.MIN_PLAYERS, game.minPlayers)
        assertEquals(LastLightRules.MAX_PLAYERS, game.maxPlayers)
        assertIs<GamePresentation.Compose>(game.presentation)
        assertIs<EngineResolution.NotRequired>(EmbeddedGameRegistry.Empty.resolve(game))
    }

    @Test
    fun duplicateGameIdsAreRejectedAndTheCatalogCopiesItsInput() {
        val entries = mutableListOf(PartyDeckGames.lastLight)
        val catalog = GameCatalog(entries)
        entries.clear()
        assertEquals(listOf(PartyDeckGames.lastLight), catalog.games)
        assertFailsWith<IllegalArgumentException> {
            GameCatalog(listOf(PartyDeckGames.lastLight, PartyDeckGames.lastLight.copy(title = "Duplicate")))
        }
    }

    @Test
    fun anEngineGameIsUnavailableUntilACompatibleFactoryIsInstalled() {
        val game = embeddedGame()
        val catalog = GameCatalog(listOf(PartyDeckGames.lastLight, game))
        assertEquals(listOf(PartyDeckGames.lastLight), catalog.availableGames())
        assertEquals(
            EngineResolution.Unavailable(EngineUnavailableReason.NOT_INSTALLED),
            EmbeddedGameRegistry.Empty.resolve(game),
        )

        val wrongVersion = TestFactory(protocolVersion = 2, supportedGames = setOf(game.id))
        assertEquals(
            EngineResolution.Unavailable(EngineUnavailableReason.UNSUPPORTED_PROTOCOL),
            EmbeddedGameRegistry(listOf(wrongVersion)).resolve(game),
        )
        assertEquals(
            EngineResolution.Unavailable(EngineUnavailableReason.UNSUPPORTED_PROTOCOL),
            EmbeddedGameRegistry(listOf(wrongVersion)).resolve(
                game.copy(presentation = GamePresentation.Embedded("test-engine", protocolVersion = 2)),
            ),
        )
        assertEquals(
            EngineResolution.Unavailable(EngineUnavailableReason.UNSUPPORTED_GAME),
            EmbeddedGameRegistry(listOf(TestFactory())).resolve(game),
        )

        val factory = TestFactory(supportedGames = setOf(game.id))
        val engines = EmbeddedGameRegistry(listOf(factory))
        assertSame(factory, assertIs<EngineResolution.Available>(engines.resolve(game)).factory)
        assertEquals(2, catalog.availableGames(engines).size)
        assertTrue(!factory.opened, "Browsing the catalog must not initialize an engine.")
        assertFailsWith<IllegalArgumentException> { EmbeddedGameRegistry(listOf(factory, factory)) }
    }

    private fun embeddedGame() = GameDescriptor(
        id = GameId("test-engine-game"),
        title = "Test fixture",
        tagline = "Only used by capability tests.",
        minPlayers = 2,
        maxPlayers = 4,
        presentation = GamePresentation.Embedded("test-engine"),
    )

    private class TestFactory(
        override val protocolVersion: Int = ENGINE_BRIDGE_PROTOCOL_VERSION,
        override val supportedGames: Set<GameId> = emptySet(),
    ) : EmbeddedGameFactory {
        override val engineId = "test-engine"
        var opened = false

        override suspend fun open(launch: EngineLaunch): EmbeddedGameSession {
            opened = true
            error("Capability lookup must not start a renderer.")
        }
    }
}
