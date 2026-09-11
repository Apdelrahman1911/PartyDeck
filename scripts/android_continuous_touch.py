"""One test-only, self-target Android touch transaction; no application-state proof."""

import hashlib
import math
import re
import time
import uuid
import xml.etree.ElementTree as ET

import android_godot_session_observation as engine

APK_NAME = "android-continuous-input-debug.apk"
PACKAGE = "dev.partydeck.qualification.input"
INSTRUMENTATION = PACKAGE + ".ContinuousTouchInstrumentation"
COMPONENT = PACKAGE + "/" + INSTRUMENTATION
RESULT_PREFIX = "INSTRUMENTATION_RESULT: partydeckContinuousTouch="
TAIL_MS = 200
TRANSPORT_SECONDS = 10.0
SOURCE_TOUCHSCREEN = 4098
HOST_RECEIPT_TIME = "continuous_input_received_host_time"
ANDROID = "{http://schemas.android.com/apk/res/android}"
require = engine.require


def inspect_manifest(raw):
    """Called on SDK-decoded helper metadata by the same-run producer and consumer."""
    require(len(raw) <= 65536, "Oversized continuous-input manifest.")
    manifest = ET.fromstring(raw)
    require(manifest.tag == "manifest" and manifest.get("package") == PACKAGE,
            "Wrong continuous-input package.")
    require(not any(child.tag.startswith("uses-permission") for child in manifest),
            "The input helper must not request application permissions.")
    apps, instruments, sdks = (manifest.findall(tag) for tag in ("application", "instrumentation", "uses-sdk"))
    require(len(apps) == len(instruments) == len(sdks) == 1, "Ambiguous helper manifest structure.")
    app, instrument, sdk = apps[0], instruments[0], sdks[0]
    require(app.get(ANDROID + "testOnly") == "true" and app.get(ANDROID + "allowBackup") == "false"
            and app.get(ANDROID + "hasCode", "true") == "true",
            "Continuous input requires a test-only helper with code and no backup.")
    require(not any(app.findall(tag) for tag in ("activity", "activity-alias", "service", "receiver", "provider")),
            "The input helper must have no launch or application components.")
    require(instrument.get(ANDROID + "name") == INSTRUMENTATION
            and instrument.get(ANDROID + "targetPackage") == PACKAGE
            and instrument.get(ANDROID + "targetProcesses") is None,
            "Instrumentation must target only the helper's default process.")
    require(sdk.get(ANDROID + "minSdkVersion") == sdk.get(ANDROID + "targetSdkVersion") == "36",
            "Continuous input is scoped to the existing API 36 lane.")
    return {"package": PACKAGE, "instrumentation": INSTRUMENTATION, "targetPackage": PACKAGE,
            "testOnly": True, "androidApi": 36}


def admit_helper(bundle, manifest, report, package_directory):
    path = bundle / APK_NAME
    item = manifest["files"].get(APK_NAME)
    require(type(item) is dict and path.is_file() and not path.is_symlink(),
            "The same-run input helper is absent or indirect.")
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    require(item == {"sha256": digest, "bytes": path.stat().st_size}, "Input-helper bytes changed.")
    inspected = report.get("continuousInput", {})
    require(inspected.get("verified") is True and inspected.get("apkSha256") == digest
            and inspected.get("metadata") == {"package": PACKAGE, "instrumentation": INSTRUMENTATION,
                "targetPackage": PACKAGE, "testOnly": True, "androidApi": 36},
            "The helper lacks same-run package, self-target, signature and test-only verification.")
    packaged = package_directory / "continuous-input-packaged-manifest.xml"
    require(packaged.is_file() and not packaged.is_symlink(), "The original verified helper manifest is required.")
    raw = packaged.read_bytes()
    require(hashlib.sha256(raw).hexdigest() == inspected.get("manifestSha256")
            and inspect_manifest(raw) == inspected["metadata"], "The verified helper manifest changed.")
    certificate = inspected.get("certificateSha256")
    require(type(certificate) is str and re.fullmatch(r"[0-9a-f]{64}", certificate),
            "The helper has no verified signer fingerprint.")
    return {"apk_sha256": digest, "apk_bytes": item["bytes"], "package": PACKAGE, "component": COMPONENT,
            "manifest_sha256": inspected["manifestSha256"], "certificate_sha256": certificate}


