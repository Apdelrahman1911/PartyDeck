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
