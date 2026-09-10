# iOS qualification facade review

Status: **accepted for source, JVM/iOS Simulator shared tests, framework compilation and generated facade declarations, 2026-09-10**. No source finding remains in this review. The native follow-up below records the new execution evidence. Actual Swift factory/method calls, factory entropy execution, native event delivery and a playable iOS match remain separate gates.

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

The root-owned workflow/build script separates framework compilation, declaration presence and bare Swift module import from compiling an actual Swift authority caller and executing the factory. The follow-up below records the completed native checks. The host must discard a failed or closed facade and clear its own retained strings/queues; clearing the facade's launch property does not erase copies already delivered to native code.

## Native framework and shared-test follow-up, 2026-09-10

**Accepted for the executed native shared tests, compiled simulator framework and inspected header.** [Workflow run 34427976260](https://github.com/Apdelrahman1911/PartyDeck/actions/runs/34427976260) succeeded at commit `cf6434df2fd32909f70feee68bfcb82e527e2b70`. This reviewer inspected the actual run metadata, all five native XML files, framework/archive receipts, generated Objective-C header, build/import logs and committed source. The reviewed facade, iOS factory, driver, both facade test files, framework configuration, workflow and build script match that commit byte-for-byte. No unchanged test was rerun by this reviewer.

The `iosSimulatorArm64` execution contains **20 tests, zero failures/errors/skips**: six owner bridge tests, six adversarial bridge tests, two public-parser API tests, four owner facade tests and two independent facade initialization tests. The retained selector evidence identifies an iPhone 17 simulator with runtime 26.4.1, build `23E254a`; Xcode is 26.4.1, build `17E202`. These are Kotlin/Native shared-test executions, including the seeded facade's complete matches and lifecycle checks. They do not call the iOS factory or execute its secure-random path through Swift.

The actual header confirms the facade's supported surface. `PDGBIosQualificationAuthority` has no public construction path through its base initializer. It exposes only the launch string, randomness enum, status and the intended operations. Results export `NSArray<NSString *> *commands`, fixed enums/reason strings and status; status properties are readonly, with the exact revision as `NSString`. No domain state/action/decision or random-generator type appears in these facade declarations. Factory and five mutating methods have the expected `NSError` parameters and recorded Swift-name annotations:

- `create(presentationId:mode:randomness:reduceMotion:soundEnabled:textScale:)`
- `handleRendererEvent(document:)`, `setForeground(isForeground:)`
- `advanceOtherPlayers()`, `refreshView()`, `close()`

The generated enum properties include `PresentationMode.twoD`/`threeD` and `IosQualificationRandomness.referenceSeed2`/`secure`. These spellings were read from the generated header. Compiling an actual Swift caller remains necessary to verify its use of those methods and types.

Independently verified artifact hashes:

| Artifact | SHA-256 |
| --- | --- |
| `PartyDeckGodotBridge-simulator.framework.tar.gz` | `f0383e1d821f0f56954a6f71458f63483981984589646e5b0686533db0c4d998` |
| Framework binary | `580b45b44dc59289a65178fa8187f3512563a918294eb1c5262398b1a240ff95` |
| Actual `PartyDeckGodotBridge.h` | `dddbb2ae23d1e87ebab18fa7c4f77326c3e370422b96f1e723c3e2f2cdde14fd` |

All four framework receipt entries, including module map and Info.plist, match the archive contents; the separately preserved header/module map match those same bytes. The architecture log records `arm64`. The framework build completed successfully and its symbol evidence includes the Security.framework random binding. That establishes compilation, not execution of the secure factory.

The Swift input file contains exactly `import PartyDeckGodotBridge`, and its typecheck step passed. The receipt correctly records `swift_module_import_typechecked=true`, while `swift_authority_host_compiled`, `ios_authority_runtime_executed` and `kmp_factory_qualified` remain false. Those flags describe the missing Swift/native-host integration; they do not negate the separately executed Kotlin/Native shared tests.

Original retained artifact tree: `/tmp/partydeck-ios-authority-ci/34427976260/artifacts/`. Independent copies of all native XML files, the header, module map, run/receipt/selector evidence and JSON audits are preserved under `/tmp/partydeck-ios-facade-review/native-34427976260/`. `independent-native-review.json` records the count, selectors and scope; `framework-hash-audit.json` records all artifact hashes. The committed/current source comparison is `/tmp/partydeck-ios-facade-review/native-cf6434d-source-hashes.json`.
