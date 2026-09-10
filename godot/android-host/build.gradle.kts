import org.gradle.api.file.DirectoryProperty
import org.gradle.api.file.FileSystemOperations
import org.gradle.api.file.RegularFileProperty
import org.gradle.process.ExecOperations
import javax.inject.Inject

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

abstract class StageGodotAssets : DefaultTask() {
    @get:InputFile
    @get:PathSensitive(PathSensitivity.NONE)
    abstract val rendererPack: RegularFileProperty

    @get:InputFile
    @get:PathSensitive(PathSensitivity.NONE)
    abstract val packVerifier: RegularFileProperty

    @get:OutputDirectory
    abstract val outputDirectory: DirectoryProperty

    @get:Inject
    abstract val execOperations: ExecOperations

    @get:Inject
    abstract val fileSystemOperations: FileSystemOperations

    @TaskAction
    fun stage() {
        execOperations.exec {
            commandLine("python3", packVerifier.get().asFile.absolutePath,
                "check-pack", "--pack", rendererPack.get().asFile.absolutePath)
        }.assertNormalExitValue()
        fileSystemOperations.sync {
            from(rendererPack)
            into(outputDirectory)
        }
    }
}

val stageGodotAssets = tasks.register<StageGodotAssets>("stageGodotAssets") {
    group = "godot"
    description = "Verify source freshness and stage the real renderer PCK as the only generated Android asset."
    rendererPack.set(rootProject.layout.buildDirectory.file("renderer/partydeck-last-light.pck"))
    packVerifier.set(rootProject.layout.projectDirectory.file("../tools/renderer.py"))
    outputDirectory.set(layout.buildDirectory.dir("generated/godotAssets"))
    // The verifier checks the receipt against current renderer sources every time.
    outputs.upToDateWhen { false }
}

androidComponents.onVariants { variant ->
    variant.sources.assets?.addGeneratedSourceDirectory(stageGodotAssets, StageGodotAssets::outputDirectory)
}

dependencies {
    implementation(project(":bridge"))
    // Official Maven Central metadata: 4.7.2.stable, not the release-tag spelling.
    implementation("org.godotengine:godot:4.7.2.stable")
    // Godot's POM declares Fragment as runtime-only; its host API uses these types.
    implementation("androidx.fragment:fragment-ktx:1.8.6")
    testImplementation(libs.kotlin.test.junit)
}
