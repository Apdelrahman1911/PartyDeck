plugins {
    alias(libs.plugins.android.application)
    alias(libs.plugins.compose.compiler)
}
val releaseSigningValues = listOf(
    "PARTYDECK_KEYSTORE_PATH", "PARTYDECK_KEYSTORE_PASSWORD", "PARTYDECK_KEY_ALIAS", "PARTYDECK_KEY_PASSWORD",
).associateWith { providers.environmentVariable(it).orNull }
val hasReleaseSigning = releaseSigningValues.values.any { it != null }
if (hasReleaseSigning) {
    require(releaseSigningValues.values.all { !it.isNullOrBlank() }) {
        "Release signing requires all four PARTYDECK_KEYSTORE_PATH, PARTYDECK_KEYSTORE_PASSWORD, PARTYDECK_KEY_ALIAS and PARTYDECK_KEY_PASSWORD variables."
    }
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
    if (hasReleaseSigning) {
        signingConfigs.create("production") {
            storeFile = file(releaseSigningValues.getValue("PARTYDECK_KEYSTORE_PATH")!!)
            storePassword = releaseSigningValues.getValue("PARTYDECK_KEYSTORE_PASSWORD")
            keyAlias = releaseSigningValues.getValue("PARTYDECK_KEY_ALIAS")
            keyPassword = releaseSigningValues.getValue("PARTYDECK_KEY_PASSWORD")
        }
    }
    buildTypes {
        release {
            if (hasReleaseSigning) signingConfig = signingConfigs.getByName("production")
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
    packaging.resources.excludes += "/META-INF/{AL2.0,LGPL2.1}"
    packaging.resources.merges += "/META-INF/LICENSE.md"
}
dependencies {
    implementation(project(":composeApp"))
    implementation(project(":games"))
    implementation(project(":bridge"))
    implementation(project(":androidRenderer"))
    implementation(libs.coroutines.android)
    implementation(libs.activity.compose)
    implementation(libs.android.lifecycle.viewmodel)
    implementation(libs.android.lifecycle.runtime)
    implementation(libs.camera.camera2)
    implementation(libs.camera.lifecycle)
    implementation(libs.camera.view)
    implementation(libs.zxing.core)
    implementation(libs.android.startup)
    testImplementation(libs.kotlin.test.junit)
}
