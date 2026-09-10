# Real Android comparison checks

`run.py` drives the shipped native chooser and real Godot controls with adb. It
reads the host's app-private, read-only evidence and independently checks native
processes, correlated scene observations, rendered captures and input results.
Host-only tests establish the checker's rejection behavior; Android qualification
requires an actual APK/device run and review of its retained images.

## Run against a scheduled emulator

Use Python 3.11+, adb, a real qualification APK containing
`assets/partydeck-last-light.pck`, and a dedicated portrait Android emulator.
The current capture path requires API 33+ and the standard Launcher3 Overview
panel. The intended CI profile is standard API 35, KVM, 720×1600, 280 dpi and
OpenGL ES 3 support for Godot's `gl_compatibility` renderer. The runner checks the
actual display and surface geometry; it does not infer phone density from a
desktop window size.

```sh
python3 -B godot/android-checks/run.py \
  --serial emulator-5554 \
  --apk godot/qualification/build/modules/androidHost/outputs/apk/debug/androidHost-debug.apk \
  --output /tmp/partydeck-godot-android-2d \
  --mode 2d \
  --font-scale 1.0
```

Use the artifact's actual path if the build names it differently. The output
directory must be new or empty. `--mode` accepts `2d`, `3d` or `both` (default).
`--font-scale` accepts `1.0` (default) or `2.0`. Separate emulator invocations for
each mode/scale preserve independent failure evidence. `both` runs sequentially
and stops on a failed check or unclean teardown.

The runner performs the baseline's strict boot/HOME readiness checks, installs
and clears only `dev.partydeck.godot.compare`, and verifies the installed APK's
hash against the selected file. It does not start/reboot an emulator, build an
APK, dismiss a crash/system shade, search seeds, or relaunch a failed scenario.
The caller owns emulator creation and cleanup. Device settings are restored
even if capture or diagnostics fail; the original runtime error remains in the
result. Failure state is retained for inspection until caller cleanup.

## What must happen

The visible native **Reference scenario** checkbox selects the existing Kotlin
authority's fixed seed 2. The runner also selects reduced motion and disables
sound through the real native checkboxes. Normal interactive matches continue
to use native secure randomness.

For each selected presentation, the checker requires:

1. A fresh `:godot` PID/presentation and a surviving separate chooser; actual
   setup, main loop, plugin Ready, native foreground delivery and rendered-frame
   facts; a current correlated diagnostic response and a concealed hand.
2. Real reveal, first-card selection and hide touches. Selection and private
   bindings must change as observed, without an authority event or revision.
3. HOME and actual Launcher3 Overview entry with the native cover active, then
   focus of the same Android task. PID/presentation must survive and fresh
   resumed diagnostics must show zero private bindings and zero selection.
4. Actual play, challenge and next-round intents accepted by the existing
   authority. The canonical scenario ends in round 14 at revision 41, with two
   viewer plays, two viewer challenges and 13 advances. Observed outcomes are
   retained; unobserved truthful/bluff coverage is not invented.
5. Winner-to-chooser navigation, including the 2D confirmation; complete native
   destruction facts; absence of the actual old PID and engine process; no
   upstream renderer-exit timeout; the original chooser with both entries usable.
6. Two predetermined fresh entries. One exercises scene Exit through the
   native bridge. The other exercises the native Close button for 2D or Android
   Back for 3D. Each must again destroy the engine and preserve the chooser.

Every scene touch uses a fresh diagnostic's full control rectangle and its
ancestor clip rectangle. A target must fit wholly inside the clip and mapped
native surface. Bounded real swipes can bring clipped controls into view; they
do not directly set scene scroll offsets. Native touches reuse the baseline's
app-owned viewport checks. Pre-input logs contain numeric geometry, fixed
control identifiers and lifecycle counters, without hand IDs/ranks or field text.

Each diagnostic refresh uses one visible native request and requires a newer
request ID and scene sequence with the host's current authority revision. Missing
or stale evidence, rejected authority input, a crash, a retained private binding,
an alive old PID, missing native teardown markers, or collection/restore failure
cannot produce a successful result.

