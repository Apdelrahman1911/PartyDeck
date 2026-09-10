"""Strict build-expectation and decoded-APK metadata checks; no runtime activation."""

import json
import xml.etree.ElementTree as ET


PROFILE_KEY = "dev.partydeck.GODOT_ACTIVATION_PROFILE"
MODES_KEY = "dev.partydeck.GODOT_PRESENTATION_MODES"
ANDROID = "{http://schemas.android.com/apk/res/android}"
MODE_ORDER = ("2d", "3d")


def activation_values(profile, modes_csv):
    if type(profile) is not str or profile not in {"shipping", "qualification"} or type(modes_csv) is not str:
        raise ValueError("Activation requires a recognized string profile and string modes CSV.")
    modes = modes_csv.split(",") if modes_csv else []
    if (any(mode not in MODE_ORDER for mode in modes) or len(modes) != len(set(modes))
            or ",".join(mode for mode in MODE_ORDER if mode in modes) != modes_csv):
        raise ValueError("Presentation modes must be unique known tokens in canonical 2d,3d order.")
    if profile == "qualification" and not modes:
        raise ValueError("A qualification APK must expose a nonempty mode list.")
    return {"profile": profile, "modesCsv": modes_csv, "modes": modes}


def unique_json_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate key in the activation build expectation.")
        result[key] = value
    return result


def parse_build_expectation(raw):
    value = json.loads(raw, object_pairs_hook=unique_json_object)
    if (type(value) is not dict or set(value) != {"schemaVersion", "profile", "modesCsv"}
            or type(value["schemaVersion"]) is not int or value["schemaVersion"] != 1):
        raise ValueError("Invalid activation build expectation schema.")
    return activation_values(value["profile"], value["modesCsv"])


def parse_packaged_manifest(raw):
    manifest = ET.fromstring(raw)
    if manifest.tag != "manifest" or manifest.get("package") != "dev.partydeck.app":
        raise ValueError("The decoded manifest is not the production PartyDeck package.")
    applications = manifest.findall("application")
    if len(applications) != 1:
        raise ValueError("Expected one packaged application declaration.")
    values = {}
    for key in (PROFILE_KEY, MODES_KEY):
        entries = [item for item in applications[0].findall("meta-data") if item.get(ANDROID + "name") == key]
        if len(entries) != 1 or ANDROID + "resource" in entries[0].attrib or ANDROID + "value" not in entries[0].attrib:
            raise ValueError(f"Expected one literal packaged metadata value: {key}")
        values[key] = entries[0].get(ANDROID + "value")
    return activation_values(values[PROFILE_KEY], values[MODES_KEY])


def require_qualification_match(expected, packaged, requested_modes_csv):
    required = activation_values("qualification", requested_modes_csv)
    if expected != required:
        raise ValueError("The build expectation differs from the explicitly requested qualification modes.")
    if packaged != expected:
        raise ValueError("The actual APK activation metadata differs from the build expectation.")
