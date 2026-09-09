# PartyDeck privacy and local multiplayer

Last reviewed: **2026-09-09**. This document records the intended first-release
behavior and the audit needed to turn it into an accurate published policy.
Implementation is in progress. It is not yet a verified store privacy declaration.

## Data needed to play

PartyDeck is designed for local multiplayer, with one player's device hosting
the room. The host runs the game rules and holds the authoritative match state.
The design does not require a PartyDeck account or a PartyDeck-operated server.

| Information | Purpose and intended recipients | Intended retention |
| --- | --- | --- |
| Chosen display name and room membership | Identify players to the host and other room participants | Current session; saved nickname preferences must be listed if implemented |
| Local network address and connection metadata | Connect participating devices and detect connection loss | Active connections; no application telemetry or address history is intended |
| Invitation and admission information | Allow intended players to join the correct host | Room lifetime; sharing it grants room access according to the implemented protocol |
| Private seat/resume capability | Authenticate a returning player without giving away their seat | Session lifetime; any persistent implementation needs a separate secure-storage audit |
| Game actions and public results | Let the host validate moves and tell all participants what happened | Current match/session |
| Private cards and future random outcomes | Let the host enforce the game; each player receives only their own current hand | Authoritative host memory and the applicable player's current view |
| Audio, haptic, motion, and other preferences | Remember choices on that device | Until changed or app data is removed, if persistence is implemented |

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

The final transport and security review must establish exactly how host
authentication, encryption, invitations, and reconnection work. **Do not claim
encrypted transport, end-to-end encryption, or protection from other Wi-Fi users
until the implemented protocol and packaged builds have been verified.** The
host's authority over game secrets remains even with an encrypted connection.

Share invitations only with the people intended to join. Treat a reconnect
capability as a credential: it must not be shown in public lobby text, included
in screenshots or analytics, or written to ordinary logs. Public bug reports
should omit real invitations, network addresses, and personal display names.

## Local storage and optional services

The release design has no advertising, analytics, crash-reporting upload,
account, payment, location, contacts, microphone, or camera feature. These are
design constraints that must be checked against the final dependency graph and
runtime behavior. A future SDK or feature that transmits data requires this
document and the store answers to be updated before release.

Inspect settings storage, Android backup configuration, iOS preferences/keychain
usage, debug logging, crash output, and session cleanup in the final build.
State whether a nickname is remembered, whether a reconnect survives process
death, and how a person can erase saved data. Do not promise secure deletion of
information held or recorded by another participant.

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
