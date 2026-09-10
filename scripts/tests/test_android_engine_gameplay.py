"""Host regressions for strict observation/input boundaries; no device qualification."""

import ast
from contextlib import redirect_stderr, redirect_stdout
import copy
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET
import zipfile


SCRIPTS = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("partydeck_engine_gameplay_tests", SCRIPTS / "smoke-android-godot-session.py")
smoke = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = smoke
SPEC.loader.exec_module(smoke)
observation = smoke.engine_observation


def control(role="reveal", slot=-1, *, selected=False, enabled=True, visible=True):
    return dict(role=role, slot=slot, rect=[10, 20, 200, 50], clip=[0, 0, 400, 600],
                visible=visible, enabled=enabled, selected=selected)


def snapshot():
    return dict(schemaVersion=1, mode="2d", request="1", sequence="1", generation="3", command="2", input="0",
                projectionRevision="7", requestedUptimeMs=1000, capturedUptimeMs=1050, expiresUptimeMs=13050,
                surface=[0, 300, 800, 1200], viewport=[400, 600], sceneStateApplied=True,
                handConcealed=True, selectedCount=0, privateFaceCount=0, privateLabelCount=0,
                controls=[control()])


def parse(value):
    return observation.parse(json.dumps(value), "2d", [800, 1600])


