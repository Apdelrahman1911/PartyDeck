# Independent security review

Review owner: `review_security`. Research checked on 2026-09-09. This is an independent architecture assessment and an implementation review record, not a cryptographic audit or evidence of physical-device qualification.

## Architecture recommendation

Use a host-authoritative common session layer over small platform TLS adapters: Android/JVM JSSE TLS sockets, Apple `NWListener`/`NWConnection` with TLS. Exchange the full SHA-256 host-certificate fingerprint through the room invitation and verify it before sending any admission or reconnect credential. Use native DNS-SD only to locate candidate rooms. Keep framing, game messages, and authorization separate from TLS and discovery.

The transport and security reviewers independently reached this recommendation. Platform TLS avoids introducing a PartyDeck implementation of a cryptographic handshake. It still leaves certificate creation, exact pin verification, resource ownership, and application authorization to implement and test.

### Why P2pKit was not selected

P2pKit addresses the right general problem: Android, iOS, local discovery, encrypted streams, and connection lifecycle in one Kotlin API. Its published `0.7.0-rc3` tag resolves to `deed9e77b81b6f1082519f44804de038eb5dcc0e`. Its security model describes `Noise_XX_25519_ChaChaPoly_SHA256`, exact out-of-band identity pins, platform identity storage, and a fail-closed default. Its documentation explicitly says that names, TXT records, `AppId`, peer IDs, and short codes do not authorize a device [S1].

There are two material objections to making that candidate PartyDeck's production transport:

1. The immutable candidate's validation document explicitly leaves Android instrumentation/physical devices, Apple device and lifecycle behavior, hostile networks, independent secure-protocol interoperability, and professional cryptographic review pending [S2]. Automated compilation or a successful PartyDeck sample cannot close those claims.
2. Independently comparing the published candidate with development commit `eb444cccfc290be5435c5c10629c24183293606f` shows security-relevant hardening absent from the published artifacts [S3]. Examples include delaying terminal connection state until encrypted records have been authenticated, propagating authentication failures to reconnect policy, disposing handshake outcomes abandoned during cancellation, JSON field-name validation, and per-source connection admission. The secure-stream source specifically explains that exposing raw EOF can let reconnect cancel the old reader before queued tampering is classified. These changes are concrete reasons to avoid assuming current documentation/tests describe the published candidate.

This review does not claim to have demonstrated an exploitable confidentiality break in P2pKit. It also does not treat a large diff as a vulnerability count. The relevant facts are that the published version is a release candidate, external validation is pending, and meaningful hardening is unpublished. Vendoring development `main` would transfer that maintenance and qualification burden into PartyDeck; it is not a stable dependency substitution.

Reconsider P2pKit after a stable published release, review of relevant fixes, and reproducible Android-to-iOS and iOS-to-Android hostile/lifecycle evidence. Its feature set could justify replacing the adapters later; the session/domain boundaries should permit this.

### Why common Ktor hosting is insufficient

Ktor 3.5.2 lists CIO as a Kotlin/Native server engine, but its pinned source rejects HTTPS connectors with `UnsupportedOperationException("CIO Engine does not currently support HTTPS...")` [S4]. Native server support therefore does not establish native TLS server support. Plain WebSockets with an application room code would expose credentials and hidden hands to network observers. A TLS client engine also does not supply a TLS listener.

### Native TLS feasibility and its real cost

Android documents `SSLServerSocket` as a TLS-capable listener whose accepted sockets inherit protocol and authentication settings [S5]. Android Keystore can generate an EC private key with a corresponding self-signed certificate. Its documentation cautions that the generated certificate's signature is invalid unless signing purpose, digest, validity, and user-authentication restrictions permit signing [S6]. Use the documented P-256/signing configuration and verify the generated certificate and an actual TLS handshake; do not assume any generated certificate is usable.

Apple documents `NWParameters(tls:tcp:)` for TLS connections and listeners, `sec_protocol_options_set_local_identity`, and custom verification blocks [S7]. `SecIdentityCreate(_:_:_:)` constructs an identity from a certificate and matching private key; its documentation lists iOS 11.2 availability [S8]. The different `SecIdentityCreateWithCertificate` API is macOS-only and is unsuitable for an iOS bridge. Check the actual selected Xcode SDK in CI as well as documentation.

