"""Read-only validation of *named*, bounded iOS completed-frame observations.

This module validates recorded structure and association, never performance,
GPU completion, compositor display, readiness, or stable user-visible activity.
The caller owns original-file provenance; this module neither fetches nor edits
evidence. See HANDOFF.md for pins, integration and execution limits.
"""
import argparse
import hashlib
import json
from pathlib import Path
import types

MAX_BYTES = 32768
BASE_SHA256 = "fc9cea014f6996891fe643a0e97e9a337134d2192df20761192415b4c1b9d335"
CODES = frozenset((
    "ARGUMENTS", "INPUT_BYTES", "INPUT_IO", "JSON", "SOURCE_LABEL", "BASE_SOURCE",
    "BASE_SCHEMA", "TIMING_REQUIRED", "TIMING_UNAVAILABLE", "TIMING_SHAPE",
    "TIMING_NUMBER", "TIMING_COUNTER", "TIMING_FLAGS", "TIMING_COUNTERS",
    "TIMING_SAMPLE", "TIMING_GENERATION", "TIMING_ORDER", "TIMING_MARKER",
    "TIMING_ASSOCIATION", "TIMING_JOINT", "TIMING_HISTORY", "INTERNAL_VALIDATION",
))


class ValidationError(ValueError):
    """Safe fixed error category: never contains input keys, values or paths."""
    def __init__(self, code):
        self.code = code if code in CODES else "INTERNAL_VALIDATION"
        super().__init__(self.code)


def require(condition, code):
    if not condition:
        raise ValidationError(code)


def _load_base():
    # Execute the exact immutable helper without creating a __pycache__ file.
    try:
        source = Path(__file__).with_name("ios_current_attachment_schema_v1.py").read_bytes()
        require(hashlib.sha256(source).hexdigest() == BASE_SHA256, "BASE_SOURCE")
        module = types.ModuleType("pinned_ios_current_attachment_schema_v1")
        exec(compile(source, "<pinned attachment schema v1>", "exec"), module.__dict__)
        return module
    except (OSError, SyntaxError) as error:
        raise ValidationError("BASE_SOURCE") from None


try:
    _BASE = _load_base()
except ValidationError:
    _BASE = None


def _check(check, value, code):
    try:
        check(value, "$")
    except (ValueError, TypeError, OverflowError):
        raise ValidationError(code) from None


def _counter(value):
    _check(_BASE.counter, value, "TIMING_COUNTER")
    return int(value)


def _time(value):
    _check(_BASE.duration, value, "TIMING_NUMBER")


def _bool(value):
    _check(_BASE.boolean, value, "TIMING_SHAPE")


def _shape(value, keys):
    require(type(value) is dict and set(value) == set(keys.split()), "TIMING_SHAPE")


def _context(value):
    require(type(value) is list and len(value) == 8, "TIMING_SHAPE")
    for counter in value[:7]:
        _counter(counter)
    require(type(value[7]) is int and 0 <= value[7] <= 511, "TIMING_FLAGS")


def _sample_shape(value):
    _shape(value, "scopeOrdinal completedOrdinal startedUptime completedUptime seconds begin end")
    for key in ("scopeOrdinal", "completedOrdinal"):
        _counter(value[key])
    for key in ("startedUptime", "completedUptime", "seconds"):
        _time(value[key])
    _context(value["begin"])
    _context(value["end"])


def _marker_shape(value):
    _shape(value, "uptime context")
    _time(value["uptime"])
    _context(value["context"])


COUNTS = ("startedCount", "completedCount", "slowCompletedCount", "overwrittenCount", "invalidCompletedCount")
MARKERS = ("readyConfirmed", "firstNativeCoverRelease")
ASSOCIATIONS = ("firstNativeReleaseDraw", "lastIterationInReleaseDraw")


