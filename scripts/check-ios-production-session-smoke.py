#!/usr/bin/env python3
"""Bind the selected two-case qualification scope; never promote platform or shipping acceptance."""

import argparse
import hashlib
import json
import math
from pathlib import Path
import re
import sys


EXPECTED = {
    ("PartyDeckUITests.PartyDeckGodotSessionUITests", "testProduction2DPracticeSession"),
    ("PartyDeckUITests.PartyDeckGodotSessionUITests", "testProduction3DPracticeSession"),
}
PREFIX = r"^Test Case '-\[([^\]\s]+) (test\w+)\]' "


def inspect_log(text: str, expected=EXPECTED) -> tuple[list, list, bool]:
    started = re.findall(PREFIX + r"started\.$", text, re.MULTILINE)
    finished = re.findall(PREFIX + r"(passed|failed|skipped) \((\d+(?:\.\d+)?) seconds\)\.$", text, re.MULTILINE)
    passed = (
        len(started) == len(expected) and set(started) == expected
        and len(finished) == len(expected)
        and {(target, name) for target, name, _, _ in finished} == expected
        and all(status == "passed" for _, _, status, _ in finished)
        and "** TEST SUCCEEDED **" in text
        and "** TEST FAILED **" not in text
    )
    return started, finished, passed


def inspect_summary(value: object) -> bool:
    expected = {"totalTestCount": 2, "passedTests": 2, "failedTests": 0, "skippedTests": 0, "expectedFailures": 0}
    return (isinstance(value, dict) and value.get("result") == "Passed" and value.get("testFailures") == []
            and all(type(value.get(key)) is int and value[key] == count for key, count in expected.items()))


def digest(path: Path) -> str:
    checksum = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            checksum.update(block)
    return checksum.hexdigest()



SCROLL_SCOPE = "qualification-scroll"
SCROLL_METHODS = {mode: f"testProduction{mode.upper()}ConcealedLobbyScrollAndCancel" for mode in ("2d", "3d")}
SCROLL_EXPECTED = {("PartyDeckUITests.PartyDeckGodotSessionUITests", method) for method in SCROLL_METHODS.values()}
SCROLL_TEST_SHA256 = "769b3c190d6a07313ac7d4ac883ec8a2a4fb3e17b50c79c99b14d2cb2bf3eda4"
SCROLL_FIXED_CAPTURES = ("concealed before drag", "full lobby bounds", "lobby confirmation", "lobby cancelled", "cleanup Home")


def require(condition, message):
    if not condition:
        raise ValueError(message)


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, "Duplicate qualification-scroll JSON field.")
        result[key] = value
    return result


def reject_constant(_):
    raise ValueError("Nonfinite qualification-scroll JSON value.")


def scroll_json(path, limit=32768):
    require(path.is_file() and not path.is_symlink(), "A required original scroll JSON attachment is missing or aliased.")
    with path.open("rb") as stream:
        payload = stream.read(limit + 1)
    require(0 < len(payload) <= limit, "Qualification-scroll JSON exceeds its source bound.")
    return json.loads(payload, object_pairs_hook=unique_object, parse_constant=reject_constant)


def file_identity(path):
    return {"path": str(path.resolve()), "bytes": path.stat().st_size, "sha256": digest(path)}


def check_scroll_source(path):
    require(path is not None and path.is_file() and not path.is_symlink(),
            "Qualification-scroll requires its reviewed Swift source.")
    source = file_identity(path)
    require(source["sha256"] == SCROLL_TEST_SHA256, "Qualification-scroll Swift source differs from the reviewed tests.")
    return source


def counter(value):
    require(type(value) is str and re.fullmatch(r"0|[1-9][0-9]{0,19}", value) is not None
            and int(value) < 2**64, "Invalid qualification-scroll sequence or context counter.")
    return int(value)


def unsigned(value):
    require(type(value) is int and 0 <= value < 2**64, "Invalid qualification-scroll event count.")
    return value


def rect(value):
    require(type(value) is list and len(value) == 4
            and all(type(item) in (int, float) and math.isfinite(item) for item in value)
            and value[2] > 0 and value[3] > 0, "Invalid measured qualification-scroll rectangle.")
    return value


def contains(outer, inner):
    return (inner[0] >= outer[0] - 0.5 and inner[1] >= outer[1] - 0.5
            and inner[0] + inner[2] <= outer[0] + outer[2] + 0.5
            and inner[1] + inner[3] <= outer[1] + outer[3] + 0.5)


