# PartyDeck Godot comparison

The user requested real **2D and 3D versions of Last Light**, built in parallel,
with both retained for hands-on comparison. This work is active; neither version
is yet claimed production-qualified. The previously validated Compose application
continues to provide the existing product baseline.

## Architecture

Both presentations consume the same recipient-safe views and emit player
intents. The existing Kotlin `core` authority validates actions and owns all game
randomness. The renderer receives its player's hand, public opponent counts and
legitimate challenge reveals; it never receives authoritative state, other hands,
future penalty results, or network admission/reconnect credentials.

The KMP shell owns navigation, networking, settings and lifecycle. Godot owns
only the active game's graphics, local animation and input. Android and iOS
embedding are separate qualification gates. An exported Godot-owned iOS app is
not evidence that an existing KMP app can own and dispose of a native Godot view.

## Parallel ownership

All implementation and review agents use **gpt-6-astra, max reasoning**.

| Owner | Files | Deliverable |
| --- | --- | --- |
| Coordinator | `qualification/`, module Gradle files, this plan, workflows | Isolated builds, integration, CI and delivery |
| `ui_game` | `renderer/`, excluding `assets/`, `licenses/` and `presentations/two_d/` | Verified Godot installation, shared scene runtime and 3D presentation |
| `ui_shell` | `renderer/presentations/two_d/` | Complete 2D presentation using the same bridge |
| `game_domain` | `bridge/`, excluding Gradle | Strict versioned codec, safe adapter, authority driver and focused tests |
| `network_transport` | `android-host/`, excluding Gradle | Real Android Godot host, native event bridge and 2D/3D launch choices |
| `ios_platform` | `ios-host/` | Actual iOS embedding probe and documented supported/unsupported lifecycle behavior |
| `assets` | `renderer/assets/`, `renderer/licenses/`, `tools/prepare_assets.py` | Shared artwork, fonts, sound, engine/native notices and source inventory |
| `app_controller` | `comparison/`, excluding Gradle | Playable desktop comparison harness and common authority scenarios |
| `session_protocol` | `tools/`, excluding `prepare_assets.py` | Reproducible import, PCK export and separate preview commands |
| `android_platform` | `android-checks/` | Actual Android entry, input, background, exit and re-entry verification |
| `engine_ci` | Existing baseline CI/scripts and assigned evidence | Complete existing Android qualification alongside Godot work |
| `review_game` | Assigned bridge/game review files in `reviews/` | Independent privacy, codec, revision and action review |
| `review_design` | `reviews/design-review.md` | Fair visual/input comparison and mobile accessibility review |
| `review_environment` | `reviews/environment-review.md` | Independent installation, build and export verification |
| `review_release` | `reviews/release-review.md` | Exact dependency, license and artifact audit |
| `review_security` | `reviews/security-review.md` | Source-only trust-boundary and lifecycle review |

Owners coordinate contracts before crossing boundaries. Local Gradle runs use
`flock /tmp/partydeck-gradle.lock`; the coordinator commits explicit completed
paths. Renderer, bridge, native hosts, assets, tools and reviews can progress
independently after agreeing the wire contract. Integration tests depend on their
real artifacts; native runtime claims require execution.

## Build isolation

`qualification/settings.gradle.kts` imports the production version catalog and
references existing `core` and `games` sources without modifying them. New
`:bridge`, `:androidHost` and `:comparison` projects live here. Every module writes outputs under
`qualification/build/modules/<projectName>`, including the referenced projects,
so comparison work does not overwrite the production build's outputs.

From the repository root:

```sh
flock /tmp/partydeck-gradle.lock ./gradlew -p godot/qualification projects
flock /tmp/partydeck-gradle.lock ./gradlew -p godot/qualification :bridge:jvmTest
```

Both real presentations now complete the same full desktop match, including
challenge outcomes, winner, lobby return and a fresh entry. Their complete
authority traces match. Run either presentation interactively with the
[desktop comparison launcher](comparison/README.md); its `--presentation 2d`
and `--presentation 3d` options select the same rules with different graphics.
The [renderer instructions](renderer/README.md) explain scene checks and
[export tooling](tools/README.md) verifies the packed inputs.

The [Android comparison host](android-host/README.md) builds a standalone
local-practice APK with **Play Last Light · 2D** and **Play Last Light · 3D**
choices and an explicit repeatable reference match.

Session attachment is also implemented in the actual PartyDeck Android and iOS
apps. Their shipping profiles currently expose only Standard table; both Godot
styles require an explicit qualification build. Follow the
[Android session preview](android-host/README.md#production-session-preview)
or the [iOS comparison app instructions](../iosApp/README.md#compare-2d-and-3d).
In an enabled game, **Table style** offers **2D table** and **3D table**;
returning to **Standard table** preserves the same session. Native lifecycle,
mobile accessibility, physical-device and multiplayer qualification remain
separate gates. The [iOS probes](ios-host/README.md) retain their separate
embedding and retained-engine evidence.

Captured screenshots are preserved in the
[review gallery](../docs/screenshots/README.md), with original image files,
source/evidence links, explicit review status, and labeled failed or superseded iterations. Current
progress and remaining production gates are recorded in
[the status report](../docs/STATUS.md).

## Acceptance

1. Verify official engine and AAR pins, import both scenes, and export their real
   resources reproducibly. Record actual package sizes and hashes.
2. Pass common bridge tests: malformed/oversized messages, exact revision and
   sequence handling, replay/lifetime rejection, hidden information and legal
   authority actions. Both renderers use the same schema and rule engine.
3. Run the same scenarios through 2D and 3D: hidden/revealed hand, selection,
   claim, challenge, truthful/bluff outcome, round progression, winner and leave.
   Preserve actual input/capture evidence and comparison launch instructions.
4. Prove native entry, event round trip, background concealment, exit/re-entry
   and teardown; no active engine in the home/lobby. Test each supported host
   independently and report source-only/export-only evidence accurately.
5. Review visual hierarchy, touch targets, responsive layout, safe areas,
   reduced motion and sound. Standard table remains the accessible gameplay
   route. Verify its actual TalkBack/VoiceOver behavior and the native controls
   for returning to it; Godot's desktop accessibility support does not establish
   mobile screen-reader acceptance.
6. Deliver both independently selectable previews. Keep both implementations
   until the user chooses. A later production renderer must also pass the
   existing physical-device, multiplayer, performance and publisher gates.

## Verified dependency sources

- [Godot 4.7.2 release](https://github.com/godotengine/godot/releases/tag/4.7.2-stable)
- [Official Android Maven metadata](https://repo.maven.apache.org/maven2/org/godotengine/godot/maven-metadata.xml)
- [Exact Android AAR POM](https://repo.maven.apache.org/maven2/org/godotengine/godot/4.7.2.stable/godot-4.7.2.stable.pom)
- [Gradle catalog imports](https://docs.gradle.org/current/userguide/version_catalogs.html)
- [Platform research and qualification limits](../docs/research/engine-ci.md)