Apple's maintained `swift-certificates` stable 1.20.0 release creates X.509 certificates and has a public `Certificate.PrivateKey(SecKey)` initializer, so certificate signing can use a native key without exporting it [S9]. This release's manifest requires Swift 6.1. It is a feasibility finding, not permission to add an unverified dependency matrix: the iOS owner must compile the exact package/SDK combination. Do not handwrite ASN.1 certificate generation, bundle a shared server private key, or require players to install a root CA.

The practical cost is two listener/client adapters, an Apple certificate helper, DNS-SD lifecycle code, and interoperability tests. A narrow four-byte length-prefixed message stream is sufficient for this turn-based game. HTTP/WebSocket framing and an embedded native web server provide no necessary benefit here. TLS 1.2 or newer with platform-supported modern cipher suites is the minimum; disable old protocols and do not enable early application data.

## Trust and data flow

The host is trusted with all hidden cards, undealt cards, future fuse outcomes, and game randomness. This architecture protects one client from learning another client's private state and protects transport against an uninvited network observer or active intermediary. It cannot prevent a modified host from cheating. There is no claim of trustless fairness or protection against a compromised operating system.

The TLS server certificate establishes host key possession and, when checked against the out-of-band pin, the intended host. Without client certificates, TLS alone does **not** establish an individual player's identity. The session must bind its own credentials to opaque connection handles supplied by the transport.

The invitation contains a protocol version, session/room identifier, endpoint information, the complete certificate fingerprint, and an independently random admission credential. Prefer a QR or exact copyable invitation. A short room code is a discovery convenience, not a substitute for an authenticated invitation. Never obtain the trusted pin solely from the same untrusted discovery record being authenticated.

Credentials contain 32 bytes from the platform CSPRNG. An admission credential permits requesting a seat in the current lobby. Once admitted, the host issues a different, unique 32-byte reconnect credential for that seat, sent only over its pinned TLS connection. Other clients must never receive that credential. Reconnect possession authorizes replacing that seat's current connection. A room-wide TLS PSK alone would allow any participant who knows it to impersonate the host to others; do not substitute it for the host's asymmetric identity.

Each fresh accepted socket receives an unguessable or process-unique opaque connection identifier from the adapter. A client-supplied player ID, display name, claimed role, room ID, or connection ID is never an authority. Resolve the current connection binding to a seat before evaluating an intent. Resume must revoke the previous binding atomically before projecting state to the replacement. A late disconnect from the old socket must not disconnect the new one.

Keep per-seat reconnect credentials and private keys outside UI state. The admission invitation is intentionally visible in the explicit host/share and join flows; clear it when the session closes. No credentials belong in snapshots, discovery TXT records, error text, analytics, or cached command receipts. Keep room state and credentials in memory for the initial release. If credential persistence is added, separately review Keychain/Keystore protection, backup, expiry, and lifecycle behavior. A process restart that lost host state ends the session; it must not restore stale authority from client data.

## Required security invariants

### Hidden information

Only explicitly constructed recipient projections cross the network and reach nonhost UI or bots. The authoritative game state must not be serializable through a server DTO. A projection may include public counts, the receiving seat's own hand, public challenge evidence, and public fuse progress. It must omit other hands, undisclosed discards, undealt cards, pending claim ranks/truth, future burnout steps, and RNG state.

Fresh round card IDs must not encode card rank or predictable deck position. Revealing challenged cards does not authorize revealing previous accepted plays. Eliminated and unknown recipients receive no private hand. Test the encoded bytes of welcomes, snapshots, and error responses in addition to testing the domain projection.

Live deck shuffling, table-rank selection, and hidden fuse selection must obtain every random value from a platform CSPRNG. Seeding Kotlin `Random(seed)` with a secure seed is insufficient: the pinned Kotlin implementation uses a repeatable XorWow generator [S10]. Keep the domain's injectable `Random` interface, supply `SecureRandom().asKotlinRandom()` on Android/JVM and a native-secure `nextBits` implementation on Apple, and reserve deterministic seeded generators for tests or nonauthoritative bot strategy.

