# Android tester APK

Maintainers can run **Publish Android preview APK** from the Actions tab on
`main`, or use:

```sh
gh workflow run android-preview-release.yml --ref main
```

The workflow builds the full PartyDeck debug APK with Standard initially selected
and both real Godot styles explicitly enabled for testing. It checks JVM behavior,
Android lint, the actual APK signature/alignment, native phone library, activation
metadata and source-matching renderer pack. An API36 emulator installs and
cold-launches the exact APK and exercises the existing Standard practice checks.

Only a successful build/check job can publish. The separate publication job
receives `contents: write`, downloads that run's checked assets, verifies checksums
and source metadata, uploads to a draft, and publishes it as a prerelease. The
tag `android-preview-<run-id>-<publication-attempt>` points to the exact built
commit; retries create distinct releases instead of replacing an earlier tester
APK. Retrying only a failed publication can reuse this run's successful build
artifact by its exact artifact ID. Build metadata preserves the original build
attempt; a different source, run or future build attempt is rejected.

Download `PartyDeck-android-preview.apk` from the repository's
[Releases page](https://github.com/Apdelrahman1911/PartyDeck/releases). Android
may require allowing installation from the browser or file manager. This is
a debug-signed preview; a different key on a future build can require uninstalling
the previous version, which clears local settings. Production credentials are
not used or required. The workflow does not retain the debug signing key.

In a game, use **Table style** to compare **Standard**, **2D** and **3D**. For
multiplayer, everyone needs the same build and reachable Wi-Fi, and the host must
keep the app open. The standalone Godot comparison APK is a separate practice
tool; this release contains the real PartyDeck host/join app.

Physical phone/LAN testing and native Godot interaction/performance acceptance
remain open. This workflow does not grant production or store qualification.
Send feedback through repository issues with the release tag, device, Android
version, table style and reproduction steps. Keep live invitations private.

The workflow reuses the project's researched/pinned Actions and Android tools.
Release CLI behavior and permission requirements were checked against
[gh release create](https://cli.github.com/manual/gh_release_create),
[gh release edit](https://cli.github.com/manual/gh_release_edit), and
[GitHub's job token permissions](https://docs.github.com/en/actions/writing-workflows/workflow-syntax-for-github-actions#jobsjob_idpermissions).
