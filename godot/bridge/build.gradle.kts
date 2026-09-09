plugins {
    alias(libs.plugins.kotlin.multiplatform)
    alias(libs.plugins.android.kmp.library)
    alias(libs.plugins.kotlin.serialization)
}

kotlin {
    android {
        namespace = "dev.partydeck.godot.bridge"
        compileSdk { version = release(37) { minorApiLevel = 1 } }
        minSdk = 26
    }
    jvm {
        val main = compilations.getByName("main")
        tasks.register<JavaExec>("generateFixtures") {
            group = "verification"
            description = "Generate recipient-safe comparison fixtures with the real Last Light authority."
            classpath(main.output.allOutputs, main.runtimeDependencyFiles)
            mainClass.set("dev.partydeck.godot.bridge.GenerateFixtures")
            args(providers.gradleProperty("partydeck.fixtures.dir")
                .orElse(layout.projectDirectory.dir("fixtures").asFile.absolutePath).get())
        }
    }
    iosArm64()
    iosSimulatorArm64()
    jvmToolchain(21)
    sourceSets {
        commonMain.dependencies {
            api(project(":core"))
            api(project(":games"))
            implementation(libs.serialization.json)
        }
        commonTest.dependencies { implementation(libs.kotlin.test) }
    }
}
