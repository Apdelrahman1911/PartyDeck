# Independent security review

Review owner: `review_security`. Research checked on 2026-09-09. This is an independent architecture assessment and an implementation review record, not a cryptographic audit or evidence of physical-device qualification.

## Architecture recommendation

Use a host-authoritative common session layer over small platform TLS adapters: Android `SSLServerSocket`/`SSLSocket`, Apple `NWListener`/`NWConnection` with TLS. Exchange the full SHA-256 host-certificate fingerprint through the room invitation and verify it before sending any admission or reconnect credential. Use native DNS-SD only to locate candidate rooms. Keep framing, game messages, and authorization separate from TLS and discovery.

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

The proposed application-frame ceiling is 64 KiB, checked before payload allocation by transport and independently by the codec. Length zero, overflow, truncation, malformed UTF-8, unsupported versions, unknown fields/types, excessive nesting, and duplicate decoded JSON field names must be rejected. Escaped forms such as `"type"` and `"\u0074ype"` count as the same field. Tests must include nesting inside unexpected fields and delimiters inside strings.

Schema limits are also necessary: display-name length and controls, identifier/token lengths, maximum card selections, player count, and error sizes. A byte ceiling alone does not prevent excessive object creation or expensive malformed payloads. Never log raw frames or parser exception messages containing attacker-controlled text.

Bound concurrent TLS handshakes, pre-admission connections, receive and send queues, discovery candidates, rejected-request rates, and connection attempts. Use finite connect/handshake/partial-frame deadlines. Capacity must be enforced before starting another reader/task. One stalled or flooding peer must not stall the host actor or allocate an unbounded backlog. The final implementation should expose small named constants and tests; ordinary six-player traffic does not need large queues.

### Lifecycle

Subscribe to incoming events before advertising/listening is exposed. Each socket has one receive owner and serialized writes. Failure in a peer task must close that peer without cancelling unrelated peers or the host session actor. Closing a room must stop accepting, stop discovery, revoke bindings, close sockets, release platform listeners/locks, and cancel owned work; repeated close must be safe.

Treat pin mismatch and TLS authentication failure as terminal for that attempt, never as reasons to try plaintext or trust another key. Reconnect must reuse the original host pin and seat credential for the same room. Host background suspension, path changes, and process termination require explicit state transitions; a network status callback alone does not prove a healthy game connection. Device behavior remains a separate qualification task.

## Implementation review record

Architecture research is complete. Code-level findings and independently run test results will be recorded here as the implementation lands. No implementation has yet been approved by this review.

| Finding | Evidence and resolution | Status |
| --- | --- | --- |
| SEC-01: deterministic live secret randomness | The first `PlatformServices` contract exposed `secureSeed(): Long`, encouraging `LastLightEngine(Random(seed))`. The coordinator/controller accepted changing it to `gameRandom(): Random` backed by per-output native secure randomness. Domain API remains unchanged. | Contract corrected; platform implementations still to verify |

| Area | Evidence required | Current status |
| --- | --- | --- |
| TLS/pinning | Real handshake succeeds with the invited certificate; altered pin fails before credentials or gameplay; no plaintext fallback. | Pending implementation |
| Platform bridge | Compile the exact Apple SDK/package; connect Android/JVM TLS to the Apple TLS listener in both host directions. | Pending implementation |
| Projection | Adversarial recipient and serialized-message tests exclude every unauthorized private field. | Pending implementation |
| Parser | Malformed UTF-8, lengths, truncation, decoded duplicate keys, depth, unknown fields/types, and field/collection bounds. | Pending implementation |
| Identity/replay | Stale socket, wrong credential, resume/disconnect race, ID conflict, cache eviction, session mismatch, and integer exhaustion. | Pending implementation |
| Resource ownership | Handshake flood, slow partial frame, full queues, per-peer failure isolation, repeated start/stop, cancellation during setup. | Pending implementation |
| Mobile network behavior | Physical Android/iOS cross-host play, network permission denial, background/foreground, network change, host loss. | External/device qualification required |

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
