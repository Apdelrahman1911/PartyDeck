#!/usr/bin/env python3
"""Pure activation boundary tests; these do not execute or qualify an iOS runtime."""

import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import plistlib
import runpy
import subprocess
import sys
import tempfile
import unittest


HELPER = Path(__file__).with_name("prepare-ios-godot-activation.py")
ACTIVATION = runpy.run_path(str(HELPER))
PROFILE = ACTIVATION["PROFILE_KEY"]
ACCEPTED = ACTIVATION["ACCEPTED_KEY"]
REQUESTED = ACTIVATION["REQUESTED_KEY"]


class ActivationTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="partydeck-ios-activation-")
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name)
        self.source = self.directory / "source Info.plist"
        self.generated = self.directory / "qualification output/Info.plist"
        self.expectation = self.directory / "qualification output/activation.json"
        self.source_info = {
            PROFILE: "shipping", ACCEPTED: ["2d"],
            "CFBundleDisplayName": "PartyDeck", "CFBundleExecutable": "$(EXECUTABLE_NAME)",
            "UIApplicationSceneManifest": {"UIApplicationSupportsMultipleScenes": False},
        }
        self.source.write_bytes(plistlib.dumps(self.source_info))

    def generate(self, modes="3d"):
        return ACTIVATION["generate_qualification"](self.source, modes, self.generated, self.expectation)

    def stage(self):
        return ACTIVATION["checked_activation"](self.source, self.generated, self.expectation)

    def test_profile_selects_one_set_without_union_or_promotion(self):
        legacy = ACTIVATION["resolve_activation"]({})
        self.assertEqual(legacy["profile"], "shipping")
        self.assertEqual(legacy["configured_enabled_native_modes"], [])
        shipping = ACTIVATION["resolve_activation"](self.source_info)
        self.assertEqual(shipping["configured_enabled_native_modes"], ["2d"])
        original = self.source.read_bytes()
        document = self.generate()
        generated, identity = ACTIVATION["read_plist"](self.generated)
        self.assertEqual(self.source.read_bytes(), original)
        self.assertEqual(document["activation"]["accepted_shipping_modes"], ["2d"])
        self.assertEqual(document["activation"]["configured_enabled_native_modes"], ["3d"])
        self.assertEqual(document["generated_plist"], identity)
        self.assertIs(document["ios_runtime_executed"], False)
        self.assertIs(document["kmp_factory_qualified"], False)
        expected = dict(self.source_info)
        expected.update({PROFILE: "qualification", REQUESTED: ["3d"]})
        self.assertEqual(plistlib.dumps(generated), plistlib.dumps(expected))

    def test_invalid_fields_in_either_list_reject_entire_activation(self):
        malformed = (None, True, "2d", {"2d": True}, ("2d",), [True], [2], [None],
                     [""], ["2d", "unknown"], ["2d", ""], ["2d", "2d"])
        for field in (ACCEPTED, REQUESTED):
            for value in malformed:
                with self.subTest(field=field, value=value):
                    info = {PROFILE: "qualification", ACCEPTED: ["2d"], REQUESTED: ["3d"]}
                    info[field] = value
                    with self.assertRaises(ValueError):
                        ACTIVATION["resolve_activation"](info)
        for profile in (None, True, 1, [], "", "unknown", "Qualification"):
            with self.subTest(profile=profile), self.assertRaises(ValueError):
                ACTIVATION["resolve_activation"]({PROFILE: profile, ACCEPTED: ["2d"]})

    def test_pending_shipping_and_empty_qualification_are_invalid(self):
        for info in (
            {PROFILE: "shipping", ACCEPTED: ["2d"], REQUESTED: ["3d"]},
            {REQUESTED: ["2d"]},
            {PROFILE: "qualification", ACCEPTED: ["2d"]},
            {PROFILE: "qualification", REQUESTED: []},
            {PROFILE: "shipping", ACCEPTED: ["2d"], REQUESTED: ["invalid"]},
        ):
            with self.subTest(info=info), self.assertRaises(ValueError):
                ACTIVATION["resolve_activation"](info)

    def test_request_cli_is_explicit_strict_and_canonical(self):
        for request in ("", "2d,", ",3d", "2d,,3d", "2d,2d", "2d,4d", " 2d", "2d, 3d"):
            with self.subTest(request=request), self.assertRaises(ValueError):
                ACTIVATION["requested_modes"](request)
        subprocess.run([
            sys.executable, "-B", str(HELPER), "--source-plist", str(self.source),
            "--modes", "3d,2d", "--output-plist", str(self.generated),
            "--expectation", str(self.expectation),
        ], check=True, capture_output=True, text=True)
        generated, _ = ACTIVATION["read_plist"](self.generated)
        self.assertEqual(generated[REQUESTED], ["2d", "3d"])
        self.assertEqual(self.stage()["configuration"]["configured_enabled_native_modes"], ["2d", "3d"])

    def test_shipping_needs_no_opt_in_but_qualification_requires_matching_expectation(self):
        shipping = ACTIVATION["checked_activation"](self.source, self.source)
        self.assertIsNone(shipping["expectation"])
        self.generate()
        with self.assertRaises(ValueError):
            ACTIVATION["checked_activation"](self.source, self.generated)
        with self.assertRaises(ValueError):
            ACTIVATION["checked_activation"](self.source, self.source, self.expectation)
        staged = self.stage()
        self.assertEqual(staged["expectation"]["file"]["sha256"],
                         hashlib.sha256(self.expectation.read_bytes()).hexdigest())
        self.assertEqual(staged["expectation"]["document"], json.loads(self.expectation.read_text()))
        self.assertEqual(ACTIVATION["validated_staged_activation"](staged), staged["configuration"])

    def test_expectation_binds_source_generated_fields_and_false_runtime_claims(self):
        original = self.generate()
        changes = (
            ("schema_version", 2), ("schema_version", True),
            ("stage", "production_ios_app_link_only"),
            ("ios_runtime_executed", True), ("kmp_factory_qualified", True),
            ("source_plist", {**original["source_plist"], "sha256": "0" * 64}),
            ("generated_plist", {**original["generated_plist"], "bytes": 1}),
            ("activation", {**original["activation"], "configured_enabled_native_modes": ["2d", "3d"]}),
        )
        for key, value in changes:
            with self.subTest(key=key, value=value):
                document = copy.deepcopy(original)
                document[key] = value
                self.expectation.write_text(json.dumps(document))
                with self.assertRaises(ValueError):
                    self.stage()

    def test_source_change_and_unrelated_clone_edits_cannot_be_authorized_by_expectation(self):
        original = self.generate()
        for mutate in (
            lambda info: info.update({ACCEPTED: ["2d", "3d"]}),
            lambda info: info.update({"CFBundleDisplayName": "Changed"}),
            lambda info: info["UIApplicationSceneManifest"].update({"UIApplicationSupportsMultipleScenes": 0}),
        ):
            with self.subTest(mutate=mutate):
                self.generate()
                info, _ = ACTIVATION["read_plist"](self.generated)
                info = dict(info)
                # Convert the nested strict reader dictionary before editing the fixture.
                info["UIApplicationSceneManifest"] = dict(info["UIApplicationSceneManifest"])
                mutate(info)
                self.generated.write_bytes(plistlib.dumps(info))
                document = copy.deepcopy(original)
                document["generated_plist"] = ACTIVATION["file_identity"](self.generated, self.generated.read_bytes())
                document["activation"] = ACTIVATION["resolve_activation"](info)
                self.expectation.write_text(json.dumps(document))
                with self.assertRaises(ValueError):
                    self.stage()
        self.generate()
        self.source.write_bytes(plistlib.dumps({**self.source_info, "CFBundleDisplayName": "New source"}))
        with self.assertRaises(ValueError):
            self.stage()

    def test_built_plist_allows_xcode_merge_but_requires_exact_activation(self):
        self.generate()
        staged = self.stage()
        generated, _ = ACTIVATION["read_plist"](self.generated)
        built = dict(generated)
        built.update({"CFBundleExecutable": "PartyDeck", "DTSDKName": "iphonesimulator"})
        built_path = self.directory / "PartyDeck.app/Info.plist"
        built_path.parent.mkdir()
        built_path.write_bytes(plistlib.dumps(built, fmt=plistlib.FMT_BINARY))
        actual, built_identity = ACTIVATION["read_plist"](built_path)
        self.assertNotEqual(built_identity["sha256"], staged["input_plist"]["sha256"])
        self.assertEqual(ACTIVATION["verify_packaged_activation"](actual, staged), staged["configuration"])
        for key, value in ((PROFILE, "shipping"), (ACCEPTED, []), (REQUESTED, ["2d"]),
                           (REQUESTED, ["3d", "3d"]), (REQUESTED, ["3d", "unknown"])):
            with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                ACTIVATION["verify_packaged_activation"]({**actual, key: value}, staged)

    def test_staged_qualification_cannot_drop_or_contradict_explicit_request(self):
        self.generate()
        staged = self.stage()
        for mutate in (
            lambda value: value.update({"expectation": None}),
            lambda value: value["configuration"].update({"configured_enabled_native_modes": ["2d", "3d"]}),
            lambda value: value["expectation"]["document"]["activation"].update({"qualification_modes": ["2d"]}),
            lambda value: value["expectation"]["file"].update({"sha256": "invalid"}),
        ):
            with self.subTest(mutate=mutate):
                changed = copy.deepcopy(staged)
                mutate(changed)
                with self.assertRaises(ValueError):
                    ACTIVATION["validated_staged_activation"](changed)

    def test_duplicate_dictionary_keys_and_non_dictionary_plist_are_rejected(self):
        self.generate()
        expectation = self.expectation.read_text()
        self.expectation.write_text(expectation.replace('"schema_version": 1', '"schema_version": 1, "schema_version": 1'))
        with self.assertRaises(ValueError):
            self.stage()
        self.generated.write_bytes(b'<?xml version="1.0"?><plist version="1.0"><dict>'
                                   b'<key>duplicate</key><string>a</string><key>duplicate</key><string>b</string>'
                                   b'</dict></plist>')
        with self.assertRaises(ValueError):
            ACTIVATION["read_plist"](self.generated)
        self.generated.write_bytes(plistlib.dumps(["qualification"]))
        with self.assertRaises(ValueError):
            ACTIVATION["read_plist"](self.generated)

    def test_generation_cannot_overwrite_its_source(self):
        original = self.source.read_bytes()
        hardlink = self.directory / "source alias.plist"
        os.link(self.source, hardlink)
        for output, expectation in ((self.source, self.expectation), (self.generated, self.source),
                                    (self.generated, self.generated), (hardlink, self.expectation)):
            with self.subTest(output=output, expectation=expectation), self.assertRaises(ValueError):
                ACTIVATION["generate_qualification"](self.source, "3d", output, expectation)
        self.assertEqual(self.source.read_bytes(), original)

    def test_stager_rejects_unexpected_qualification_before_native_input_access(self):
        self.generate()
        stager = runpy.run_path(str(HELPER.with_name("prepare-ios-godot.py")))
        args = argparse.Namespace(configuration="Debug", platform="iphonesimulator",
                                  app_info_plist=self.generated, activation_expectation=None,
                                  engine_root=self.directory / "nonexistent-engine", pack=self.directory / "nonexistent.pck")
        with self.assertRaisesRegex(ValueError, "explicit generated qualification expectation"):
            stager["checked_inputs"](args)


if __name__ == "__main__":
    unittest.main(verbosity=2)
