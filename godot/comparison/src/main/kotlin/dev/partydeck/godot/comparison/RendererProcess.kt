package dev.partydeck.godot.comparison

import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonElement
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.boolean
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import kotlinx.serialization.json.put
import java.net.InetSocketAddress
import java.nio.ByteBuffer
import java.nio.ByteOrder
import java.nio.channels.ServerSocketChannel
import java.nio.channels.SocketChannel
import java.nio.file.Files
import java.nio.file.Path
import java.security.SecureRandom
import java.time.Duration
import java.util.concurrent.TimeUnit

/** Only this test process listens, on an ephemeral IPv4 loopback port. No game LAN protocol. */
internal class RendererProcess private constructor(
    private val process: Process,
    private val channel: SocketChannel,
    val output: Path,
    private val lifetimeDeadline: Long,
    var godotVersion: String,
) : AutoCloseable {
    private val receiveBuffer = ByteBuffer.allocate(MAX_FRAME_BYTES + 4).order(ByteOrder.BIG_ENDIAN)
    private val events = ArrayDeque<String>()
    private var requestId = 0
    private var closed = false
    var requestCount = 0
        private set
    var exitCode: Int? = null
        private set

    fun request(operation: String, parameters: JsonObject = JsonObject(emptyMap())): JsonElement {
        check(!closed && requestId < 100_000) { "Comparison request limit exceeded" }
        val id = (++requestId).toString()
        val request = buildJsonObject {
            put("kind", "request")
            put("id", id)
            put("operation", operation)
            parameters.forEach { (key, value) -> put(key, value) }
        }
        send(request)
        requestCount++
        val deadline = minOf(lifetimeDeadline, System.nanoTime() + Duration.ofSeconds(12).toNanos())
        while (System.nanoTime() < deadline) {
            val message = receive(deadline) ?: continue
            when (message.text("kind")) {
                "event" -> queueEvent(message.text("document"))
                "reply" -> {
                    check(message.text("id") == id) { "Unexpected comparison reply identity" }
                    if (!message.getValue("ok").jsonPrimitive.boolean) {
                        throw ProbeRejected(operation, message.getValue("result"))
                    }
                    return message.getValue("result")
                }
                else -> error("Unexpected comparison message")
            }
        }
        error("Renderer did not complete $operation within its deadline; see ${output.resolve("godot.log")}")
    }

    fun wire(document: String): JsonObject {
        check(document.toByteArray(Charsets.UTF_8).size <= 65_536) { "Bridge document exceeded its contract" }
        return request("document", buildJsonObject { put("document", document) }).jsonObject
    }

    fun state(): JsonObject = request("state").jsonObject

    fun click(group: String, cardIndex: Int? = null): JsonObject = request("click", buildJsonObject {
        put("group", group)
        if (cardIndex != null) put("cardIndex", cardIndex)
    }).jsonObject

    fun nextEvent(waitMillis: Long = 0): String? {
        if (events.isNotEmpty()) return events.removeFirst()
        val deadline = minOf(lifetimeDeadline, System.nanoTime() + Duration.ofMillis(waitMillis).toNanos())
        do {
            val message = receive(deadline) ?: return null
            check(message.text("kind") == "event") { "Unexpected unsolicited comparison reply" }
            queueEvent(message.text("document"))
        } while (events.isEmpty() && System.nanoTime() < deadline)
        return if (events.isEmpty()) null else events.removeFirst()
    }

    fun isAlive(): Boolean = !closed && process.isAlive && System.nanoTime() < lifetimeDeadline

    private fun queueEvent(document: String) {
        check(events.size < 16 && document.toByteArray(Charsets.UTF_8).size <= 4096) { "Renderer event queue exceeded its bound" }
        events.addLast(document)
    }

    private fun send(message: JsonObject) {
        val bytes = message.toString().toByteArray(Charsets.UTF_8)
        check(bytes.size in 1..MAX_FRAME_BYTES) { "Comparison message exceeded its bound" }
        val packet = ByteBuffer.allocate(bytes.size + 4).order(ByteOrder.BIG_ENDIAN).putInt(bytes.size).put(bytes).flip()
        val deadline = minOf(lifetimeDeadline, System.nanoTime() + Duration.ofSeconds(5).toNanos())
        while (packet.hasRemaining()) {
            check(process.isAlive && System.nanoTime() < deadline) { "Renderer write deadline expired" }
            if (channel.write(packet) == 0) Thread.sleep(2)
        }
    }

    private fun receive(deadline: Long): JsonObject? {
        while (true) {
            receiveBuffer.flip()
            if (receiveBuffer.remaining() >= 4) {
                receiveBuffer.mark()
                val length = receiveBuffer.int
                check(length in 1..MAX_FRAME_BYTES) { "Invalid comparison frame length" }
                if (receiveBuffer.remaining() >= length) {
                    val bytes = ByteArray(length)
                    receiveBuffer.get(bytes)
                    receiveBuffer.compact()
                    val text = bytes.toString(Charsets.UTF_8)
                    check(text.toByteArray(Charsets.UTF_8).contentEquals(bytes)) { "Invalid comparison UTF-8" }
                    return Json.parseToJsonElement(text).jsonObject
                }
                receiveBuffer.reset()
            }
            receiveBuffer.compact()
            check(receiveBuffer.hasRemaining()) { "Comparison receive buffer exceeded its bound" }
            val count = channel.read(receiveBuffer)
            check(count >= 0) { "Renderer closed the loopback channel; see ${output.resolve("godot.log")}" }
            if (count == 0) {
                if (System.nanoTime() >= deadline) return null
                check(process.isAlive) { "Godot exited; see ${output.resolve("godot.log")}" }
                Thread.sleep(5)
            }
        }
    }

    override fun close() {
        if (closed) return
        var failure: Exception? = null
        try {
            if (process.isAlive) {
                check(channel.isOpen && System.nanoTime() < lifetimeDeadline) { "Renderer lifetime ended before graceful close" }
                request("quit")
                check(process.waitFor(3, TimeUnit.SECONDS)) { "Godot did not finish its graceful quit" }
            }
            check(process.exitValue() == 0) { "Godot exited with code ${process.exitValue()}" }
            val engineErrors = Files.lines(output.resolve("godot.log")).use { lines ->
                lines.anyMatch { it.trimStart().startsWith("ERROR:") || it.trimStart().startsWith("SCRIPT ERROR:") }
            }
            check(!engineErrors) { "Godot reported an engine or script error" }
        } catch (error: Exception) {
            failure = error
        } finally {
            closed = true
            channel.close()
            terminate(process)
            if (!process.isAlive) exitCode = process.exitValue()
        }
        if (failure != null) throw IllegalStateException("Renderer did not close cleanly; see ${output.resolve("godot.log")}", failure)
    }

    companion object {
        const val MAX_FRAME_BYTES = 131_072

        fun start(options: ComparisonOptions, mode: String): RendererProcess {
            val output = Files.createDirectories(options.output.resolve(mode))
            val token = ByteArray(32).also(SecureRandom()::nextBytes).joinToString("") { "%02x".format(it) }
            val processDeadline = System.nanoTime() + Duration.ofSeconds(options.seconds.toLong()).toNanos()
            ServerSocketChannel.open().use { server ->
                server.bind(InetSocketAddress("127.0.0.1", 0), 1)
                server.configureBlocking(false)
                val port = (server.localAddress as InetSocketAddress).port
                val arguments = mutableListOf<String>()
                if (options.xvfb) arguments += listOf("xvfb-run", "-a", "-s", "-screen 0 ${maxOf(options.width, 1280)}x${maxOf(options.height, 1024)}x24")
                arguments += options.godot.argument()
                if (options.pack == null) arguments += listOf("--path", options.project.argument())
                else arguments += listOf("--main-pack", options.pack.argument())
                arguments += listOf(
                    "--script", options.repository.resolve("godot/comparison/renderer_probe.gd").argument(),
                    "--rendering-method", "gl_compatibility", "--display-driver", "x11", "--audio-driver", "Dummy",
                    "--resolution", "${options.width}x${options.height}", "--position", "0,0",
                    "--", "--manual-bridge", "--presentation=$mode", "--comparison-port=$port",
                    "--comparison-token=$token", "--comparison-output=${output.argument()}", "--comparison-seconds=${options.seconds}",
                )
                val process = ProcessBuilder(arguments).directory(options.repository.toFile())
                    .redirectErrorStream(true).redirectOutput(output.resolve("godot.log").toFile()).start()
                var socket: SocketChannel? = null
                try {
                    val acceptDeadline = minOf(processDeadline, System.nanoTime() + Duration.ofSeconds(30).toNanos())
                    while (socket == null && process.isAlive && System.nanoTime() < acceptDeadline) {
                        socket = server.accept()
                        if (socket == null) Thread.sleep(10)
                    }
                    check(socket != null) { "Godot did not connect within 30 seconds; see ${output.resolve("godot.log")}" }
                    check((socket.remoteAddress as InetSocketAddress).address.hostAddress == "127.0.0.1") { "Non-loopback comparison peer" }
                    socket.configureBlocking(false)
                    socket.socket().tcpNoDelay = true
                    val pending = RendererProcess(process, socket, output, processDeadline, "")
                    val hello = pending.receive(minOf(processDeadline, System.nanoTime() + Duration.ofSeconds(15).toNanos()))
                    check(hello != null && hello.text("kind") == "hello" && hello.text("token") == token && hello["protocol"] == JsonPrimitive(1)) {
                        "Comparison peer handshake failed"
                    }
                    val version = hello.text("godotVersion")
                    check(hello["versionMajor"] == JsonPrimitive(4) && hello["versionMinor"] == JsonPrimitive(7) &&
                        hello["versionPatch"] == JsonPrimitive(2) && hello.text("versionStatus") == "stable") {
                        "Comparison requires the verified Godot 4.7.2 stable build, received $version"
                    }
                    pending.godotVersion = version
                    return pending
                } catch (failure: Throwable) {
                    socket?.close()
                    terminate(process)
                    throw failure
                }
            }
        }

        private fun terminate(process: Process) {
            val descendants = process.toHandle().descendants().use { it.toList().reversed() }
            if (!process.waitFor(1, TimeUnit.SECONDS)) {
                descendants.forEach { if (it.isAlive) it.destroy() }
                process.destroy()
                if (!process.waitFor(2, TimeUnit.SECONDS)) {
                    descendants.forEach { if (it.isAlive) it.destroyForcibly() }
                    process.destroyForcibly()
                    process.waitFor(2, TimeUnit.SECONDS)
                }
            }
            descendants.forEach { if (it.isAlive) it.destroyForcibly() }
        }
    }
}

internal fun JsonObject.text(key: String): String = getValue(key).jsonPrimitive.content

internal class ProbeRejected(val operation: String, val result: JsonElement) :
    IllegalStateException("Renderer probe rejected $operation: $result")
