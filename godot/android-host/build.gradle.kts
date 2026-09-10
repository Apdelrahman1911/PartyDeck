plugins {
    alias(libs.plugins.android.application)
}

android {
    namespace = "dev.partydeck.godot.compare"
    compileSdk { version = release(37) { minorApiLevel = 1 } }
    defaultConfig {
        applicationId = "dev.partydeck.godot.compare"
        minSdk = 26
        targetSdk = 36
        versionCode = 1
        versionName = "0.1.0"
    }
    buildTypes {
        release {
            isMinifyEnabled = true
            isShrinkResources = true
            proguardFiles(getDefaultProguardFile("proguard-android-optimize.txt"), "proguard-rules.pro")
        }
    }
    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_21
        targetCompatibility = JavaVersion.VERSION_21
    }
    androidResources { noCompress += "pck" }
}

dependencies {
    implementation(project(":bridge"))
    implementation(project(":androidRenderer"))
    testImplementation(libs.kotlin.test.junit)
}