def _frame_shape(frame):
    _shape(frame, "schemaVersion clock snapshotUptime presentationGeneration slowThresholdSeconds sampleCapacity "
                  "draw iterate readyConfirmed firstNativeCoverRelease firstNativeReleaseDraw lastIterationInReleaseDraw")
    require(type(frame["schemaVersion"]) is int and frame["schemaVersion"] == 1 and
            type(frame["sampleCapacity"]) is int and frame["sampleCapacity"] == 4 and
            type(frame["clock"]) is str and frame["clock"] == "system_uptime", "TIMING_SHAPE")
    _time(frame["snapshotUptime"])
    _time(frame["slowThresholdSeconds"])
    require(frame["slowThresholdSeconds"] == 1, "TIMING_SHAPE")
    _counter(frame["presentationGeneration"])
    for name in ("draw", "iterate"):
        stage = frame[name]
        _shape(stage, " ".join(COUNTS) + " counterExhausted last maximum slowSamples")
        for key in COUNTS:
            _counter(stage[key])
        _bool(stage["counterExhausted"])
        require(type(stage["slowSamples"]) is list and len(stage["slowSamples"]) <= 4, "TIMING_SHAPE")
        for key in ("last", "maximum"):
            if stage[key] is not None:
                _sample_shape(stage[key])
        for sample in stage["slowSamples"]:
            _sample_shape(sample)
    for key in MARKERS:
        if frame[key] is not None:
            _marker_shape(frame[key])
    for key in ASSOCIATIONS:
        if frame[key] is not None:
            _sample_shape(frame[key])


def _joint_shape(joint):
    _shape(joint, "presentationGeneration lifecycleGeneration inputGeneration nativeSnapshotUptime "
                  "nativeCoverVisible bothCoversClear shell")
    for key in ("presentationGeneration", "lifecycleGeneration", "inputGeneration"):
        _counter(joint[key])
    _time(joint["nativeSnapshotUptime"])
    _bool(joint["nativeCoverVisible"])
    _bool(joint["bothCoversClear"])
    shell = joint["shell"]
    _shape(shell, "snapshotUptime outerCoverVisible coverTransitions counterExhausted firstReleaseUptime lastTransitionUptime")
    _time(shell["snapshotUptime"])
    _counter(shell["coverTransitions"])
    _bool(shell["outerCoverVisible"])
    _bool(shell["counterExhausted"])
    for key in ("firstReleaseUptime", "lastTransitionUptime"):
        if shell[key] is not None:
            _time(shell[key])


def _context_bounds(context, frame, native):
    bounds = (frame["presentationGeneration"], native["lifecycleGeneration"], native["inputGeneration"],
              frame["draw"]["startedCount"], native["nativePresentedFrames"], native["iterations"])
    require(all(int(context[index]) <= int(bound) for index, bound in enumerate(bounds)), "TIMING_GENERATION")


def _sample(sample, stage, is_draw, frame, native):
    require(0 < int(sample["scopeOrdinal"]) <= int(stage["startedCount"]) and
            0 < int(sample["completedOrdinal"]) <= int(stage["completedCount"]), "TIMING_SAMPLE")
    start, end, seconds = (sample[key] for key in ("startedUptime", "completedUptime", "seconds"))
    require(start <= end <= frame["snapshotUptime"] and abs(seconds - (end - start)) <= 0.000001, "TIMING_SAMPLE")
    begin, finish = sample["begin"], sample["end"]
    _context_bounds(begin, frame, native)
    _context_bounds(finish, frame, native)
    require(all(int(begin[i]) <= int(finish[i]) for i in (0, 1, 2, 4, 5, 6)) and
            begin[3] == finish[3] and (not is_draw or begin[3] == sample["scopeOrdinal"]), "TIMING_SAMPLE")


def _samples(stage):
    return [item for item in (stage["last"], stage["maximum"]) if item is not None] + stage["slowSamples"]