def whole_control(control, viewport):
    target, clip = rect(control["rect"]), rect(control["clipRect"])
    require(control.get("enabled") is True and control.get("visible") is True
            and target[2] >= 48 and target[3] >= 48 and contains(viewport, clip) and contains(clip, target),
            "The scroll target must have whole 48-point bounds inside its measured clip.")
    return target, clip


def scroll_control(scene, action):
    controls = scene.get("controls")
    require(type(controls) is list and all(type(item) is dict for item in controls), "Missing scroll renderer controls.")
    matches = [item for item in controls if type(item) is dict
               and item.get("group") == "partydeck_action_" + action
               and type(item.get("cardIndex")) is int and item["cardIndex"] == -1]
    require(len(matches) == 1, "Missing or duplicate exact scroll renderer control.")
    return matches[0]


def check_scroll_report(value, mode):
    keys = {"schemaVersion", "kind", "mode", "scrollGestures", "beforeObservationSequence", "afterObservationSequence",
            "beforeRendererSequence", "afterRendererSequence", "beforeRect", "beforeClipRect", "afterRect",
            "afterClipRect", "nativeFrame", "nativeBounds", "rendererViewport", "concealed",
            "authorityIntentCountBefore", "authorityIntentCountAfter", "lastSeatVisibility", "horizontalRoster"}
    require(type(value) is dict and set(value) == keys and type(value["schemaVersion"]) is int
            and value["schemaVersion"] == 1 and value["kind"] == "native_concealed_body_lobby_reachability"
            and value["mode"] == mode and value["concealed"] is True,
            "Require the exact named concealed body/lobby report for this mode.")
    gestures = unsigned(value["scrollGestures"])
    require(1 <= gestures <= 8, "The scroll report must record one to eight actual body drags.")
    require(counter(value["afterObservationSequence"]) > counter(value["beforeObservationSequence"])
            and counter(value["afterRendererSequence"]) > counter(value["beforeRendererSequence"]),
            "Scroll reachability requires fresh observation and renderer sequences.")
    require(unsigned(value["authorityIntentCountBefore"]) == unsigned(value["authorityIntentCountAfter"]),
            "Body scrolling must not submit an authority intent.")
    require(value["lastSeatVisibility"] == "independent_pixel_review_required"
            and value["horizontalRoster"] == "not_exercised_no_observed_target",
            "The scroll report must retain the last-seat and horizontal-roster coverage limits.")
    before, before_clip = rect(value["beforeRect"]), rect(value["beforeClipRect"])
    after, after_clip = rect(value["afterRect"]), rect(value["afterClipRect"])
    frame, bounds = rect(value["nativeFrame"]), rect(value["nativeBounds"])
    size = value["rendererViewport"]
    require(type(size) is list and len(size) == 2
            and all(type(item) in (int, float) and math.isfinite(item) and item > 0 for item in size),
            "Invalid logical scroll viewport.")
    viewport = [0, 0, *size]
    require(abs(bounds[0]) <= 0.5 and abs(bounds[1]) <= 0.5
            and all(abs(measured - logical) <= 1 for measured, logical in
                    zip(frame[2:] + bounds[2:], size + size)),
            "Use measured native frame/bounds and logical viewport, never screenshot dimensions.")
    require(contains(viewport, before_clip) and before[1] + before[3] > before_clip[1] + before_clip[3] + 0.5
            and before[2] <= before_clip[2] + 0.5 and before[3] <= before_clip[3] + 0.5,
            "The initial lobby target must actually overflow below its measured body clip.")
    whole_control({"rect": after, "clipRect": after_clip, "visible": True, "enabled": True}, viewport)
    return gestures


