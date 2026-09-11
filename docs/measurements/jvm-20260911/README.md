[Run 34547302716](https://github.com/Apdelrahman1911/PartyDeck/actions/runs/34547302716), at [commit 5341ffe873df](https://github.com/Apdelrahman1911/PartyDeck/commit/5341ffe873df5a571905b8bfd0dfdd6554ea3247), completed both measurement suites and the three `LanMultiplayerIntegrationTest` cases: **3 passed, 0 failed, 0 skipped**. Each suite ran two warmups and five samples with seed `20260910`. Statistics below use only `run_kind=sample`; the unchanged CSVs retain the warmups.

The runner reported Java 21.0.12.1, Kotlin 2.4.20, Linux amd64 and four available processors. [metadata.csv](metadata.csv) records the environment and measurement scopes. This directory retains the baseline after the original Actions artifact expires; [manifest.json](manifest.json) records its digest, source pins, named test outcomes and CSV hashes.

Each authority/codec sample completed 55 steps: initial dispatch, five joins, five readiness commands and 44 game commands. The game commands were one start, 18 plays, 13 challenges and 12 round advances. These are **per-trial totals**, with the median and observed minimum–maximum across five samples.

| Timed work | Median | Observed range |
| --- | ---: | ---: |
| Separate reference engine rule calls (44 calls) | 1.561 ms | 0.943–1.773 ms |
| Authority handling, including its own rules and recipient views (55 steps) | 4.124 ms | 3.502–4.913 ms |
| Outbound in-memory serial codec fanout (55 steps) | 57.082 ms | 51.825–76.499 ms |

The reference engine performs separate work before the authority call; its duration must not be added to or subtracted from the authority duration. Server encoding/decoding timers are nested inside fanout, which also includes routing and measurement overhead. Client encoding/decoding occurs earlier, outside fanout. Host-local object routes have blank codec/byte fields. The clock measures elapsed `System.nanoTime`, not CPU time or socket latency.

Each TLS active sample completed the remaining **43 game commands after START_GAME**, advancing revision 11 to 54. The full active interval had a median of **442.069 ms**, with an observed range of **441.668–446.664 ms**. It includes six controllers, polling, assertions and final settling, and excludes setup, admission and START_GAME. It does not measure individual command latency.

Every active sample recorded the same application payload totals:

| Direction | Messages | Payload bytes |
| --- | ---: | ---: |
| Host to five guests | 238 | 401,495 |
| Five guests to host | 23 | 3,769 |
| All sent deliveries, counted once | 261 | 405,264 |

Sender totals exactly matched the corresponding recipients in both directions. Interval fields repeat across six endpoint rows and were counted once per interval. All five idle samples, lasting **1.000191–1.000304 seconds**, recorded **zero application payload messages and bytes**. Framing, keepalives, TLS records/handshakes and TCP/IP bytes are excluded, so this does not establish zero wire traffic.

All six CSVs below are copied unchanged from the original artifact. Row counts exclude headers and include both warmups and samples. Completion counts, contiguous revisions, input/output byte totals, host-local blanks, six-recipient reference views, command receipt recipients and both TLS directions reconciled across all seven trials per suite.

| File | Contents | Rows |
| --- | --- | ---: |
| [metadata.csv](metadata.csv) | Environment, completion and scope | 37 |
| [authority-steps.csv](authority-steps.csv) | Rule, authority and outbound fanout timings | 385 |
| [codec-messages.csv](codec-messages.csv) | Per-message codec timings and payload sizes | 2,926 |
| [rule-views.csv](rule-views.csv) | Separate reference recipient-view timings | 1,848 |
| [tls-payload-intervals.csv](tls-payload-intervals.csv) | Six endpoints per idle/active interval | 84 |
| [completed-trials.csv](completed-trials.csv) | Seven completed trials per suite | 14 |

See the [measurement method and reproduction instructions](../../jvm-rule-network-measurements.md). These observations describe one repeated seeded fixture with real TLS and six controllers in one JVM. They do not qualify mobile hardware, a physical LAN or a performance threshold.