class ObservationSchemaTests(unittest.TestCase):
    def test_exact_sanitized_schema_and_native_origin_mapping(self):
        value = parse(snapshot())
        self.assertEqual(set(value), observation.FIELDS)
        self.assertEqual([220, 390], observation.touch_point(value, value["controls"][0]))
        self.assertEqual(smoke.PACKAGE, observation.PACKAGE)
        self.assertEqual(smoke.NATIVE_COMPONENT, observation.NATIVE_COMPONENT)

    def test_unknown_private_fields_and_roles_never_become_observations(self):
        for field in ("presentationId", "sessionId", "playerId", "cardId", "cardRank", "label", "texturePath"):
            with self.subTest(field=field), self.assertRaises(observation.ObservationFailure):
                parse(snapshot() | {field: "private-sentinel"})
            value = snapshot()
            value["controls"][0][field] = "private-sentinel"
            with self.subTest(control=field), self.assertRaises(observation.ObservationFailure):
                parse(value)
        value = snapshot()
        value["controls"][0]["role"] = "private-sentinel"
        with self.assertRaises(observation.ObservationFailure):
            parse(value)

    def test_loose_duplicate_nonfinite_and_oversized_json_fails(self):
        good = json.dumps(snapshot())
        bad = [good[:-1] + ', "request":"2"}', good.replace('"role": "reveal"', '"role":"reveal", "role":"play"'),
               good.replace('"schemaVersion": 1', "'schemaVersion': 1"), "/* comment */" + good,
               good.replace('"schemaVersion": 1', '"schemaVersion": NaN'), good + " " * 8192,
               good.replace('"mode": "2d"', '"mode": "\\ud800"'), "[" * 2000 + "]" * 2000]
        for raw in bad:
            with self.subTest(raw=raw[:30]), self.assertRaises(observation.ObservationFailure):
                observation.parse(raw, "2d", [800, 1600])

    def test_counter_types_canonical_form_and_overflow_fail(self):
        for field in observation.COUNTERS:
            for value in (None, True, 1, -1, "", "01", "-1", "+1", "1.0", "1e0", str(1 << 63)):
                with self.subTest(field=field, value=value), self.assertRaises(observation.ObservationFailure):
                    parse(snapshot() | {field: value})

    def test_timeouts_expiry_and_noninteger_timestamps_fail(self):
        for change in ({"capturedUptimeMs": 999}, {"capturedUptimeMs": 3000, "expiresUptimeMs": 15000},
                       {"expiresUptimeMs": 13051}, {"requestedUptimeMs": True}, {"capturedUptimeMs": 1050.0},
                       {"expiresUptimeMs": 1 << 63}):
            with self.subTest(change=change), self.assertRaises(observation.ObservationFailure):
                parse(snapshot() | change)

    def test_scene_application_concealment_and_selection_consistency_fail_closed(self):
        changes = [{"sceneStateApplied": False}, {"sceneStateApplied": 1}, {"handConcealed": "true"},
                   {"selectedCount": 1}, {"privateFaceCount": 1}, {"privateLabelCount": 1},
                   {"privateFaceCount": True}, {"privateLabelCount": 61}]
        for change in changes:
            with self.subTest(change=change), self.assertRaises(observation.ObservationFailure):
                parse(snapshot() | change)
        revealed = snapshot() | dict(handConcealed=False, selectedCount=1, privateFaceCount=5, privateLabelCount=5,
                                     controls=[control("select", 0, selected=True)])
        self.assertEqual(1, parse(revealed)["selectedCount"])
        with self.assertRaises(observation.ObservationFailure):
            parse(revealed | {"selectedCount": 2})

    def test_duplicate_or_unbounded_control_identities_and_action_selection_fail(self):
        cases = [[control(), control()], [control("select", -1)], [control("play", 0)],
                 [control("play", selected=True)], [control("select", i) for i in range(9)]]
        for controls in cases:
            with self.subTest(controls=controls), self.assertRaises(observation.ObservationFailure):
                parse(snapshot() | {"controls": controls})

    def test_surface_geometry_requires_actual_display_and_uniform_mapping(self):
        for change in ({"surface": [-1, 0, 800, 1200]}, {"surface": [0, 300, 801, 1200]},
                       {"surface": [0, 300, 800, 0]}, {"surface": [0, 300, 800.0, 1200]},
                       {"viewport": [400, 500]}, {"viewport": [0, 600]}, {"viewport": [float("inf"), 600]}):
            with self.subTest(change=change), self.assertRaises(observation.ObservationFailure):
                parse(snapshot() | change)

    def test_partial_or_hidden_or_disabled_targets_cannot_be_tapped(self):
        for change in ({"rect": [-1, 20, 200, 50]}, {"rect": [10, 580, 200, 50]},
                       {"visible": False}, {"enabled": False}):
            value = snapshot()
            value["controls"][0].update(change)
            value = parse(value)
            with self.subTest(change=change), self.assertRaises(observation.ObservationFailure):
                observation.touch_point(value, value["controls"][0])

    def test_clip_cannot_escape_viewport_or_claim_empty_visibility(self):
        for change in ({"clip": [-1, 0, 400, 600]}, {"clip": [0, 0, 401, 600]},
                       {"rect": [0, 0, 0, 0]}, {"rect": [0, 0, -1, 5]}, {"visible": 1}):
            value = snapshot()
            value["controls"][0].update(change)
            with self.subTest(change=change), self.assertRaises(observation.ObservationFailure):
                parse(value)

    def test_corrective_swipe_uses_actual_clip_and_bounded_slow_coordinates(self):
        for target in ([10, 640, 200, 50], [-100, 20, 200, 50], [300, 20, 200, 50], [10, -70, 200, 50]):
            value = snapshot()
            value["controls"][0].update(rect=target, visible=False)
            value = parse(value)
            start, end, duration = observation.scroll_gesture(value, value["controls"][0])
            self.assertTrue(350 <= duration <= 1004)
            for x, y in (start, end):
                self.assertTrue(0 < x < 800 and 300 < y < 1500)
            self.assertTrue(abs(end[0] - start[0]) <= 500 and abs(end[1] - start[1]) <= 500)

    def test_scroll_cannot_resurrect_disabled_hidden_or_oversized_controls(self):
        for change in ({"enabled": False}, {"visible": False}, {"rect": [0, 650, 401, 50], "visible": False}):
            value = snapshot()
            value["controls"][0].update(change)
            with self.subTest(change=change), self.assertRaises(observation.ObservationFailure):
                observation.scroll_gesture(value, value["controls"][0])

    def test_every_new_stamp_or_publication_expiry_blocks_real_input(self):
        value = parse(snapshot())
        sample = {"value": value, "requested_host_time": 100.0}
        observation.fresh_for_input(sample, copy.deepcopy(value), 108.999)
        for now in (99, 109, 120):
            with self.assertRaises(observation.ObservationFailure):
                observation.fresh_for_input(sample, value, now)
        for field in observation.COUNTERS:
            changed = value | {field: str(int(value[field]) + 1)}
            with self.subTest(field=field), self.assertRaises(observation.ObservationFailure):
                observation.fresh_for_input(sample, changed, 101)
        changed = copy.deepcopy(value)
        changed["controls"][0]["rect"][0] += 1
        with self.assertRaises(observation.ObservationFailure):
            observation.fresh_for_input(sample, changed, 101)

    def test_settlement_compares_layout_local_state_and_all_currentness_stamps(self):
        value = parse(snapshot())
        fresh = value | dict(request="2", sequence="2", requestedUptimeMs=1600, capturedUptimeMs=1650, expiresUptimeMs=13650)
        self.assertEqual(observation.stable_state(value), observation.stable_state(fresh))
        for field in ("generation", "command", "input", "projectionRevision"):
            self.assertNotEqual(observation.stable_state(value), observation.stable_state(fresh | {field: "42"}))