def check_scroll_observation(value, mode, checkpoint):
    require(type(value) is dict and type(value.get("schemaVersion")) is int and value["schemaVersion"] == 1
            and value.get("observationInstalled") is True, "Require the named installed qualification observation.")
    sequence = counter(value["observationSequence"])
    port, state = value["port"], value["controller"]
    require(type(port) is dict and type(state) is dict and type(port.get("native")) is dict,
            "Missing scroll port, controller or native observation.")
    require(port.get("profile") == "qualification" and port.get("activationValid") is True
            and port.get("enabledModes") == ["2d", "3d"], "Scroll captures require the qualification profile.")
    native = port["native"]
    if checkpoint == "cleanup Home":
        require(state.get("screen") == "HOME" and state.get("sessionPresent") is False
                and state.get("mode") == "COMPOSE" and port.get("active") is False
                and native.get("dormant") is True and native.get("emptyTree") is True
                and native.get("renderLoopActive") is False,
                "The scroll cleanup capture must record actual Home and dormant native state.")
        return sequence, None
    scene, geometry = port["renderer"], port["geometry"]
    require(type(scene) is dict and type(geometry) is dict and type(scene.get("viewport")) is dict
            and type(scene.get("controls")) is list and all(type(item) is dict for item in scene["controls"]),
            "Missing scroll renderer, viewport, controls or native geometry.")
    require(state.get("screen") == "SESSION" and state.get("sessionPresent") is True
            and state.get("practice") is True and state.get("mode") == "GODOT_" + mode.upper()
            and state.get("phase") == "PLAYING" and state.get("ownTurn") is True
            and state.get("canPlay") is True and state.get("canSendAction") is True and state.get("pending") is None
            and type(state.get("handCount")) is int and state["handCount"] == 5
            and type(native.get("queuedEvents")) is int and native["queuedEvents"] == 0
            and port.get("active") is True and scene.get("presentationMode") == mode
            and scene.get("handConcealed") is True
            and all(type(scene.get(key)) is int and scene[key] == 0
                    for key in ("selectedCount", "privateFaceCount", "privateLabelCount")),
            "Each scroll checkpoint must retain its own concealed practice presentation.")
    receipt = state.get("lastViewerReceipt")
    require(receipt is None or type(receipt) is dict, "Invalid scroll viewer receipt.")
    receipt_serial = None if receipt is None else counter(receipt["serial"])
    context = (
        tuple(counter(state[key]) for key in ("sessionGeneration", "privacyEpoch", "presentationOrdinal",
                                             "sessionRevision", "projectedSessionRevision", "projectedRendererRevision")),
        tuple(counter(native[key]) for key in ("presentationGeneration", "lifecycleGeneration", "inputGeneration")),
        unsigned(native["intentEvents"]), unsigned(native["exitEvents"]), unsigned(native["rejectedEvents"]), receipt_serial,
        state.get("round"), state.get("canChallenge"),
        counter(scene["revision"]), geometry, scene["viewport"],
    )
    counter(scene["sequence"])
    if checkpoint == "lobby confirmation":
        viewport = [0, 0, scene["viewport"]["width"], scene["viewport"]["height"]]
        whole_control(scroll_control(scene, "lobby_cancel"), viewport)
        confirmation = scroll_control(scene, "lobby_confirm")
        require(confirmation.get("visible") is True and confirmation.get("enabled") is True,
                "The dialog capture must own the renderer's local lobby confirmation and cancel.")
    elif checkpoint == "lobby cancelled":
        require(not any(item.get("group") in ("partydeck_action_lobby_confirm", "partydeck_action_lobby_cancel")
                        for item in scene["controls"])
                and scroll_control(scene, "lobby").get("enabled") is True,
                "The cancel capture must show the local dialog removed from the same game.")
    return sequence, context


