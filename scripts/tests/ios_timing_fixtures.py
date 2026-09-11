"""Synthetic numeric fixtures only; no original observations or private data."""
from copy import deepcopy
import json


def encoded(value):
    return json.dumps(value, separators=(",", ":"), allow_nan=False).encode("utf-8")


def source_name(mode="2d"):
    return mode + " production concealed entry latest sanitized observation"


def context(draw, presented=9, iterations=19, flags=399, generation=3, lifecycle=4, input_generation=5, covers=1):
    return [str(value) for value in (generation, lifecycle, input_generation, draw, presented, iterations, covers)] + [flags]


def sample(scope, completed, start, end, begin, finish, seconds=None):
    return {"scopeOrdinal": str(scope), "completedOrdinal": str(completed), "startedUptime": start,
            "completedUptime": end, "seconds": end - start if seconds is None else seconds,
            "begin": begin, "end": finish}


def stage(started=0, completed=0, last=None, maximum=None, slow=0, ring=None):
    return {"startedCount": str(started), "completedCount": str(completed), "slowCompletedCount": str(slow),
            "overwrittenCount": str(max(0, slow - 4)), "invalidCompletedCount": "0", "counterExhausted": False,
            "last": deepcopy(last), "maximum": deepcopy(maximum), "slowSamples": deepcopy(ring or [])}


def baseline(mode="2d"):
    draw = sample(8, 8, 100, 101, context(8, flags=415), context(8, 10, 20))
    iteration = sample(20, 20, 100.2, 100.8, context(8, flags=415), context(8, flags=415), seconds=0.6)
    frame = {"schemaVersion": 1, "clock": "system_uptime", "snapshotUptime": 102,
             "presentationGeneration": "3", "slowThresholdSeconds": 1, "sampleCapacity": 4,
             "draw": stage(8, 8, draw, draw, 1, [draw]), "iterate": stage(20, 20, iteration, iteration),
             "readyConfirmed": {"uptime": 99, "context": context(0, flags=415)},
             "firstNativeCoverRelease": {"uptime": 101, "context": context(8, 10, 20)},
             "firstNativeReleaseDraw": deepcopy(draw), "lastIterationInReleaseDraw": deepcopy(iteration)}
    native = {
        "bootstrapCount": 1, "processIdentifier": 123, "readyEvents": 1, "intentEvents": 0, "exitEvents": 0,
        "rejectedEvents": 0, "nativePresentedFrames": 10, "nativeFailedPresentations": 0, "iterations": 20,
        "drawCalls": 8, "queuedCommands": 0, "queuedEvents": 0, "queuedBytes": 0,
        "presentationGeneration": "3", "lifecycleGeneration": "4", "inputGeneration": "5",
        "authorityReadyConfirmed": True, "nativeForeground": True, "authorityForegroundGrant": True,
        "applicationBackgrounded": False, "inputViewEnabled": True, "privacyCoverVisible": False,
        "renderLoopActive": True, "dormant": False, "emptyTree": False, "surfaceAttached": True,
        "surfaceAccessibilityHidden": False, "retainedEnginePolicy": True, "failurePresent": False,
        "quarantined": False, "retainedIdentitiesMatchFirstEntry": True,
        "surfaceSize": {"width": 390, "height": 844}, "frameTimingStatus": "available", "frameTiming": frame,
    }
    controller = {
        "supported": True, "exhausted": False, "sessionPresent": True, "practice": True,
        "ownTurn": True, "canSendAction": True, "canPlay": True, "canChallenge": False,
        "canAdvanceRound": False, "foreground": True, "backgrounded": False, "leaveConfirmation": False,
        "sessionGeneration": "1", "privacyEpoch": "2", "presentationOrdinal": "3", "screen": "SESSION",
        "mode": "GODOT_" + mode.upper(), "lifecycle": "ACTIVE", "round": 0, "handCount": 5,
        "sessionRevision": "22", "projectedRendererRevision": "7", "projectedSessionRevision": "22",
    }
    renderer = {
        "schemaVersion": 1, "requestId": "30", "sequence": "30", "revision": "7", "foreground": True,
        "sceneStateApplied": True, "handConcealed": True, "selectedCount": 0, "privateFaceCount": 0,
        "privateLabelCount": 0, "presentationMode": mode, "coordinateSpace": "root_viewport",
        "viewport": {"width": 390, "height": 844}, "controls": [],
    }
    geometry = {"coordinateSpace": "screen", "frame": [0, 0, 390, 844], "bounds": [0, 0, 390, 844],
                "outerCoverVisible": False, "engineAccessibilityHidden": True, "surfaceAccessibilityHiddenByContainer": True}
    joint = {"presentationGeneration": "3", "lifecycleGeneration": "4", "inputGeneration": "5",
             "nativeSnapshotUptime": 102, "nativeCoverVisible": False, "bothCoversClear": True,
             "shell": {"snapshotUptime": 102.01, "outerCoverVisible": False, "coverTransitions": "1",
                       "counterExhausted": False, "firstReleaseUptime": 101.2, "lastTransitionUptime": 101.2}}
    return {"schemaVersion": 1, "observationSequence": "50", "observationInstalled": True, "controller": controller,
            "port": {"profile": "qualification", "enabledModes": ["2d", "3d"], "activationValid": True,
                     "ownerCreated": True, "active": True, "closing": False, "quarantined": False,
                     "disposed": False, "portReadyConfirmed": True, "native": native, "geometry": geometry,
                     "renderer": renderer, "preparation": None, "jointVisibility": joint}}


