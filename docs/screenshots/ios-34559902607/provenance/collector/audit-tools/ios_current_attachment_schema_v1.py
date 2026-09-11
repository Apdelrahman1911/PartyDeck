"""Source-scoped production attachment validation; never decode unnamed JSON."""
import math
import re


def require(ok, path):
    if not ok:
        raise ValueError("Invalid named sanitized attachment field: " + path)


def object_fields(value, required, optional, path):
    require(type(value) is dict, path)
    require(set(required) <= set(value) <= set(required) | set(optional), path)
    for key, check in required.items():
        check(value[key], path + "." + key)
    for key, check in optional.items():
        if key in value and value[key] is not None:
            check(value[key], path + "." + key)


def boolean(value, path):
    require(type(value) is bool, path)


def uint(value, path):
    require(type(value) is int and 0 <= value < 2**64, path)


def integer(value, path):
    require(type(value) is int and -(2**63) <= value < 2**63, path)


def number(value, path):
    require(type(value) in (int, float) and math.isfinite(value), path)


def duration(value, path):
    number(value, path)
    require(value >= 0, path)


def counter(value, path):
    require(type(value) is str and re.fullmatch(r"0|[1-9][0-9]{0,19}", value) is not None, path)
    require(int(value) < 2**64, path)


def enum_name(value, path):
    require(type(value) is str and re.fullmatch(r"[A-Z][A-Z0-9_]{0,63}", value) is not None, path)


def choices(*values):
    def check(value, path):
        require(type(value) is str and value in values, path)
    return check


def one(value, path):
    require(type(value) is int and value == 1, path)


def rect(value, path):
    require(type(value) is list and len(value) == 4, path)
    for item in value:
        number(item, path + "[]")


def size(value, path):
    object_fields(value, {"width": duration, "height": duration}, {}, path)


def receipt(value, path):
    required = {key: counter for key in ("serial", "sessionGeneration", "presentationOrdinal", "expectedRevision", "revision")}
    required.update(mode=choices("COMPOSE", "GODOT_2D", "GODOT_3D"), action=enum_name, accepted=boolean)
    object_fields(value, required, {"error": enum_name}, path)


def controller(value, path):
    required = {key: boolean for key in (
        "supported", "exhausted", "sessionPresent", "practice", "ownTurn", "canSendAction", "canPlay",
        "canChallenge", "canAdvanceRound", "foreground", "backgrounded", "leaveConfirmation")}
    required.update({key: counter for key in ("sessionGeneration", "privacyEpoch", "presentationOrdinal")})
    required.update(screen=enum_name, mode=choices("COMPOSE", "GODOT_2D", "GODOT_3D"), lifecycle=enum_name,
                    round=integer, handCount=integer)
    optional = {key: counter for key in ("sessionRevision", "projectedRendererRevision", "projectedSessionRevision")}
    optional.update({key: enum_name for key in ("phase", "pending", "problem", "fallbackReason")})
    optional["lastViewerReceipt"] = receipt
    object_fields(value, required, optional, path)


def native(value, path):
    required = {key: uint for key in (
        "bootstrapCount", "processIdentifier", "readyEvents", "intentEvents", "exitEvents", "rejectedEvents",
        "nativePresentedFrames", "nativeFailedPresentations", "iterations", "drawCalls",
        "queuedCommands", "queuedEvents", "queuedBytes")}
    required.update({key: counter for key in ("presentationGeneration", "lifecycleGeneration", "inputGeneration")})
    required.update({key: boolean for key in (
        "authorityReadyConfirmed", "nativeForeground", "authorityForegroundGrant", "applicationBackgrounded",
        "inputViewEnabled", "privacyCoverVisible", "renderLoopActive", "dormant", "emptyTree", "surfaceAttached",
        "surfaceAccessibilityHidden", "retainedEnginePolicy", "failurePresent", "quarantined", "retainedIdentitiesMatchFirstEntry")})
    required["surfaceSize"] = size
    optional = {key: duration for key in ("maxDrawSeconds", "maxIterateSeconds", "maxDrainSeconds", "maxBootstrapSeconds")}
    optional["bootstrapPhase"] = choices("not_started", "running", "returned")
    object_fields(value, required, optional, path)


def geometry(value, path):
    object_fields(value, {
        "coordinateSpace": choices("screen"), "frame": rect, "bounds": rect,
        "outerCoverVisible": boolean, "engineAccessibilityHidden": boolean,
        "surfaceAccessibilityHiddenByContainer": boolean}, {}, path)


def control(value, path):
    def group(item, item_path):
        require(type(item) is str and re.fullmatch(r"partydeck_(?:hand_card|action_[a-z_]+)", item) is not None, item_path)
    object_fields(value, {"group": group, "cardIndex": integer, "rect": rect, "clipRect": rect,
                          "visible": boolean, "enabled": boolean, "selected": boolean}, {}, path)


def controls(value, path):
    require(type(value) is list, path)
    for item in value:
        control(item, path + "[]")


def renderer(value, path):
    required = {key: counter for key in ("requestId", "sequence", "revision")}
    required.update({key: boolean for key in ("foreground", "sceneStateApplied", "handConcealed")})
    required.update({key: uint for key in ("selectedCount", "privateFaceCount", "privateLabelCount")})
    required.update(schemaVersion=one, presentationMode=choices("2d", "3d"), coordinateSpace=choices("root_viewport"),
                    viewport=size, controls=controls)
    object_fields(value, required, {}, path)


def preparation(value, path):
    object_fields(value, {"phase": choices("preparing", "succeeded", "failed", "rejected"),
                          "creationPhase": choices("not_started", "running", "returned", "threw")},
                  {"elapsedSeconds": duration, "creationElapsedSeconds": duration}, path)