The checker has a 600-second setup budget, a 600-second budget for each selected
mode, and a 180-second diagnostic/restore budget. Individual entry waits are
45 seconds, ordinary response waits 30 seconds and teardown waits 25 seconds;
all device commands are capped by the enclosing budget. A target allows at most
16 swipes and stops after stationary geometry. Match progression allows at most
300 authority actions, within the same mode budget. These are failure bounds,
not promises of normal execution time. CI must also impose its own process limit.

## Evidence and limits

`result.json` records the aggregate outcome, selected cases, source/APK/embedded
PCK hashes, installed APK hash, device/access facts, steps and original failure.
Mode results identify each presentation and PID. Each mode/entry directory holds
host observations, scene input geometry, process-specific live logcat, screenshots
and UI trees, public outcome/counter evidence, and final teardown evidence. Native
input geometry and final system diagnostics remain at the output root. Exit 0
requires every selected case and cleanup check to pass.

Inspect `06-recents-privacy.png` and the concealed/revealed/resumed/game/outcome
captures independently. Native cover observations, the Recents policy flag and
cleared resumed bindings are checked automatically; no generic pixel classifier
proves that a Recents thumbnail contains no private material. Non-flat engine
pixels and changed reveal captures detect missing render evidence, without
replacing visual review. The Godot scene buttons are not Android accessibility
nodes; this does not establish TalkBack support. This local practice harness does
not qualify production sessions, physical LAN behavior or store signing.

Default `--evidence-access run-as` requires the debuggable qualification APK.
An optimized APK can later use explicit `--evidence-access root` only on a
separately scheduled, already-rooted `userdebug`/`eng` emulator. The runner verifies
Android user 0, `ro.debuggable=1` and adbd's UID 0, then reads the same private file
at `/data/user/0/dev.partydeck.godot.compare/files/godot-qualification.json`.
It never calls `adb root`, marks a release debuggable, changes app exports, or
adds an external diagnostic endpoint. The result labels privileged observation;
support on a particular image still requires execution evidence. API 26–32 keep
the host's secure-window privacy; this capture qualification does not bypass it.

## Host-only checks

```sh
python3 -B -m unittest discover -s godot/android-checks -p 'test_*.py' -v
```

These tests include stale/wrong-lifetime diagnostics, missing native round trips,
retained hidden bindings, clipping/density mapping, corrupt/flat PNGs, an alive
old PID, missing teardown callbacks, a replaced chooser, crashes, bounded waits,
and preservation of the original failure during cleanup. Replay devices never
run a simulated authority or claim Android runtime recovery.

## Checked platform contracts

- [Exact Godot 4.7.2 Android source artifact](https://repo.maven.apache.org/maven2/org/godotengine/godot/4.7.2.stable/godot-4.7.2.stable-sources.jar):
  `Godot.kt` owns `destroyAndKillProcess`, native termination and the explicit
  1500 ms renderer-exit timeout. Callback flags alone do not prove process death.
- [Android 15 ActivityManager shell source](https://android.googlesource.com/platform/frameworks/base/+/refs/tags/android-15.0.0_r1/services/core/java/com/android/server/am/ActivityManagerShellCommand.java):
  `task focus TASK_ID` focuses the existing task, avoiding a duplicate engine
  Activity during resume.
- [Android 15 Activity source](https://android.googlesource.com/platform/frameworks/base/+/refs/tags/android-15.0.0_r1/core/java/android/app/Activity.java):
  `setRecentsScreenshotEnabled(false)` concerns Recents representation; the host
  still permits foreground captures on API 33+.
- [Android 15 toybox pidof source](https://android.googlesource.com/platform/external/toybox/+/refs/tags/android-15.0.0_r1/toys/lsb/pidof.c):
  an empty exit 1 means no matching process; adb failures are not process absence.
- [Godot CanvasItem coordinate API](https://docs.godotengine.org/en/stable/classes/class_canvasitem.html#class-canvasitem-method-get-global-transform-with-canvas)
  and [Control clipping](https://docs.godotengine.org/en/stable/classes/class_control.html#class-control-property-clip-contents)
  define the root-viewport rectangles recorded by the real renderer.
