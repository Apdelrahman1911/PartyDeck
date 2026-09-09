package dev.partydeck.app

import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.material3.Surface
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.toAwtImage
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.test.ExperimentalTestApi
import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.captureToImage
import androidx.compose.ui.test.onNodeWithTag
import androidx.compose.ui.test.performClick
import androidx.compose.ui.test.performScrollTo
import androidx.compose.ui.test.v2.runSkikoComposeUiTest
import androidx.compose.ui.unit.Density
import dev.partydeck.app.ui.shell.HomeScreen
import dev.partydeck.app.ui.theme.PartyDeckTheme
import dev.partydeck.app.ui.theme.PartyDeckColors
import java.io.File
import javax.imageio.ImageIO
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.time.Duration.Companion.seconds

/** Layout qualification at actual compact viewport sizes, including 200% text. */
@OptIn(ExperimentalTestApi::class)
class HomeLayoutTest {
    @Test
    fun homeAtPhoneSize() = qualifyHome(390, 844, 1f, "home-phone")

    @Test
    fun navigationRemainsReachableAtTwoHundredPercentText() = qualifyHome(320, 740, 2f, "home-large-text")

    @Test
    fun homeAdaptsToLandscape() = qualifyHome(1000, 700, 1f, "home-landscape")

    @Test
    fun navigationRemainsReachableOnShortLandscapePhone() = qualifyHome(844, 390, 1f, "home-phone-landscape")

    private fun qualifyHome(width: Int, height: Int, fontScale: Float, name: String) = runSkikoComposeUiTest(
        size = Size(width.toFloat(), height.toFloat()),
        density = Density(1f, fontScale),
        testTimeout = 45.seconds,
    ) {
        var destination = ""
        setContent {
            PartyDeckTheme {
              Surface(Modifier.fillMaxSize(), color = PartyDeckColors.Ink) {
                HomeScreen(
                    onHost = { destination = "host" },
                    onJoin = { destination = "join" },
                    onPractice = { destination = "practice" },
                    onHowTo = { destination = "how-to" },
                    onSettings = { destination = "settings" },
                    modifier = Modifier.fillMaxSize().testTag("snapshot-root"),
                )
              }
            }
        }
        waitForIdle()
        val output = File("build/ui-snapshots/$name.png").apply { parentFile.mkdirs() }
        ImageIO.write(onNodeWithTag("snapshot-root").captureToImage().toAwtImage(), "png", output)
        for (screen in listOf("host", "join", "practice", "how-to", "settings")) {
            onNodeWithTag("home-$screen").performScrollTo().assertIsDisplayed().performClick()
            assertEquals(screen, destination, "$screen must be reachable at ${width}px and ${fontScale}x text")
        }
    }
}
