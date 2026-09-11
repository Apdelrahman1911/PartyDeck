#!/usr/bin/env python3
"""Check shipping APK activation through both real picker/native/Standard routes.

record-inputs binds the build outputs immediately after building/signing. run
checks those bytes, the actual shipping manifest and signature before any adb.
This uses native controls only; it never requests qualification observations or
engine gameplay. Native Ready is host/draw evidence, not renderer pixel review.
The specified device is a dedicated test device: its PartyDeck data is cleared.
"""

import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import xml.etree.ElementTree as ET
import zipfile


sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("partydeck_shipping_session", Path(__file__).with_name("smoke-android-godot-session.py"))
session = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(session)
activation = session.activation
require = session.require
MODES = ("2d", "3d")
EXPECTED = activation.activation_values("shipping", "2d,3d")
INPUT_KEYS = {"schemaVersion", "scope", "context", "variant", "files"}


def read_json(raw):
    return json.loads(raw, object_pairs_hook=activation.unique_json_object)


def file_record(path):
    require(path.is_file() and not path.is_symlink(), "Input must be a regular non-symlink file.")
    return {"bytes": path.stat().st_size, "sha256": session.sha256_file(path)}


def build_context(revision):
    require(re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", revision), "A full source revision is required.")
    actual = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, check=True, timeout=20)
    require(actual.stdout.decode().strip() == revision, "Source revision differs from the current checkout.")
    clean = subprocess.run(["git", "status", "--porcelain=v1", "--untracked-files=all"],
                           cwd=ROOT, capture_output=True, timeout=20)
    require(clean.returncode == 0 and not clean.stdout.strip(),
            "Working tree contains uncommitted tracked or untracked files.")
    context = {"sourceRevision": revision, "attribution": "Build-step receipt; not an embedded APK attestation."}
    keys = ("GITHUB_SHA", "GITHUB_RUN_ID", "GITHUB_RUN_ATTEMPT", "GITHUB_REPOSITORY")
    values = [os.environ.get(key, "") for key in keys]
    if any(values):
        sha, run, attempt, repository = values
        require(sha == revision and run.isdigit() and attempt.isdigit()
                and re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repository),
                "Complete matching GitHub source/run/attempt/repository context is required.")
        context.update(runId=run, runAttempt=attempt, repository=repository)
    else:
        context.update(runId=None, runAttempt=None, repository=None)
    return context


def input_paths(args):
    paths = {"apk": args.apk, "buildExpectation": args.build_expectation,
             "rendererPack": args.renderer_pack,
             "rendererReceipt": args.renderer_pack.with_suffix(".receipt.json")}
    if args.variant == "optimized-test-signed":
        require(args.signing_receipt is not None and args.unsigned_apk is not None,
                "Optimized input requires its disposable-signing receipt and original unsigned APK.")
        paths.update(signingReceipt=args.signing_receipt, unsignedApk=args.unsigned_apk)
    else:
        require(args.signing_receipt is None and args.unsigned_apk is None,
                "Debug input must not claim an optimized signing receipt.")
    return paths


def input_record(args):
    paths = input_paths(args)
    expected_raw = paths["buildExpectation"].read_bytes()
    require(len(expected_raw) <= 4096 and activation.parse_build_expectation(expected_raw) == EXPECTED,
            "Build expectation must expose both modes with the shipping profile.")
    return {"schemaVersion": 1, "scope": "shipping-native-entry", "context": build_context(args.source_revision),
            "variant": args.variant, "files": {key: file_record(path) for key, path in paths.items()}}


