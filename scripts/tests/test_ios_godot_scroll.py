#!/usr/bin/env python3
"""Metadata-only scope gates. Synthetic PNG headers are not native screenshots or pixel evidence."""

from contextlib import nullcontext, redirect_stdout
from copy import deepcopy
import hashlib
import io
import json
from pathlib import Path
import runpy
import subprocess
import sys
from types import SimpleNamespace
import unittest
from unittest import mock

from ios_timing_fixtures import baseline, encoded

CHECKS = runpy.run_path(str(Path(__file__).resolve().parents[1] / "check-ios-production-session-smoke.py"))
SUMMARY = {"result": "Passed", "testFailures": [], "totalTestCount": 2,
           "passedTests": 2, "failedTests": 0, "skippedTests": 0, "expectedFailures": 0}
PNG_HEADER = b"\x89PNG\r\n\x1a\n" + b"\x00\x00\x00\rIHDR" + (1).to_bytes(4, "big") * 2


def case_log(cases, status="passed"):
    return "".join(f"Test Case '-[{target} {method}]' started.\n"
                   f"Test Case '-[{target} {method}]' {status} (1.000 seconds).\n"
                   for target, method in cases) + "** TEST SUCCEEDED **\n"


def control(action, target, clip=(0, 80, 390, 650), visible=True):
    return {"group": "partydeck_action_" + action, "cardIndex": -1,
            "rect": list(target), "clipRect": list(clip), "visible": visible, "enabled": True, "selected": False}


def fixture(gestures=1):
    """Full numeric observations, JSON metadata and headers live only in memory."""
    manifest, files = [], {}
    for mode, method in CHECKS["SCROLL_METHODS"].items():
        attachments, observations = [], {}
        steps = ["concealed before drag", *[f"concealed body drag {n}" for n in range(1, gestures + 1)],
                 "full lobby bounds", "lobby confirmation", "lobby cancelled", "cleanup Home"]

        def add(caption, filename, value):
            attachments.append({"suggestedHumanReadableName": caption + "_fixture" + Path(filename).suffix,
                                "exportedFileName": filename, "isAssociatedWithFailure": False})
            files[filename] = value if type(value) is bytes else encoded(value)

        for index, step in enumerate(steps):
            value = baseline(mode)
            value["controller"]["phase"] = "PLAYING"
            value["observationSequence"] = str(100 + index)
            scene, native = value["port"]["renderer"], value["port"]["native"]
            scene["sequence"] = str(70 + index)
            native.update(nativePresentedFrames=20 + index, iterations=40 + index)
            y = 780 if index == 0 else 670
            if step.startswith("concealed body drag "):
                y = 780 - 110 * int(step.rsplit(" ", 1)[1]) / gestures
            scene["controls"] = [control("lobby", (24, y, 342, 48), visible=y + 48 <= 730)]
            if step == "lobby confirmation":
                scene["controls"] = [control("lobby_cancel", (60, 400, 120, 48)),
                                     control("lobby_confirm", (210, 400, 120, 48))]
            if step == "cleanup Home":
                value["controller"].update(screen="HOME", sessionPresent=False, mode="COMPOSE")
                value["port"].update(active=False, renderer=None, geometry=None)
                native.update(dormant=True, emptyTree=True, renderLoopActive=False)
            caption = mode + " native scroll " + step
            add(caption, f"{mode}-{index}.png", PNG_HEADER)
            add(caption + " latest sanitized observation", f"{mode}-{index}.json", value)
            observations[step] = value

        before, after = observations["concealed before drag"], observations["full lobby bounds"]
        first, last = before["port"]["renderer"], after["port"]["renderer"]
        add(mode + " native scroll measured lobby reachability", mode + "-report.json", {
            "schemaVersion": 1, "kind": "native_concealed_body_lobby_reachability", "mode": mode,
            "scrollGestures": gestures, "beforeObservationSequence": before["observationSequence"],
            "afterObservationSequence": after["observationSequence"], "beforeRendererSequence": first["sequence"],
            "afterRendererSequence": last["sequence"], "beforeRect": first["controls"][0]["rect"],
            "beforeClipRect": first["controls"][0]["clipRect"], "afterRect": last["controls"][0]["rect"],
            "afterClipRect": last["controls"][0]["clipRect"],
            "nativeFrame": after["port"]["geometry"]["frame"], "nativeBounds": after["port"]["geometry"]["bounds"],
            "rendererViewport": [390, 844], "concealed": True,
            "authorityIntentCountBefore": 0, "authorityIntentCountAfter": 0,
            "lastSeatVisibility": "independent_pixel_review_required",
            "horizontalRoster": "not_exercised_no_observed_target",
        })
        manifest.append({"testIdentifier": f"PartyDeckGodotSessionUITests/{method}()",
                         "testIdentifierURL": f"test://com.apple.xcode/PartyDeck/PartyDeckUITests/PartyDeckGodotSessionUITests/{method}",
                         "attachments": attachments})
    return manifest, files