### Replay, deduplication, and actor mapping

Process every join, resume, command, disconnect, and host action through the same serialized session authority. Each seat has monotonically increasing positive command IDs and a high-water mark retained for the room lifetime. A bounded recent-command cache may return the original receipt for an exact duplicate, but cache eviction must never make an old action executable again. Reusing an ID with different contents is rejected.

Validate the session identifier, protocol version, current connection binding, revision, action structure, turn, and card ownership before mutating game state. Receipts contain no private state; a duplicate may receive a separately generated current private projection. Reconnect retains command history/high-water state and returns the next safe ID. Guard integer exhaustion instead of wrapping IDs or revisions. Rejected actions must not consume game randomness.

### Parsing and resource bounds

The application-frame ceiling is 64 KiB, checked before payload allocation by transport and independently by the codec. Empty application messages, overflow, truncation, malformed UTF-8, unsupported versions, unknown fields/types, excessive nesting, and duplicate decoded JSON field names must be rejected. The transport consumes zero-length records as keepalives; they never become application messages. Escaped forms such as `"type"` and `"\u0074ype"` count as the same field. Tests must include nesting inside unexpected fields and delimiters inside strings.

Schema limits are also necessary: display-name length and controls, identifier/token lengths, maximum card selections, player count, and error sizes. A byte ceiling alone does not prevent excessive object creation or expensive malformed payloads. Never log raw frames or parser exception messages containing attacker-controlled text.

Bound concurrent TLS handshakes, pre-admission connections, receive and send queues, discovery candidates, rejected-request rates, and connection attempts. Use finite connect/handshake/partial-frame deadlines. Capacity must be enforced before starting another reader/task. One stalled or flooding peer must not stall the host actor or allocate an unbounded backlog. The final implementation should expose small named constants and tests; ordinary six-player traffic does not need large queues.

### Lifecycle

Subscribe to incoming events before advertising/listening is exposed. Each socket has one receive owner and serialized writes. Failure in a peer task must close that peer without cancelling unrelated peers or the host session actor. Closing a room must stop accepting, stop discovery, revoke bindings, close sockets, release platform listeners/locks, and cancel owned work; repeated close must be safe.

Treat pin mismatch and TLS authentication failure as terminal for that attempt, never as reasons to try plaintext or trust another key. Reconnect must reuse the original host pin and seat credential for the same room. Host background suspension, path changes, and process termination require explicit state transitions; a network status callback alone does not prove a healthy game connection. Device behavior remains a separate qualification task.

## Implementation review record

Architecture research and the first independent protocol tests are complete. Further native TLS, certificate, and lifecycle review proceeds through source inspection. This reviewer has not conducted an active network security campaign or physical-device qualification. Code-level findings and evidence are recorded below; they are not a blanket production approval.

The Java implementation creates an ephemeral P-256 key through the default JCA provider, constructs a self-signed certificate with Bouncy Castle, and retains the identity in memory for the listener lifetime. It does not currently persist an Android Keystore identity. It accepts raw sockets solely to wrap them in server-mode `SSLSocket`; application reads/writes occur after the TLS handshake. The client compares the full SHA-256 digest of the first certificate against the invitation using `MessageDigest.isEqual`, then checks validity, EC key type, digital-signature usage, server-auth usage, and self-signature. Only TLS 1.2/1.3 and the explicit modern cipher-suite list are enabled. These are source observations in `JavaTlsIdentity.kt` and `JavaLanDriver.kt`, not an interoperability test result.

The Apple identity helper creates a nonpersistent native P-256 key, signs a short-lived self-signed leaf through `swift-certificates`, and constructs a native TLS identity without exporting the key. Client verification parses a canonical 64-character pin, compares all 32 digest bytes against the leaf certificate, checks dates, P-256/ECDSA-SHA256, self-signature, non-CA status, and server/digital-signature usage, and evaluates SSL server trust using only that pinned leaf as an anchor. It installs the SSL policy before disabling network fetching and retains that policy through evaluation [S12]. Hostname matching is deliberately absent because the out-of-band certificate pin supplies host identity. The helper disables TLS resumption, tickets, and false start. These are source observations in `IosTlsIdentity.swift`; the exact Apple SDK/package build and cross-platform handshake remain integration gates.