def _stage(stage, is_draw, frame, native, associated):
    started, completed, slow, overwritten, invalid = (int(stage[key]) for key in COUNTS)
    ring = stage["slowSamples"]
    require(not stage["counterExhausted"] and invalid == 0 and completed <= started and slow <= completed and
            len(ring) == min(slow, 4) and overwritten == slow - len(ring), "TIMING_COUNTERS")
    last, maximum = stage["last"], stage["maximum"]
    require((completed == 0) == (last is None) and (completed == 0) == (maximum is None), "TIMING_COUNTERS")
    if last is not None:
        require(int(last["completedOrdinal"]) == completed, "TIMING_ORDER")
        require((slow > 0) == (maximum["seconds"] >= 1), "TIMING_COUNTERS")
    all_samples = _samples(stage) + ([associated] if associated is not None else [])
    for sample in all_samples:
        _sample(sample, stage, is_draw, frame, native)
        require(maximum is not None and sample["seconds"] <= maximum["seconds"], "TIMING_SAMPLE")
        if sample["seconds"] == maximum["seconds"]:
            require(int(maximum["completedOrdinal"]) <= int(sample["completedOrdinal"]), "TIMING_ORDER")
        for other in all_samples:
            order, other_order = int(sample["completedOrdinal"]), int(other["completedOrdinal"])
            if order == other_order or sample["scopeOrdinal"] == other["scopeOrdinal"]:
                require(sample == other, "TIMING_ORDER")
            elif order < other_order:
                require(sample["completedUptime"] <= other["completedUptime"], "TIMING_ORDER")
            # Start chronology is independent of completion chronology (nesting).
            if int(sample["scopeOrdinal"]) < int(other["scopeOrdinal"]):
                require(sample["startedUptime"] <= other["startedUptime"], "TIMING_ORDER")
        # Known qualifying references must occur in the latest-four ring unless
        # they precede its oldest retained completion and overwrite is explicit.
        if sample["seconds"] >= 1 and sample not in ring:
            require(overwritten > 0 and int(sample["completedOrdinal"]) < int(ring[0]["completedOrdinal"]), "TIMING_ORDER")
    for index, sample in enumerate(ring):
        require(sample["seconds"] >= 1, "TIMING_COUNTERS")
        if index:
            before = ring[index - 1]
            require(int(before["completedOrdinal"]) < int(sample["completedOrdinal"]) and
                    before["completedUptime"] <= sample["completedUptime"], "TIMING_ORDER")
    if last is not None and last["seconds"] >= 1:
        require(ring[-1] == last, "TIMING_ORDER")


def _eligible(context):
    return context[7] & 399 == 399 and context[7] & 112 == 0


def _markers(frame, native):
    for key in MARKERS:
        marker = frame[key]
        if marker is not None:
            _context_bounds(marker["context"], frame, native)
            require(int(frame["presentationGeneration"]) > 0 and marker["context"][0] == frame["presentationGeneration"] and
                    marker["uptime"] <= frame["snapshotUptime"], "TIMING_MARKER")
    ready, release = (frame[key] for key in MARKERS)
    if ready is not None:
        require(ready["context"][7] & 9 == 9, "TIMING_MARKER")
    if release is not None:
        require(ready is not None and _eligible(release["context"]) and int(release["context"][3]) > 0 and
                int(release["context"][4]) > 0 and release["uptime"] >= ready["uptime"], "TIMING_MARKER")
    draw, iteration = (frame[key] for key in ASSOCIATIONS)
    if draw is not None:
        require(release is not None, "TIMING_ASSOCIATION")
        require(draw["begin"][0] == draw["end"][0] == frame["presentationGeneration"] and
                draw["scopeOrdinal"] == release["context"][3] and
                draw["startedUptime"] <= release["uptime"] <= draw["completedUptime"] and
                int(draw["begin"][4]) < int(release["context"][4]) <= int(draw["end"][4]), "TIMING_ASSOCIATION")
    if iteration is not None:
        require(release is not None, "TIMING_ASSOCIATION")
        require(iteration["begin"][0] == iteration["end"][0] == frame["presentationGeneration"] and
                iteration["begin"][3] == iteration["end"][3] == release["context"][3] and
                iteration["completedUptime"] <= release["uptime"] and
                int(iteration["end"][5]) < int(release["context"][5]), "TIMING_ASSOCIATION")
        if draw is not None:
            require(draw["startedUptime"] <= iteration["startedUptime"] and
                    iteration["completedUptime"] <= draw["completedUptime"], "TIMING_ASSOCIATION")