class InputExecutionTests(unittest.TestCase):
    def probe(self, *, fail_transport=False, clipped=False):
        value = snapshot() | dict(handConcealed=False, selectedCount=1, privateFaceCount=5, privateLabelCount=5,
                                 controls=[control("select", 0, selected=True), control("play")])
        if clipped:
            value["controls"][1].update(rect=[10, 640, 200, 50], visible=False)
        calls = []
        def adb(*args, **kwargs):
            calls.append(args)
            if fail_transport:
                raise subprocess.TimeoutExpired(args, 10)
        probe = object.__new__(observation.EngineObservationProbe)
        probe.play_attempted = False
        probe.smoke = SimpleNamespace(adb=adb)
        probe.settled = lambda predicate, seconds=60: {"value": value}
        probe._before_input = lambda *args: {"file": "host-only-input.xml"}
        return probe, calls, value

    def test_real_play_is_one_coordinate_command_and_timeout_never_authorizes_retry(self):
        probe, calls, _ = self.probe(fail_transport=True)
        with self.assertRaises(subprocess.TimeoutExpired):
            probe.tap("play", lambda value: True)
        with self.assertRaises(observation.ObservationFailure):
            probe.tap("play", lambda value: True)
        self.assertEqual([("shell", "input", "tap", "220", "390")], calls)

    def test_changed_preinput_ownership_prevents_any_tap(self):
        probe, calls, _ = self.probe()
        def reject(*args):
            raise observation.ObservationFailure("Native window changed")
        probe._before_input = reject
        with self.assertRaises(observation.ObservationFailure):
            probe.tap("play", lambda value: True)
        self.assertEqual([], calls)

    def test_unreachable_geometry_gets_at_most_eight_real_swipes_and_no_play(self):
        probe, calls, _ = self.probe(clipped=True)
        with self.assertRaises(observation.ObservationFailure):
            probe.tap("play", lambda value: True)
        self.assertEqual(8, len(calls))
        self.assertTrue(all(call[:3] == ("shell", "input", "swipe") for call in calls))
        self.assertFalse(probe.play_attempted)