def changed_json(files, filename, keys, value):
    result = dict(files)
    document = json.loads(files[filename])
    target = document
    for key in keys[:-1]:
        target = target[key]
    target[keys[-1]] = value
    result[filename] = encoded(document)
    return result


class ScrollGateTests(unittest.TestCase):
    def captures(self, manifest, files, *, missing=None, symlink=None):
        def identity(path):
            payload = files[path.name]
            return {"path": str(path), "bytes": len(payload), "sha256": hashlib.sha256(payload).hexdigest()}
        with mock.patch.object(Path, "is_file", autospec=True,
                               side_effect=lambda path: path.name in files and path.name != missing), \
             mock.patch.object(Path, "is_symlink", autospec=True, side_effect=lambda path: path.name == symlink), \
             mock.patch.object(Path, "open", autospec=True,
                               side_effect=lambda path, *args, **kwargs: io.BytesIO(files[path.name])), \
             mock.patch.dict(CHECKS["check_scroll_captures"].__globals__, {"file_identity": identity}):
            return CHECKS["check_scroll_captures"](manifest, Path("/synthetic-scroll-attachments"))

    def test_original_default_and_explicit_scroll_logs_keep_separate_exact_cases(self):
        production, scroll = list(CHECKS["EXPECTED"]), list(CHECKS["SCROLL_EXPECTED"])
        for expected in (production, scroll):
            for order in (expected, list(reversed(expected))):
                with self.subTest(expected=expected, order=order):
                    self.assertTrue(CHECKS["inspect_log"](case_log(order), set(expected))[2])
            for invalid in ([], expected[:1], [expected[0], expected[0]], expected + [("OtherTarget", "testExtra")]):
                with self.subTest(invalid=invalid):
                    self.assertFalse(CHECKS["inspect_log"](case_log(invalid), set(expected))[2])
            for status in ("failed", "skipped"):
                self.assertFalse(CHECKS["inspect_log"](case_log(expected, status), set(expected))[2])
            for log in (case_log(expected) + "** TEST FAILED **\n",
                        case_log(expected).replace("started.", "not-started."),
                        case_log(expected).replace(expected[0][0], "OtherTarget"),
                        case_log(expected).replace("** TEST SUCCEEDED **", "")):
                self.assertFalse(CHECKS["inspect_log"](log, set(expected))[2])
        self.assertTrue(CHECKS["inspect_log"](case_log(production))[2])
        self.assertFalse(CHECKS["inspect_log"](case_log(scroll))[2])
        self.assertFalse(CHECKS["inspect_log"](case_log(production), CHECKS["SCROLL_EXPECTED"])[2])

    def test_summary_independently_requires_two_actual_passes(self):
        self.assertTrue(CHECKS["inspect_summary"](SUMMARY))
        for key, value in (("totalTestCount", 1), ("totalTestCount", 3), ("passedTests", 1),
                           ("failedTests", 1), ("skippedTests", 1), ("expectedFailures", 1),
                           ("failedTests", False), ("skippedTests", False), ("expectedFailures", False),
                           ("result", "Failed"), ("testFailures", [{}])):
            with self.subTest(key=key, value=value):
                self.assertFalse(CHECKS["inspect_summary"]({**SUMMARY, key: value}))
        for key in SUMMARY:
            with self.subTest(missing=key):
                self.assertFalse(CHECKS["inspect_summary"]({k: v for k, v in SUMMARY.items() if k != key}))

    def test_both_modes_one_through_eight_drags_keep_explicit_coverage_limits(self):
        for gestures in range(1, 9):
            manifest, files = fixture(gestures)
            # Existing helper diagnostics are permitted but cannot stand in for the named scope.
            manifest[0]["attachments"].append({"suggestedHumanReadableName": "2d measured lobby before actual scroll_fixture.json"})
            with self.subTest(gestures=gestures):
                result = self.captures(list(reversed(manifest)), files)
                self.assertEqual(len(result["captures"]), 2 * (5 + gestures))
                self.assertEqual([item["scroll_gestures"] for item in result["reports"]], [gestures, gestures])
                for key in ("native_pixel_review_complete", "shipping_profile_evidence",
                            "last_seat_pixel_acceptance", "horizontal_roster_exercised"):
                    self.assertIs(result[key], False)

    def test_every_required_png_observation_and_report_must_belong_to_its_case(self):
        manifest, files = fixture()
        for owner in range(2):
            for index in range(len(manifest[owner]["attachments"])):
                changed = deepcopy(manifest)
                del changed[owner]["attachments"][index]
                with self.subTest(owner=owner, index=index), self.assertRaises(ValueError):
                    self.captures(changed, files)
        changed = deepcopy(manifest)
        changed[0]["attachments"], changed[1]["attachments"] = changed[1]["attachments"], changed[0]["attachments"]
        with self.assertRaises(ValueError):
            self.captures(changed, files)

    def test_case_records_urls_and_scope_family_captions_cannot_be_substituted(self):
        manifest, files = fixture()
        variants = [[], manifest[:1], manifest + [manifest[0]], [manifest[0], manifest[0]]]
        for key in ("testIdentifier", "testIdentifierURL"):
            changed = deepcopy(manifest); changed[1][key] = changed[0][key]; variants.append(changed)
        changed = deepcopy(manifest)
        changed[0]["testIdentifier"] = "PartyDeckGodotSessionUITests/testProduction2DPracticeSession()"
        variants.append(changed)
        for name in ("2d native scroll concealed body drag 0_fixture.png",
                     "2d native scroll concealed body drag 9_fixture.png",
                     "3d native scroll concealed before drag_fixture.png",
                     "2d native scroll unsupported extra_fixture.json"):
            changed = deepcopy(manifest)
            changed[0]["attachments"].append({"suggestedHumanReadableName": name})
            variants.append(changed)
        for changed in variants:
            with self.subTest(changed=changed), self.assertRaises(ValueError):
                self.captures(changed, files)

    def test_alias_traversal_failed_misnamed_duplicate_and_non_original_files_fail(self):
        manifest, files = fixture()
        variants = []
        changed = deepcopy(manifest); changed[0]["attachments"].append(changed[0]["attachments"][0]); variants.append(changed)
        for key, bad in (("exportedFileName", "../outside.png"), ("exportedFileName", r"..\outside.png"),
                         ("exportedFileName", "bad\nname.png"), ("exportedFileName", "3d-0.png"),
                         ("isAssociatedWithFailure", True), ("isAssociatedWithFailure", 0),
                         ("suggestedHumanReadableName", "2d native scroll concealed before drag.png")):
            changed = deepcopy(manifest); changed[0]["attachments"][0][key] = bad; variants.append(changed)
        for changed in variants:
            with self.subTest(changed=changed), self.assertRaises(ValueError):
                self.captures(changed, files)
        for filename in ("2d-0.png", "2d-0.json", "2d-report.json"):
            for option in ("missing", "symlink"):
                with self.subTest(filename=filename, option=option), self.assertRaises(ValueError):
                    self.captures(manifest, files, **{option: filename})
        for header in (b"not PNG", PNG_HEADER[:20], PNG_HEADER[:16] + b"\0" * 8):
            with self.subTest(header=header), self.assertRaises(ValueError):
                self.captures(manifest, {**files, "2d-0.png": header})

    def test_reports_reject_zero_progress_extra_gestures_false_counts_and_claim_inflation(self):
        _, files = fixture()
        report = json.loads(files["2d-report.json"])
        CHECKS["check_scroll_report"](report, "2d")
        for key, value in (("scrollGestures", 0), ("scrollGestures", 9), ("scrollGestures", True),
                           ("afterObservationSequence", report["beforeObservationSequence"]),
                           ("afterRendererSequence", report["beforeRendererSequence"]),
                           ("afterObservationSequence", "01"), ("afterRendererSequence", str(2**64)),
                           ("authorityIntentCountAfter", 1), ("authorityIntentCountBefore", False),
                           ("mode", "3d"), ("concealed", False), ("schemaVersion", True),
                           ("lastSeatVisibility", "passed"), ("horizontalRoster", "passed")):
            with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                CHECKS["check_scroll_report"]({**report, key: value}, "2d")
        for changed in ({k: v for k, v in report.items() if k != "beforeRect"}, {**report, "extra": True}, None, []):
            with self.subTest(changed=changed), self.assertRaises(ValueError):
                CHECKS["check_scroll_report"](changed, "2d")

    def test_reports_need_lower_overflow_complete_48_point_targets_and_logical_geometry(self):
        _, files = fixture()
        report = json.loads(files["2d-report.json"])
        variants = [
            ("beforeRect", [24, 670, 342, 48]), ("beforeRect", [24, 780, 400, 48]),
            ("beforeClipRect", [0, 80, 390, 900]), ("afterRect", [24, 710, 342, 48]),
            ("afterRect", [24, 670, 47, 48]), ("afterRect", [24, 670, 342, 47]),
            ("afterRect", [24, 670, -1, 48]), ("afterRect", [24, 670, True, 48]),
            ("afterClipRect", [0, 80, 391, 650]), ("nativeFrame", [0, 0, 1170, 2532]),
            ("nativeBounds", [2, 0, 390, 844]), ("rendererViewport", [1170, 2532]),
            ("rendererViewport", [390, False]), ("nativeBounds", [0, 0, 390]),
        ]
        for key, value in variants:
            with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                CHECKS["check_scroll_report"]({**report, key: value}, "2d")

    def test_report_must_bind_the_exact_paired_before_and_full_lobby_observations(self):
        manifest, files = fixture()
        for keys, value in ((("beforeObservationSequence",), "99"), (("afterObservationSequence",), "103"),
                            (("beforeRendererSequence",), "69"), (("afterRendererSequence",), "73"),
                            (("beforeRect", 1), 779), (("afterRect", 1), 669), (("nativeFrame", 0), 1)):
            changed = changed_json(files, "2d-report.json", keys, value)
            with self.subTest(keys=keys), self.assertRaisesRegex(ValueError, "exact before and full-lobby"):
                self.captures(manifest, changed)

    def test_each_drag_requires_fresh_observations_renderers_and_native_progress(self):
        manifest, files = fixture()
        changes = [(("observationSequence",), "100"), (("port", "renderer", "sequence"), "70"),
                   (("port", "native", "nativePresentedFrames"), 20), (("port", "native", "iterations"), 40)]
        for keys, value in changes:
            with self.subTest(keys=keys), self.assertRaisesRegex(ValueError, "progress"):
                self.captures(manifest, changed_json(files, "2d-1.json", keys, value))
        manifest, files = fixture(2)
        del manifest[0]["attachments"][2:4]  # A final screenshot cannot substitute for drag 1.
        with self.assertRaises(ValueError):
            self.captures(manifest, files)

    def test_every_active_checkpoint_stays_concealed_in_the_same_idle_practice(self):
        manifest, files = fixture()
        variants = [(("port", "renderer", "handConcealed"), False),
                    (("port", "renderer", "privateFaceCount"), 1),
                    (("port", "renderer", "privateLabelCount"), 1),
                    (("port", "renderer", "selectedCount"), 1),
                    (("controller", "mode"), "GODOT_3D"), (("controller", "practice"), False),
                    (("controller", "phase"), "RESULTS"), (("controller", "handCount"), 4),
                    (("controller", "ownTurn"), False), (("controller", "canPlay"), False),
                    (("controller", "canSendAction"), False), (("controller", "pending"), "PLAY"),
                    (("port", "native", "queuedEvents"), 1), (("port", "profile"), "shipping")]
        for keys, value in variants:
            with self.subTest(keys=keys), self.assertRaises(ValueError):
                self.captures(manifest, changed_json(files, "2d-1.json", keys, value))

    def test_scroll_and_local_cancel_cannot_change_session_input_privacy_or_receipt_context(self):
        manifest, files = fixture()
        variants = [(("controller", key), "99") for key in ("sessionGeneration", "privacyEpoch", "presentationOrdinal",
                    "sessionRevision", "projectedSessionRevision", "projectedRendererRevision")]
        variants += [(("port", "native", key), "99") for key in ("presentationGeneration", "lifecycleGeneration", "inputGeneration")]
        variants += [(("port", "native", key), 1) for key in ("intentEvents", "exitEvents", "rejectedEvents")]
        variants += [(("controller", "lastViewerReceipt"), {"serial": "1"}), (("controller", "round"), 1),
                     (("controller", "canChallenge"), True), (("port", "renderer", "revision"), "99"),
                     (("port", "geometry", "frame", 0), 1)]
        for filename in ("2d-1.json", "2d-4.json"):
            for keys, value in variants:
                with self.subTest(filename=filename, keys=keys), self.assertRaisesRegex(ValueError, "preserve session"):
                    self.captures(manifest, changed_json(files, filename, keys, value))

    def test_real_lobby_dialog_cancel_and_actual_home_are_required(self):
        manifest, files = fixture()
        changes = [
            ("2d-2.json", ("port", "renderer", "controls", 0, "visible"), False),
            ("2d-2.json", ("port", "renderer", "controls", 0, "cardIndex"), -1.0),
            ("2d-3.json", ("port", "renderer", "controls"), []),
            ("2d-3.json", ("port", "renderer", "controls", 0, "rect"), [60, 710, 120, 48]),
            ("2d-3.json", ("port", "renderer", "controls", 1, "enabled"), False),
            ("2d-4.json", ("port", "renderer", "controls"), [control("lobby_cancel", (60, 400, 120, 48))]),
            ("2d-5.json", ("controller", "screen"), "SESSION"),
            ("2d-5.json", ("controller", "sessionPresent"), True),
            ("2d-5.json", ("controller", "mode"), "GODOT_2D"),
            ("2d-5.json", ("port", "active"), True),
            ("2d-5.json", ("port", "native", "dormant"), False),
            ("2d-5.json", ("port", "native", "emptyTree"), False),
            ("2d-5.json", ("port", "native", "renderLoopActive"), True),
        ]
        for filename, keys, value in changes:
            with self.subTest(filename=filename, keys=keys), self.assertRaises(ValueError):
                self.captures(manifest, changed_json(files, filename, keys, value))

    def test_malformed_nested_observations_fail_without_counting_as_checkpoints(self):
        manifest, files = fixture()
        for keys, value in ((("port",), None), (("controller",), []), (("port", "native"), []),
                            (("port", "renderer"), None), (("port", "geometry"), []),
                            (("port", "renderer", "controls"), [None]),
                            (("controller", "lastViewerReceipt"), [])):
            with self.subTest(keys=keys), self.assertRaises(ValueError):
                self.captures(manifest, changed_json(files, "2d-1.json", keys, value))

    def test_json_originals_are_bounded_unique_and_finite(self):
        path = Path("/synthetic-scroll.json")
        for payload in (b"", b"{" + b" " * 32768, b'{"x":1,"x":2}', b'{"x":NaN}', b'{"x":Infinity}', b'{"x":-Infinity}'):
            with self.subTest(payload=payload[:32]), mock.patch.object(Path, "is_file", return_value=True), \
                 mock.patch.object(Path, "is_symlink", return_value=False), \
                 mock.patch.object(Path, "open", side_effect=lambda *args, **kwargs: io.BytesIO(payload)), \
                 self.assertRaises(ValueError):
                CHECKS["scroll_json"](path)
        for present, symlink in ((False, False), (True, True)):
            with self.subTest(present=present, symlink=symlink), \
                 mock.patch.object(Path, "is_file", return_value=present), \
                 mock.patch.object(Path, "is_symlink", return_value=symlink), self.assertRaises(ValueError):
                CHECKS["scroll_json"](path)

    def test_scroll_requires_the_selected_reviewed_swift_source(self):
        path = Path("/synthetic/PartyDeckGodotSessionUITests.swift")
        for present, symlink, digest in ((True, False, CHECKS["SCROLL_TEST_SHA256"]),
                                         (False, False, CHECKS["SCROLL_TEST_SHA256"]),
                                         (True, True, CHECKS["SCROLL_TEST_SHA256"]), (True, False, "0" * 64)):
            with self.subTest(present=present, symlink=symlink, digest=digest), \
                 mock.patch.object(Path, "is_file", return_value=present), \
                 mock.patch.object(Path, "is_symlink", return_value=symlink), \
                 mock.patch.dict(CHECKS["check_scroll_source"].__globals__,
                                 {"file_identity": lambda path: {"sha256": digest}}):
                if present and not symlink and digest == CHECKS["SCROLL_TEST_SHA256"]:
                    self.assertEqual(CHECKS["check_scroll_source"](path)["sha256"], digest)
                else:
                    with self.assertRaises(ValueError):
                        CHECKS["check_scroll_source"](path)
        with self.assertRaises(ValueError):
            CHECKS["check_scroll_source"](None)

    def test_runner_selects_exact_two_cases_and_separate_outputs_before_native_guards(self):
        runner = Path(__file__).resolve().parents[1] / "validate-ios-godot-session.sh"
        prefix, marker, _ = runner.read_text().partition('if [[ "$(uname -s)"')
        self.assertTrue(marker)
        self.assertNotIn("xcodebuild", prefix)
        code = prefix + 'printf "%s\\n" "$PARTYDECK_SESSION_SCOPE" "$PARTYDECK_SESSION_OUTPUT_NAME" "${PARTYDECK_SESSION_TESTS[@]}"\n'
        for args, scope, output in (([], "production", "godot-session"),
                                    (["production"], "production", "godot-session"),
                                    (["qualification-scroll"], "qualification-scroll", "godot-session-scroll")):
            with self.subTest(args=args):
                result = subprocess.run(["bash", "-s", "--", *args], input=code, text=True,
                                        capture_output=True, timeout=5, check=False)
                self.assertEqual(result.returncode, 0, result.stderr)
                expected = CHECKS["SCROLL_EXPECTED"] if scope == "qualification-scroll" else CHECKS["EXPECTED"]
                selectors = ["-only-testing:" + target.replace(".", "/") + "/" + name for target, name in sorted(expected)]
                self.assertEqual(result.stdout.splitlines(), [scope, output, *selectors])
        for args in ([""], ["picker"], ["native-leave"], ["all"], ["production", "qualification-scroll"]):
            with self.subTest(args=args):
                result = subprocess.run(["bash", "-s", "--", *args], input=code, text=True,
                                        capture_output=True, timeout=5, check=False)
                self.assertEqual(result.returncode, 2)
                self.assertEqual(result.stdout, "")