def _joint(joint, frame, port, native):
    if joint is None:
        return
    geometry = port.get("geometry")
    require(geometry is not None and port["active"] and not port["closing"] and port["portReadyConfirmed"] and
            native["surfaceAttached"] and native["nativeForeground"] and native["authorityForegroundGrant"] and
            native["authorityReadyConfirmed"] and native["renderLoopActive"] and not native["applicationBackgrounded"] and
            not native["dormant"] and not native["emptyTree"], "TIMING_JOINT")
    require(all(joint[key] == native[key] for key in ("presentationGeneration", "lifecycleGeneration", "inputGeneration")) and
            joint["nativeSnapshotUptime"] == frame["snapshotUptime"] and
            joint["nativeCoverVisible"] == native["privacyCoverVisible"] and
            joint["shell"]["outerCoverVisible"] == geometry["outerCoverVisible"] and
            joint["bothCoversClear"] == (not joint["nativeCoverVisible"] and not joint["shell"]["outerCoverVisible"]), "TIMING_JOINT")
    shell = joint["shell"]
    transitions = int(shell["coverTransitions"])
    require(shell["snapshotUptime"] >= joint["nativeSnapshotUptime"] and not shell["counterExhausted"] and
            shell["outerCoverVisible"] == (transitions % 2 == 0), "TIMING_JOINT")
    first, last = shell["firstReleaseUptime"], shell["lastTransitionUptime"]
    if transitions == 0:
        require(first is None and last is None, "TIMING_JOINT")
    else:
        require(first is not None and last is not None and first <= last <= shell["snapshotUptime"], "TIMING_JOINT")


def _unique_object(pairs):
    value = {}
    for key, item in pairs:
        require(key not in value, "JSON")
        value[key] = item
    return value


def _reject_constant(_value):
    raise ValidationError("JSON")


def _decode(payload, mode, source_name):
    require(type(payload) is bytes and 0 < len(payload) <= MAX_BYTES, "INPUT_BYTES")
    require(type(mode) is str and mode in ("2d", "3d"), "SOURCE_LABEL")
    try:
        source = _BASE.source_label(source_name, mode)
    except (ValueError, TypeError):
        raise ValidationError("SOURCE_LABEL") from None
    require(source is not None and source[0] == "observation", "SOURCE_LABEL")
    try:
        value = json.loads(payload.decode("utf-8"), object_pairs_hook=_unique_object, parse_constant=_reject_constant)
    except (UnicodeError, ValueError, RecursionError, OverflowError):
        raise ValidationError("JSON") from None
    require(type(value) is dict and type(value.get("port")) is dict, "BASE_SCHEMA")
    port = value["port"]
    require("jointVisibility" in port, "TIMING_REQUIRED")
    native, joint = port.get("native"), port["jointVisibility"]
    legacy = {**value, "port": {key: item for key, item in port.items() if key != "jointVisibility"}}
    if native is not None:
        require(type(native) is dict, "BASE_SCHEMA")
        require({"frameTiming", "frameTimingStatus"} <= set(native), "TIMING_REQUIRED")
        legacy["port"]["native"] = {key: item for key, item in native.items() if key not in ("frameTiming", "frameTimingStatus")}
    _check(lambda item, _path: _BASE.validate_observation(item, mode), legacy, "BASE_SCHEMA")
    if joint is not None:
        _joint_shape(joint)
    require(native is not None, "TIMING_UNAVAILABLE")
    status, frame = native["frameTimingStatus"], native["frameTiming"]
    require(type(status) is str and status in ("available", "invalid", "payload_budget"), "TIMING_SHAPE")
    require((status == "available") == (frame is not None) and (status != "invalid" or joint is None), "TIMING_SHAPE")
    require(status == "available", "TIMING_UNAVAILABLE")
    _frame_shape(frame)
    require(frame["presentationGeneration"] == native["presentationGeneration"], "TIMING_GENERATION")
    _stage(frame["draw"], True, frame, native, frame["firstNativeReleaseDraw"])
    _stage(frame["iterate"], False, frame, native, frame["lastIterationInReleaseDraw"])
    _markers(frame, native)
    _joint(joint, frame, port, native)
    return value, source[1]


