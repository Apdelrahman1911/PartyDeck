# Compare the real Last Light renderers

This isolated desktop runner plays both real Godot presentations through the
same existing Kotlin authority implementation and bridge. Each automated run
starts a fresh `QualificationAuthorityDriver` with the same seed/roster and
requires the complete authority-view trace to match between 2D and 3D. The fixed
automated seed is **2**, audited through the real driver to include both viewer
play and viewer challenge before a complete winner. No game
rules, outcomes, accepted moves, or snapshots are implemented in the harness.

The runner scrolls actual controls into view, rejects a target that remains
partially clipped, and injects mouse motion, press, and release events through
Godot at its real button position. It never calls gameplay controller methods to make a
test pass. Reveal, selection, and concealment must remain local; play,
challenge, continuation, lobby and exit travel through the actual renderer
events and the shared adapter. The scenario manifest is [scenarios.json](scenarios.json).

## Build and run

Use Linux with the repository's [build prerequisites](../../README.md#build-and-run)
and verified Godot 4.7.2 executable. This runner explicitly selects X11 and
OpenGL compatibility. Its automatic editor installer supports Linux x86_64.
Without a display, install/use Xvfb; the runner automatically launches
`xvfb-run` when `DISPLAY` is absent. Interactive play needs a visible desktop
session; Xvfb runs are useful for automated captures.

From the repository root, install the pinned editor and prepare the packed
resources before building the launcher:

```sh
python3 godot/tools/renderer.py install
bash scripts/prepare-godot-renderer.sh
flock /tmp/partydeck-gradle.lock ./gradlew -p godot/qualification :comparison:installDist --console=plain

godot/qualification/build/modules/comparison/install/partydeck-godot-compare/bin/partydeck-godot-compare \
  --godot godot/qualification/build/toolchain/godot \
  --pack godot/qualification/build/renderer/partydeck-last-light.pck \
  --presentation both --size 430x932
```

