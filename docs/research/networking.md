# PartyDeck networking decision

Research date: 2026-09-09. This is a decision based on primary sources, not a claim that physical devices have already passed qualification.

## Decision

Use a host-authoritative star topology over ordinary, mutually reachable LAN TCP, secured by the operating system's TLS implementation. One host has one independently encrypted connection per guest. The shared Kotlin transport owns bounded framing, cancellation, operation deadlines and lifecycle state. Small native adapters own sockets, TLS identities and DNS-SD. The session module owns player admission, game messages, validation, revisions, deduplication and resume credentials.

Android/JVM use JSSE `SSLServerSocket` / `SSLSocket`. The Android adapter uses `NsdManager`; no Wi-Fi scan, Bluetooth or hotspot provisioning is needed. iOS uses Swift `NWListener`, `NWConnection` and `NWBrowser`. iOS code is injected through a plain Kotlin callback interface, with coroutine/Flow adaptation kept in the shared transport. This avoids a second iOS-only game/session implementation.

The host generates an ephemeral self-signed certificate. Guests verify its **complete SHA-256 fingerprint from an out-of-band invitation** during the TLS handshake. The invitation also carries the session's high-entropy lobby admission credential. A public mDNS record, host name, short display code or certificate received from the network is never the source of trust. TLS provides encryption and independent traffic keys for each connection; knowing the lobby admission credential does not let one guest decrypt another guest's cards or impersonate the pinned TLS host.

The coordinator and independent security reviewer accepted this route. Do not implement bespoke encryption, a custom Noise implementation, trust-all certificate validation, or plaintext fallback.

## Verified implementation building blocks

