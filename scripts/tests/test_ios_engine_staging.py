"""The checked-in native module must pass the same input gate used by CI."""
import hashlib
from pathlib import Path
import runpy
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]
STAGER = runpy.run_path(str(ROOT / "godot/ios-host/stage-engine-inputs.py"))
MODULES = ROOT / "godot/ios-host/modules"


class NativeEngineStagingTests(unittest.TestCase):
    def test_checked_in_module_including_timing_header_is_admitted(self):
        contents = STAGER["capture"](MODULES)
        header = "partydeck_ios_probe/frame_timing.h"
        self.assertEqual(contents[header], (MODULES / header).read_bytes())

    def test_timing_header_change_invalidates_captured_inputs(self):
        contents = STAGER["capture"](MODULES)
        inventory = STAGER["inventory"](contents)
        with tempfile.TemporaryDirectory(prefix="partydeck-staging-fixture-") as name:
            snapshot = Path(name)
            for relative, data in contents.items():
                target = snapshot / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(data)
            receipt = {
                "module_snapshot_path": str(snapshot),
                "native_module_sources": inventory,
                "module_snapshot_sha256": STAGER["inventory_digest"](inventory),
            }
            STAGER["verify"](receipt)
            header = snapshot / "partydeck_ios_probe/frame_timing.h"
            header.write_bytes(header.read_bytes() + b"\n// fixture mutation\n")
            self.assertNotEqual(hashlib.sha256(header.read_bytes()).hexdigest(),
                                inventory["partydeck_ios_probe/frame_timing.h"])
            with self.assertRaisesRegex(RuntimeError, "changed after capture"):
                STAGER["verify"](receipt)


if __name__ == "__main__":
    unittest.main()