The runner finds the repository from its working directory, or accepts
`--repository /absolute/path/to/PartyDeck`. `--output` selects a fresh evidence
directory; existing reports are not overwritten. `--size`, `--text-scale`,
`--seed`, and `--seconds` select a bounded comparison configuration. Run `--help`
for all options. These commands use the PCK, which contains the imported runtime
resources. To run the loose source project, omit `--pack` only after the
[source-project import](../renderer/README.md#run). The packaging tool imports a
temporary copy and does not populate the source project's import cache.

To play either variant directly, use a real desktop display and choose it:

```sh
godot/qualification/build/modules/comparison/install/partydeck-godot-compare/bin/partydeck-godot-compare \
  --pack godot/qualification/build/renderer/partydeck-last-light.pck \
  --presentation 2d --interactive

godot/qualification/build/modules/comparison/install/partydeck-godot-compare/bin/partydeck-godot-compare \
  --pack godot/qualification/build/renderer/partydeck-last-light.pck \
  --presentation 3d --interactive
```

Interactive play uses native `SecureRandom` output for every authority random
request. An explicit `--seed` changes it to a documented, reproducible comparison
session. Other seats use the driver's bounded policy, reading only each seat's
own safe view. Continue is a real host action; round outcomes are never skipped
automatically. Lobby/Leave closes the presentation. This runner owns a local
practice session. The [mobile session adapters](../README.md#build-isolation)
attach the same renderers to the actual PartyDeck app behind qualification
profiles; they have separate native and multiplayer acceptance gates.

The launcher finds the installed editor at
`godot/qualification/build/toolchain/godot`; use `--godot` for another verified
executable. The probe script stays outside the PCK and is passed explicitly by this desktop runner.
Both packaged presentations use the same root bridge entry point.

## Evidence

Each run writes `report.json`, per-renderer `result.json`, `godot.log`, and
actual viewport PNGs with individual `.receipt.json` files. Receipts record the
source commit, working-tree fingerprint, renderer artifact path and PCK SHA-256
when packaged, engine/backend, dimensions, scenario, seed, current safe-view
hash, and image SHA-256. The full report preserves
authority revision hashes and input coordinates. No admission/reconnect
credentials or hidden authoritative state enter this process.

The runner requires normal Godot exit code 0 and no engine/script errors in its
log, and refuses a final pass if sources or the selected PCK change during a run. Earlier images
and a failure report remain available for honest iteration review. Keep each
iteration in a new directory and pass its paths/receipts to the screenshot
gallery owner; root owns publishing reviewed evidence.

Automated captures use Reduce Motion and muted audio for deterministic input
and frames. Interactive play enables ordinary motion and sound preferences in
the renderer, but the launcher always selects Godot's `Dummy` audio driver, so
this desktop harness produces no audible output. Desktop
software-rendered frames demonstrate input/bridge behavior and appearance;
native device accessibility, suspension, touch feel, GPU performance and LAN
behavior still need their own qualification.

## Initial packed milestone

The packed comparison completed successfully on 2026-09-10 from 00:47:44 to
00:48:15 UTC, using the installed launcher after `:comparison:installDist`:

```sh
godot/qualification/build/modules/comparison/install/partydeck-godot-compare/bin/partydeck-godot-compare \
  --godot /opt/partydeck-godot/4.7.2-stable/Godot_v4.7.2-stable_linux.x86_64 \
  --pack godot/qualification/build/renderer/partydeck-last-light.pck \
  --presentation both --seed 2 --size 430x932 --xvfb \
  --output godot/qualification/build/comparison/matched-packed-20260910
```

That evidence directory is retained locally; use a new `--output` for another
run. Its `report.json`, `2d/result.json`, and `3d/result.json` record:

| Result | 2D | 3D |
| --- | --- | --- |
| Authority snapshots in the full match | 42 | 42 |
| Viewer plays / challenges | 2 / 2 | 2 / 2 |
| Actual round advances | 13 | 13 |
| Renderer bridge events, including fresh entry/exit | 21 | 21 |
| Probe requests before graceful quit | 129 | 129 |
| Captured PNGs with individual receipts | 11 | 11 |
| Renderer exit code | 0 | 0 |

Both complete authority traces are exactly equal, with SHA-256
`79b5b2a6415a365d531da3488b7b87f1b2309f2b1208899ee5b4618da16be674`.
Both logs contain no engine/script errors. All 22 PNG hashes match their
receipts. The run exercised actual input, concealment and foreground privacy,
pending actions, real round outcomes and winner, lobby return, a fresh scene
and presentation identity, and Exit. The pack ran through the external probe
under real X11/OpenGL compatibility rendering (Mesa llvmpipe).

The tested PCK SHA-256 is
`2c840bb8a20177aaed657cf5ae6f0bcee74964bc591d269ed741cd9e58365e35`.
The source commit was `e1ee4fb7d498449035181515dd7f40899b2b6c2f` with a dirty
working tree; the recorded source fingerprint was
`26426170ab4341d7ff72b3b387b3f70f5938376d0285f216d102fb27689f9637`.
The report and every screenshot receipt preserve these identifiers. The
screenshot gallery owner received every PNG and receipt for independent review
and publication.

Earlier `first-real-2d-input` evidence remains preserved as an iteration that
passed gameplay assertions but reported a shutdown error. Its old `passed`
field does not qualify clean shutdown. The matched packed run above includes
the corrected quit-reply drain and process-exit checks.

## Final packed renderer qualification

The final renderer updates passed the same real-input comparison on 2026-09-10,
from 02:01:32 to 02:02:03 UTC:

```sh
godot/qualification/build/modules/comparison/install/partydeck-godot-compare/bin/partydeck-godot-compare \
  --godot /opt/partydeck-godot/4.7.2-stable/Godot_v4.7.2-stable_linux.x86_64 \
  --pack godot/qualification/build/renderer/partydeck-last-light.pck \
  --presentation both --seed 2 --size 430x932 --xvfb \
  --output godot/qualification/build/comparison/matched-packed-v5-20260910
```

Both presentations again completed 42 identical authority snapshots, two viewer
plays, two viewer challenges, thirteen continuations, lobby return, fresh entry
and Exit. Each produced 21 renderer events and 11 PNGs, then exited with code 0.
Both complete logs contain no engine/script errors; all 22 image hashes match
their receipts. The full authority trace SHA-256 remains
`79b5b2a6415a365d531da3488b7b87f1b2309f2b1208899ee5b4618da16be674`.

The exact tested final PCK SHA-256 is
`0b3de6b276d15972708cfc7919d7f2f5bf2aefe8a05afb8859357e7139057d37`.
The source commit was `19501a23606c44ffd94eba3b24855a239e703a74` with a dirty
working tree; the stable source fingerprint was
`642422de487b33a6dc2951d8a9a178c5a40737bf0e80bb6831fa197116cda515`.
The report and every receipt retain these values. The gallery owner received
all 22 final PNGs and receipts for independent review and publication. The
initial PCK, receipt and logs were archived before replacement under
`godot/qualification/build/renderer/milestone-6457270`; earlier screenshots and
reports remain in their original run directories.

## Local probe boundary

The JVM runner binds only `127.0.0.1` on an ephemeral port. Its child Godot probe
connects once and proves a fresh 32-byte random token. Frames are four-byte
big-endian lengths plus UTF-8 JSON, capped at 131,072 bytes, with at most 16
queued renderer events/frames. Inner bridge commands retain the shared 65,536
byte bound and renderer events the shared 4,096 byte bound. Startup, writes,
requests, input steps and the complete child lifetime have explicit deadlines.
Partial socket reads/writes never block the Godot frame thread. Both sides close
their channel and child processes on completion or failure.

Only the probe knows the test operations (`document`, `state`, `click`,
`capture`, `reset`, `quit`). The shared renderer remains transport-free.
`receive_document` and `bridge_event` carry the normal frozen bridge schema;
read-only state/diagnostics verify local privacy and hit regions separately.

## Checked sources

Research used the actual bridge [contract](../bridge/CONTRACT.md), Kotlin driver,
renderer controller/main scripts, and these tagged authoritative sources before
choosing the harness interfaces:

- [Godot 4.7.2 StreamPeerSocket](https://github.com/godotengine/godot/blob/4.7.2-stable/doc/classes/StreamPeerSocket.xml),
  [StreamPeerTCP](https://github.com/godotengine/godot/blob/4.7.2-stable/doc/classes/StreamPeerTCP.xml),
  and [StreamPeer](https://github.com/godotengine/godot/blob/4.7.2-stable/doc/classes/StreamPeer.xml):
  explicit polling/status and partial, bounded reads/writes.
- [Input.parse_input_event](https://github.com/godotengine/godot/blob/4.7.2-stable/doc/classes/Input.xml)
  and [CanvasItem coordinates](https://github.com/godotengine/godot/blob/4.7.2-stable/doc/classes/CanvasItem.xml):
  real engine input routing and local-to-viewport transforms. This injects
  Godot input, without pretending to exercise operating-system touch delivery.
- [ScrollContainer.ensure_control_visible](https://github.com/godotengine/godot/blob/4.7.2-stable/doc/classes/ScrollContainer.xml)
  and [Rect2 enclosure/intersection](https://github.com/godotengine/godot/blob/4.7.2-stable/doc/classes/Rect2.xml):
  scroll newly laid-out controls on a later frame, then require their complete
  transformed bounds inside the root/ancestor clip regions with 1px rounding tolerance.
- [Viewport capture](https://github.com/godotengine/godot/blob/4.7.2-stable/doc/classes/Viewport.xml)
  and [RenderingServer.force_draw](https://github.com/godotengine/godot/blob/4.7.2-stable/doc/classes/RenderingServer.xml):
  an early texture may be blank/stale; the main-thread probe forces a fresh
  draw before capture. The 2D owner confirmed that waiting for a future
  `frame_post_draw` alone can stall a static low-processor scene.
- [Godot OS user arguments](https://github.com/godotengine/godot/blob/4.7.2-stable/doc/classes/OS.xml):
  explicit `--` separates comparison parameters from engine options.
- [OpenJDK 21 SocketChannel](https://github.com/openjdk/jdk21u/blob/master/src/java.base/share/classes/java/nio/channels/SocketChannel.java),
  [ServerSocketChannel](https://github.com/openjdk/jdk21u/blob/master/src/java.base/share/classes/java/nio/channels/ServerSocketChannel.java),
  and [ProcessHandle](https://github.com/openjdk/jdk21u/blob/master/src/java.base/share/classes/java/lang/ProcessHandle.java):
  nonblocking local IO, explicit accepted-channel configuration, and bounded
  cleanup of owned child processes. No new dependency/version was added.
