#!/usr/bin/env python3
"""Host-only preflight checks; no engine, framework, simulator or app is built."""

import contextlib
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock


HOST = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HOST))
try:
    SPEC = importlib.util.spec_from_file_location("prepare_authority_host", HOST / "prepare-authority-host.py")
    PREPARE = importlib.util.module_from_spec(SPEC)
    SPEC.loader.exec_module(PREPARE)
finally:
    sys.path.pop(0)

PACK_BYTES = b"Synthetic host-test bytes; pack verification is a separate boundary.\n"
PACK_SHA256 = hashlib.sha256(PACK_BYTES).hexdigest()
OTHER_SHA256 = hashlib.sha256(b"Different audited pack").hexdigest()


def declaration(pin=PACK_SHA256):
    return f'static NSString *const PDQualifiedRetainedPackSHA256 = @"{pin}";\n'


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value) + "\n")


class RetainedPinTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory(prefix="partydeck-retained-pin-")
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.runtime = self.root / "PDGodotRuntime.mm"
        self.pack = self.root / "partydeck-last-light.pck"
        self.pack.write_bytes(PACK_BYTES)
        self.verified_pack = PREPARE.file_receipt(self.pack)
        self.runtime.write_text(declaration())

    def check(self):
        return PREPARE.verify_retained_pack_pin(self.runtime, self.pack, self.verified_pack)

    def test_exact_literal_accepts_without_rewriting_source_or_pack(self):
        source = self.runtime.read_bytes()
        self.assertEqual(self.check(), PACK_SHA256)
        self.assertEqual(self.runtime.read_bytes(), source)
        self.assertEqual(self.pack.read_bytes(), PACK_BYTES)

    def test_mismatch_reports_both_hashes_without_rewriting_the_pin(self):
        self.runtime.write_text(declaration(OTHER_SHA256))
        source = self.runtime.read_bytes()
        with self.assertRaises(SystemExit) as failure:
            self.check()
        self.assertIn(PACK_SHA256, str(failure.exception))
        self.assertIn(OTHER_SHA256, str(failure.exception))
        self.assertEqual(self.runtime.read_bytes(), source)
        self.assertEqual(self.pack.read_bytes(), PACK_BYTES)

    def test_missing_or_commented_out_literal_is_rejected(self):
        for source in (
            "",
            "if (![hash isEqual:PDQualifiedRetainedPackSHA256]) { return NO; }\n",
            "// " + declaration(),
            "/*\n" + declaration() + "*/\n",
        ):
            with self.subTest(source=source):
                self.runtime.write_text(source)
                with self.assertRaisesRegex(SystemExit, "exactly one literal"):
                    self.check()

    def test_malformed_or_nonliteral_initializer_is_rejected(self):
        for source in (
            declaration(PACK_SHA256[:-1]),
            declaration(PACK_SHA256 + "0"),
            declaration(PACK_SHA256.upper()),
            declaration("g" * 64),
            declaration().replace('@\"', '\"'),
            declaration().replace(f'@"{PACK_SHA256}"', "anotherPin"),
            declaration().replace('";', '" @"extra";'),
            declaration().replace(";", " unexpected();"),
        ):
            with self.subTest(source=source):
                self.runtime.write_text(source)
                with self.assertRaisesRegex(SystemExit, "exactly one literal"):
                    self.check()

    def test_duplicate_and_ambiguous_initializers_are_rejected(self):
        for extra in (
            declaration(),
            declaration(OTHER_SHA256),
            declaration("invalid"),
            declaration().replace(f'@"{PACK_SHA256}"', "anotherPin"),
            declaration().replace("SHA256 =", "SHA256 /* ambiguous */ =").replace(
                f'@"{PACK_SHA256}"', "anotherPin"),
            f'static NSString *const PDQualifiedRetainedPackSHA256(@"{OTHER_SHA256}");\n',
            f'static NSString *const PDQualifiedRetainedPackSHA256{{@"{OTHER_SHA256}"}};\n',
            "static NSString *PDQualifiedRetainedPackSHA256;\n",
            f'auto PDQualifiedRetainedPackSHA256{{@"{OTHER_SHA256}"}};\n',
        ):
            with self.subTest(extra=extra):
                self.runtime.write_text(declaration() + extra)
                with self.assertRaisesRegex(SystemExit, "exactly one literal"):
                    self.check()
        for alternative in (
            declaration(),
            f'static NSString *const PDQualifiedRetainedPackSHA256(@"{OTHER_SHA256}");\n',
            f'static NSString *const PDQualifiedRetainedPackSHA256{{@"{OTHER_SHA256}"}};\n',
            "static NSString *PDQualifiedRetainedPackSHA256;\n",
        ):
            with self.subTest(alternative=alternative):
                self.runtime.write_text("#if FIRST\n" + declaration() + "#else\n" + alternative + "#endif\n")
                with self.assertRaisesRegex(SystemExit, "exactly one literal"):
                    self.check()

    def test_comments_do_not_supply_a_second_pin(self):
        self.runtime.write_text(
            'static NSString *example = @"https://example.invalid/*literal*/";\n'
            + "/*\n" + declaration(OTHER_SHA256) + "*/\n"
            + declaration() + "// " + declaration("invalid")
        )
        self.assertEqual(self.check(), PACK_SHA256)

    def test_quoted_and_raw_strings_cannot_supply_a_native_declaration(self):
        for source in (
            'static NSString *message = @"PDQualifiedRetainedPackSHA256 = a diagnostic";\n',
            'static const char *message = R"(\n' + declaration() + ')";\n',
            'static const char *message = R"custom(\n' + declaration() + ')custom";\n',
            'static const char *message = u8R"custom(\n' + declaration() + ')custom";\n',
        ):
            with self.subTest(source=source):
                self.runtime.write_text(source)
                with self.assertRaisesRegex(SystemExit, "exactly one literal"):
                    self.check()
                self.runtime.write_text(source + declaration())
                self.assertEqual(self.check(), PACK_SHA256)

    def test_escaped_newlines_are_rejected_instead_of_reinterpreting_comments(self):
        for source in (
            "// Continued comment \\\n" + declaration(),
            "// Continued comment \\ \n" + declaration(),
            "// Continued comment \\\r\n" + declaration(),
            declaration().replace(" = ", " = \\\n"),
        ):
            with self.subTest(source=source):
                self.runtime.write_text(source)
                with self.assertRaisesRegex(SystemExit, "escaped source newlines"):
                    self.check()

    def test_ordinary_native_references_do_not_count_as_declarations(self):
        self.runtime.write_text(
            declaration()
            + "if (![hash isEqual:PDQualifiedRetainedPackSHA256]) { return NO; }\n"
            + "if (PDQualifiedRetainedPackSHA256 == nil) { return NO; }\n"
            + "return PDQualifiedRetainedPackSHA256;\n"
        )
        self.assertEqual(self.check(), PACK_SHA256)

    def test_staged_pack_must_match_the_verified_hash_and_size(self):
        for receipt in (
            None, {}, {"sha256": PACK_SHA256},
            {**self.verified_pack, "sha256": OTHER_SHA256},
            {**self.verified_pack, "bytes": len(PACK_BYTES) + 1},
        ):
            with self.subTest(receipt=receipt), self.assertRaisesRegex(SystemExit, "receipt-verified staged PCK"):
                PREPARE.verify_retained_pack_pin(self.runtime, self.pack, receipt)
        self.pack.write_bytes(PACK_BYTES + b"changed")
        with self.assertRaisesRegex(SystemExit, "receipt-verified staged PCK"):
            self.check()
        self.pack.unlink()
        with self.assertRaisesRegex(SystemExit, "receipt-verified staged PCK"):
            self.check()


class AuthorityStagingTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory(prefix="partydeck-retained-staging-")
        self.addCleanup(directory.cleanup)
        self.directory = Path(directory.name)
        self.root = self.directory / "godot/ios-host"
        self.evidence = self.root / "build/evidence"
        self.evidence.mkdir(parents=True)
        self.runtime = self.root / "modules/partydeck_ios_probe/PDGodotRuntime.mm"
        self.runtime.parent.mkdir(parents=True)
        self.runtime.write_text(declaration())
        self.pack = self.directory / "incoming/renderer.pck"
        self.pack.parent.mkdir()
        self.pack.write_bytes(PACK_BYTES)
        self.staged = self.root / "build/host-resources/ProbeResources/partydeck-last-light.pck"
        self.resources = {"optional_shared_pack": PREPARE.file_receipt(self.pack)}
        self.framework = self.directory / "incoming/PartyDeckGodotBridge.framework"
        framework_files = {}
        for name in PREPARE.FRAMEWORK_FILES:
            path = self.framework / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("Synthetic framework fixture: " + name)
            framework_files[name] = PREPARE.file_receipt(path)
        self.framework_receipt = self.directory / "incoming/framework.json"
        write_json(self.framework_receipt, {
            "target": "iosSimulatorArm64", "framework_compiled": True,
            "expected_facade_declarations_present": True, "swift_module_import_typechecked": True,
            "framework": framework_files,
        })
        archives = []
        for name in ("libpartydeck_godot_ios_probe.a", "libpartydeck_godot_camera.a"):
            path = self.root / "build/artifacts" / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("Synthetic archive fixture: " + name)
            archives.append({"artifact": name, **PREPARE.file_receipt(path)})
        patches = []
        for name in PREPARE.PATCH_FILES_BY_NAME:
            path = HOST / "patches" / f"{name}.json"
            manifest = json.loads(path.read_text())
            patches.append({
                "name": name, "base_commit": PREPARE.COMMIT,
                "patch_sha256": manifest["patchSha256"],
                "manifest_sha256": PREPARE.file_receipt(path)["sha256"],
                "applied": True, "files": manifest["files"],
            })
        self.engine = {
            **archives[0], "auxiliary_archives": archives[1:],
            "engine_commit": PREPARE.COMMIT, "path_overrides_enabled": True,
            "upstream_patches": patches, "sdl_enabled": False,
            "native_input_scope": "touch_and_hardware_keyboard",
            "native_module_capture_phase": "before_scons",
            "engine_checkout_policy": "fresh_isolated_checkout",
        }
        self.refresh_module_receipt()

    def refresh_module_receipt(self):
        sources = {"partydeck_ios_probe/PDGodotRuntime.mm": PREPARE.file_receipt(self.runtime)["sha256"]}
        self.engine["native_module_sources"] = sources
        self.engine["module_snapshot_sha256"] = hashlib.sha256(
            json.dumps(sources, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        write_json(self.evidence / "engine-artifact.json", self.engine)

    def stage(self, retained=True, resource_failure=False, staged_bytes=PACK_BYTES):
        def verified_resources(command, check):
            self.assertEqual(command, [
                sys.executable, str(self.root / "prepare-host-resources.py"),
                "--pack", str(self.pack.resolve()),
            ])
            self.assertTrue(check)
            if resource_failure:
                raise subprocess.CalledProcessError(1, command)
            self.staged.parent.mkdir(parents=True, exist_ok=True)
            self.staged.write_bytes(staged_bytes)
            write_json(self.evidence / "host-resources.json", self.resources)

        arguments = [
            str(HOST / "prepare-authority-host.py"),
            "--framework", str(self.framework),
            "--framework-receipt", str(self.framework_receipt),
            "--pack", str(self.pack),
        ] + (["--retained"] if retained else [])
        with mock.patch.object(PREPARE, "ROOT", self.root), mock.patch.object(sys, "argv", arguments), \
                mock.patch.object(PREPARE.subprocess, "run", side_effect=verified_resources) as resource_stage, \
                contextlib.redirect_stdout(io.StringIO()):
            self.resource_stage = resource_stage
            PREPARE.main()
        return json.loads((self.evidence / "authority-host-inputs.json").read_text())

    def assert_no_success_receipt(self):
        self.assertFalse((self.evidence / "authority-host-inputs.json").exists())

    def test_retained_acceptance_records_the_verified_native_pin(self):
        result = self.stage()
        self.assertEqual(result["native_pack_sha256"], PACK_SHA256)
        self.assertEqual(result["resources"], self.resources)
        self.assertFalse(result["swift_authority_host_compiled"])
        self.assertFalse(result["ios_authority_runtime_executed"])
        self.assertFalse(result["kmp_factory_qualified"])
        self.resource_stage.assert_called_once()

    def test_generic_authority_path_does_not_require_a_retained_literal(self):
        self.runtime.write_text("// The generic host does not use the retained entry point.\n")
        self.refresh_module_receipt()
        result = self.stage(retained=False)
        self.assertNotIn("native_pack_sha256", result)
        self.assertEqual(result["stage"], "authority_host_inputs_only")
        self.assertEqual(result["resources"], self.resources)

    def test_retained_mismatch_is_rejected_after_resource_verification(self):
        self.runtime.write_text(declaration(OTHER_SHA256))
        self.refresh_module_receipt()
        with self.assertRaisesRegex(SystemExit, "native execution would reject it"):
            self.stage()
        self.resource_stage.assert_called_once()
        self.assert_no_success_receipt()

    def test_resource_verification_failure_still_stops_preparation(self):
        self.runtime.write_text(declaration(OTHER_SHA256))
        self.refresh_module_receipt()
        with self.assertRaises(subprocess.CalledProcessError):
            self.stage(resource_failure=True)
        self.assert_no_success_receipt()

    def test_changed_staged_bytes_are_rejected(self):
        with self.assertRaisesRegex(SystemExit, "receipt-verified staged PCK"):
            self.stage(staged_bytes=PACK_BYTES + b"changed during staging")
        self.assert_no_success_receipt()

    def test_existing_module_receipt_check_cannot_be_bypassed_by_a_matching_pin(self):
        self.runtime.write_text(declaration() + "// Changed after native compilation.\n")
        with self.assertRaisesRegex(SystemExit, "current authority-host module sources"):
            self.stage()
        self.resource_stage.assert_not_called()
        self.assert_no_success_receipt()

    def test_existing_archive_and_framework_receipts_still_reject_changes(self):
        archive = self.root / "build/artifacts/libpartydeck_godot_ios_probe.a"
        original = archive.read_bytes()
        archive.write_bytes(original + b"changed")
        with self.assertRaisesRegex(SystemExit, "native engine archive differs"):
            self.stage()
        self.resource_stage.assert_not_called()
        archive.write_bytes(original)
        (self.framework / PREPARE.FRAMEWORK_FILES[0]).write_text("changed")
        with self.assertRaisesRegex(SystemExit, "framework does not match its receipt"):
            self.stage()
        self.resource_stage.assert_not_called()
        self.assert_no_success_receipt()

    def test_existing_patch_and_snapshot_receipts_still_reject_changes(self):
        original = self.engine["upstream_patches"][0]["patch_sha256"]
        self.engine["upstream_patches"][0]["patch_sha256"] = OTHER_SHA256
        self.refresh_module_receipt()
        with self.assertRaisesRegex(SystemExit, "every current reviewed iOS patch"):
            self.stage()
        self.resource_stage.assert_not_called()
        self.engine["upstream_patches"][0]["patch_sha256"] = original
        self.refresh_module_receipt()
        self.engine["module_snapshot_sha256"] = OTHER_SHA256
        write_json(self.evidence / "engine-artifact.json", self.engine)
        with self.assertRaisesRegex(SystemExit, "verified module inputs captured before"):
            self.stage()
        self.resource_stage.assert_not_called()
        self.assert_no_success_receipt()

    def test_retained_runner_stops_before_link_or_simulator_on_mismatch(self):
        # The real shell/stager run against synthetic input files. Every native
        # command is replaced with a sentinel; resource validation is a fixture.
        self.runtime.write_text(declaration(OTHER_SHA256))
        self.refresh_module_receipt()
        for name in ("prepare-authority-host.py", "source_audit.py", "test-retained-host.sh"):
            shutil.copy2(HOST / name, self.root / name)
        shutil.copytree(HOST / "patches", self.root / "patches")
        (self.root / "prepare-host-resources.py").write_text(
            "from pathlib import Path\nimport json\n"
            f"pack = Path({str(self.staged)!r})\n"
            "pack.parent.mkdir(parents=True, exist_ok=True)\n"
            f"pack.write_bytes({PACK_BYTES!r})\n"
            f"Path({str(self.evidence / 'host-resources.json')!r}).write_text("
            f"json.dumps({self.resources!r}))\n"
        )
        (self.root / "record-retained-result.py").write_text("# Host test: no native result to decode.\n")
        commands = self.directory / "commands"
        commands.mkdir()
        sentinel = self.directory / "native-command-reached"
        scripts = {
            "uname": "import sys\nprint({'-s': 'Darwin', '-m': 'arm64'}[sys.argv[1]])\n",
            "python3": "import os, sys\nos.execv(sys.executable, [sys.executable, '-B', *sys.argv[1:]])\n",
            "xcodebuild": (
                "import sys\nfrom pathlib import Path\n"
                "if sys.argv[1:] == ['-version']:\n    print('Xcode 26.4.1')\n    sys.exit(0)\n"
                f"Path({str(sentinel)!r}).write_text('xcodebuild')\nsys.exit(91)\n"
            ),
            "xcrun": f"from pathlib import Path\nPath({str(sentinel)!r}).write_text('xcrun')\n",
            "plutil": f"from pathlib import Path\nPath({str(sentinel)!r}).write_text('plutil')\n",
        }
        for name, body in scripts.items():
            script = commands / name
            script.write_text(f"#!{sys.executable}\n" + body)
            script.chmod(0o755)
        environment = {
            **os.environ, "PATH": str(commands) + os.pathsep + os.environ.get("PATH", ""),
            "PYTHONDONTWRITEBYTECODE": "1",
            "PARTYDECK_GODOT_RETAINED_FRAMEWORK": str(self.framework),
            "PARTYDECK_GODOT_RETAINED_FRAMEWORK_RECEIPT": str(self.framework_receipt),
            "PARTYDECK_GODOT_RETAINED_PCK": str(self.pack),
        }
        for stage in ("build", "test"):
            with self.subTest(stage=stage):
                result = subprocess.run(
                    ["bash", str(self.root / "test-retained-host.sh"), stage],
                    env=environment, capture_output=True, text=True, timeout=15,
                )
                self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertIn("native execution would reject it", result.stderr)
                self.assertFalse(sentinel.exists())
                self.assert_no_success_receipt()


if __name__ == "__main__":
    unittest.main()
