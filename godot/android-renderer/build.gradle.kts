import org.gradle.api.file.DirectoryProperty
import org.gradle.api.file.FileSystemOperations
import org.gradle.api.file.RegularFileProperty
import org.gradle.process.ExecOperations
import javax.inject.Inject

plugins {
    alias(libs.plugins.android.library)
}

android {
    namespace = "dev.partydeck.godot.android"
    compileSdk { version = release(37) { minorApiLevel = 1 } }
    defaultConfig {
        minSdk = 26
        consumerProguardFiles("consumer-rules.pro")
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
    description = "Verify source freshness and stage the real renderer pack for both native hosts."
    rendererPack.set(layout.projectDirectory.file("../qualification/build/renderer/partydeck-last-light.pck"))
    packVerifier.set(layout.projectDirectory.file("../tools/renderer.py"))
    outputDirectory.set(layout.buildDirectory.dir("generated/godotAssets"))
    outputs.upToDateWhen { false }
}

androidComponents.onVariants { variant ->
    variant.sources.assets?.addStaticSourceDirectory(
        layout.projectDirectory.dir("../android-host/src/main/assets").asFile.absolutePath,
    )
    variant.sources.assets?.addGeneratedSourceDirectory(stageGodotAssets, StageGodotAssets::outputDirectory)
}

dependencies {
    implementation(project(":bridge"))
    api("org.godotengine:godot:4.7.2.stable")
    // Godot's public host signatures require Fragment on the consumer compile classpath.
    api("androidx.fragment:fragment-ktx:1.8.6")
    testImplementation(libs.kotlin.test.junit)
}