The Swift driver stores at most eight native connection handles before starting them, attaches a ten-second timer to each pending connection, and guards readiness and terminal cleanup on the same serial queue. It starts application reads after the TLS connection reports ready, closes rejected receive streams, cancels listener/connection/timer ownership at shutdown, and clears its Kotlin observer reference. Both native discovery implementations expose bounded candidate lists and advertise only public version/name/port metadata. Their source does not advertise admission credentials, reconnect credentials, or a trusted certificate pin.

Source inspection confirms live `gameRandom()` implementations use `SecureRandom().asKotlinRandom()` on Android/JVM and `SecRandomCopyBytes` for each Apple `nextBits` draw. Apple secure-random failure throws instead of returning weak fallback output. Session tokens use 32 secure random bytes. The initial deterministic-seed contract is no longer present.

Runtime source inspection confirms a ten-second deadline for the first session admission, bounded per-peer output queues, a single authority event owner, and removal of old connection bindings independently of socket flushing. The client sends Join/Resume only after pinned TLS connects, keeps reconnect credentials in its private runtime, treats pin mismatch as terminal, and checks loop ownership before old-loop cleanup can close a replacement link. Native TLS handshakes precede these application deadlines and require their own elapsed-time bound.

| Finding | Evidence and resolution | Status |
| --- | --- | --- |
| SEC-01: deterministic live secret randomness | Replaced `secureSeed(): Long` with `gameRandom(): Random`; reviewed the Android/JVM and Apple implementations described above. Domain API remains unchanged. | Resolved by source review; Apple compilation remains a platform gate |
| SEC-02: shared receive-queue failure affected every peer | The first shared callback adapter stopped the whole transport when its event queue filled. The implementation now reserves bounded byte-event credits per registered peer, closes only the affected peer, deduplicates terminal callbacks, and coalesces discovery updates. | Fix reviewed in source; no physical-network capacity claim |
| SEC-03: acquired resource lost on dispatcher-return cancellation | `host()` and `connect()` originally marked a result claimed inside `withContext`, before the caller received it. The outer methods now retain the acquired resource and close it under `NonCancellable` if return dispatch is cancelled, matching the documented coroutine pitfall [S11]. | Fix reviewed in source |
| SEC-04: TLS wrapper cleanup | Java now adopts the TLS wrapper immediately after construction and before configuration/handshake in both host and client paths. Rejected adoption closes the wrapper; disconnect and candidate retry close raw TCP first, then TLS. | Fix reviewed in source; platform close timing remains an integration check |
| SEC-05: Apple no-network policy replaced before evaluation | Apple's no-network restriction is stored in the trust policy, so a later `SecTrustSetPolicies` discarded it [S12]. The helper now installs SSL policy first, disables fetching before chain lookup, and preserves that policy through final pinned-anchor evaluation. | Resolved by source review |
| SEC-06: native handshake lacked an elapsed-time deadline | Java initially relied on `SO_TIMEOUT`, which bounds each blocking read rather than the complete handshake [S13]. Both connection paths now install a separate ten-second owned watchdog before blocking work. Expiry and readiness compete under the same lock; readiness/removal cancel the watchdog, and candidate retries do not reset it. Swift independently has a ten-second owned connection timer. | Fix reviewed in source; elapsed timing execution remains integration evidence |

Independent ordinary unit runs completed before the native review was narrowed:

- `flock /tmp/partydeck-gradle.lock ./gradlew :transport:jvmTest --tests dev.partydeck.transport.SecurityTransportTest --console=plain`: **7 tests passed**. Covers framing at every split point, unsigned length rejection, maximum-frame ownership, stopped delivery, invitation canonical form/duplicate fields, malformed UTF-8, and native-service-name controls.
- `flock /tmp/partydeck-gradle.lock ./gradlew :session:jvmTest --tests dev.partydeck.session.SecurityAdversarialTest --console=plain`: **11 tests passed**. Covers actual encoded recipient projections through play/challenge, hidden accepted discards, credential isolation, host impersonation denial, replaced sockets, replay eviction/conflicts/integer bounds, revocation, and strict bounded decoding.

