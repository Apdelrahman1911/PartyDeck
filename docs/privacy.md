# PartyDeck privacy and local multiplayer

Last reviewed: **2026-09-09**. This document records the inspected first-release
implementation and the remaining audit needed for a published policy. Native
settings, invitation actions, and scanners have been inspected in source. The
Android packages at `c73a659` passed manifest/resource inspection. iOS native
TLS/UI tests and an optimized device build passed, while its packaged inventory
awaits a successful artifact upload. Android emulator subflows confirmed hand
concealment and settings persistence within an overall failed smoke run.
Physical-network checks remain open. Artifact hashes and executed evidence are
recorded in [release qualification](release-qualification.md).
This is not yet a store privacy declaration.

## Data needed to play

PartyDeck is designed for local multiplayer, with one player's device hosting
the room. The host runs the game rules and holds the authoritative match state.
The design does not require a PartyDeck account or a PartyDeck-operated server.

| Information | Purpose and recipients in the inspected implementation | Retention |
| --- | --- | --- |
| Chosen display name and room membership | Identify players to the host and other room participants; a host's display name also appears in public local discovery | Membership is held in session memory; the selected nickname is saved on that device |
| Bonjour/NSD service record | Advertise the host's name, service identifier, protocol version, address and port to devices on the local network | While hosting; no admission secret, certificate pin, hand, or reconnect capability is included |
| Local network address and connection metadata | Connect participating devices and detect connection loss | Active transport memory; no application address-history store was found |
| Invitation and admission information | Allow intended players to join the correct host | App form/session memory; sharing it grants room access according to the implemented protocol |
| Camera preview and decoded invitation | Optional on-device QR scan after the person chooses Scan; the decoded invitation fills the Join form | Preview only while scanning; no scanner image recording or upload path was found |
| Copied or shared invitation | The system clipboard or apps the person explicitly chooses in the share sheet | Controlled by the operating system and selected recipient, outside PartyDeck's session cleanup |
| Private seat/resume capability | Authenticate a returning player without giving away their seat | Session memory; absent from both native preference stores |
| Game actions and public results | Let the host validate moves and tell all participants what happened | Current match/session |
| Private cards and future random outcomes | Let the host enforce the game; each player receives only their own current hand | Authoritative host memory and the applicable player's current view |
| Sound, haptic, and reduced-motion preferences | Remember choices on that device | Until changed or app data is removed |

The application must not publish another player's remaining cards, the ranks
of an unchallenged claim, future fuse outcome, random seed, or resume capability
to other participants. A challenged play is intentionally revealed to the room.

The host is trusted: its device necessarily holds all hands and authoritative
random outcomes. The application cannot prevent a modified host from inspecting
that state, or prevent another participant from photographing, recording, or
remembering information they can see.

## Network access and protection

Local-network access is used to host or join a room. iOS may ask for local-network
permission; denying it can prevent joining until access is enabled in Settings.
Permission behavior must be verified on a real device. Android permissions
depend on the shipped target SDK and actual transport. [1][2]

The inspected transport uses TLS and checks the complete SHA-256 host-certificate
fingerprint carried in the invitation before sending admission or reconnect
credentials. Public discovery does not establish a trusted host identity.
Android/JVM socket and session tests have executed. Three native iOS TLS tests
also passed, covering ordered frames/cleanup, wrong-pin rejection, and actual
Java–Swift exchanges in both host directions on simulator/host loopback.
Physical Android/iPhone LAN behavior remains unverified. See
[security review](security-review.md) and [release qualification](release-qualification.md)
for the checks and their limits.
The host retains authority over game secrets even with an encrypted connection.

Share invitations only with the people intended to join. Treat a reconnect
capability as a credential: it must not be shown in public lobby text, included
in screenshots or analytics, or written to ordinary logs. Public bug reports
should omit real invitations, network addresses, and personal display names.

Scanning is optional; pasting an invitation remains available. Camera permission
is requested in the scanner flow, and cancelling or denying a scan must leave
the existing Join form unchanged. A successful scan fills the form rather than
automatically joining. QR images shown by the host contain the shareable room
invitation, never a player's private reconnect capability. These behaviors must
also be confirmed in the packaged Android and iOS apps. The inspected Android
scanner decodes a bounded luminance buffer and closes every analyzed camera
image. The iOS scanner consumes AVFoundation QR metadata and has no photo/video
file output; it hides the preview and stops capture when its scene is inactive.
Android binds capture to the scanner Activity's lifecycle and stops analyzer
delivery when that Activity stops. Both tear capture down when the scanner closes.

