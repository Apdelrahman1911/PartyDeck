import org.jetbrains.compose.desktop.application.dsl.TargetFormat

plugins {
    alias(libs.plugins.kotlin.multiplatform)
    alias(libs.plugins.android.kmp.library)
    alias(libs.plugins.compose.multiplatform)
    alias(libs.plugins.compose.compiler)
}
kotlin {
    android {
        namespace = "dev.partydeck.app.shared"
        compileSdk { version = release(37) { minorApiLevel = 1 } }
        minSdk = 26
        androidResources.enable = true
    }
    jvm()
    listOf(iosArm64(), iosSimulatorArm64()).forEach {
        it.binaries.framework {
            baseName = "PartyDeckKit"
            isStatic = true
            export(project(":transport"))
        }
    }
    jvmToolchain(21)
    sourceSets {
        commonMain.dependencies {
            implementation(project(":core"))
            api(project(":session"))
            api(project(":transport"))
            implementation(project(":games"))
            implementation(project(":bridge"))
            implementation(libs.compose.runtime)
            implementation(libs.compose.foundation)
            implementation(libs.compose.material3)
            api(libs.compose.ui)
            implementation(libs.compose.resources)
            implementation(libs.coroutines.core)
            implementation(libs.lifecycle.runtime.compose)
            implementation(libs.lifecycle.viewmodel.compose)
            implementation(libs.qrose)
        }
        commonTest.dependencies {
            implementation(libs.kotlin.test)
            implementation(libs.coroutines.test)
        }
        androidMain.dependencies { implementation(libs.coroutines.android) }
        jvmMain.dependencies {
            implementation(compose.desktop.currentOs)
            implementation(libs.coroutines.swing)
        }
        jvmTest.dependencies {
            implementation(libs.compose.ui.test.junit4)
            implementation(libs.zxing.core)
        }
    }
}
compose.resources { packageOfResClass = "dev.partydeck.resources" }
compose.desktop {
    application {
        mainClass = "dev.partydeck.app.MainKt"
        nativeDistributions {
            targetFormats(TargetFormat.Deb, TargetFormat.Dmg, TargetFormat.Msi)
            packageName = "PartyDeck"
            packageVersion = "1.0.0"
        }
    }
}