An additional in-process fake-driver lifecycle unit run identified SEC-02 and SEC-03 before their fixes. It used no real sockets or external systems. Its follow-up completion/queue claims must be distinguished from the 18 independently passed tests above; the remaining review here is source-only.

| Area | Evidence required | Current status |
| --- | --- | --- |
| TLS/pinning | Real handshake succeeds with the invited certificate; altered pin fails before credentials or gameplay; no plaintext fallback. | Java and Apple identity source reviewed; native execution evidence is recorded below |
| Platform bridge | Compile the exact Apple SDK/package; connect Android/JVM TLS to the Apple TLS listener in both host directions. | Exact Apple SDK/packages compiled; Java–Swift Simulator interoperability passed in both directions; physical Android/iOS networking remains |
| Projection | Adversarial recipient and serialized-message tests exclude unauthorized private fields. | Independent session unit tests passed for described cases |
| Parser | Malformed UTF-8, lengths, truncation, decoded duplicate keys, depth, unknown fields/types, and field/collection bounds. | Independent session/transport unit tests passed for described cases |
| Identity/replay | Stale socket, wrong credential, resume/disconnect race, ID conflict, cache eviction, session mismatch, and integer exhaustion. | Independent session unit tests passed for described cases |
| Resource ownership | Bounded connection admission, partial-frame expiry, queue isolation, repeated start/stop, and cancellation during setup/return. | Shared ownership/queue, Java wrapper, and native handshake deadline fixes reviewed in source; runtime/device qualification remains |
| Mobile network behavior | Physical Android/iOS cross-host play, network permission denial, background/foreground, network change, host loss. | External/device qualification required |

### Integration evidence