def install_helper(smoke, bundle, identity):
    path = bundle / APK_NAME
    require(hashlib.sha256(path.read_bytes()).hexdigest() == identity["apk_sha256"],
            "Admitted helper changed before installation.")
    output = smoke.adb("install", "-t", str(path), timeout=60)
    require(output.rstrip().endswith("Success") and "Failure" not in output,
            "Test-only input-helper installation did not complete.")
    smoke.identity["continuous_input_helper"] = identity


def request_arguments(observation, gesture, sweep_deadline, now, request_id):
    require(re.fullmatch(r"[0-9a-f]{32}", request_id), "Invalid continuous-input correlation id.")
    # The existing caller must still run _before_input() against the current publication.
    engine.fresh_for_input(observation, observation["value"], now)
    received = observation.get(HOST_RECEIPT_TIME)
    requested = observation["requested_host_time"]
    require(type(received) in (int, float) and math.isfinite(received) and requested <= received <= now,
            "Missing current observation receipt clock anchor.")
    require(type(gesture) is dict and set(gesture) == {"start", "end", "duration_ms"},
            "Unexpected continuous-input geometry fields.")
    for point in (gesture["start"], gesture["end"]):
        require(type(point) is list and len(point) == 2 and all(type(v) is int and 0 < v <= 2147483647 for v in point),
                "Input points must be the admitted positive physical coordinates.")
    require(gesture["start"][0] == gesture["end"][0] and gesture["start"][1] > gesture["end"][1],
            "Continuous input supports only the admitted upward body swipe.")
    duration = gesture["duration_ms"]
    require(type(duration) is int and 0 < duration and duration + TAIL_MS < TRANSPORT_SECONDS * 1000,
            "The gesture exceeds the existing input-command budget.")
    require(math.isfinite(sweep_deadline) and now < sweep_deadline, "Context sweep deadline expired.")
    timeout = min(TRANSPORT_SECONDS, sweep_deadline - now)
    captured = engine.integer(observation["value"]["capturedUptimeMs"], 0, engine.MAX_COUNTER)
    expires = engine.integer(observation["value"]["expiresUptimeMs"], 0, engine.MAX_COUNTER)
    # capturedUptimeMs was sampled before this host receipt. Anchoring deadlines to the receipt
    # therefore rounds them earlier; no equality between host and device clock epochs is assumed.
    stop = captured + math.floor((min(now + timeout, sweep_deadline) - received) * 1000)
    start = min(stop, expires, captured + math.floor(
        (requested + engine.MAX_INPUT_AGE_SECONDS - received) * 1000))
    require(captured < start <= stop, "No fresh continuous-input start budget remains.")
    return {"request_id": request_id, "x0": gesture["start"][0], "y0": gesture["start"][1],
            "x1": gesture["end"][0], "y1": gesture["end"][1], "move_ms": duration,
            "start_deadline": start, "stop_deadline": stop}, timeout


RECEIPT_FIELDS = {
    "schemaVersion", "requestId", "ok", "phase", "failureClass", "releaseFailureClass", "start", "end",
    "moveDurationMs", "tailDurationMs", "startDeadlineUptimeMs", "stopDeadlineUptimeMs",
    "downTimeUptimeMs", "downAckUptimeMs", "endpointAckUptimeMs", "tailStartUptimeMs", "tailEndUptimeMs",
    "upEventUptimeMs", "upAckUptimeMs", "eventsAttempted", "eventsAcknowledged", "stationaryMoveEvents",
    "downAttempted", "upAttempted", "tailCompleted", "inputUncertain", "automationFlags",
    "pointerCount", "pointerId", "inputSource",
}


