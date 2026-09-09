#!/usr/bin/env python3
"""Select an installed iPhone simulator matching the active Xcode SDK."""

import json
import pathlib
import subprocess
import sys


def simctl_list(kind):
    return json.loads(
        subprocess.check_output(["xcrun", "simctl", "list", kind, "--json"], text=True)
    )[kind]


def main():
    sdk = subprocess.check_output(
        ["xcrun", "--sdk", "iphonesimulator", "--show-sdk-version"], text=True
    ).strip()
    sdk_version = sdk.split(".")[:2]
    runtimes = [
        runtime
        for runtime in simctl_list("runtimes")
        if runtime.get("isAvailable")
        and runtime.get("name", "").startswith("iOS ")
        and runtime.get("version", "").split(".")[:2] == sdk_version
    ]
    devices = simctl_list("devices")
    for runtime in runtimes:
        phones = [
            device
            for device in devices.get(runtime["identifier"], [])
            if device.get("isAvailable") and device.get("name", "").startswith("iPhone ")
        ]
        if not phones:
            continue
        # Prefer an already booted device; otherwise choose deterministically.
        phone = min(phones, key=lambda device: (device.get("state") != "Booted", device["name"]))
        evidence = {"sdk": sdk, "runtime": runtime, "device": phone}
        if len(sys.argv) == 2:
            path = pathlib.Path(sys.argv[1])
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(evidence, indent=2) + "\n")
        print(f"Using {phone['name']} / {runtime['name']} ({phone['udid']})", file=sys.stderr)
        print(phone["udid"])
        return
    raise SystemExit(f"No available iPhone simulator matches iOS SDK {sdk}. Check the selected Xcode/runtime inventory.")


if __name__ == "__main__":
    main()