Copy and Share deliberately pass the room invitation to the operating system.
iOS requests a local-only clipboard item with a two-minute expiration; Android
marks it sensitive on API 33 and later. These requests do not erase a copy that
a person or another app has already saved. System share recipients and clipboard
retention are outside PartyDeck's session cleanup.

## Local storage and optional services

The inspected release source has no advertising, analytics, crash-reporting
upload, account, payment, location, contacts, or microphone feature. Final
Android manifests contain only Internet, optional-scanner Camera, and an
AndroidX signature permission. The automatic EmojiCompat downloadable-font
initializer and unused network-state permission were removed; packaged startup
metadata contains only lifecycle and profile initialization. This package
inspection does not replace observing native network behavior. A future SDK or
feature that transmits data requires this document and store answers to be
updated before release.

The inspected Android settings implementation stores the display name and the
sound, haptic, and reduced-motion choices in app-private preferences. iOS uses
this app's own UserDefaults for the same values. Neither preference store
contains a hand, admission secret, or resume capability. Android's manifest and
extraction rules exclude app data from cloud backup and device transfer. iOS
preferences remain subject to the operating system's ordinary backup behavior;
the app does not place game credentials in them. Apple's UserDefaults
documentation explicitly includes persistent defaults databases in device
backups. [7]

Temporary backgrounding retains the app owner, while a client connection is
closed and can reconnect with its in-memory seat capability on return. Permission
dialogs that only interrupt interaction are tracked separately from actual OS
backgrounding. Host process death ends the room; the implementation does not
restore a match or seat from disk. Runtime controller tests cover cleanup, stale
connection events, and permission interruption. In the optimized Android
emulator run, returning from background concealed the practice hand, removed
private-card accessibility nodes, and cleared selection. That run later failed
an unrelated text-entry step; actual phone suspension, app-switcher images, and
process-death behavior remain release gates.
Saved preferences can be changed in the app or removed through the operating
system's app-data deletion controls. On iOS, offloading an app is different from
deleting its data. [8] Do not promise secure deletion of information held or recorded
by another participant.

The iOS app privacy manifest currently declares app-owned UserDefaults reason
`CA92.1`, app/container file timestamp reason `C617.1`, and elapsed-time/timer
reason `35F9.1`. Their permitted uses were checked against Apple's published
reason catalog. [9] Final framework/archive inspection must still verify all
required-reason API use and dependency manifests.

## Store privacy audit

The absence of a central server does **not** by itself justify selecting “no
data collected.” Local multiplayer transmits information to another device;
Google and Apple define their form questions differently.

- Google Play says data transmitted off-device and processed ephemerally still
  belongs in the form response, even when qualifying ephemeral data is omitted
  from the public Data safety section. Its on-device exception is for processing
  that stays on the user's own device. Its end-to-end encryption exception has
  explicit readability/key-access requirements. Assess the actual local peer
  flow against those definitions; do not assume either exception applies. [3]
- Apple's definition of collection considers transmission that lets the
  developer or third-party partners access data longer than needed to service
  the request in real time. Audit all SDKs and features, including gameplay
  content, against that definition before completing App Privacy. [4]
- An Apple privacy manifest and the App Store privacy answers are separate
  deliverables. Required-reason APIs must have accurate allowed reasons in the
  applicable bundle; third-party SDK manifests must be included where required.
  Inspect the final archive and Xcode's aggregated privacy report. Do not add
  reason codes by guessing, or leave arrays empty merely because there is no
  analytics SDK. [5][6]

Before public distribution, replace intended behavior above with the verified
data inventory; publish a stable publicly accessible policy; add the publisher's
identity, effective date, and privacy contact; provide an in-app route to it; and
complete store disclosures for the signed release. These publication/account
details require the publisher's confirmation. They do not prevent implementing
and testing the application.

## Sources

Official sources accessed on 2026-09-09:

[1]: https://developer.apple.com/documentation/technotes/tn3179-understanding-local-network-privacy
[2]: https://developer.android.com/privacy-and-security/local-network-permission
[3]: https://support.google.com/googleplay/android-developer/answer/10787469?hl=en
[4]: https://developer.apple.com/app-store/app-privacy-details/
[5]: https://developer.apple.com/documentation/bundleresources/describing-data-use-in-privacy-manifests
[6]: https://developer.apple.com/documentation/bundleresources/describing-use-of-required-reason-api
[7]: https://developer.apple.com/documentation/foundation/userdefaults
[8]: https://support.apple.com/en-us/108429
[9]: https://developer.apple.com/documentation/bundleresources/app-privacy-configuration/nsprivacyaccessedapitypes/nsprivacyaccessedapitypereasons
