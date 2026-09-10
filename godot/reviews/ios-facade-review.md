# iOS qualification facade review

Status: **accepted for source and common-code behavior, 2026-09-10**. No source finding remains in this review. Native compilation, generated Swift method spellings, factory/entropy execution, native event delivery and a playable iOS match require the separate macOS/device evidence.

## Reviewed behavior

`IosQualificationAuthority` privately owns the existing `QualificationAuthorityDriver`. Events, opponent actions, foreground changes, view refreshes and closure delegate to that driver. The facade adds receipt/lifecycle handling without adding rules or changing the recipient projection. Its supported return types contain copied lists of safe command strings, bridge-local enums, primitive values, canonical revision strings, public winner IDs and fixed reason codes. No `GameState`, `GameView`, random generator, core action or sealed decision is returned through this facade surface.

Rejections return the driver's reason without a hidden view refresh. The native owner must explicitly request reconciliation. Receipt counters distinguish an accepted bridge event from an accepted authority action; a gate-consumed event subsequently rejected by the adapter does not become a facade acceptance. Foreground and readiness remain separate states. The host must serialize calls, deliver commands in order and retain its native generation/queue limits, as the facade documentation requires.

Accepted lobby, Exit and renderer-failure events return a driver close document, mark the facade closed and clear its cached launch string. Repeated close is idempotent. Later renderer events still hit the driver's closed boundary; native refresh/foreground/opponent calls reject closure without commands. The original gate remains decisive during initialization: an early Exit or intent is rejected, while a correctly bound initialization failure may close before Ready. Foreign or unsupported-protocol failure events cannot terminate the lifetime. Returned status objects remain snapshots for native consumers.

The iOS factory explicitly selects reference seed 2 or `SecRandomCopyBytes` through `kSecRandomDefault`. The secure implementation pins a four-byte destination, checks `errSecSuccess` before consuming it, uses all requested random bits, has no seeded fallback, and clears its temporary array in `finally`. This is source validation; the Security.framework binding has not been executed by this reviewer. Factory and mutating operations use `@Throws(Exception::class)` so expected Kotlin exceptions can cross Objective-C/Swift as errors; ordinary bridge rejections remain data.

## Executed checks

- **Owner execution, independently inspected:** `IosQualificationFacadeTest`, 4 tests, zero failures/errors/skips, 0.371 seconds. Both modes match independently constructed real drivers for every command through a complete match, plus rejection/reconciliation, terminal events, closure and replacement isolation.
- **Independent reviewer execution:** the separate `IosQualificationFacadeAdversarialReviewTest`, 2 tests, zero failures/errors/skips, 0.117 seconds. It covers malformed/foreign/unsupported/early input during preparation, a current initialization failure before Ready, retained receipt snapshots, background-before-Ready, explicit refresh without core-state change, and readiness/foreground/replay/counter behavior.

```sh
flock /tmp/partydeck-gradle.lock ./gradlew -p godot/qualification \
  :bridge:jvmTest --tests '*IosQualificationFacadeAdversarialReviewTest*' --console=plain
```

Gradle exited zero. The existing bridge suites and full-match owner tests were not redundantly rerun. Preserved XML under `/tmp/partydeck-ios-facade-review/`:

- `TEST-dev.partydeck.godot.bridge.IosQualificationFacadeTest.xml`, SHA-256 `6a989b155a72674e24fbc20f18495bfe03b1d12f3193610e3335b07f957ba55c`.
- `TEST-dev.partydeck.godot.bridge.IosQualificationFacadeAdversarialReviewTest.xml`, SHA-256 `4e4b19d90e790b41b11345a7b6954243ceb109c99caa987af30268a08605955e`.

Reviewed common facade SHA-256: `bdaa5adfa74d7bc0ab16834cc8e32c006b5636a2c44656f33aa306c024615dc8`. Reviewed iOS factory/random source SHA-256: `90872ec850f633b7bcc165a24764055983f563b768584652c0981b0e1b0037f9`. The full reviewed source/test hash list is retained in `/tmp/partydeck-ios-facade-review/reviewed-source-hashes.json`.

## Authoritative checks and remaining native gates

Retrieved directly on 2026-09-10:

1. [Apple SecRandomCopyBytes](https://developer.apple.com/documentation/security/secrandomcopybytes(_:_:_:)) specifies cryptographically secure bytes, an adequately sized destination, `kSecRandomDefault`, and checking the returned status before consuming the result.
2. [Kotlin Objective-C interoperability](https://kotlinlang.org/docs/native-objc-interop.html) documents internal visibility, enums and immutable-list export, plus `@Throws` propagation of the named exception classes and subclasses through `NSError`/Swift `throws`. Unexpected exceptions outside that contract terminate the program.
3. [Kotlin native binary configuration](https://kotlinlang.org/docs/multiplatform/multiplatform-build-native-binaries.html) distinguishes linked implementation dependencies from explicitly exported APIs. The supported facade does not require exporting domain dependencies to Swift.

The root-owned workflow/build script accurately separates framework compilation, declaration presence and bare Swift module import from compiling an actual Swift authority caller and executing the factory. This review does not mark any of those native gates complete. The host must discard a failed or closed facade and clear its own retained strings/queues; clearing the facade's launch property does not erase copies already delivered to native code.
