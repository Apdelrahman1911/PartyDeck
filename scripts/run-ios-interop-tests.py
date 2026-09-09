#!/usr/bin/env python3
"""Keep the real JVM TLS peer alive while Xcode runs the iOS-hosted tests."""

import argparse
import json
import os
from pathlib import Path
import re
import selectors
import signal
import subprocess
import sys
import time


def stop_process(process):
    if process is None:
        return
    # Both children start new sessions. Their groups contain only owned work,
    # including Xcode's compiler children, and may outlive the direct process.
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        process.wait(timeout=5)
        return
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        process.poll()
        try:
            os.killpg(process.pid, 0)
        except ProcessLookupError:
            break
        time.sleep(0.1)
    else:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    process.wait(timeout=5)


def collect_xcode_output(xcode, fixture, log):
    deadline = time.monotonic() + 30 * 60
    with selectors.DefaultSelector() as selector:
        selector.register(xcode.stdout, selectors.EVENT_READ)
        while selector.get_map() or xcode.poll() is None:
            if time.monotonic() >= deadline:
                raise RuntimeError("xcodebuild test exceeded its 30-minute deadline.")
            fixture_status = fixture.poll()
            if fixture_status is not None and fixture_status != 0:
                raise RuntimeError(f"The Java TLS fixture failed during XCTest with exit code {fixture_status}.")
            for key, _events in selector.select(timeout=0.5):
                chunk = os.read(key.fileobj.fileno(), 65536)
                if not chunk:
                    selector.unregister(key.fileobj)
                    continue
                log.write(chunk)
                log.flush()
                sys.stdout.buffer.write(chunk)
                sys.stdout.buffer.flush()
    return xcode.wait(timeout=5)


def await_manifest(path, fixture):
    deadline = time.monotonic() + 60
    while time.monotonic() < deadline:
        if fixture.poll() is not None:
            raise RuntimeError("The Java TLS fixture exited before publishing its manifest.")
        if path.exists():
            manifest = json.loads(path.read_text())
            if (
                manifest.get("version") != 1
                or type(manifest.get("port")) is not int
                or not 1 <= manifest["port"] <= 65535
                or re.fullmatch(r"[0-9a-f]{64}", manifest.get("certificateSha256", "")) is None
            ):
                raise RuntimeError("The Java TLS fixture published an invalid manifest.")
            return manifest
        time.sleep(0.2)
    raise RuntimeError("The Java TLS fixture did not become ready within 60 seconds.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--classpath", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("command", nargs=argparse.REMAINDER)
    arguments = parser.parse_args()
    command = arguments.command
    if command[:1] == ["--"]:
        command = command[1:]
    if not command:
        parser.error("Provide the xcodebuild test command after --.")

    output = arguments.output.resolve()
    interop = output / "interop"
    interop.mkdir(parents=True, exist_ok=True)
    manifest_path, result_path = interop / "manifest.json", interop / "result.json"
    for path in (manifest_path, result_path):
        path.unlink(missing_ok=True)
    classpath = arguments.classpath.read_text().strip()
    if not classpath:
        raise RuntimeError("The exported JVM test runtime classpath is empty.")

    fixture = xcode = None
    evidence = {"passed": False}
    try:
        with (interop / "java-fixture.log").open("w") as fixture_log:
            fixture = subprocess.Popen(
                ["java", "-cp", classpath, "dev.partydeck.transport.JavaSwiftInteropFixture",
                 str(manifest_path), str(result_path)],
                stdout=fixture_log, stderr=subprocess.STDOUT,
                start_new_session=True,
            )
            manifest = await_manifest(manifest_path, fixture)
            environment = os.environ.copy()
            environment["TEST_RUNNER_PARTYDECK_INTEROP_MANIFEST"] = json.dumps(manifest)
            environment["TEST_RUNNER_PARTYDECK_INTEROP_REQUIRED"] = "1"
            with (output / "xcodebuild.log").open("wb") as xcode_log:
                xcode = subprocess.Popen(
                    command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                    env=environment, start_new_session=True,
                )
                xcode_status = collect_xcode_output(xcode, fixture, xcode_log)
            evidence["xcodeExitCode"] = xcode_status
            if xcode_status != 0:
                raise RuntimeError(f"xcodebuild test failed with exit code {xcode_status}.")

            # A missing environment handoff must not become an unnoticed XCTest
            # skip. Require actual success of the named native interop method.
            native_test = "testSwiftAndJavaTLSInteroperabilityInBothDirections"
            test_log = (output / "xcodebuild.log").read_text(errors="replace")
            if re.search(r"Test [Cc]ase[^\n]*" + native_test + r"[^\n]*\bpassed\b", test_log) is None:
                raise RuntimeError("XCTest did not report the required Java–Swift interop test as passed.")
            evidence["nativeInteropTest"] = native_test
            fixture_status = fixture.wait(timeout=30)
            evidence["javaExitCode"] = fixture_status
            if fixture_status != 0:
                raise RuntimeError(f"The Java TLS fixture failed with exit code {fixture_status}.")
            result = json.loads(result_path.read_text())
            expected = {
                "version": 1, "status": "PASS",
                "forwardBytesReceived": 65536, "forwardBytesSent": 20000,
                "reverseBytesSent": 20000, "reverseBytesReceived": 65536,
            }
            if any(result.get(key) != value for key, value in expected.items()):
                raise RuntimeError("The Java TLS fixture did not report the complete two-direction exchange.")
            terminal_states = {"Closed", "Failed:UNAVAILABLE", "Failed:IO_ERROR"}
            if any(result.get(key) not in terminal_states for key in ("forwardTerminalState", "reverseTerminalState")):
                raise RuntimeError("The Java TLS fixture did not report both connections terminating after remote close.")
            evidence["passed"] = True
    except BaseException as error:
        evidence["error"] = str(error)
        raise
    finally:
        stop_process(xcode)
        stop_process(fixture)
        if xcode is not None:
            evidence["xcodeExitCode"] = xcode.returncode
            xcode.stdout.close()
        if fixture is not None:
            evidence["javaExitCode"] = fixture.returncode
        (interop / "orchestration.json").write_text(json.dumps(evidence, indent=2) + "\n")


if __name__ == "__main__":
    signal.signal(signal.SIGTERM, lambda _signum, _frame: sys.exit(143))
    main()