def _history(before, after):
    require(int(after["observationSequence"]) >= int(before["observationSequence"]), "TIMING_HISTORY")
    old_native, native = before["port"]["native"], after["port"]["native"]
    if native["processIdentifier"] != old_native["processIdentifier"]:
        return "different_process"
    # These are native lifetime counters. Ready/intent/exit event counts are
    # deliberately excluded: the runtime resets those on each presentation.
    lifetime = ("presentationGeneration", "lifecycleGeneration", "inputGeneration",
                "nativePresentedFrames", "iterations", "drawCalls")
    require(all(int(native[key]) >= int(old_native[key]) for key in lifetime), "TIMING_HISTORY")
    old, new = old_native["frameTiming"], native["frameTiming"]
    require(new["snapshotUptime"] >= old["snapshotUptime"] and
            int(new["presentationGeneration"]) >= int(old["presentationGeneration"]), "TIMING_HISTORY")
    for name, association in zip(("draw", "iterate"), ASSOCIATIONS):
        prior, current = old[name], new[name]
        require(all(int(current[key]) >= int(prior[key]) for key in COUNTS), "TIMING_HISTORY")
        completed_delta = int(current["completedCount"]) - int(prior["completedCount"])
        slow_delta = int(current["slowCompletedCount"]) - int(prior["slowCompletedCount"])
        require(slow_delta <= completed_delta, "TIMING_HISTORY")
        prior_samples = _samples(prior) + ([old[association]] if old[association] is not None else [])
        current_samples = _samples(current) + ([new[association]] if new[association] is not None else [])
        for sample in current_samples:
            if int(sample["completedOrdinal"]) > int(prior["completedCount"]):
                require(sample["completedUptime"] >= old["snapshotUptime"], "TIMING_HISTORY")
            if int(sample["scopeOrdinal"]) > int(prior["startedCount"]):
                require(sample["startedUptime"] >= old["snapshotUptime"], "TIMING_HISTORY")
        for sample in prior_samples:
            for other in current_samples:
                if sample["completedOrdinal"] == other["completedOrdinal"] or sample["scopeOrdinal"] == other["scopeOrdinal"]:
                    require(sample == other, "TIMING_HISTORY")
                elif int(sample["completedOrdinal"]) < int(other["completedOrdinal"]):
                    require(sample["completedUptime"] <= other["completedUptime"], "TIMING_HISTORY")
        surviving_count = min(len(prior["slowSamples"]), max(0, 4 - slow_delta))
        surviving = prior["slowSamples"][-surviving_count:] if surviving_count else []
        require(current["slowSamples"][:surviving_count] == surviving, "TIMING_HISTORY")
        new_slow = current["slowSamples"][surviving_count:]
        require(len(new_slow) == min(slow_delta, 4) and
                all(int(sample["completedOrdinal"]) > int(prior["completedCount"]) for sample in new_slow), "TIMING_HISTORY")
        maximum = prior["maximum"]
        if maximum is not None:
            require(current["maximum"] is not None and current["maximum"]["seconds"] >= maximum["seconds"], "TIMING_HISTORY")
            if current["maximum"]["seconds"] == maximum["seconds"]:
                require(current["maximum"] == maximum, "TIMING_HISTORY")
            else:
                require(int(current["maximum"]["completedOrdinal"]) > int(prior["completedCount"]), "TIMING_HISTORY")
        if prior["slowCompletedCount"] == current["slowCompletedCount"]:
            require(prior["slowSamples"] == current["slowSamples"], "TIMING_HISTORY")
        if prior["completedCount"] == current["completedCount"]:
            require(prior["last"] == current["last"], "TIMING_HISTORY")
    if old["presentationGeneration"] == new["presentationGeneration"]:
        for key in MARKERS + ASSOCIATIONS:
            require(old[key] is None or old[key] == new[key], "TIMING_HISTORY")
        left, right = before["port"]["jointVisibility"], after["port"]["jointVisibility"]
        if left is not None and right is not None:
            previous_shell, shell = left["shell"], right["shell"]
            require(shell["snapshotUptime"] >= previous_shell["snapshotUptime"] and
                    int(shell["coverTransitions"]) >= int(previous_shell["coverTransitions"]) and
                    (previous_shell["firstReleaseUptime"] is None or
                     previous_shell["firstReleaseUptime"] == shell["firstReleaseUptime"]), "TIMING_HISTORY")
            if shell["coverTransitions"] == previous_shell["coverTransitions"]:
                require(shell["lastTransitionUptime"] == previous_shell["lastTransitionUptime"], "TIMING_HISTORY")
            else:
                require(shell["lastTransitionUptime"] >= previous_shell["snapshotUptime"], "TIMING_HISTORY")
                if previous_shell["firstReleaseUptime"] is None:
                    require(shell["firstReleaseUptime"] >= previous_shell["snapshotUptime"], "TIMING_HISTORY")
    return "same_process_monotonic"


