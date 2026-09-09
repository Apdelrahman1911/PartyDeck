plugins {
    alias(libs.plugins.kotlin.multiplatform)
    alias(libs.plugins.android.kmp.library)
    alias(libs.plugins.kotlin.serialization)
}
kotlin {
    android { namespace = "dev.partydeck.transport"; compileSdk { version = release(37) { minorApiLevel = 1 } }; minSdk = 26 }
    jvm()
    iosArm64()
    iosSimulatorArm64()
    jvmToolchain(21)
    applyDefaultHierarchyTemplate()
    sourceSets {
        commonMain.dependencies {
            api(libs.coroutines.core)
            implementation(libs.serialization.json)
        }
        val javaMain by creating {
            dependsOn(commonMain.get())
            dependencies { implementation("org.bouncycastle:bcpkix-jdk18on:1.85") }
        }
        androidMain { dependsOn(javaMain) }
        jvmMain { dependsOn(javaMain) }
        commonTest.dependencies {
            implementation(libs.kotlin.test)
            implementation(libs.coroutines.test)
        }
    }
}