class ScrollMainTests(unittest.TestCase):
    def result(self, *, scope="qualification-scroll", change=None, command_exit=0, existing=False):
        manifest, attachments = fixture()
        root = Path("/synthetic-scroll-main")
        cases = CHECKS["SCROLL_EXPECTED"] if scope == "qualification-scroll" else CHECKS["EXPECTED"]
        files = {str(root / "attachments" / name): value for name, value in attachments.items()}
        files.update({str(root / "attachments/manifest.json"): encoded(manifest),
                      str(root / "test.log"): case_log(cases).encode(),
                      str(root / "test-summary.json"): encoded(SUMMARY),
                      str(root / "PartyDeckGodotSessions.xcresult/data"): b"synthetic result marker"})
        if change:
            change(files, root)
        output = io.StringIO()

        def open_file(path, mode="r", *args, **kwargs):
            if mode == "x":
                self.assertEqual(path, root / "result.json")
                return nullcontext(output)
            self.assertEqual(mode, "rb")
            return io.BytesIO(files[str(path)])

        def source(path):
            self.assertEqual(scope, "qualification-scroll")
            self.assertEqual(path, root / "test.swift")
            return {"path": str(path), "sha256": CHECKS["SCROLL_TEST_SHA256"]}

        def descendants(path, pattern):
            return [Path(name) for name in sorted(files) if name.startswith(str(path) + "/")]

        argv = ["checker", "--test-log", str(root / "test.log"), "--xcresult", str(root / "PartyDeckGodotSessions.xcresult"),
                "--attachments", str(root / "attachments"), "--summary", str(root / "test-summary.json"),
                "--command-exit", str(command_exit), "--output", str(root / "result.json")]
        if scope == "qualification-scroll":
            argv += ["--scope", scope, "--test-source", str(root / "test.swift")]
        with mock.patch.object(sys, "argv", argv), \
             mock.patch.object(Path, "exists", return_value=existing), \
             mock.patch.object(Path, "is_file", autospec=True, side_effect=lambda path: str(path) in files), \
             mock.patch.object(Path, "is_dir", autospec=True, side_effect=lambda path: path.name.endswith(".xcresult")), \
             mock.patch.object(Path, "is_symlink", return_value=False), \
             mock.patch.object(Path, "rglob", autospec=True, side_effect=descendants), \
             mock.patch.object(Path, "stat", autospec=True, side_effect=lambda path: SimpleNamespace(st_size=len(files[str(path)]))), \
             mock.patch.object(Path, "read_bytes", autospec=True, side_effect=lambda path: files[str(path)]), \
             mock.patch.object(Path, "read_text", autospec=True, side_effect=lambda path, **kwargs: files[str(path)].decode()), \
             mock.patch.object(Path, "resolve", autospec=True, side_effect=lambda path: path), \
             mock.patch.object(Path, "open", autospec=True, side_effect=open_file), \
             mock.patch.object(Path, "mkdir") as mkdir, \
             mock.patch.dict(CHECKS["main"].__globals__, {"check_scroll_source": source}), redirect_stdout(io.StringIO()):
            status = CHECKS["main"]()
        mkdir.assert_called_once()
        return status, json.loads(output.getvalue())

    def test_main_binds_selected_scope_and_leaves_default_production_receipts_compatible(self):
        for scope in ("production", "qualification-scroll"):
            with self.subTest(scope=scope):
                status, result = self.result(scope=scope)
                self.assertEqual(status, 0)
                self.assertIs(result["named_test_evidence_complete"], True)
                self.assertIs(result["native_acceptance_or_shipping_promotion"], False)
                if scope == "production":
                    self.assertEqual(result["stage"], "production_session_named_test_evidence")
                    self.assertNotIn("qualification_scroll", result)
                    self.assertNotIn("selected_test_source", result)
                else:
                    self.assertEqual(result["stage"], "qualification_scroll_named_test_evidence")
                    self.assertEqual(result["test_scope"], "qualification-scroll")
                    self.assertEqual(result["selected_test_source"]["sha256"], CHECKS["SCROLL_TEST_SHA256"])

    def test_main_fails_for_wrong_named_outcomes_missing_evidence_and_failed_command(self):
        changes = [
            lambda files, root: files.__setitem__(str(root / "test.log"), case_log(CHECKS["EXPECTED"]).encode()),
            lambda files, root: files.__setitem__(str(root / "test-summary.json"), encoded({**SUMMARY, "passedTests": 1})),
            lambda files, root: files.__setitem__(str(root / "attachments/2d-report.json"), b'{"invalid":true}'),
            lambda files, root: files.pop(str(root / "attachments/2d-0.json")),
            lambda files, root: files.pop(str(root / "PartyDeckGodotSessions.xcresult/data")),
        ]
        for index, change in enumerate(changes):
            with self.subTest(change=index):
                status, result = self.result(change=change)
                self.assertEqual(status, 1)
                self.assertIs(result["named_test_evidence_complete"], False)
                self.assertTrue(result["problems"])
                self.assertIs(result["native_acceptance_or_shipping_promotion"], False)
        status, result = self.result(command_exit=1)
        self.assertEqual(status, 1)
        self.assertIs(result["named_test_evidence_complete"], False)

    def test_existing_result_is_never_replaced(self):
        with redirect_stdout(io.StringIO()), mock.patch.object(sys, "stderr", io.StringIO()), self.assertRaises(SystemExit) as error:
            self.result(existing=True)
        self.assertEqual(error.exception.code, 2)


if __name__ == "__main__":
    unittest.main(verbosity=2)
