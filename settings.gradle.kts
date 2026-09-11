pluginManagement {
    repositories {
        google()
        mavenCentral()
        gradlePluginPortal()
    }
}
dependencyResolutionManagement {
    repositoriesMode.set(RepositoriesMode.FAIL_ON_PROJECT_REPOS)
    repositories {
        google()
        mavenCentral()
    }
}
rootProject.name = "PartyDeck"
include(":core", ":session", ":transport", ":games", ":composeApp", ":androidApp")
include(":bridge", ":androidRenderer")
project(":bridge").projectDir = file("godot/bridge")
project(":androidRenderer").projectDir = file("godot/android-renderer")

// Separate test-only input helper; no dependency from the production application.
include(":android-continuous-input")
project(":android-continuous-input").projectDir = file("tools/android-continuous-input")