def check_scroll_captures(manifest, directory):
    require(type(manifest) is list and len(manifest) == 2, "Require exactly two scroll testcase attachment records.")
    captures, reports, used_files = [], [], set()
    for mode, method in SCROLL_METHODS.items():
        case = "PartyDeckUITests.PartyDeckGodotSessionUITests/" + method
        matches = [entry for entry in manifest if type(entry) is dict
                   and entry.get("testIdentifier") == f"PartyDeckGodotSessionUITests/{method}()"]
        require(len(matches) == 1, "Each exact scroll testcase must own one attachment record.")
        entry = matches[0]
        require(entry.get("testIdentifierURL") ==
                f"test://com.apple.xcode/PartyDeck/PartyDeckUITests/PartyDeckGodotSessionUITests/{method}",
                "Scroll attachments must bind the exact testcase URL.")
        attachments = entry.get("attachments")
        require(type(attachments) is list and all(type(item) is dict for item in attachments),
                "Missing scroll testcase attachment list.")
        consumed = set()

        def attachment(caption, extension):
            pattern = re.escape(caption) + r"_[^\x00-\x1f/\\]+\." + extension
            found = [(index, item) for index, item in enumerate(attachments)
                     if type(item.get("suggestedHumanReadableName")) is str
                     and re.fullmatch(pattern, item["suggestedHumanReadableName"]) is not None]
            require(len(found) == 1, "Each exact scroll caption must occur once under its own mode and case.")
            index, item = found[0]
            filename = item.get("exportedFileName")
            require(type(filename) is str and filename == Path(filename).name
                    and re.search(r"[\x00-\x1f/\\]", filename) is None
                    and filename.endswith("." + extension) and filename not in used_files
                    and item.get("isAssociatedWithFailure") is False,
                    "Scroll attachments need distinct retained originals without traversal or failure association.")
            path = directory / filename
            require(path.is_file() and not path.is_symlink(), "A required original scroll attachment is missing or aliased.")
            if extension == "png":
                with path.open("rb") as stream:
                    header = stream.read(24)
                require(len(header) == 24 and header[:8] == b"\x89PNG\r\n\x1a\n" and header[12:16] == b"IHDR"
                        and int.from_bytes(header[16:20], "big") > 0 and int.from_bytes(header[20:24], "big") > 0,
                        "Scroll captures need original PNG dimensions; full pixel review remains separate.")
                value = None
            else:
                value = scroll_json(path)
            used_files.add(filename)
            consumed.add(index)
            return file_identity(path), value

        report_file, report = attachment(f"{mode} native scroll measured lobby reachability", "json")
        gestures = check_scroll_report(report, mode)
        steps = [SCROLL_FIXED_CAPTURES[0], *[f"concealed body drag {n}" for n in range(1, gestures + 1)],
                 *SCROLL_FIXED_CAPTURES[1:]]
        observations, baseline, previous_sequence, previous_renderer = {}, None, -1, -1
        previous_live = None
        for step in steps:
            caption = f"{mode} native scroll {step}"
            screenshot, _ = attachment(caption, "png")
            observation_file, value = attachment(caption + " latest sanitized observation", "json")
            sequence, context = check_scroll_observation(value, mode, step)
            require(sequence > previous_sequence, "Scroll checkpoint observations must progress in source order.")
            previous_sequence = sequence
            if context is not None:
                renderer_sequence = counter(value["port"]["renderer"]["sequence"])
                require(renderer_sequence > previous_renderer, "Scroll checkpoint renderer sequences must progress in source order.")
                previous_renderer = renderer_sequence
                if step.startswith("concealed body drag "):
                    require(previous_live is not None and all(
                        unsigned(value["port"]["native"][key]) > unsigned(previous_live["port"]["native"][key])
                        for key in ("nativePresentedFrames", "iterations")),
                        "Every body-drag checkpoint requires fresh presented-frame and native-iteration progress.")
                previous_live = value
                if baseline is None:
                    baseline = context
                require(context == baseline, "Scrolling and local cancel must preserve session, input, privacy, receipt and event context.")
            observations[step] = value
            captures.append({"case": case, "capture": caption, "screenshot": screenshot, "observation": observation_file})
        before, after = observations["concealed before drag"], observations["full lobby bounds"]
        before_scene, after_scene = before["port"]["renderer"], after["port"]["renderer"]
        before_lobby, after_lobby = scroll_control(before_scene, "lobby"), scroll_control(after_scene, "lobby")
        require(report["beforeObservationSequence"] == before["observationSequence"]
                and report["afterObservationSequence"] == after["observationSequence"]
                and report["beforeRendererSequence"] == before_scene["sequence"]
                and report["afterRendererSequence"] == after_scene["sequence"]
                and report["beforeRect"] == before_lobby["rect"] and report["beforeClipRect"] == before_lobby["clipRect"]
                and report["afterRect"] == after_lobby["rect"] and report["afterClipRect"] == after_lobby["clipRect"]
                and report["nativeFrame"] == after["port"]["geometry"]["frame"]
                and report["nativeBounds"] == after["port"]["geometry"]["bounds"]
                and report["rendererViewport"] == [after_scene["viewport"]["width"], after_scene["viewport"]["height"]]
                and report["authorityIntentCountBefore"] == before["port"]["native"]["intentEvents"]
                and report["authorityIntentCountAfter"] == after["port"]["native"]["intentEvents"],
                "The measured report must bind the exact before and full-lobby capture observations.")
        require(before_lobby.get("enabled") is True, "The initial clipped lobby control must be enabled.")
        whole_control(after_lobby, [0, 0, *report["rendererViewport"]])
        require(all(index in consumed for index, item in enumerate(attachments)
                    if type(item.get("suggestedHumanReadableName")) is str
                    and item["suggestedHumanReadableName"].startswith(("2d native scroll ", "3d native scroll "))),
                "Unexpected, duplicate or cross-mode scroll captions cannot be relabeled as this scope.")
        reports.append({"case": case, "mode": mode, "scroll_gestures": gestures, "report": report_file})
    return {"captures": captures, "reports": reports, "native_pixel_review_complete": False, "shipping_profile_evidence": False,
            "last_seat_pixel_acceptance": False, "horizontal_roster_exercised": False}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scope", choices=("production", SCROLL_SCOPE), default="production")
    parser.add_argument("--test-source", type=Path)
    parser.add_argument("--test-log", required=True, type=Path)
    parser.add_argument("--xcresult", required=True, type=Path)
    parser.add_argument("--attachments", required=True, type=Path)
    parser.add_argument("--summary", required=True, type=Path)
    parser.add_argument("--command-exit", required=True, type=int)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("Preserve the existing result receipt before another execution.")
    problems = []
    text = args.test_log.read_text(errors="replace") if args.test_log.is_file() else ""
    expected = SCROLL_EXPECTED if args.scope == SCROLL_SCOPE else EXPECTED
    started, finished, passed = inspect_log(text, expected)
    if not passed:
        problems.append("The two exact XCTest cases must each start once and pass once; zero, missing, skipped, failed, extra or repeated cases fail.")
    if args.command_exit != 0:
        problems.append("The native test command or required evidence export did not exit successfully.")
    result_preserved = args.xcresult.is_dir() and any(path.is_file() and path.stat().st_size > 0 for path in args.xcresult.rglob("*"))
    if not result_preserved:
        problems.append("The original nonempty XCResult bundle must be preserved.")
    attachments = [path for path in sorted(args.attachments.rglob("*")) if path.is_file() and path.stat().st_size > 0]
    screenshots = [path for path in attachments if path.suffix.lower() in {".png", ".jpg", ".jpeg"}]
    scroll_evidence, selected_source = None, None
    if args.scope == SCROLL_SCOPE:
        try:
            selected_source = check_scroll_source(args.test_source)
            scroll_evidence = check_scroll_captures(scroll_json(args.attachments / "manifest.json", 4194304), args.attachments)
        except (OSError, ValueError, KeyError, TypeError, RecursionError):
            problems.append("The selected reviewed scroll source and exact per-case captures/report must all pass their scope checks.")
    else:
        observations = []
        for path in attachments:
            if path.suffix.lower() != ".json" or path.stat().st_size > 32768:
                continue
            try:
                value = json.loads(path.read_bytes())
                if isinstance(value, dict) and value.get("schemaVersion") == 1 and value.get("observationInstalled") is True:
                    observations.append(path)
            except (OSError, ValueError, RecursionError):
                continue
        if not screenshots or not observations:
            problems.append("Original screenshot and sanitized observation attachments must both be exported.")
    summary_hash = None
    try:
        summary = json.loads(args.summary.read_bytes())
        summary_hash = digest(args.summary)
        if not inspect_summary(summary):
            problems.append("The XCResult summary must independently report exactly two passes with zero failures, skips or expected failures.")
    except (OSError, ValueError, RecursionError):
        problems.append("The original XCResult test summary must be exported and preserved.")
    result = {
        "schemaVersion": 1,
        "stage": "qualification_scroll_named_test_evidence" if args.scope == SCROLL_SCOPE else "production_session_named_test_evidence",
        "test_scope": args.scope,
        "command_exit": args.command_exit,
        "expected_cases": [f"{target}/{name}" for target, name in sorted(expected)],
        "started": [f"{target}/{name}" for target, name in started],
        "finished": [{"case": f"{target}/{name}", "status": status, "seconds": seconds}
                     for target, name, status, seconds in finished],
        "test_log_sha256": digest(args.test_log) if args.test_log.is_file() else None,
        "test_summary_sha256": summary_hash,
        "xcresult_preserved": result_preserved,
        "attachments": [{"path": path.relative_to(args.attachments).as_posix(), "sha256": digest(path)} for path in attachments],
        "named_test_evidence_complete": passed and not problems,
        "native_acceptance_or_shipping_promotion": False,
        "problems": problems,
    }
    if args.scope == SCROLL_SCOPE:
        result["selected_test_source"] = selected_source
        result["qualification_scroll"] = scroll_evidence
    args.output.parent.mkdir(parents=True, exist_ok=True)
    # Exclusive creation preserves earlier failures and prevents accidental replacement by a rerun.
    with args.output.open("x") as stream:
        json.dump(result, stream, indent=2)
        stream.write("\n")
    print(json.dumps({"named_test_evidence_complete": result["named_test_evidence_complete"], "problems": problems}))
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