def checked_command(argv, output, name, timeout=60):
    argv = [str(item) for item in argv]
    receipt = {"argv": argv, "startedUtc": session.utc_now(), "exitCode": None}
    stdout = stderr = b""
    try:
        completed = subprocess.run(argv, capture_output=True, timeout=timeout)
        stdout, stderr = completed.stdout, completed.stderr
        receipt["exitCode"] = completed.returncode
    except subprocess.TimeoutExpired as error:
        stdout, stderr = error.stdout or b"", error.stderr or b""
        receipt["timedOut"] = True
        raise
    finally:
        receipt["endedUtc"] = session.utc_now()
        for stream, raw in (("stdout", stdout), ("stderr", stderr)):
            path = output / (name + "." + stream + ".log")
            path.write_bytes(raw)
            receipt[stream] = {"file": path.name, "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}
        (output / (name + ".json")).write_text(json.dumps(receipt, indent=2) + "\n")
    require(completed.returncode == 0, name + " failed; inspect the original command receipt.")
    return stdout


def packaged_boundary(raw, variant):
    require(len(raw) <= 2_097_152 and activation.parse_packaged_manifest(raw) == EXPECTED,
            "Actual APK must package shipping and both modes.")
    application = ET.fromstring(raw).find("application")
    android = activation.ANDROID
    debuggable = application.get(android + "debuggable", "false")
    require(debuggable == ("true" if variant == "debug" else "false"), "Actual debuggable flag differs from variant.")

    def component(tag, name):
        matches = [node for node in application.findall(tag) if node.get(android + "name") == name]
        require(len(matches) == 1, "Expected exactly one private production component.")
        return matches[0]

    renderer = component("activity", "dev.partydeck.app.godot.SessionGodotActivity")
    broker = component("service", "dev.partydeck.app.godot.GodotSessionBrokerService")
    require(renderer.get(android + "exported") == "false" and renderer.get(android + "process") == ":godot"
            and broker.get(android + "exported") == "false" and broker.get(android + "process") is None
            and application.get(android + "process") is None, "Private renderer/broker process boundary differs.")
    return {"activation": EXPECTED, "debuggable": debuggable == "true", "rendererProcess": ":godot",
            "rendererExported": False, "brokerExported": False}


def verify_inputs(args, output):
    file_record(args.inputs)
    raw = args.inputs.read_bytes()
    require(len(raw) <= 65_536, "Producer receipt is oversized.")
    recorded = read_json(raw)
    require(type(recorded) is dict and set(recorded) == INPUT_KEYS and type(recorded["schemaVersion"]) is int,
            "Unexpected producer receipt schema.")
    require(recorded == input_record(args), "Build inputs, source/run context or variant changed since the producer receipt.")
    (output / "producer-inputs.json").write_bytes(raw)
    paths = input_paths(args)
    for key, name in (("buildExpectation", "activation-build-expectation.json"),
                      ("rendererReceipt", "renderer.receipt.json"), ("signingReceipt", "runtime-package.json")):
        if key in paths:
            (output / name).write_bytes(paths[key].read_bytes())
    checked_command([sys.executable, "-B", ROOT / "godot/tools/renderer.py", "check-pack", "--pack", args.renderer_pack],
                    output, "source-pack-check")
    sdk = Path(os.environ.get("ANDROID_HOME", ""))
    require(os.environ.get("ANDROID_HOME") and sdk.is_dir(), "Set ANDROID_HOME to the installed Android SDK.")
    manifest = checked_command([sdk / "cmdline-tools/latest/bin/apkanalyzer", "manifest", "print", args.apk],
                               output, "packaged-manifest")
    (output / "packaged-manifest.xml").write_bytes(manifest)
    boundary = packaged_boundary(manifest, args.variant)
    with zipfile.ZipFile(args.apk) as archive:
        entries = [row for row in archive.infolist() if row.filename == "assets/partydeck-last-light.pck"]
        require(len(entries) == 1, "APK must contain one real renderer PCK.")
        with archive.open(entries[0]) as stream:
            embedded_hash = hashlib.file_digest(stream, "sha256").hexdigest()
    require(embedded_hash == recorded["files"]["rendererPack"]["sha256"], "Embedded PCK differs from the bound source pack.")
    tools = sdk / "build-tools/36.0.0"
    signature = checked_command([tools / "apksigner", "verify", "--verbose", "--print-certs", args.apk],
                                output, "signature").decode("utf-8")
    certificates = re.findall(r"^Signer #\d+ certificate SHA-256 digest: ([0-9a-fA-F]{64})$", signature, re.M)
    require(len(certificates) == 1, "Expected one freshly verified APK signer.")
    certificate = certificates[0].lower()
    if args.variant == "optimized-test-signed":
        signing = read_json(paths["signingReceipt"].read_bytes())
        require(type(signing) is dict and signing.get("variant") == args.variant
                and signing.get("signingIdentity") == "disposable-ci-test-key" and signing.get("distributionSigned") is False
                and signing.get("alignmentKiB") == 16 and signing.get("certificateSha256") == certificate
                and signing.get("runtimeApkSha256") == recorded["files"]["apk"]["sha256"]
                and signing.get("originalUnsignedSha256") == recorded["files"]["unsignedApk"]["sha256"],
                "Optimized APK, original unsigned input and verified signer differ from the CI signing receipt.")
    checked_command([tools / "zipalign", "-c", "-P", "16", "-v", "4", args.apk], output, "alignment")
    require(input_record(args) == recorded, "An input or source context changed during package checks.")
    return {"verified": True, "producerReceiptSha256": hashlib.sha256(raw).hexdigest(), "inputs": recorded,
            "packaged": boundary, "embeddedPackSha256": embedded_hash, "certificateSha256": certificate,
            "signingCategory": "disposable-ci-test-key" if args.variant == "optimized-test-signed" else "debuggable-test-package",
            "publisherSigningQualified": False}


def reject_observer(root):
    require(not any(node.get("resource-id", "").rsplit("/", 1)[-1] == "godot_qualification_observation"
                    for node in root.iter("node")), "Shipping UI exposes a qualification observation node.")


class ShippingSmoke(session.GodotSessionSmoke):
    def dump_ui(self, deadline=None):
        root = super().dump_ui(deadline)
        reject_observer(root)
        return root

    def run_shipping_mode(self, mode):
        with self.check(f"{mode}.practice-baseline") as entry:
            self.tap_action("home-practice")
            self.wait_for_human_turn()
            self.assert_concealed()
            baseline = self.observe_match(f"{mode}-baseline")
            self.select_first_card(f"{mode}-baseline")
            entry["baseline"] = baseline
        with self.check(f"{mode}.native-entry") as entry:
            pid, task, _ = self.enter_native(mode, f"{mode}-entry")
            entry.update(selectedMode=mode, rendererPid=pid, taskId=task,
                         scope="Actual picker input, distinct app-owned native process and Ready/draw; pixels require review.")
        with self.check(f"{mode}.standard-return") as entry:
            self.tap_action("native-standard-table", "Standard table", scroll=None)
            entry["continuity"] = self.require_concealed_return(baseline, f"{mode}-standard")
            entry["scope"] = "Actual native Standard button; original shell/task, public round/rank/turn, one indexed card/count and cleared selection."
        with self.check(f"{mode}.reentry-leave") as entry:
            pid, task, _ = self.enter_native(mode, f"{mode}-reentry")
            self.tap_action("native-leave-table", "Leave table", scroll=None)
            self.leave_dialog(f"{mode}-leave")
            self.tap_action("leave-confirm", "Leave table")
            self.wait_for_action("home-practice", scroll="down")
            self.wait_activity(session.MAIN_COMPONENT, child_absent=True)
            root = self.dump_ui()
            require(not any(session.tagged_node(root, tag) is not None for tag in ("game-table", "game-hand", "leave-confirm")),
                    "Practice remains after the real Leave confirmation.")
            self.capture_evidence(f"{mode}-home", session.MAIN_COMPONENT)
            entry.update(selectedMode=mode, rendererPid=pid, taskId=task,
                         scope="Fresh renderer lifetime, actual native Leave, real confirmation and Home without a renderer child.")


def parser():
    result = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = result.add_subparsers(dest="command", required=True)
    for name in ("record-inputs", "run"):
        child = commands.add_parser(name, allow_abbrev=False)
        child.add_argument("--apk", type=Path, required=True)
        child.add_argument("--variant", choices=("debug", "optimized-test-signed"), required=True)
        child.add_argument("--source-revision", required=True)
        child.add_argument("--build-expectation", type=Path, required=True)
        child.add_argument("--renderer-pack", type=Path, required=True)
        child.add_argument("--signing-receipt", type=Path)
        child.add_argument("--unsigned-apk", type=Path)
        child.add_argument("--inputs", type=Path, required=True, help="Fresh producer JSON for record-inputs; original JSON for run.")
        if name == "run":
            child.add_argument("--serial", required=True, help="Dedicated test device; PartyDeck data will be cleared.")
            child.add_argument("--output", type=Path, required=True, help="Fresh evidence directory; never overwritten.")
            child.add_argument("--font-scale", choices=("1.0", "2.0"), default="1.0")
    return result


def main(argv=None):
    arguments = parser()
    args = arguments.parse_args(argv)
    if args.command == "record-inputs":
        record = input_record(args)
        args.inputs.parent.mkdir(parents=True, exist_ok=True)
        with args.inputs.open("x") as stream:
            json.dump(record, stream, indent=2, sort_keys=True)
            stream.write("\n")
        print("Recorded shipping build inputs: " + str(args.inputs))
        return 0
    try:
        session.fresh_output(args.output)
    except FileExistsError:
        arguments.error("--output already exists; preserve prior evidence and choose a fresh directory")
    report = {"schemaVersion": 1, "scope": "shipping-native-entry", "status": "running", "startedUtc": session.utc_now(),
              "requestedModes": list(MODES), "engineGameplayRequested": False, "qualificationObservationRequested": False,
              "variant": args.variant, "fontScale": args.font_scale,
              "limits": ["Shipping picker/native controls and session continuity only; real engine gameplay remains separately qualified.",
                         "Native Ready is host/draw evidence; original renderer and privacy pixels require independent review.",
                         "Continuity uses the surviving shell/task, public round/rank/turn and one indexed card/count; not full-hand or authority-session identity.",
                         "No child-kill, physical LAN, hardware performance, screen-reader or publisher-signing qualification."]}
    smoke = None
    failed = True
    try:
        package_output = args.output / "package"
        package_output.mkdir()
        report["package"] = verify_inputs(args, package_output)
        native_output = args.output / "runtime"
        native_output.mkdir()
        smoke = ShippingSmoke(args.serial, native_output, args.variant, args.font_scale)
        smoke.identity.update(input_apk=str(args.apk.resolve()), input_apk_sha256=report["package"]["inputs"]["files"]["apk"]["sha256"],
                              checker_sha256=session.sha256_file(Path(__file__)),
                              session_helper_sha256=session.sha256_file(Path(__file__).with_name("smoke-android-godot-session.py")),
                              ui_helper_sha256=session.sha256_file(session.HELPER_PATH))
        report.update(identity=smoke.identity, checks=smoke.checks, captures=smoke.captures,
                      steps=smoke.steps, observations=smoke.observations)
        smoke.setup_session(args.apk)
        for mode in MODES:
            smoke.run_shipping_mode(mode)
        require(input_record(args) == report["package"]["inputs"], "Build inputs or source context changed during native execution.")
        failed = False
    except Exception as error:
        failed = True
        report.update(error=session.ui.redacted(str(error)), failedStage=smoke.stage if smoke is not None else "package")
        print("Shipping activation failed: " + session.ui.redacted(str(error)), file=sys.stderr)
    finally:
        if smoke is not None:
            errors = []
            try:
                errors.extend(smoke.diagnostics())
            except Exception as error:
                errors.append(session.ui.redacted(str(error)))
            try:
                errors.extend(smoke.restore_environment())
            except Exception as error:
                errors.append(session.ui.redacted(str(error)))
            expected_checks = {"installation"} | {f"{mode}.{suffix}" for mode in MODES
                                                 for suffix in ("practice-baseline", "native-entry", "standard-return", "reentry-leave")}
            if set(smoke.checks) != expected_checks or any(check.get("status") != "passed" for check in smoke.checks.values()):
                errors.append("Every required shipping check must finish with an explicit pass.")
            if errors:
                report["diagnosticOrRestoreErrors"] = errors
                failed = True
        report.update(status="failed" if failed else "passed", passed=not failed, endedUtc=session.utc_now())
        report["artifacts"] = [{"file": str(path.relative_to(args.output)), **file_record(path)}
                               for path in sorted(args.output.rglob("*")) if path.is_file()]
        (args.output / "shipping-activation-result.json").write_text(json.dumps(report, indent=2) + "\n")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
