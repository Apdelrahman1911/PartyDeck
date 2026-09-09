plugins {
    alias(libs.plugins.kotlin.multiplatform)
    alias(libs.plugins.android.kmp.library)
    alias(libs.plugins.kotlin.serialization)
}
kotlin {
    android {
        namespace = "dev.partydeck.core"
        compileSdk { version = release(37) { minorApiLevel = 1 } }
        minSdk = 26
    }
    jvm()
    iosArm64()
    iosSimulatorArm64()
    jvmToolchain(21)
    sourceSets {
        commonMain.dependencies { implementation(libs.serialization.json) }
        commonTest.dependencies { implementation(libs.kotlin.test) }
    }
}
