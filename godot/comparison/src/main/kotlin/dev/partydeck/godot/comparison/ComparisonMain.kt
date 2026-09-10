package dev.partydeck.godot.comparison

import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.put
import java.nio.file.Files
import java.nio.file.Path
import java.security.MessageDigest
import java.time.Instant
import java.util.concurrent.TimeUnit
import kotlin.io.path.extension
import kotlin.system.exitProcess

fun main(args: Array<String>) {
    if (args.any { it == "--help" || it == "-h" }) {
        println(USAGE.trimIndent())
        return
    }
    var output: Path? = null
    val results = mutableListOf<JsonObject>()
    var provenance = JsonObject(emptyMap())
    try {
        val options = ComparisonOptions.parse(args)
        output = Files.createDirectories(options.output)
        val sourceFingerprint = sourceFingerprint(options.repository)
        val packFingerprint = options.pack?.let { sha256(Files.readAllBytes(it)) }
        provenance = buildJsonObject {
            put("schemaVersion", 1)
            put("runStartedUtc", Instant.now().toString())
            put("sourceCommit", git(options.repository, "rev-parse", "HEAD"))
            put("workingTreeDirty", git(options.repository, "status", "--porcelain", "--", "godot", "core", "games").isNotBlank())
            put("sourceFingerprintSha256", sourceFingerprint)
            put("rendererArtifact", buildJsonObject {
                put("kind", if (options.pack == null) "source-project" else "pck")
                put("path", (options.pack ?: options.project).toString())
                if (packFingerprint != null) put("sha256", packFingerprint)
            })
            put("scenarioManifest", "godot/comparison/scenarios.json")
            put("authority", "Existing KMP LastLightEngine through QualificationAuthorityDriver and LastLightBridgeAdapter")
            put("qualificationScope", "Desktop renderer comparison; no multiplayer/native-device claim")
        }
        for (mode in options.modes) {
            println("Starting $mode with ${if (options.seed == null) "fresh secure randomness" else "comparison seed ${options.seed}"}")
            val renderer = RendererProcess.start(options, mode)
            val scenarioResult = renderer.use { ComparisonScenario(options, it, mode, provenance).run() }
            val result = buildJsonObject {
                scenarioResult.forEach { (key, value) -> put(key, value) }
                put("rendererExitCode", checkNotNull(renderer.exitCode))
            }
            results += result
            Files.writeString(output.resolve(mode).resolve("result.json"), result.toString())
        }
        check(sourceFingerprint(options.repository) == sourceFingerprint) { "Comparison sources changed during the run; retained captures need rerunning against a stable source snapshot" }
        check(options.pack == null || sha256(Files.readAllBytes(options.pack)) == packFingerprint) { "Renderer pack changed during the run; retained captures need rerunning against a stable artifact" }
        if (!options.interactive && results.size == 2) {
            check(results[0]["authorityTraceSha256"] == results[1]["authorityTraceSha256"]) { "2D and 3D produced different authoritative game progressions" }
        }
        val report = buildJsonObject {
            provenance.forEach { (key, value) -> put(key, value) }
            put("status", "passed")
            put("completedUtc", Instant.now().toString())
            put("sameAuthorityTrace", !options.interactive && results.size == 2)
            put("results", JsonArray(results))
        }
        Files.writeString(output.resolve("report.json"), report.toString())
        println("Comparison passed. Report: ${output.resolve("report.json")}")
    } catch (failure: Exception) {
        if (output != null) {
            val report = buildJsonObject {
                provenance.forEach { (key, value) -> put(key, value) }
                put("status", "failed")
                put("completedUtc", Instant.now().toString())
                put("error", failure.message ?: failure.javaClass.simpleName)
                put("results", JsonArray(results))
            }
            Files.writeString(output.resolve("report.json"), report.toString())
        }
        System.err.println("Comparison failed: ${failure.message}")
        exitProcess(1)
    }
}

internal fun sha256(bytes: ByteArray): String = MessageDigest.getInstance("SHA-256").digest(bytes).joinToString("") { "%02x".format(it) }

private fun sourceFingerprint(repository: Path): String {
    val roots = listOf("core/src", "games/src", "godot/bridge/src", "godot/renderer", "godot/comparison")
    val paths = roots.flatMap { relative ->
        val path = repository.resolve(relative)
        if (!Files.exists(path)) emptyList() else Files.walk(path).use { files ->
            files.filter { Files.isRegularFile(it) && it.extension in setOf("kt", "kts", "gd", "tscn", "godot", "cfg", "gdshader", "json", "png", "svg", "ttf", "wav") }
                .filter { ".godot" !in repository.relativize(it).map(Path::toString) && "build" !in repository.relativize(it).map(Path::toString) }
                .toList()
        }
    }.sortedBy { repository.relativize(it).toString() }
    val digest = MessageDigest.getInstance("SHA-256")
    for (path in paths) {
        digest.update(repository.relativize(path).toString().toByteArray(Charsets.UTF_8))
        digest.update(0)
        Files.newInputStream(path).use { input ->
            val buffer = ByteArray(16_384)
            while (true) {
                val count = input.read(buffer)
                if (count < 0) break
                digest.update(buffer, 0, count)
            }
        }
    }
    return digest.digest().joinToString("") { "%02x".format(it) }
}

private fun git(repository: Path, vararg args: String): String {
    val process = ProcessBuilder(listOf("git", "-C", repository.toString()) + args).redirectErrorStream(true).start()
    val output = process.inputStream.bufferedReader().readText()
    check(process.waitFor(5, TimeUnit.SECONDS) && process.exitValue() == 0) { "Could not read Git provenance" }
    return output.trim()
}