The coordinator and environment reviewer verified the saved artifacts from
[`987d380`, run 34398824935](https://github.com/Apdelrahman1911/PartyDeck/actions/runs/34398824935).
All three native TLS tests passed: pinned ordered frames and closure, wrong-pin
rejection, and actual Java–Swift TLS in both host directions. The fixture reported
65,536 bytes received and 20,000 sent in the forward direction, 20,000 sent and
65,536 received in reverse, and both terminal states `Closed`; XCTest and the Java
process exited successfully. The optimized unsigned iOS device app also built.
These are integration results, separate from this reviewer's 18 independent
tests and subsequent source-only review. They do not qualify physical-device
LAN, permission, suspension, or hostile-network behavior. Current package and
runtime evidence is maintained in [release qualification](release-qualification.md).

## Primary sources

- **S1:** [P2pKit RC3 security model](https://github.com/p2pKit/P2pKit/blob/deed9e77b81b6f1082519f44804de038eb5dcc0e/docs/security/model.md), [tag](https://github.com/p2pKit/P2pKit/tree/v0.7.0-rc3). Read the immutable tree, not only current `main` documentation.
- **S2:** [RC3 validation status](https://github.com/p2pKit/P2pKit/blob/deed9e77b81b6f1082519f44804de038eb5dcc0e/docs/testing/validation-status.md). The file still describes completed RC2 publication evidence; its pending external areas are explicit. Current release documentation is newer and must not silently replace tag evidence.
- **S3:** [Exact candidate-to-development comparison](https://github.com/p2pKit/P2pKit/compare/deed9e77b81b6f1082519f44804de038eb5dcc0e...eb444cccfc290be5435c5c10629c24183293606f), [development secure-stream source](https://github.com/p2pKit/P2pKit/blob/eb444cccfc290be5435c5c10629c24183293606f/library/p2p-core/src/commonMain/kotlin/dev/p2pkit/core/internal/security/noise/NoiseSecureRawConnection.kt), [candidate secure-stream source](https://github.com/p2pKit/P2pKit/blob/deed9e77b81b6f1082519f44804de038eb5dcc0e/library/p2p-core/src/commonMain/kotlin/dev/p2pkit/core/internal/security/noise/NoiseSecureRawConnection.kt). Compared locally with `git diff v0.7.0-rc3 HEAD` in a separate research checkout.
- **S4:** [Ktor 3.5.2 CIO source](https://github.com/ktorio/ktor/blob/3.5.2/ktor-server/ktor-server-cio/common/src/io/ktor/server/cio/CIOApplicationEngine.kt), [server-engine platform table](https://ktor.io/docs/server-engines.html).
- **S5:** [Android SSLServerSocket reference](https://developer.android.com/reference/javax/net/ssl/SSLServerSocket), [Android native DNS-SD](https://developer.android.com/develop/connectivity/wifi/use-nsd).
- **S6:** [Android KeyGenParameterSpec: self-signed-certificate requirements and P-256 example](https://developer.android.com/reference/android/security/keystore/KeyGenParameterSpec).
- **S7:** [Apple TLS parameters](https://developer.apple.com/documentation/network/nwparameters/init(tls:tcp:)), [local TLS identity](https://developer.apple.com/documentation/security/sec_protocol_options_set_local_identity(_:_:)), [verification callback](https://developer.apple.com/documentation/security/sec_protocol_options_set_verify_block(_:_:_:)), [local-network TLS article](https://developer.apple.com/documentation/network/creating-an-identity-for-local-network-tls). The article's managed-CA deployment example is not the proposed player UX.
- **S8:** [SecIdentityCreate](https://developer.apple.com/documentation/security/secidentitycreate(_:_:_:)), [SecIdentityCreateWithCertificate](https://developer.apple.com/documentation/security/secidentitycreatewithcertificate(_:_:_:)), [DER certificate import](https://developer.apple.com/documentation/security/seccertificatecreatewithdata(_:_:)). Availability and declarations were read through Apple's corresponding official DocC JSON resources.
- **S9:** [swift-certificates 1.20.0 release](https://github.com/apple/swift-certificates/releases/tag/1.20.0), [public native-key initializer](https://github.com/apple/swift-certificates/blob/1.20.0/Sources/X509/CertificatePrivateKey.swift), [native signing implementation](https://github.com/apple/swift-certificates/blob/1.20.0/Sources/X509/SecKeyWrapper.swift), [package manifest](https://github.com/apple/swift-certificates/blob/1.20.0/Package.swift).
- **S10:** [Kotlin 2.4.20 Random and seeded constructors](https://github.com/JetBrains/kotlin/blob/v2.4.20/libraries/stdlib/src/kotlin/random/Random.kt), [JVM `asKotlinRandom` adapter](https://github.com/JetBrains/kotlin/blob/v2.4.20/libraries/stdlib/jvm/src/kotlin/random/PlatformRandom.kt). The live-generator requirement is PartyDeck's security design; the source establishes the seeded algorithm and available adapter.
- **S11:** [kotlinx.coroutines 1.11.0 `withContext` documentation/source](https://github.com/Kotlin/kotlinx.coroutines/blob/1.11.0/kotlinx-coroutines-core/common/src/Builders.common.kt): prompt cancellation on return dispatch discards the result; its “Returning closeable resources” section describes this ownership hazard.
- **S12:** [Apple Security `SecTrust.c`](https://github.com/apple-oss-distributions/Security/blob/main/OSX/sec/Security/SecTrust.c), [anchor-only trust](https://developer.apple.com/documentation/security/sectrustsetanchorcertificatesonly(_:_:)), [SSL policy](https://developer.apple.com/documentation/security/secpolicycreatessl(_:_:)). Source checked on the review date: `SecTrustSetNetworkFetchAllowed` writes `kSecPolicyCheckNoNetworkAccess` into the policies, `SecTrustSetPolicies` replaces those policies, and `SecTrustCopyCertificateChain` first evaluates if necessary. The order of these calls therefore matters even before the final trust evaluation.
- **S13:** [Java `Socket.setSoTimeout` contract](https://docs.oracle.com/en/java/javase/21/docs/api/java.base/java/net/Socket.html#setSoTimeout(int)): the configured timeout limits a blocking `InputStream.read()` call and leaves the socket valid on expiry; it does not specify an overall TLS-handshake deadline.
