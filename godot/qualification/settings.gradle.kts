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
    versionCatalogs {
        create("libs") {
            from(files("../../gradle/libs.versions.toml"))
            plugin("kotlin-jvm", "org.jetbrains.kotlin.jvm").versionRef("kotlin")
        }
    }
}

rootProject.name = "PartyDeckGodotQualification"

// Share the production domain and event contracts, without changing that build.
include(":core", ":games", ":bridge", ":androidHost", ":comparison")
project(":core").projectDir = file("../../core")
project(":games").projectDir = file("../../games")
project(":bridge").projectDir = file("../bridge")
project(":androidHost").projectDir = file("../android-host")
project(":comparison").projectDir = file("../comparison")