def _context_class(sample, native):
    if sample is None:
        return "unknown"
    generations = [native[key] for key in ("presentationGeneration", "lifecycleGeneration", "inputGeneration")]
    begin, end = sample["begin"], sample["end"]
    if begin[:3] != generations or end[:3] != generations:
        return "historical_or_mixed_generations"
    if not _eligible(begin) or not _eligible(end):
        return "current_ineligible_boundaries"
    if begin[6] != end[6]:
        return "current_cover_transition"
    return "current_eligible_boundaries"


def _attachment_context(value, mode):
    """Existing live/interactive/concealed predicates, not a visibility grant.

    The external XCUIApplication.frame containment check cannot be recovered
    from a sanitized observation; the caller must execute it separately.
    """
    state, port = value["controller"], value["port"]
    native, scene, geometry = port["native"], port.get("renderer"), port.get("geometry")
    live = bool(scene is not None and geometry is not None and
                state["sessionPresent"] and state["practice"] and state["screen"] == "SESSION" and
                state["mode"] == "GODOT_" + mode.upper() and state["lifecycle"] == "ACTIVE" and
                state["foreground"] and not state["backgrounded"] and not state["leaveConfirmation"] and
                port["active"] and not port["closing"] and port["portReadyConfirmed"] and
                native["bootstrapCount"] == 1 and native["processIdentifier"] > 0 and native["retainedEnginePolicy"] and
                native["retainedIdentitiesMatchFirstEntry"] and native["authorityReadyConfirmed"] and native["readyEvents"] == 1 and
                native["nativeForeground"] and native["authorityForegroundGrant"] and not native["applicationBackgrounded"] and
                native["inputViewEnabled"] and native["surfaceAttached"] and geometry["surfaceAccessibilityHiddenByContainer"] and
                native["renderLoopActive"] and not native["dormant"] and not native["emptyTree"] and not native["privacyCoverVisible"] and
                not geometry["outerCoverVisible"] and geometry["engineAccessibilityHidden"] and scene["foreground"] and
                scene["sceneStateApplied"] and scene["revision"] == state.get("projectedRendererRevision") and
                state.get("sessionRevision") is not None and state["sessionRevision"] == state.get("projectedSessionRevision"))
    dimensions = False
    if scene is not None and geometry is not None:
        frame, bounds, viewport, surface = geometry["frame"], geometry["bounds"], scene["viewport"], native["surfaceSize"]
        dimensions = (frame[2] > 0 and frame[3] > 0 and bounds[2] > 0 and bounds[3] > 0 and
                      abs(bounds[0]) <= 0.5 and abs(bounds[1]) <= 0.5 and
                      viewport["width"] > 0 and viewport["height"] > 0 and
                      all(abs(parts[index] - viewport[key]) <= 1 for parts in (frame, bounds)
                          for index, key in ((2, "width"), (3, "height"))) and
                      all(abs(surface[key] - viewport[key]) <= 1 for key in ("width", "height")))
    concealed = None if scene is None else (scene["handConcealed"] and scene["selectedCount"] == 0 and
                                          scene["privateFaceCount"] == 0 and scene["privateLabelCount"] == 0)
    return {"liveAttachmentPredicatesSatisfied": live, "attachmentGeometryAgrees": dimensions,
            "concealedRendererPredicateSatisfied": concealed, "externalApplicationFrameVerified": False}


