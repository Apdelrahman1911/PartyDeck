# JVM rule and network measurements

The [2026-09-11 baseline](measurements/jvm-20260911/README.md) preserves all six raw CSVs,
source pins and artifact hashes from run `34547302716`. All three real TLS integration cases
passed, and both measurement suites completed two warmups and five samples. The report
summarizes sample-only medians and observed ranges for the six-controller JVM fixture;
mobile hardware and physical-LAN qualification remain pending.

Run this opt-in harness on the existing JVM test classpath. It adds no dependency or default test
run, and the standalone init script leaves shared Gradle configuration unchanged. Use a new output
directory for every run:

```sh
./gradlew --no-configuration-cache \
  -I scripts/jvm-rule-network-measurements.init.gradle \
  :composeApp:measureJvmRuleNetwork \
  -PmeasurementOutput=/tmp/partydeck-jvm-measurements-01 \
  -PmeasurementSeed=20260910 \
  -PmeasurementWarmups=2 \
  -PmeasurementSamples=5 \
  -PmeasurementIdleMillis=1000
```

The manual **JVM rule and network measurements** GitHub Actions workflow runs all three
`LanMultiplayerIntegrationTest` cases first, then this harness with the values above. Dispatch it
with `gh workflow run jvm-rule-network-measurements.yml --ref main`. Its artifact retains the
source revision, source hashes, toolchain versions, JUnit results, execution logs and raw CSVs.
Both execution steps have process and CI deadlines; a failed integration suite prevents the
measurement step. Hard termination may prevent CSV output, and cancellation may prevent upload;
only available artifacts can be retained. A hosted-runner result is still a JVM baseline, not
phone performance.

Each suite runs the requested warmup count followed by the sample count in one JVM. Every trial
creates a fresh six-seat table using the same seeded game RNG. Warmup rows remain in the raw output
with `run_kind=warmup`; exclude those when summarizing samples. The real TLS fixture retains real
SecureRandom credentials and TLS identities. Admission, connection setup and teardown sit outside
its two measured intervals.

Both workloads first let all six seats play one card from their own received hand. They then
challenge whenever legal, otherwise play the first received card, and let only the host advance an
ended round. They finish at the actual winner. The pure suite includes `START_GAME` in its game
command count; the TLS active interval starts after setup has started the game. The ordinary
integration test separately verifies return-to-lobby and rematch.

The files contain raw observations, with no pass/fail speed limits or generated percentiles:

| File | Meaning |
| --- | --- |
| `metadata.csv` | JVM/OS allowlist, seed, requested warmups/samples/idle interval, completed counts and measurement scopes. `completed=false` identifies a partial failed run. |
| `authority-steps.csv` | One real `HostAuthority` operation per row: bare reference-rule call, inclusive authority handling, serial codec fan-out, exact remote byte counts and local delivery counts. Setup rows are labeled separately by operation. |
| `codec-messages.csv` | Every generated input and actual authority delivery, with recipient index, direction, message category, exact `ByteArray.size` and individual encode/decode elapsed nanoseconds. |
| `rule-views.csv` | Timed `LastLightEngine.viewFor` calls for all six recipients after each game operation. Each view is compared with the corresponding actual decoded authority snapshot. |
| `tls-payload-intervals.csv` | Six endpoint rows per idle/active interval, from the existing production-controller/JSSE/TLS fixture. Successful send and delivered incoming payload counts/bytes are separate. |
| `completed-trials.csv` | Completed trial and command counts, distinguishing the in-memory and real TLS suites. |

Timing scopes matter:

- `reference_rule_ns` measures a separate real `LastLightEngine` with the same seed, immediately
  before the actual authority call. The authority uses its own real engine. The reference supplies
  verification, never state to the authority. These are separate invocations; do not add their
  durations. Rule rejection checks and recipient-view comparisons occur outside the stopwatches.
- `authority_handle_ns` includes authority validation, the actual rule call, and construction of
  all recipient views. The `INITIAL` row measures `initialDispatch()` instead of `handle()`.
- `serial_codec_fanout_ns` is an in-memory loop encoding and decoding the five remote recipients,
  including routing, timer and measurement-record overhead. It excludes sockets, output-file I/O
  and post-decode assertions. Individual codec durations are nested within it, so do not add them
  to the fan-out duration. All decoded messages are checked and used by the workload.
- Host-local commands/deliveries follow production object routing. Their codec fields are blank;
  they produce no encoded network bytes. Seat `0` is the host, seats `1` through `5` are guests.
- TLS interval durations include the instrumented fixture's controller work, convergence polling
  and gameplay/privacy assertions. They are not isolated rule latency or physical-device latency.

The TLS byte counters observe **application payloads over actual TLS**, excluding four-byte frame
headers, transport keepalives, TLS records/handshakes and TCP/IP/socket traffic. A zero idle payload
count does not mean zero network traffic. The requested idle duration and actual elapsed duration
are both retained; one interval cannot establish behavior outside that observation window. Adding
sent and received totals counts each payload twice: sum either direction, or inspect individual
endpoints. Compare host sent bytes with the sum of guest received bytes, and the reverse direction
separately.

This is an exploratory JVM workload harness, not hardware qualification. JVM compilation, GC,
timer and observer overhead remain part of the environment. Keep the source revision and raw
directory with any analysis. It records no card contents, authoritative state, credentials,
addresses, arbitrary messages, JVM arguments or environment-variable dump.

Verified API/source references:

- [JDK 21 `System.nanoTime`](https://docs.oracle.com/en/java/javase/21/docs/api/java.base/java/lang/System.html#nanoTime())
- [Gradle 9.7.0 `JavaExec`](https://docs.gradle.org/9.7.0/dsl/org.gradle.api.tasks.JavaExec.html)
  and [`Test` classpath/toolchain](https://docs.gradle.org/9.7.0/dsl/org.gradle.api.tasks.testing.Test.html)
- [Kotlin 2.4.20 `KotlinJvmTest` extends Gradle `Test`](https://github.com/JetBrains/kotlin/blob/v2.4.20/libraries/tools/kotlin-gradle-plugin/src/common/kotlin/org/jetbrains/kotlin/gradle/targets/jvm/tasks/KotlinJvmTest.kt)
- `LastLightEngine.kt`, `HostAuthority.kt`, `SessionCodec.kt`, `AuthoritySessionRuntime.kt`,
  `CallbackLanTransport.kt`, and the existing `LanMultiplayerIntegrationTest.kt` fixture.
