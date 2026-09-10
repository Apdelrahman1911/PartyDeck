package dev.partydeck.godot.comparison

import java.nio.file.Files
import java.nio.file.Path
import java.time.Instant
import kotlin.io.path.absolutePathString

internal data class ComparisonOptions(
    val repository: Path,
    val godot: Path,
    val project: Path,
    val pack: Path?,
    val output: Path,
    val modes: List<String>,
    val seed: Int?,
    val width: Int,
    val height: Int,
    val textScale: Double,
    val interactive: Boolean,
    val seconds: Int,
    val xvfb: Boolean,
) {
    companion object {
        fun parse(args: Array<String>): ComparisonOptions {
            val values = mutableMapOf<String, String>()
            val flags = mutableSetOf<String>()
            var index = 0
            while (index < args.size) {
                val argument = args[index++]
                if (argument in setOf("--interactive", "--xvfb")) {
                    check(flags.add(argument)) { "Duplicate option: $argument" }
                } else {
                    check(argument in setOf("--repository", "--godot", "--project", "--pack", "--output", "--presentation", "--seed", "--size", "--text-scale", "--seconds")) {
                        "Unknown option: $argument"
                    }
                    check(index < args.size && values.put(argument, args[index++]) == null) { "Missing or duplicate option: $argument" }
                }
            }
            val repository = values["--repository"]?.let(Path::of)?.toAbsolutePath()?.normalize() ?: findRepository()
            val candidates = listOfNotNull(
                values["--godot"]?.let(Path::of),
                System.getenv("PARTYDECK_GODOT_BIN")?.let(Path::of),
                repository.resolve("godot/qualification/build/toolchain/godot"),
                Path.of("/opt/partydeck-godot/godot"),
                Path.of("/opt/partydeck-godot/4.7.2-stable/Godot_v4.7.2-stable_linux.x86_64"),
            )
            val godot = if (values.containsKey("--godot")) candidates.first() else candidates.firstOrNull(Files::isExecutable)
            check(godot != null && Files.isExecutable(godot)) { "Pass --godot with the verified Godot 4.7.2 executable" }
            val presentation = values["--presentation"] ?: "both"
            check(presentation in setOf("2d", "3d", "both")) { "Presentation must be 2d, 3d, or both" }
            val interactive = "--interactive" in flags
            check(!interactive || presentation != "both") { "Interactive play needs --presentation 2d or 3d" }
            val dimensions = (values["--size"] ?: "430x932").split('x').map(String::toInt)
            check(dimensions.size == 2 && dimensions.all { it in 320..2560 }) { "Size must be WIDTHxHEIGHT between 320 and 2560" }
            val scale = values["--text-scale"]?.toDouble() ?: 1.0
            check(scale in 1.0..2.0) { "Text scale must be between 1 and 2" }
            val seconds = values["--seconds"]?.toInt() ?: if (interactive) 1800 else 240
            check(seconds in 10..3600) { "Lifetime must be between 10 and 3600 seconds" }
            val runName = Instant.now().toString().replace(':', '-').replace('.', '-')
            val output = (values["--output"]?.let(Path::of) ?: repository.resolve("godot/qualification/build/comparison/$runName"))
                .toAbsolutePath().normalize()
            check(!Files.exists(output.resolve("report.json"))) { "Choose a new output directory to preserve earlier comparison evidence" }
            return ComparisonOptions(
                repository, godot.toAbsolutePath().normalize(),
                (values["--project"]?.let(Path::of) ?: repository.resolve("godot/renderer")).toAbsolutePath().normalize(),
                values["--pack"]?.let(Path::of)?.toAbsolutePath()?.normalize(),
                output, if (presentation == "both") listOf("2d", "3d") else listOf(presentation),
                values["--seed"]?.toInt() ?: if (interactive) null else 2,
                dimensions[0], dimensions[1], scale, interactive, seconds,
                "--xvfb" in flags || System.getenv("DISPLAY").isNullOrEmpty(),
            )
        }

        private fun findRepository(): Path {
            var path: Path? = Path.of("").toAbsolutePath()
            while (path != null) {
                if (Files.isRegularFile(path.resolve("plan.md")) && Files.isDirectory(path.resolve("godot/comparison"))) return path
                path = path.parent
            }
            error("Pass --repository with the PartyDeck checkout path")
        }
    }
}

internal fun Path.argument(): String = absolutePathString()

internal const val USAGE = """
partydeck-godot-compare [--presentation both|2d|3d] [--interactive]
  --godot PATH          Verified Godot 4.7.2 executable (or PARTYDECK_GODOT_BIN)
  --repository PATH     PartyDeck checkout; defaults to an ancestor of cwd
  --project PATH        Godot project; defaults to godot/renderer
  --pack PATH           Use an exported PCK instead of the source project
  --output PATH         New directory for report, captures and engine logs
  --seed INT            Reproducible comparison seed; automated default 2
  --size WIDTHxHEIGHT   Default 430x932; allowed range 320..2560
  --text-scale NUMBER   1..2; default 1
  --seconds INT         Per-renderer limit; default 240, or 1800 for interactive
  --xvfb                Launch through xvfb-run (automatic without DISPLAY)

Automated mode injects real Godot Button input and verifies shared authority traces.
Interactive mode uses fresh secure randomness unless --seed explicitly selects a fixture.
"""
