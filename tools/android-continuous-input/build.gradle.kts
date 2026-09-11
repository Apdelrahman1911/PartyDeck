plugins {
    alias(libs.plugins.android.application)
}

android {
    namespace = "dev.partydeck.qualification.input"
    compileSdk { version = release(37) { minorApiLevel = 1 } }
    defaultConfig {
        applicationId = "dev.partydeck.qualification.input"
        minSdk = 36
        targetSdk = 36
        versionCode = 1
        versionName = "1"
    }
    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_21
        targetCompatibility = JavaVersion.VERSION_21
    }
}
