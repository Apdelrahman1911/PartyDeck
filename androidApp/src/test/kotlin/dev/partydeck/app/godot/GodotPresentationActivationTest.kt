package dev.partydeck.app.godot

import dev.partydeck.app.controller.GameplayPresentation
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFalse
import kotlin.test.assertTrue

class GodotPresentationActivationTest {
    @Test
    fun qualificationExposesOnlyThePackagedSubset() {
        assertEquals(setOf(GameplayPresentation.GODOT_2D), GodotPresentationActivation.fromPackagedMetadata("qualification", "2d"))
        assertEquals(setOf(GameplayPresentation.GODOT_3D), GodotPresentationActivation.fromPackagedMetadata("qualification", "3d"))
        assertEquals(
            setOf(GameplayPresentation.GODOT_2D, GameplayPresentation.GODOT_3D),
            GodotPresentationActivation.fromPackagedMetadata("qualification", "2d,3d"),
        )
    }

    @Test
    fun missingOrEmptyMetadataKeepsChoicesClosed() {
        for (profile in listOf(null, "shipping", "qualification")) {
            for (modes in listOf(null, "")) {
                assertEquals(emptySet(), GodotPresentationActivation.fromPackagedMetadata(profile, modes))
            }
        }
    }

    @Test
    fun unknownProfilesCannotEnableKnownModes() {
        for (profile in listOf("", "debug", "release", "Qualification", "qualification ", "true")) {
            assertEquals(emptySet(), GodotPresentationActivation.fromPackagedMetadata(profile, "2d,3d"), profile)
        }
    }

    @Test
    fun aMalformedTokenClosesTheWholeList() {
        for (modes in listOf("2d,unknown", "2d,2d", "3d,2d", "2d,", ",2d", "2d,,3d", ",", " 2d", "2d, 3d", "2D", "compose")) {
            for (profile in listOf("shipping", "qualification")) {
                assertEquals(emptySet(), GodotPresentationActivation.fromPackagedMetadata(profile, modes), "$profile: $modes")
            }
        }
    }

    @Test
    fun futureShippingExposureUsesTheSamePackagedList() {
        // The checked-in Gradle shipping list is empty; acceptance can later change only that list.
        assertEquals(setOf(GameplayPresentation.GODOT_3D), GodotPresentationActivation.fromPackagedMetadata("shipping", "3d"))
    }

    @Test
    fun observationRequiresQualificationAndTheAdmittedMode() {
        assertTrue(GodotPresentationActivation.qualificationObservationFromPackagedMetadata("qualification", "2d", "2d"))
        assertTrue(GodotPresentationActivation.qualificationObservationFromPackagedMetadata("qualification", "2d,3d", "3d"))
        for (mode in listOf("2d", "3d")) {
            for (profile in listOf(null, "shipping", "Qualification", "debug", "qualification ")) {
                assertFalse(GodotPresentationActivation.qualificationObservationFromPackagedMetadata(profile, "2d,3d", mode))
            }
        }
        for (modes in listOf(null, "", "3d", "2d,unknown", "2d,2d", "3d,2d", "2d,", "2d, 3d")) {
            assertFalse(GodotPresentationActivation.qualificationObservationFromPackagedMetadata("qualification", modes, "2d"))
        }
        for (mode in listOf("", "2D", "3d ", "compose")) {
            assertFalse(GodotPresentationActivation.qualificationObservationFromPackagedMetadata("qualification", "2d,3d", mode))
        }
    }
}