| Area | Verified source and API | Consequence |
| --- | --- | --- |
| Android/JVM TLS | [JSSE reference](https://docs.oracle.com/en/java/javase/17/security/java-secure-socket-extension-jsse-reference-guide.html), `SSLContext`, `SSLServerSocket`, `SSLSocket`, `X509TrustManager` | Native TLS, explicit minimum TLS 1.2, a leaf-certificate pinning trust manager on outgoing connections. Certificate generation is separate from the TLS implementation. |
| Certificate construction on Java | [Bouncy Castle 1.85 POM](https://repo.maven.apache.org/maven2/org/bouncycastle/bcpkix-jdk18on/1.85/bcpkix-jdk18on-1.85.pom), [official repository](https://github.com/bcgit/bc-java) | `bcpkix-jdk18on:1.85` is published, supports Java 1.8+, and can use native cryptographic providers. Use its X.509 builder with JCA P-256 keys; do not install a global replacement security provider. |
| Optional Android key storage | [KeyGenParameterSpec](https://developer.android.com/reference/android/security/keystore/KeyGenParameterSpec) | AndroidKeyStore can generate a valid self-signed certificate when key signing purpose, digests and validity permit it. This is an alternative to the shared Java ephemeral certificate builder, not an assumed API. |
| Apple certificate generation | [Swift Certificates 1.20.0 release](https://github.com/apple/swift-certificates/releases/tag/1.20.0), [private-key source](https://github.com/apple/swift-certificates/blob/1.20.0/Sources/X509/CertificatePrivateKey.swift) | Stable release published 2026-09-01; `Certificate.PrivateKey(SecKey)` wraps a Security-framework key. Product `X509`; package has a Swift 6.1 tools manifest. |
| Apple TLS identity | [SecIdentityCreate](https://developer.apple.com/documentation/security/secidentitycreate(_:_:_:)), [sec_identity_create](https://developer.apple.com/documentation/security/sec_identity_create(_:)), [set local identity](https://developer.apple.com/documentation/security/sec_protocol_options_set_local_identity(_:_:)) | `SecIdentityCreate(nil, certificate, privateKey)` is documented on iOS 11.2+, converts a matching certificate/key into `SecIdentity`, then into the identity consumed by Network TLS options. This avoids assuming the macOS-only `SecIdentityCreateWithCertificate` works on iOS. |
| Apple networking | [Choosing the right networking API, TN3151](https://developer.apple.com/documentation/technotes/tn3151-choosing-the-right-networking-api), [Apple custom peer game sample](https://developer.apple.com/documentation/network/building-a-custom-peer-to-peer-protocol) | Network.framework is Apple's recommended TCP/TLS and Bonjour API; both listeners and connections are supported. The sample demonstrates Bonjour+TLS game transport. Its passcode/PSK scheme is not our authentication design. |
| Android DNS-SD | [Use network service discovery](https://developer.android.com/develop/connectivity/wifi/use-nsd) | `NsdServiceInfo`, `registerService`, `discoverServices` and resolution provide interoperable DNS-SD. Handle service-name collision callbacks and explicitly stop discovery/unregister advertising. |

## Alternatives evaluated

### P2pKit

Inspected the [official repository](https://github.com/p2pKit/P2pKit), the [published RC3 release](https://github.com/p2pKit/P2pKit/releases/tag/v0.7.0-rc3), the actual Apple/JVM/Android source and the [Maven publication metadata](https://repo.maven.apache.org/maven2/io/github/apdelrahman1911/p2p-transport-lan/0.7.0-rc3/p2p-transport-lan-0.7.0-rc3.module). RC3's source commit is `deed9e77b81b6f1082519f44804de038eb5dcc0e`.

P2pKit is an active Apache-2.0 KMP project with real Android/JVM and iOS implementations. RC3 publishes Android, JVM, `iosArm64`, `iosSimulatorArm64` and `iosX64` variants. Its published metadata requires Kotlin 2.4.10 and coroutines 1.11.0. Android/JVM discovery uses JmDNS; Apple discovery and TCP use Network.framework. It supplies bounded records, keepalive, outgoing reconnect, persistent identities and authenticated v2 transport using `Noise_XX_25519_ChaChaPoly_SHA256`. Its default `RejectUnknown` authorization requires the full trusted peer fingerprint. `AcceptAnyAuthenticatedSameApp` proves key possession and encrypts but requires separate application admission. The explicit plaintext-v1 mode is not a secure substitute.

These features fit PartyDeck in principle. Integration behind a transport interface would be straightforward, and its low-rate messaging is sufficient for a card game. Godot does not need a direct dependency: the shell would deliver coarse session events to a game bridge.

However, RC3 explicitly leaves Android physical-device, Apple device/background/path-change, hostile-network, independent protocol interoperability and professional cryptographic audit campaigns pending. These are upstream claims of incomplete evidence, not tests completed by PartyDeck. See its [validation status](https://github.com/p2pKit/P2pKit/blob/main/docs/testing/validation-status.md) and [security model](https://github.com/p2pKit/P2pKit/blob/main/docs/security/model.md).

The inspected post-RC3 main tree also changes 165 core/transport source and test files, with over 21,000 added lines relative to RC3. Relevant changes include terminal secure-record error propagation, abandoned-handshake cleanup, bounded admission, strict JSON parsing, connection ownership and reconnect behavior. Some additions are tests and unrelated file-transfer work; the line count is not a vulnerability count. It does establish that current-main fixes and automation cannot be represented as validation of the published RC. Using a moving snapshot or vendoring a young transport stack would add a maintenance obligation without a clear advantage over platform TLS for this small application.

**Decision: do not use P2pKit for the first shipping transport.** Reconsider a future stable, qualified release behind the same adapter boundary. Do not describe the project as abandoned or as lacking iOS support; neither claim is supported.

### Ktor

The [official latest stable release](https://github.com/ktorio/ktor/releases/tag/3.5.2) is 3.5.2. [Server engine documentation](https://ktor.io/docs/server-engines.html) lists Native support for CIO, and the [client engine guide](https://ktor.io/docs/client-engines.html) documents Darwin's `NSURLSession` client. Therefore, claiming Ktor has no Native server would be incorrect.

However, [CIOApplicationEngine at the 3.5.2 tag](https://github.com/ktorio/ktor/blob/3.5.2/ktor-server/ktor-server-cio/common/src/io/ktor/server/cio/CIOApplicationEngine.kt) explicitly throws `UnsupportedOperationException` for HTTPS connectors. Its own [raw-socket guide](https://ktor.io/docs/server-sockets.html) labels the socket API experimental and documents TLS as a client operation. A shared CIO WebSocket server does not supply an encrypted iOS host. Adding another platform TLS terminator would retain the native-adapter work and add HTTP/WebSocket machinery that this turn-based protocol does not require.

**Decision: no Ktor dependency for LAN gameplay.** This does not preclude using its HTTP client for a future unrelated service.

### Other paths

- MultipeerConnectivity does not provide an Android peer. Current [Apple TN3151](https://developer.apple.com/documentation/technotes/tn3151-choosing-the-right-networking-api) also records its 2026 deprecation and recommends Network.framework. Apple's undocumented peer-to-peer Wi-Fi wire protocol only interoperates between Apple devices; do not promise cross-platform routerless connectivity.
- A room-wide TLS PSK or symmetric encryption key cannot establish an individual host identity against another admitted guest. A low-entropy short passcode also cannot be treated as a strong offline-resistant encryption key. Certificate pinning plus application admission avoids these problems.
- WebRTC, signaling, relays, NAT traversal and cloud accounts are unnecessary for the requested reachable-LAN game.

## Public transport boundary

See `transport/src/commonMain/kotlin/dev/partydeck/transport/LanTransport.kt` for the authoritative names.

- `LanTransportFactory.create()` supplies a new owned `LanTransport`.
- `host(displayName)` returns a `LanHost`, its public endpoints/certificate fingerprint and a bounded stream of TLS-ready incoming connections.
- `connect(endpoint, certificateSha256)` returns only after verifying the pinned host certificate.
- `LanConnection.id` identifies a connection lifetime. It is not a stable player or device identity. The host does not require a client certificate.
- `LanConnection.incoming` is one ordered, bounded message stream; `send()` confirms local write completion only. Protocol acknowledgements, action IDs and state repair live in `:session`.
- Discovery returns untrusted public host/service/address information; it never authenticates the host or supplies an invitation secret.
- `close()` terminates all listeners, browsing, connections, pending operations and owned coroutines. Per-connection close is idempotent.

The iOS callback bridge does not expose Kotlin Flow or a suspend protocol to Swift implementations. Shared Kotlin adapts native operation and byte callbacks to suspending operations and bounded channels. Native code supplies actual TLS and discovery behavior; there is no unsupported iOS stub.

## Pairing and network UX

Host and guests must be mutually reachable on the same LAN; Wi-Fi client isolation can block both discovery and TCP. Existing user-created hotspots may work only when the OS/network allows peer reachability; the application does not create or configure them.

The host invitation is a versioned encoded value containing a direct LAN endpoint, optional Bonjour service identity for rediscovery, the full certificate fingerprint, the session ID and an independently generated admission secret. It contains no individual resume credential. The UI can copy/paste or render/scan this exact string as a QR code when those UI capabilities are implemented. It must not advertise a short numeric code as equivalent security. Never put the invitation secret into a service name or TXT record, logging, telemetry or crash breadcrumbs.

Manual endpoint information in the invitation bypasses multicast discovery. If a host address changes, public discovery may provide a candidate replacement, but the original fingerprint must still match. If the host is recreated and its ephemeral certificate changes, guests need a new invitation. There is no certificate-warning bypass.

## Platform permission and lifecycle requirements

Android ships with target SDK 36 and minimum API 26. [Current Android local-network guidance](https://developer.android.com/privacy-and-security/local-network-permission) says target <=36 uses the `INTERNET` permission and explicitly says not to declare/request `ACCESS_LOCAL_NETWORK` before targeting 37. On target 37+, local access requires that runtime permission; the app must gate host/join/discovery and explain denial. Native NSD does not require an application raw-multicast lock. This route needs no location permission. Android's system NSD picker grants limited selected-device access but does not replace permission for a general incoming host listener.

iOS minimum is 15. [Apple TN3179](https://developer.apple.com/documentation/technotes/tn3179-understanding-local-network-privacy) requires `NSLocalNetworkUsageDescription` and the exact `_partydeck._tcp` service in `NSBonjourServices` for the Bonjour operations used. Start local networking after a user chooses Host or Join so the system prompt has context. The native Bonjour route avoids inventing a custom UDP discovery protocol or requesting the restricted multicast entitlement. Do not hard-code `en0` as the Wi-Fi interface; Apple explicitly warns that interface names are not API.

Neither platform's background behavior should be represented as an uninterrupted host-service guarantee. Keep the game host foreground. On suspension/disconnect, the session layer pauses or follows its documented grace policy. Foreground return establishes a fresh pinned connection and uses the individual resume token; transport does not automatically replay game actions. Host process loss ends the current session; no host migration is implemented.

## Bounds and qualification

Use a four-byte big-endian payload length, a 65,536-byte message ceiling shared with the session codec, bounded pending connections and receive queues, serialized writes, finite TLS/connect/write deadlines and explicit idle detection. Invalid framing, queue overflow, identity mismatch or TLS failure closes the connection. Never fall back to cleartext. Validate length before allocating an attacker-controlled payload buffer.

Linux qualification must exercise actual TLS sockets: two or more clients, pinned connection success, wrong-pin rejection, exact frame boundaries, truncated/oversized frames, slow peers, cancellation and teardown. Common tests exercise fragmentation/coalescing, invitation validation and the callback adapter's ownership behavior. macOS CI must compile the iOS framework and Swift app with the exact certificate package. Real Android-to-iOS and iOS-host-to-Android games, multicast loss, permission denial, backgrounding and network path changes remain device qualification work until executed and recorded. Passing a JVM fake or an iOS compilation must not be labeled physical interoperability evidence.
