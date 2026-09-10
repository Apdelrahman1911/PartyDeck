"""Host-only receipt binding checks; fixture bytes are not APK/PCK runtime inputs."""

import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.dont_write_bytecode = True
SOURCE = Path(__file__).resolve().parents[1] / "android_godot_adaptive_inputs.py"
spec = importlib.util.spec_from_file_location("adaptive_input_candidate", SOURCE)
inputs = importlib.util.module_from_spec(spec)
spec.loader.exec_module(inputs)


class ReceiptBindingTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix="partydeck-adaptive-input-binding-")
        self.addCleanup(self.directory.cleanup)
        self.bundle = Path(self.directory.name)
        for name in inputs.FILES:
            (self.bundle / name).write_bytes(b"non-runtime receipt-binding fixture: " + name.encode())
        self.current = dict(sourceRevision="a" * 40, runId="42", runAttempt="1", repository="owner/project")
        self.manifest = dict(schemaVersion=1, **self.current, androidApi=36, modesCsv="2d,3d",
                             qualificationProfile="qualification", checkerSha256=inputs.PINS,
                             files=inputs.file_records(self.bundle))

    def check(self, value=None, current=None):
        raw = json.dumps(self.manifest if value is None else value, sort_keys=True).encode()
        return inputs.verify_manifest(raw, hashlib.sha256(raw).hexdigest(), self.bundle,
                                      self.current if current is None else current)

    def test_same_run_later_consumer_attempt_keeps_exact_producer_inputs(self):
        later = dict(self.current, runAttempt="2")
        self.assertEqual(self.manifest, self.check(current=later))

    def test_every_changed_apk_pack_or_receipt_is_rejected(self):
        for name in inputs.FILES:
            with self.subTest(name=name):
                path = self.bundle / name
                original = path.read_bytes()
                path.write_bytes(original + b"changed")
                with self.assertRaisesRegex(ValueError, "bytes differ"):
                    self.check()
                path.write_bytes(original)

    def test_revision_run_repository_scope_and_checker_changes_are_rejected(self):
        for change in (dict(sourceRevision="b" * 40), dict(runId="43"), dict(repository="another/project"),
                       dict(androidApi=35), dict(qualificationProfile="shipping"), dict(modesCsv="2d"),
                       dict(checkerSha256={}), dict(schemaVersion=True)):
            with self.subTest(change=change), self.assertRaises(ValueError):
                self.check(dict(self.manifest, **change))

    def test_manifest_bytes_are_bound_to_the_separate_producer_output(self):
        raw = json.dumps(self.manifest).encode()
        with self.assertRaisesRegex(ValueError, "producer output"):
            inputs.verify_manifest(raw, "0" * 64, self.bundle, self.current)

    def test_duplicate_receipt_keys_and_symlinked_inputs_are_rejected(self):
        raw = json.dumps(self.manifest).encode().replace(b'"schemaVersion": 1', b'"schemaVersion": 1, "schemaVersion": 1')
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            inputs.verify_manifest(raw, hashlib.sha256(raw).hexdigest(), self.bundle, self.current)
        path = self.bundle / "androidApp-debug.apk"
        target = self.bundle / "relocated-input"
        path.rename(target)
        path.symlink_to(target)
        with self.assertRaisesRegex(ValueError, "indirect"):
            self.check()


if __name__ == "__main__":
    unittest.main(verbosity=2)
