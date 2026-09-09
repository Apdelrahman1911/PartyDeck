plugins {
    alias(libs.plugins.kotlin.multiplatform)
    alias(libs.plugins.android.kmp.library)
}
kotlin {
    android { namespace = "dev.partydeck.games"; compileSdk { version = release(37) { minorApiLevel = 1 } }; minSdk = 26 }
    jvm()
    iosArm64()
    iosSimulatorArm64()
    jvmToolchain(21)
    sourceSets {
        commonMain.dependencies { api(libs.coroutines.core) }
        commonTest.dependencies { implementation(libs.kotlin.test) }
    }
}