def modes(value, path):
    require(type(value) is list and len(value) == 2 and all(type(item) is str for item in value)
            and set(value) == {"2d", "3d"}, path)


def port(value, path):
    required = {key: boolean for key in (
        "activationValid", "ownerCreated", "active", "closing", "quarantined", "disposed", "portReadyConfirmed")}
    required.update(profile=choices("qualification"), enabledModes=modes)
    object_fields(value, required, {"lastCloseSucceeded": boolean, "native": native, "geometry": geometry,
                                    "renderer": renderer, "preparation": preparation}, path)


def validate_observation(value, mode):
    object_fields(value, {"schemaVersion": one, "observationSequence": counter,
                          "observationInstalled": boolean, "port": port}, {"controller": controller}, "$")
    state, current = value.get("controller"), value["port"]
    require(value["observationInstalled"] is True and current["activationValid"] is True, "$.qualification")
    require(type(state) is dict and state["supported"] and not state["exhausted"] and state.get("problem") is None,
            "$.controller.health")
    require(not current["quarantined"] and not current["disposed"], "$.port.health")
    native_value, scene = current.get("native"), current.get("renderer")
    if native_value is not None:
        require(not native_value["failurePresent"] and not native_value["quarantined"]
                and native_value["nativeFailedPresentations"] == native_value["rejectedEvents"] == 0,
                "$.port.native.health")
    require(state["mode"] in ("COMPOSE", "GODOT_" + mode.upper()), "$.controller.mode")
    if scene is not None:
        require(scene["presentationMode"] == mode, "$.port.renderer.presentationMode")
    return value


def validate_body_scroll(value, mode):
    def scroll_controls(items, path):
        require(type(items) is list and 1 <= len(items) <= 3, path)
        for item in items:
            object_fields(item, {"action": choices("lobby", "play", "challenge"), "enabled": boolean,
                                "rect": rect, "clipRect": rect}, {}, path + "[]")
        require(len({item["action"] for item in items}) == len(items), path)
    fields = {key: counter for key in ("beforeObservationSequence", "afterObservationSequence",
                                      "beforeRendererSequence", "afterRendererSequence")}
    fields.update({key: uint for key in ("selectedCount", "authorityIntentCountBefore", "authorityIntentCountAfter")})
    fields.update(schemaVersion=one, round=integer, controls=scroll_controls, scrollGestures=uint,
                  canChallenge=boolean, handConcealed=boolean,
                  challengeCoverage=choices("full_bounds_after_native_scroll", "authority_unavailable_not_exercised"))
    object_fields(value, fields, {}, "$")
    require(mode == "3d", "$.sourceMode")
    require(value["scrollGestures"] > 0 and value["selectedCount"] == 1 and value["handConcealed"] is False
            and value["authorityIntentCountBefore"] == value["authorityIntentCountAfter"], "$.scrollContext")
    require(int(value["afterObservationSequence"]) > int(value["beforeObservationSequence"])
            and int(value["afterRendererSequence"]) > int(value["beforeRendererSequence"]), "$.scrollSequences")
    expected = {"lobby", "play", "challenge"} if value["canChallenge"] else {"lobby", "play"}
    coverage = "full_bounds_after_native_scroll" if value["canChallenge"] else "authority_unavailable_not_exercised"
    require({item["action"] for item in value["controls"]} == expected and value["challengeCoverage"] == coverage,
            "$.controls")
    return value


def source_label(human_name, mode):
    """Accept exact source names with xcresulttool's exported-name suffix."""
    require(type(human_name) is str and len(human_name) <= 1024, "$.attachmentName")
    fixed = [
        "production concealed entry", "real native card selection", "Hide removes private faces labels and selection",
        "real authority accepted native Play", "same session Standard return", "Leave cancelled on same concealed session",
        "confirmed Leave ended the session", "new practice reuses engine and receives fresh input",
        "production smoke cleanup complete", "production smoke failure",
        "Standard concealed", "Standard all five native card descriptions", "Standard maximum selection and count-only feedback",
        "Standard Hide removes private nodes and selection", "Standard fresh Reveal is unselected",
    ]
    capture = "(?:" + "|".join(re.escape(mode + " " + item) for item in fixed) + "|" + \
              re.escape(mode) + r" real Standard authority accepted (?:PLAY_CARDS|CHALLENGE|NEXT_ROUND|RETURN_TO_LOBBY|START_GAME)|" + \
              re.escape(mode) + r" round [0-9]+ full native action bounds preserve selection|Actual production Leave confirmation)"
    observation_patterns = [capture + " latest sanitized observation",
                            re.escape(mode) + r" round [0-9]+ selected hand before body scroll",
                            re.escape(mode) + r" measured (?:reveal|card|hide|play|challenge|lobby) before actual coordinate tap",
                            re.escape(mode) + r" measured whole (?:reveal|card|hide|play|challenge|lobby) bounds without tapping",
                            re.escape(mode) + r" measured (?:reveal|card|hide|play|challenge|lobby) before actual scroll"]
    patterns = [("observation", pattern, "json") for pattern in observation_patterns]
    patterns.append(("body-scroll", re.escape(mode) + r" round [0-9]+ actual body scroll coverage", "json"))
    patterns.append(("capture", capture, "(?:png|jpg|jpeg)"))
    for kind, pattern, extension in patterns:
        match = re.fullmatch("(?P<source>" + pattern + r")(?:_[^\x00-\x1f/\\]+\." + extension + ")?", human_name)
        if match:
            return kind, match.group("source")
    return None
