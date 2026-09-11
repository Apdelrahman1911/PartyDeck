"""Host-only wrapper routing/exit tests. Command stubs never start native tools."""

import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import tempfile
import unittest


SCRIPTS = Path(__file__).resolve().parents[1]
REVISION = "a" * 40


def function_source(source, name):
    start = source.index(name + "() {\n")
    return source[start:source.index("\n}\n", start) + 3]


class ShippingWrapperTest(unittest.TestCase):
    def invoke(self, *, profile="shipping", modes="2d,3d", raw=None,
               session=False, adaptive=False, selection_only=False, failures=None):
        with tempfile.TemporaryDirectory(prefix="partydeck-shipping-wrapper-host-") as temporary:
            root = Path(temporary)
            scripts = root / "scripts"
            scripts.mkdir()
            shutil.copy2(SCRIPTS / "android_godot_activation.py", scripts)
            output = root / "build/ci/android"
            for name in ("debug", "optimized-test-signed"):
                (output / name).mkdir(parents=True)
            expectation = output / "godot-activation-build.json"
            expectation.write_bytes(raw if raw is not None else json.dumps({
                "schemaVersion": 1, "profile": profile, "modesCsv": modes,
            }).encode())
            recorder = (
                "import json, os, sys\nfrom pathlib import Path\n"
                "def record(event):\n"
                "    with Path('calls.jsonl').open('a') as stream: stream.write(json.dumps(event) + '\\n')\n"
            )
            # Synthetic command receipts exercise shell sequencing and pipefail only.
            # No production checker, SDK, build, package, emulator or device is executed.
            (scripts / "smoke-android-godot-shipping.py").write_text(recorder +
                "phase = sys.argv[1]\nargs = dict(zip(sys.argv[2::2], sys.argv[3::2]))\n"
                "variant = args['--variant']\n"
                "record({'kind': phase, 'variant': variant, 'arguments': sys.argv[2:]})\n"
                "status = int(os.environ.get('HOST_FAIL_' + phase + '_' + variant, '0'))\n"
                "if status == 0 and phase == 'record-inputs':\n"
                "    with Path(args['--inputs']).open('x') as stream: stream.write('host-only receipt\\n')\n"
                "if phase == 'run' and not Path(args['--inputs']).is_file(): sys.exit(81)\n"
                "sys.exit(status)\n")
            (scripts / "smoke-android-ui.py").write_text(recorder +
                "args = dict(zip(sys.argv[1::2], sys.argv[2::2]))\nvariant = args['--variant']\n"
                "record({'kind': 'ui', 'variant': variant})\n"
                "sys.exit(int(os.environ.get('HOST_FAIL_ui_' + variant, '0')))\n")
            (scripts / "qualification-host-stub.py").write_text(recorder +
                "record({'kind': 'qualification', 'variant': sys.argv[1], 'arguments': sys.argv[2:]})\n"
                "sys.exit(int(os.environ.get('HOST_FAIL_qualification_' + sys.argv[1], '0')))\n")
            preparation = scripts / "prepare-android-runtime-apk.sh"
            preparation.write_text("#!/usr/bin/env python3\n" + recorder +
                "record({'kind': 'signing-preparation'})\n"
                "sys.exit(int(os.environ.get('HOST_FAIL_signing', '0')))\n")
            preparation.chmod(0o700)
            binary = root / "bin"
            binary.mkdir()
            adb = binary / "adb"
            adb.write_text("#!/usr/bin/env python3\n" + recorder +
                           "record({'kind': 'uninstall-host-stub', 'arguments': sys.argv[1:]})\n")
            adb.chmod(0o700)
            source = (SCRIPTS / "smoke-android-emulator.sh").read_text()
            selection = source[source.index("select_godot_shipping_smoke() {\n"):
                               source.index('if [[ "$PARTYDECK_ANDROID_GODOT_ADAPTIVE_SMOKE" == 1 ]]; then')]
            prefix = "set -euo pipefail\n" + "\n".join((
                "PARTYDECK_ANDROID_OUTPUT=" + shlex.quote(str(output)),
                "PARTYDECK_SOURCE_REVISION=" + REVISION,
                "PARTYDECK_EMULATOR_SERIAL=host-only-no-device",
                "PARTYDECK_ANDROID_API=36",
                "PARTYDECK_ANDROID_GODOT_SESSION_SMOKE=" + str(int(session)),
                "PARTYDECK_ANDROID_GODOT_ADAPTIVE_SMOKE=" + str(int(adaptive)),
            )) + "\n"
            if selection_only:
                script = prefix + selection + '\nprintf "%s" "$PARTYDECK_ANDROID_GODOT_SHIPPING_SMOKE"\n'
            else:
                script = prefix + selection + "\n" + function_source(source, "run_godot_shipping_phase") + (
                    "\nrun_godot_session_smoke() { python3 scripts/qualification-host-stub.py \"$@\"; }\n"
                ) + source[source.index("\nPARTYDECK_DEBUG_STATUS=0\n"):]
            wrapper = root / "wrapper.sh"
            wrapper.write_text(script)
            environment = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", PATH=str(binary) + os.pathsep + os.environ["PATH"])
            for key in tuple(environment):
                if key.startswith("HOST_FAIL_"):
                    del environment[key]
            environment.update({"HOST_FAIL_" + key: str(value) for key, value in (failures or {}).items()})
            result = subprocess.run(["bash", str(wrapper)], cwd=root, env=environment,
                                    capture_output=True, text=True, timeout=20)
            calls = root / "calls.jsonl"
            report = output / "runtime-variants.json"
            return (result, [json.loads(line) for line in calls.read_text().splitlines()] if calls.exists() else [],
                    json.loads(report.read_text()) if report.exists() else None)

    def test_actual_shipping_receipt_selects_both_modes_or_empty_baseline(self):
        for modes, selected in (("2d,3d", "1"), ("", "0")):
            with self.subTest(modes=modes):
                result, calls, _ = self.invoke(modes=modes, selection_only=True)
                self.assertEqual(0, result.returncode, result.stderr)
                self.assertEqual(selected, result.stdout)
                self.assertEqual([], calls)

    def test_subset_qualification_and_ambiguous_receipts_fail_before_commands(self):
        cases = [dict(modes="2d"), dict(modes="3d"), dict(profile="qualification"),
                 dict(raw=b'{"schemaVersion":1,"profile":"shipping","profile":"shipping","modesCsv":"2d,3d"}'),
                 dict(raw=b" " * 4097)]
        for change in cases:
            with self.subTest(change=change):
                result, calls, report = self.invoke(**change)
                self.assertNotEqual(0, result.returncode)
                self.assertEqual([], calls)
                self.assertIsNone(report)

    def test_explicit_qualification_and_adaptive_routes_do_not_read_shipping_receipt(self):
        for flags in (dict(session=True), dict(adaptive=True)):
            with self.subTest(flags=flags):
                result, calls, _ = self.invoke(raw=b"not a shipping receipt", selection_only=True, **flags)
                self.assertEqual(0, result.returncode, result.stderr)
                self.assertEqual("0", result.stdout)
                self.assertEqual([], calls)

    def test_both_variants_bind_before_ui_and_optimized_binding_follows_signing(self):
        result, calls, report = self.invoke()
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual([
            ("record-inputs", "debug"), ("ui", "debug"), ("run", "debug"),
            ("signing-preparation", None), ("record-inputs", "optimized-test-signed"),
            ("uninstall-host-stub", None), ("ui", "optimized-test-signed"), ("run", "optimized-test-signed"),
        ], [(call["kind"], call.get("variant")) for call in calls])
        receipts = {}
        for call in calls:
            if call["kind"] not in ("record-inputs", "run"):
                continue
            arguments = call["arguments"]
            values = dict(zip(arguments[::2], arguments[1::2]))
            self.assertEqual(REVISION, values["--source-revision"])
            self.assertEqual("build/ci/android/godot-activation-build.json", values["--build-expectation"])
            self.assertEqual("godot/qualification/build/renderer/partydeck-last-light.pck", values["--renderer-pack"])
            self.assertNotIn("--engine-gameplay", arguments)
            self.assertNotIn("--engine-package-inputs", arguments)
            self.assertNotIn("--modes", arguments)
            variant = call["variant"]
            if call["kind"] == "record-inputs":
                receipts[variant] = values["--inputs"]
                self.assertNotIn("--serial", values)
            else:
                self.assertEqual(receipts[variant], values["--inputs"])
                self.assertEqual("1.0", values["--font-scale"])
                self.assertEqual("host-only-no-device", values["--serial"])
            if variant == "optimized-test-signed":
                self.assertTrue(values["--signing-receipt"].endswith("/packages/runtime-package.json"))
                self.assertEqual("androidApp/build/outputs/apk/release/androidApp-release-unsigned.apk", values["--unsigned-apk"])
            else:
                self.assertNotIn("--signing-receipt", values)
                self.assertNotIn("--unsigned-apk", values)
        self.assertTrue(report["passed"])
        self.assertFalse(report["godotSessionSmoke"]["requested"])
        shipping = report["godotShippingSmoke"]
        self.assertTrue(shipping["requested"] and shipping["allRequestedPhasesPassed"])
        self.assertFalse(shipping["qualificationObservationRequested"] or shipping["engineGameplayRequested"])

    def test_ordinary_failure_does_not_hide_independent_native_or_other_variant_result(self):
        result, calls, report = self.invoke(failures={"ui_debug": 7, "run_optimized-test-signed": 9})
        self.assertEqual(1, result.returncode)
        self.assertEqual(7, report["debugExitCode"])
        self.assertEqual(0, report["optimizedTestSignedExitCode"])
        shipping = report["godotShippingSmoke"]
        self.assertEqual(0, shipping["debugPhaseExitCode"])
        self.assertEqual(9, shipping["optimizedTestSignedPhaseExitCode"])
        self.assertEqual(2, sum(call["kind"] == "run" for call in calls))
        self.assertFalse(report["passed"] or shipping["allRequestedPhasesPassed"])

    def test_each_input_failure_blocks_only_its_native_phase_and_remains_in_summary(self):
        for variant, field in (("debug", "debug"), ("optimized-test-signed", "optimizedTestSigned")):
            with self.subTest(variant=variant):
                result, calls, report = self.invoke(failures={"record-inputs_" + variant: 5})
                self.assertEqual(1, result.returncode)
                shipping = report["godotShippingSmoke"]
                self.assertEqual(5, shipping[field + "InputExitCode"])
                self.assertIsNone(shipping[field + "PhaseExitCode"])
                self.assertFalse(report["passed"])
                self.assertEqual(2, sum(call["kind"] == "ui" for call in calls))
                runs = [call["variant"] for call in calls if call["kind"] == "run"]
                self.assertEqual(["optimized-test-signed" if variant == "debug" else "debug"], runs)

    def test_signing_failure_preserves_debug_and_does_not_record_unprepared_optimized_input(self):
        result, calls, report = self.invoke(failures={"signing": 13})
        self.assertEqual(1, result.returncode)
        self.assertEqual(13, report["optimizedTestSignedExitCode"])
        shipping = report["godotShippingSmoke"]
        self.assertEqual(0, shipping["debugPhaseExitCode"])
        self.assertIsNone(shipping["optimizedTestSignedInputExitCode"])
        self.assertIsNone(shipping["optimizedTestSignedPhaseExitCode"])
        self.assertFalse(any(call.get("variant") == "optimized-test-signed" for call in calls))

    def test_nonzero_runner_status_survives_log_pipeline_and_final_aggregate(self):
        result, _, report = self.invoke(failures={"run_debug": 124})
        self.assertEqual(1, result.returncode)
        self.assertEqual(124, report["godotShippingSmoke"]["debugPhaseExitCode"])
        self.assertEqual(0, report["godotShippingSmoke"]["optimizedTestSignedPhaseExitCode"])
        self.assertFalse(report["passed"])

    def test_empty_shipping_baseline_runs_only_the_ordinary_variants(self):
        result, calls, report = self.invoke(modes="")
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual([("ui", "debug"), ("ui", "optimized-test-signed")],
                         [(call["kind"], call["variant"]) for call in calls if "variant" in call])
        self.assertFalse(report["godotShippingSmoke"]["requested"])
        self.assertIsNone(report["godotShippingSmoke"]["allRequestedPhasesPassed"])
        self.assertTrue(report["passed"])

    def test_qualification_keeps_both_existing_phases_and_renderer_death_option(self):
        result, calls, report = self.invoke(profile="qualification", session=True)
        self.assertEqual(0, result.returncode, result.stderr)
        qualification = [call for call in calls if call["kind"] == "qualification"]
        self.assertEqual(["debug", "optimized-test-signed"], [call["variant"] for call in qualification])
        self.assertNotIn("--skip-renderer-death", qualification[0]["arguments"])
        self.assertIn("--skip-renderer-death", qualification[1]["arguments"])
        self.assertTrue(report["godotSessionSmoke"]["allRequestedPhasesPassed"])
        self.assertFalse(report["godotShippingSmoke"]["requested"])


if __name__ == "__main__":
    unittest.main()