class PackageAndCompositionTests(unittest.TestCase):
    def package(self, directory):
        apk = directory / "candidate.apk"
        pack = b"host-only-pack-bytes"
        with zipfile.ZipFile(apk, "w") as archive:
            archive.writestr("assets/partydeck-last-light.pck", pack)
        expected = b'{"schemaVersion":1,"profile":"qualification","modesCsv":"2d,3d"}'
        manifest = (f'<manifest xmlns:android="http://schemas.android.com/apk/res/android" package="{smoke.PACKAGE}"><application>'
                    '<meta-data android:name="dev.partydeck.GODOT_ACTIVATION_PROFILE" android:value="qualification"/>'
                    '<meta-data android:name="dev.partydeck.GODOT_PRESENTATION_MODES" android:value="2d,3d"/>'
                    '</application></manifest>').encode()
        (directory / "activation-build-expectation.json").write_bytes(expected)
        (directory / "packaged-manifest.xml").write_bytes(manifest)
        activation = smoke.activation.parse_build_expectation(expected)
        record = dict(verified=True, variant="debug", sourceRevision="a" * 40, apkSha256=smoke.sha256_file(apk),
                      packSha256=hashlib.sha256(pack).hexdigest(), embeddedPackSha256=hashlib.sha256(pack).hexdigest(),
                      activation=dict(verified=True, manifestCommandExitCode=0, expected=activation, packaged=activation,
                                      expectationSha256=hashlib.sha256(expected).hexdigest(), manifestSha256=hashlib.sha256(manifest).hexdigest()))
        path = directory / "package-inputs.json"
        path.write_text(json.dumps(record))
        output = directory / "output"
        output.mkdir()
        (output / "identity").mkdir()
        return apk, path, record, manifest, SimpleNamespace(variant="debug", output=output)

    def test_exact_apk_pack_receipt_and_fresh_packaged_metadata_are_required(self):
        with tempfile.TemporaryDirectory() as temp:
            apk, path, _, manifest, device = self.package(Path(temp))
            result = subprocess.CompletedProcess([], 0, manifest, b"")
            with patch.dict(smoke.os.environ, {"ANDROID_HOME": "/host-only-sdk"}), patch.object(smoke.subprocess, "run", return_value=result) as run:
                verified = smoke.verify_engine_package_inputs(device, apk, path, "a" * 40)
            self.assertTrue(verified["verified"])
            self.assertEqual(["/host-only-sdk/cmdline-tools/latest/bin/apkanalyzer", "manifest", "print", str(apk)], run.call_args.args[0])

    def test_mismatched_or_shipping_input_cannot_start_engine_qualification(self):
        for change in ({"verified": False}, {"apkSha256": "0" * 64}, {"packSha256": "0" * 64},
                       {"sourceRevision": "b" * 40}, {"variant": "optimized-test-signed"}):
            with tempfile.TemporaryDirectory() as temp:
                apk, path, record, _, device = self.package(Path(temp))
                path.write_text(json.dumps(record | change))
                with patch.object(smoke.subprocess, "run") as run, self.assertRaises((smoke.CheckFailure, observation.ObservationFailure)):
                    smoke.verify_engine_package_inputs(device, apk, path, "a" * 40)
                run.assert_not_called()
        with tempfile.TemporaryDirectory() as temp:
            apk, path, _, manifest, device = self.package(Path(temp))
            result = subprocess.CompletedProcess([], 0, manifest.replace(b'android:value="qualification"', b'android:value="shipping"'), b"")
            with patch.dict(smoke.os.environ, {"ANDROID_HOME": "/host-only-sdk"}), patch.object(smoke.subprocess, "run", return_value=result), self.assertRaises(ValueError):
                smoke.verify_engine_package_inputs(device, apk, path, "a" * 40)

    def test_existing_standard_and_no_action_oracles_remain_exact(self):
        # Hashes are the reviewed Standard dd8723ec source AST, with no line-number attributes.
        expected = {
            "standard_action_outcome": "b63f5370cdd5db29a0532c5a22288942764863334ca9904f85535f3dec8f84af",
            "compare_continuity": "404c7d3ef64db4f725e8ecb85e04626636a5f4c23c5b79a13401d6373f2993f1",
            "play_standard_card": "e294dd8af6b7d374c476bc259875b0fe65d9f13f9e253bd3d29f83e81c249640",
            "require_concealed_return": "e4c9212b3c67b4f07407cc07f4c2e7d0757c893f1d3a0e17a1f94cd0e45639a3",
            "run_mode": "3d3b99fcfbb203f116aba784a18625da2cb8926091f43e3ccab39dee033006ca",
        }
        tree = ast.parse((SCRIPTS / "smoke-android-godot-session.py").read_text())
        actual = {node.name: hashlib.sha256(ast.dump(node, include_attributes=False).encode()).hexdigest()
                  for node in ast.walk(tree) if isinstance(node, ast.FunctionDef) and node.name in expected}
        self.assertEqual(expected, actual)

    def test_engine_oracle_uses_separate_action_proof_and_no_continuity_equality(self):
        tree = ast.parse((SCRIPTS / "smoke-android-godot-session.py").read_text())
        functions = {node.name: node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)}
        names = {node.func.id for node in ast.walk(functions["require_engine_play_return"])
                 if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)}
        self.assertIn("standard_action_outcome", names)
        self.assertNotIn("compare_continuity", names)
        self.assertNotIn("require_concealed_return", ast.unparse(functions["run_engine_gameplay"]))

    def test_qualified_api36_wrapper_actually_invokes_both_flags_with_original_receipt(self):
        wrapper = (SCRIPTS / "smoke-android-emulator.sh").read_text()
        self.assertIn('if [[ "$PARTYDECK_ANDROID_API" == 36 ]]; then', wrapper)
        self.assertIn('engine_arguments=(--engine-gameplay --engine-package-inputs "$output/package-inputs.json")', wrapper)
        self.assertIn('"${engine_arguments[@]}" "$@"', wrapper)
        self.assertIn('runtime_timeout=20m', wrapper)

    def test_main_completes_each_original_mode_before_its_new_engine_practice(self):
        trace = []
        class Replay(smoke.GodotSessionSmoke):
            def setup_session(self, apk):
                trace.append("setup")
            def run_mode(self, mode, skip_renderer_death):
                trace.append("original-" + mode)
            def run_engine_gameplay(self, mode):
                trace.append("engine-" + mode)
            def diagnostics(self):
                return []
            def restore_environment(self):
                return []
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            apk = directory / "host-only.apk"
            apk.write_bytes(b"host-only-mocked-input")
            arguments = ["--serial", "host-only", "--apk", str(apk), "--output", str(directory / "output"),
                         "--source-revision", "a" * 40, "--engine-gameplay", "--engine-package-inputs", str(directory / "package-inputs.json")]
            with patch.object(smoke, "GodotSessionSmoke", Replay), patch.object(smoke, "verify_engine_package_inputs", return_value={"verified": True}), redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                self.assertEqual(0, smoke.main(arguments))
        self.assertEqual(["setup", "original-2d", "engine-2d", "original-3d", "engine-3d"], trace)


if __name__ == "__main__":
    unittest.main()