def validate_attachment(payload, mode, source_name, *, previous_payload=None, previous_source_name=None):
    """Pure validation of original bytes. Raises only fixed ValidationError codes.

    A preceding observation must have its own exact source name and pass the
    same bounded validation. Repeated cached observations remain valid records
    but never prove fresh progress. No supplied object is mutated.
    """
    require(_BASE is not None, "BASE_SOURCE")
    value, source = _decode(payload, mode, source_name)
    comparison, fresh = "not_requested", False
    if previous_payload is not None:
        require(previous_source_name is not None, "SOURCE_LABEL")
        before, _source = _decode(previous_payload, mode, previous_source_name)
        comparison = _history(before, value)
        fresh = int(value["observationSequence"]) > int(before["observationSequence"])
    else:
        require(previous_source_name is None, "ARGUMENTS")
    native = value["port"]["native"]
    frame, joint = native["frameTiming"], value["port"]["jointVisibility"]
    stages = {}
    for name in ("draw", "iterate"):
        stage = frame[name]
        stages[name] = {**{key: stage[key] for key in COUNTS},
                        "lastSeconds": None if stage["last"] is None else stage["last"]["seconds"],
                        "maximumSeconds": None if stage["maximum"] is None else stage["maximum"]["seconds"],
                        "lastContext": _context_class(stage["last"], native),
                        "maximumContext": _context_class(stage["maximum"], native),
                        "retainedSlowSampleContexts": [_context_class(sample, native) for sample in stage["slowSamples"]]}
    return {"schemaVersion": 1, "timingStructureValidated": True, "mode": mode, "sourceAttachmentName": source,
            "payloadBytes": len(payload), "payloadSha256": hashlib.sha256(payload).hexdigest(),
            "observationSequence": value["observationSequence"], "processIdentifier": native["processIdentifier"],
            "presentationGeneration": frame["presentationGeneration"], "snapshotUptime": frame["snapshotUptime"],
            "stages": stages, "firstNativeCoverReleaseUptime": None if frame["firstNativeCoverRelease"] is None else frame["firstNativeCoverRelease"]["uptime"],
            "completedReleaseDrawRecorded": frame["firstNativeReleaseDraw"] is not None,
            "releaseAssociatedIterationRecorded": frame["lastIterationInReleaseDraw"] is not None,
            "jointCoversClear": None if joint is None else joint["bothCoversClear"],
            "attachmentContext": _attachment_context(value, mode), "comparison": comparison,
            "observationSequenceAdvanced": fresh, "stableActivityIntervalQualified": False,
            "performanceAccepted": False, "firstDisplayEstablished": False, "nativeAcceptance": False}


def _read_bounded(path):
    try:
        with Path(path).open("rb") as stream:
            return stream.read(MAX_BYTES + 1)
    except OSError:
        raise ValidationError("INPUT_IO") from None


class _Parser(argparse.ArgumentParser):
    def error(self, _message):
        raise ValidationError("ARGUMENTS")


def main(argv=None):
    try:
        parser = _Parser(description=__doc__)
        parser.add_argument("attachment")
        parser.add_argument("--mode", required=True, choices=("2d", "3d"))
        parser.add_argument("--source-name", required=True)
        parser.add_argument("--previous")
        parser.add_argument("--previous-source-name")
        args = parser.parse_args(argv)
        report = validate_attachment(_read_bounded(args.attachment), args.mode, args.source_name,
                                     previous_payload=None if args.previous is None else _read_bounded(args.previous),
                                     previous_source_name=args.previous_source_name)
        print(json.dumps({"ok": True, "report": report}, sort_keys=True, allow_nan=False))
        return 0
    except ValidationError as error:
        print(json.dumps({"ok": False, "code": error.code}, sort_keys=True))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
