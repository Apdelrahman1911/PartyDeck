package dev.partydeck.app

import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.material3.Surface
import androidx.compose.runtime.getValue
import androidx.compose.runtime.key
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.test.ExperimentalTestApi
import androidx.compose.ui.test.isRoot
import androidx.compose.ui.test.onAllNodesWithTag
import androidx.compose.ui.test.onNodeWithTag
import androidx.compose.ui.test.performClick
import androidx.compose.ui.test.performScrollTo
import androidx.compose.ui.test.v2.runSkikoComposeUiTest
import dev.partydeck.app.controller.GameplayPresentation
import dev.partydeck.app.controller.GameplayPresentationState
import dev.partydeck.app.controller.PresentationSelection
import dev.partydeck.app.ui.shell.GameplayPresentationPicker
import dev.partydeck.app.ui.theme.PartyDeckTheme
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.time.Duration.Companion.seconds

/** Tests the real Skiko popup lifetime at the selection boundary; it does not instantiate Godot. */
@OptIn(ExperimentalTestApi::class)
class PresentationPickerDisposalTest {
    @Test
    fun selectionCommitSeesThePickerLayerAlreadyRemoved() = runSkikoComposeUiTest(
        size = Size(402f, 874f), testTimeout = 45.seconds,
    ) {
        fun readTreeWithoutAdvancing() = runOnUiThread {
            runWithoutImplicitWait {
                PickerTree(
                    roots = onAllNodes(isRoot(), useUnmergedTree = true).fetchSemanticsNodes().size,
                    pickers = onAllNodesWithTag("presentation-options", useUnmergedTree = true)
                        .fetchSemanticsNodes().size,
                )
            }
        }
        val atClick = mutableListOf<PickerTree>()
        val atCommit = mutableListOf<PickerTree>()
        setContent {
            PartyDeckTheme(reduceMotion = false) {
                Surface(Modifier.fillMaxSize()) {
                    GameplayPresentationPicker(
                        state = GameplayPresentationState(available = GameplayPresentation.entries.toSet()),
                        onPrepareSelection = {
                            atClick += readTreeWithoutAdvancing()
                            PresentationSelection(
                                onCommit = { atCommit += readTreeWithoutAdvancing() },
                                onCancel = {},
                            )
                        },
                    )
                }
            }
        }
        waitForIdle()
        val baseline = readTreeWithoutAdvancing()
        assertEquals(PickerTree(roots = 1, pickers = 0), baseline)
        for (mode in listOf("godot_2d", "godot_3d")) {
            onNodeWithTag("presentation-picker").performClick()
            onNodeWithTag("presentation-choice-$mode").performScrollTo().performClick()
            waitForIdle()
            assertEquals(PickerTree(roots = baseline.roots + 1, pickers = 1), atClick.last())
            // The callback sampled without an implicit idle wait. A retained animated layer still
            // adds a root even if its replacement content no longer has the picker test tag.
            assertEquals(baseline, atCommit.last())
        }
        assertEquals(2, atClick.size)
        assertEquals(2, atCommit.size)
    }

    @Test
    fun pickerRemovalAndOwnerReplacementCancelBeforeCommit() {
        for (removePicker in listOf(false, true)) {
            runSkikoComposeUiTest(size = Size(402f, 874f), testTimeout = 45.seconds) {
                var visible by mutableStateOf(true)
                var owner by mutableStateOf(0)
                var commits = 0
                var cancellations = 0
                setContent {
                    PartyDeckTheme(reduceMotion = false) {
                        Surface(Modifier.fillMaxSize()) {
                            if (visible) key(owner) {
                                GameplayPresentationPicker(
                                    state = GameplayPresentationState(available = GameplayPresentation.entries.toSet()),
                                    onPrepareSelection = {
                                        if (removePicker) visible = false else owner++
                                        PresentationSelection(
                                            onCommit = { commits++ },
                                            onCancel = { cancellations++ },
                                        )
                                    },
                                )
                            }
                        }
                    }
                }
                onNodeWithTag("presentation-picker").performClick()
                onNodeWithTag("presentation-choice-godot_2d").performScrollTo().performClick()
                waitForIdle()
                assertEquals(0, commits)
                assertEquals(1, cancellations)
                onNodeWithTag("presentation-options").assertDoesNotExist()
                runOnUiThread { visible = true }
                waitForIdle()
                assertEquals(0, commits, "A replacement must not revive the removed picker's choice")
            }
        }
    }
}

private data class PickerTree(val roots: Int, val pickers: Int)
