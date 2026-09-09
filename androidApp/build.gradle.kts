plugins {
    alias(libs.plugins.android.application)
    alias(libs.plugins.compose.compiler)
}
android {
    namespace = "dev.partydeck.app"
    compileSdk { version = release(37) { minorApiLevel = 1 } }
    defaultConfig {
        applicationId = "dev.partydeck.app"
        minSdk = 26
        targetSdk = 36
        versionCode = 1
        versionName = "1.0.0"
    }
    buildFeatures { compose = true }
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
    packaging.resources.excludes += "/META-INF/{AL2.0,LGPL2.1}"
    packaging.resources.merges += "/META-INF/LICENSE.md"
}
dependencies {
    implementation(project(":composeApp"))
    implementation(libs.activity.compose)
    implementation(libs.android.lifecycle.viewmodel)
    implementation(libs.android.lifecycle.runtime)
}
