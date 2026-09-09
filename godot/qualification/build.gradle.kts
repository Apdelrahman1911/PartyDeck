plugins {
    alias(libs.plugins.kotlin.multiplatform) apply false
    alias(libs.plugins.kotlin.jvm) apply false
    alias(libs.plugins.kotlin.serialization) apply false
    alias(libs.plugins.android.application) apply false
    alias(libs.plugins.android.kmp.library) apply false
}

// Referenced source projects must never overwrite the shipping build's outputs.
subprojects {
    layout.buildDirectory.set(rootProject.layout.buildDirectory.dir("modules/$name"))
}
