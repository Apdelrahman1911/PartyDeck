# JVM and Swift TLS interoperability fixture

The fixture exercises PartyDeck's real Java JSSE transport and Swift
Network.framework driver with each acting as host once. It runs a JVM process on
the macOS CI runner and an app-hosted XCTest in iOS Simulator. A successful run
qualifies **JVM↔iOS Simulator TLS interoperability in both host directions**. It
does not establish Android TLS-provider behavior, physical-device Wi-Fi,
multicast discovery, permission handling, backgrounding, or complete multiplayer
gameplay. Those qualification gates remain in [release qualification](../release-qualification.md).

## Execution boundary and sources

- Apple's [Foundation `Process`](https://developer.apple.com/documentation/foundation/process)
  is documented for macOS and Mac Catalyst, not iOS. Its
  [primary documentation metadata](https://developer.apple.com/tutorials/data/documentation/foundation/process.json)
  was checked on 2026-09-09. CI starts Java from its shell; the iOS test does not
  attempt to launch a child process or read a file from the Mac's filesystem.
- The JVM peer uses `JvmLanTransportFactory().create()` and public
  `LanTransport`/`LanConnection` operations. The Swift peer uses `IosLanDriver`
  callbacks, matching the existing native TLS tests. These are the actual
  implementations described in [networking research](networking.md); no mock
  socket, alternate certificate implementation, or new runtime dependency is
  introduced.
- The Gradle task reads the real JVM test task's
  [`Test.classpath`](https://docs.gradle.org/9.7.0/dsl/org.gradle.api.tasks.testing.Test.html#org.gradle.api.tasks.testing.Test:classpath).
  CI launches Java separately after Gradle completes, so the fixture does not
  retain a Gradle build while Xcode embeds the Kotlin framework.
- [Coroutines `withTimeout`](https://kotlinlang.org/api/kotlinx.coroutines/kotlinx-coroutines-core/kotlinx.coroutines/with-timeout.html)
  bounds the listener wait and active exchange. Native handshake, write, and
  idle deadlines remain enabled. Simulator-to-Mac loopback is an execution
  assumption that the actual macOS run must verify; the Linux self-test cannot
  establish it.

## CI launch contract

Run `./gradlew :transport:exportInteropFixtureClasspath`. This compiles the test
fixture and writes `transport/build/interop/jvm-test-classpath.txt`. The fixture
is excluded from all shipping application classpaths.

Launch `dev.partydeck.transport.JavaSwiftInteropFixture` with Java 21 and that
classpath, passing exactly two arguments: an output manifest path and an output
result path. The CI script owns background-process startup, log capture, bounded
readiness polling, and kill/wait cleanup on failure. Both files are replaced;
stale files are removed at startup. JSON publication uses a temporary file and
rename, so readers do not observe half-written content.

The ready manifest has this schema:

```json
{"version":1,"port":12345,"certificateSha256":"64 lowercase SHA-256 hexadecimal characters"}
```

CI passes the **entire JSON string**, rather than a file path, through
`TEST_RUNNER_PARTYDECK_INTEROP_MANIFEST`. It also sets
`TEST_RUNNER_PARTYDECK_INTEROP_REQUIRED=1`. The XCTest process reads
`PARTYDECK_INTEROP_MANIFEST` and `PARTYDECK_INTEROP_REQUIRED`. The CI owner checks
the installed `xcodebuild` manual for `TEST_RUNNER_` forwarding and retains the
evidence. A required fixture with missing or invalid input must fail the test.
A local test invocation that does not request the fixture may skip this case.

Java waits up to 20 minutes after manifest publication for the first incoming
TLS connection, allowing Xcode compilation to finish. The complete exchange
then has a 120-second deadline. The script must require all three outcomes:
successful XCTest execution, JVM exit status zero, and a version-1 result with
`status: "PASS"`. An XCTest skip, missing result, or killed peer is not success.

## Wire contract, version 1

Both connections use `127.0.0.1` and a complete SHA-256 certificate pin. A is
Swift client → JVM host; B is JVM client → Swift host. Swift starts its listener
before opening A. Its callback control record contains only a port and pin; it
cannot redirect the JVM to another host or carry admission secrets or game state.

Every application payload has a four-byte unsigned big-endian length prefix.
The maximum payload is 65,536 bytes; a zero length is a transport heartbeat.
The JVM shared adapter adds/removes this framing. Swift sends framed bytes and
incrementally parses raw callbacks, including fragmented headers/bodies and
multiple frames in one callback. It ignores zero frames as application input
and echoes one zero frame on that connection, keeping the Java adapter's
20-second receive idle deadline alive while the other connection is active.
Java emits heartbeats every five seconds and does not echo them.

| Step | Sender → receiver | Payload or event |
| --- | --- | --- |
| 1 | Swift → JVM, A | UTF-8 `PARTYDECK-INTEROP-1\n<Swift port>\n<Swift full lowercase pin>`, no trailing newline |
| 2 | Swift → JVM, A | 65,536 bytes, byte at index `i` is `(i * 31 + 7) % 251` |
| 3 | JVM → Swift | Open B with the exact control-record port and pin |
| 4 | JVM → Swift, B | 20,000 bytes, byte `i` is `(i * 17 + 3) % 251` |
| 5 | Swift → JVM, B | 65,536 bytes, byte `i` is `(i * 13 + 11) % 251` |
| 6 | JVM → Swift, B | UTF-8 `PARTYDECK-INTEROP-1-REVERSE-OK` |
| 7 | Swift, then JVM | Swift receives reverse ACK and closes B; JVM observes terminal B |
| 8 | JVM → Swift, A | 20,000 bytes, byte `i` is `(i * 19 + 5) % 251` |
| 9 | Swift → JVM, A | UTF-8 `PARTYDECK-INTEROP-1-OK` |
| 10 | JVM → Swift, A | UTF-8 `PARTYDECK-INTEROP-1-COMPLETE` |
| 11 | Swift, then JVM | Swift receives COMPLETE and closes A; JVM observes terminal A |
| 12 | JVM | Close the transport/listener, write PASS, exit zero |

Each peer checks complete payload content and ordering. The ACK/close sequence
does not treat local write completion as proof of remote delivery. The JVM
records remote EOF as `Closed` and a socket/TLS reset as
`Failed:UNAVAILABLE` or `Failed:IO_ERROR`; it does not describe the latter as
an orderly TLS shutdown. An idle timeout, invalid frame, or other terminal
failure cannot substitute for the expected peer close.

PASS results include `forwardBytesReceived: 65536`, `forwardBytesSent: 20000`,
`reverseBytesSent: 20000`, `reverseBytesReceived: 65536`,
`forwardTerminalState`, and `reverseTerminalState`, plus `version: 1` and
`status: "PASS"`. Byte counts describe the four patterned payloads and exclude
control records, ACKs, framing, and heartbeats. Failure results contain
`version: 1`, `status: "FAIL"`, `stage`, and `error`; Java exits nonzero.

## Evidence

On 2026-09-09, the Linux command below passed both fixture self-tests and exported
the JVM runtime classpath successfully. The tests use two real Java transports
to complete both directions, then separately verify that changing one byte in
the maximum-size forward payload fails the fixture. This validates fixture
orchestration only and is **not evidence of Swift or Simulator execution**.
Launching the main class with the exported classpath also produced a valid ready
manifest and no premature result. That smoke process was intentionally stopped
without a peer; it did not produce an interoperability PASS.

```sh
flock /tmp/partydeck-gradle.lock ./gradlew :transport:jvmTest --tests dev.partydeck.transport.JavaSwiftInteropFixtureTest :transport:exportInteropFixtureClasspath
```

Record the actual macOS CI run, revision, XCTest outcome, fixture log, and result
JSON in release qualification before marking JVM↔iOS Simulator interoperability
executed. Keep the physical-device qualification gates separate.
