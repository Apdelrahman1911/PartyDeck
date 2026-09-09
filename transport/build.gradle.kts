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
        val javaMain = create("javaMain") {
            dependsOn(commonMain.get())
            dependencies {
                implementation("org.bouncycastle:bcpkix-jdk18on:1.85")
                implementation("org.bouncycastle:bcprov-jdk18on:1.85.2")
            }
        }
        androidMain { dependsOn(javaMain) }
        jvmMain { dependsOn(javaMain) }
        commonTest.dependencies {
            implementation(libs.kotlin.test)
            implementation(libs.coroutines.test)
        }
    }
}

// The macOS CI shell starts the real JVM peer alongside app-hosted iOS XCTest.
// Keep this helper on the test classpath and out of every shipping application.
val interopTestClasspath = tasks.named<Test>("jvmTest").map { it.classpath }
val interopClasspathFile = layout.buildDirectory.file("interop/jvm-test-classpath.txt")
tasks.register("exportInteropFixtureClasspath") {
    group = "verification"
    description = "Compile the Java/Swift transport fixture and export its JVM test classpath."
    dependsOn("jvmTestClasses")
    doLast {
        val destination = interopClasspathFile.get().asFile
        destination.parentFile.mkdirs()
        destination.writeText(interopTestClasspath.get().asPath)
    }
}