def completed_receipt(output, arguments):
    require(type(output) is str and len(output.encode("utf-8")) <= 65536,
            "Missing or oversized instrumentation completion.")
    lines = output.splitlines()
    receipts = [line[len(RESULT_PREFIX):] for line in lines if line.startswith(RESULT_PREFIX)]
    codes = [line for line in lines if line.startswith("INSTRUMENTATION_CODE:")]
    require(len(receipts) == 1 and codes == ["INSTRUMENTATION_CODE: -1"]
            and not any(token in output for token in ("INSTRUMENTATION_FAILED", "INSTRUMENTATION_ABORTED")),
            "Instrumentation did not finish exactly one successful transaction.")
    value = engine.strict_json(receipts[0])
    require(type(value) is dict and set(value) == RECEIPT_FIELDS, "Unexpected input receipt fields.")
    require(value["ok"] is True and value["phase"] == "completed"
            and value["failureClass"] == value["releaseFailureClass"] == ""
            and value["inputUncertain"] is False
            and all(value[key] is True for key in ("downAttempted", "upAttempted", "tailCompleted")),
            "The input transaction was incomplete or uncertain.")
    require(value["requestId"] == arguments["request_id"]
            and value["start"] == [arguments["x0"], arguments["y0"]]
            and value["end"] == [arguments["x1"], arguments["y1"]], "Input receipt belongs to another request.")
    require(all(type(point) is list and all(type(part) is int for part in point)
                for point in (value["start"], value["end"])), "Input receipt coordinates changed type.")
    fixed = {"schemaVersion": 1, "moveDurationMs": arguments["move_ms"], "tailDurationMs": TAIL_MS,
             "automationFlags": 3, "pointerCount": 1, "pointerId": 0, "inputSource": SOURCE_TOUCHSCREEN,
             "startDeadlineUptimeMs": arguments["start_deadline"], "stopDeadlineUptimeMs": arguments["stop_deadline"]}
    require(all(type(value[key]) is int and value[key] == expected for key, expected in fixed.items()),
            "Input identity, geometry timing or platform flags changed.")
    stamps = ["downTimeUptimeMs", "downAckUptimeMs", "endpointAckUptimeMs", "tailStartUptimeMs",
              "tailEndUptimeMs", "upEventUptimeMs", "upAckUptimeMs"]
    require(all(type(value[key]) is int and value[key] > 0 for key in stamps), "Invalid device input clocks.")
    require([value[key] for key in stamps] == sorted(value[key] for key in stamps)
            and value["downAckUptimeMs"] < arguments["start_deadline"]
            and value["upAckUptimeMs"] < arguments["stop_deadline"]
            and value["endpointAckUptimeMs"] - value["downTimeUptimeMs"] >= arguments["move_ms"]
            and value["tailEndUptimeMs"] - value["tailStartUptimeMs"] >= TAIL_MS,
            "Continuous movement/tail/release did not complete within its admitted clocks.")
    counts = [value[key] for key in ("eventsAttempted", "eventsAcknowledged", "stationaryMoveEvents")]
    require(all(type(v) is int for v in counts) and counts[0] == counts[1]
            and 2 <= counts[2] and counts[2] + 3 <= counts[0] <= int(TRANSPORT_SECONDS * 120) + 4,
            "The receipt does not acknowledge a complete bounded event stream.")
    return value


def inject_continuous_touch(smoke, observation, gesture, sweep_deadline, audit=None):
    require(not smoke.input_incomplete, "Uncertain prior input forbids continuous touch.")
    started = time.monotonic()
    arguments, timeout = request_arguments(observation, gesture, sweep_deadline,
                                          started, uuid.uuid4().hex)
    host_stop = min(started + timeout, sweep_deadline)
    audit = {} if audit is None else audit
    audit.update(arguments=arguments, host_started=started, host_deadline=host_stop, status="preparing")
    smoke.staging_time()
    argv = ["shell", "am", "instrument", "-w", "-r", "--no-test-api-access", "--always-check-signature"]
    for key, value in arguments.items():
        argv.extend(("-e", key, str(value)))
    argv.append(COMPONENT)
    try:
        remaining = host_stop - time.monotonic()
        require(remaining > 0, "Continuous input expired before transport.")
        audit["status"] = "transport-requested"
        output = smoke.adb(*argv, timeout=remaining)
        audit.update(status="validating-completion", host_returned=time.monotonic())
        if type(output) is str:
            raw = output.encode("utf-8")
            audit.update(completion_bytes=len(raw), completion_sha256=hashlib.sha256(raw).hexdigest())
        require(time.monotonic() < host_stop, "Continuous input returned after its host deadline.")
        receipt = completed_receipt(output, arguments)
        require(time.monotonic() < host_stop, "Continuous input validation exceeded its host deadline.")
        audit.update(status="completed", receipt=receipt)
        return receipt
    except BaseException as error:
        # am instrument is an input transaction even though it does not begin with shell input.
        # A timeout, partial result, false injection or bad receipt authorizes no new UI input.
        smoke.input_incomplete = True
        audit.update(status="failed-or-uncertain", failure_class=type(error).__name__)
        if isinstance(error, engine.ObservationFailure):
            audit["failure"] = str(error)
        if isinstance(error, Exception):
            raise engine.ObservationFailure("Continuous touch transport did not complete; further input is forbidden.") from error
        raise
