# Short 3D public-context regression

Apply `candidate.patch` to `godot/renderer/tests/three_d_scene_check.gd`. It adds the opt-in `--check-short-public-context=true` assertion and shares the existing scroll-before-click code with that assertion. The normal scene input/privacy checks still run.

Use an authority-generated PLAYING launch with a current claim. The demonstrated input is the existing `ordinary-claim-launch.json` from the source-fix bundle: revision 10, round 4, CROWN, Orbit's one-card claim, with Play and Challenge projected. Its SHA-256 is `e2ebe47a74369422fe9c45feb4836d757a5e3bd5238a1c3aaaa3b980be533671`. An unchanged private copy and the existing authority generation recipe/provenance are in `inputs/`; the check does not fabricate or accept an action.

With the already-imported renderer, run from the repository root during an admitted Godot window:

```sh
flock -n /tmp/partydeck-godot.lock \
  flock -n artifacts/evidence-storage/shm-evidence-arena-20260910/bulk-io.lock \
  xvfb-run -a -s '-screen 0 1280x1600x24' \
  godot/qualification/build/toolchain/godot --path godot/renderer \
  --rendering-method gl_compatibility --display-driver x11 --audio-driver Dummy \
  --resolution 389x215 --position 0,0 \
  --script res://tests/three_d_scene_check.gd -- --manual-bridge --presentation=3d \
  --check-fixture=/absolute/path/to/ordinary-claim-launch.json \
  --check-output=/absolute/path/to/fresh-evidence \
  --check-width=389 --check-height=215 --check-text-scale=2.0 \
  --check-short-public-context=true
```

The check uses native scroll positioning, as the existing click helper does. It checks a nonempty body viewport, the recipient view's current round and claim/guidance text, every non-whitespace character's bounds through ancestor clipping, and each projected action's full rectangle at a reachable scroll position. The Play button may correctly be disabled before card selection. The check restores the initial body scroll before the existing real mouse-input checks proceed.

The private `run_pair.py pair-v1` execution held both nonblocking locks across baseline and fixed runs, enforced fresh memory/disk admission, sampled live floors/output size, and bounded each child to 90 seconds. The exact executed arguments, hashes, samples and exit codes are in `runs/pair-v1/`. This runner is evidence tooling only and is not proposed for the repository or CI.

The logical 389 × 215 desktop window catches the layout regression without density adapters. Exact physical 681 × 377 / density 1.75 rendering, gestures and visual review remain in the separately sealed source-fix bundle at `/tmp/partydeck-3d-context-fit-20260911-_jvzo1j7/`. This check does not qualify native accessibility, device input, authority-accepted actions, or physical-network behavior.