def timing(value):
    return value["port"]["native"]["frameTiming"]


def forget_markers(value):
    frame = timing(value)
    for key in ("readyConfirmed", "firstNativeCoverRelease", "firstNativeReleaseDraw", "lastIterationInReleaseDraw"):
        frame[key] = None
    value["port"]["jointVisibility"] = None


def recurrence():
    value = baseline()
    value["observationSequence"] = "54"
    native, frame = value["port"]["native"], timing(value)
    first = deepcopy(frame["draw"]["maximum"])
    retained = [sample(n, n, 100 + 2 * (n - 8), 101 + 2 * (n - 8),
                       context(n, 9 + n - 8, 19 + n - 8), context(n, 10 + n - 8, 20 + n - 8)) for n in (9, 10, 11, 12)]
    frame["draw"] = stage(12, 12, retained[-1], first, 5, retained)
    last_iteration = sample(24, 24, 108.2, 108.8, context(12, 13, 23), context(12, 13, 23), seconds=0.6)
    frame["iterate"] = stage(24, 24, last_iteration, frame["iterate"]["maximum"])
    frame["snapshotUptime"] = 110
    native.update(nativePresentedFrames=14, iterations=24, drawCalls=12)
    joint = value["port"]["jointVisibility"]
    joint["nativeSnapshotUptime"] = 110
    joint["shell"]["snapshotUptime"] = 110.01
    value["port"]["renderer"]["sequence"] = "34"
    return value


def nested():
    value = baseline()
    forget_markers(value)
    frame = timing(value)
    outer = sample(7, 8, 100, 103, context(7, 8, 19), context(7, 10, 20))
    inner = sample(8, 7, 100.5, 102, context(8, 8, 19), context(8, 9, 20))
    frame["draw"] = stage(8, 8, outer, outer, 2, [inner, outer])
    iteration = sample(20, 20, 100.6, 101.5, context(8, 8, 19), context(8, 8, 19))
    frame["iterate"] = stage(20, 20, iteration, iteration)
    frame["snapshotUptime"] = 104
    return value


def mixed_generation():
    value = baseline()
    forget_markers(value)
    native, frame = value["port"]["native"], timing(value)
    native.update(presentationGeneration="4", lifecycleGeneration="5", inputGeneration="6")
    frame["presentationGeneration"] = "4"
    draw = sample(8, 8, 100, 101, context(8), context(8, 10, 20, generation=4, lifecycle=5, input_generation=6))
    frame["draw"] = stage(8, 8, draw, draw, 1, [draw])
    return value


def in_flight():
    value = baseline()
    forget_markers(value)
    native, frame = value["port"]["native"], timing(value)
    frame["draw"], frame["iterate"] = stage(started=1), stage()
    native.update(nativePresentedFrames=0, iterations=0, drawCalls=1, authorityReadyConfirmed=False,
                  readyEvents=0, inputViewEnabled=False, privacyCoverVisible=True, renderLoopActive=False)
    value["port"]["portReadyConfirmed"] = False
    value["port"]["renderer"] = None
    value["port"]["geometry"]["outerCoverVisible"] = True
    return value


FIXTURES = {"baseline": baseline, "recurrence": recurrence, "nested": nested,
            "mixed_generation": mixed_generation, "in_flight": in_flight}
