#!/usr/bin/env python3
"""Generate and verify explicit iOS Godot build activation without native tools."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import plistlib
import re
from typing import Optional


ROOT = Path(__file__).resolve().parents[1]
SOURCE_PLIST = ROOT / "iosApp/PartyDeck/Info.plist"
PROFILE_KEY = "PartyDeckGodotActivationProfile"
ACCEPTED_KEY = "PartyDeckQualifiedGodotPresentations"
REQUESTED_KEY = "PartyDeckQualificationGodotPresentations"
MODE_ORDER = ("2d", "3d")
EXPECTATION_STAGE = "production_ios_activation_expectation_only"


class UniqueDictionary(dict):
    def __setitem__(self, key, value):
        if key in self:
            raise ValueError(f"Duplicate property list key: {key}")
        super().__setitem__(key, value)


def unique_json_pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate activation expectation key: {key}")
        result[key] = value
    return result


def reject_json_constant(value):
    raise ValueError(f"Invalid activation expectation constant: {value}")


def json_bytes(value: dict) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n").encode("utf-8")


def file_identity(path: Path, data: bytes) -> dict:
    return {"path": str(path.resolve()), "sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)}


def read_plist(path: Path) -> tuple[dict, dict]:
    data = path.read_bytes()
    info = plistlib.loads(data, dict_type=UniqueDictionary)
    if not isinstance(info, dict):
        raise ValueError("The application Info.plist must contain a dictionary.")
    return info, file_identity(path, data)


def parse_modes(value, field: str) -> list[str]:
    if type(value) is not list or any(type(mode) is not str or mode not in MODE_ORDER for mode in value):
        raise ValueError(f"{field} must be an array containing only 2d and 3d strings.")
    if len(value) != len(set(value)):
        raise ValueError(f"{field} must not contain duplicate modes.")
    return [mode for mode in MODE_ORDER if mode in value]


def requested_modes(value: str) -> list[str]:
    modes = parse_modes(value.split(","), "Qualification request")
    if not modes:
        raise ValueError("An explicit qualification request must contain at least one mode.")
    return modes


def resolve_activation(info: dict) -> dict:
    """Resolve all fields strictly; never salvage valid elements from an invalid list."""
    profile = info.get(PROFILE_KEY, "shipping")
    if type(profile) is not str or profile not in ("shipping", "qualification"):
        raise ValueError("The Godot activation profile must be shipping or qualification.")
    accepted = parse_modes(info.get(ACCEPTED_KEY, []), ACCEPTED_KEY)
    requested = parse_modes(info.get(REQUESTED_KEY, []), REQUESTED_KEY)
    if profile == "shipping" and requested:
        raise ValueError("A shipping plist must not contain pending qualification modes.")
    if profile == "qualification" and not requested:
        raise ValueError("A qualification plist requires a nonempty requested mode list.")
    return {
        "profile": profile,
        "accepted_shipping_modes": accepted,
        "qualification_modes": requested,
        "configured_enabled_native_modes": accepted if profile == "shipping" else requested,
    }


def validated_configuration(value: dict) -> dict:
    keys = {"profile", "accepted_shipping_modes", "qualification_modes", "configured_enabled_native_modes"}
    if not isinstance(value, dict) or set(value) != keys:
        raise ValueError("Missing or unexpected staged activation fields.")
    resolved = resolve_activation({
        PROFILE_KEY: value["profile"],
        ACCEPTED_KEY: value["accepted_shipping_modes"],
        REQUESTED_KEY: value["qualification_modes"],
    })
    if json_bytes(value) != json_bytes(resolved):
        raise ValueError("The staged activation must contain canonical modes and the selected profile's effective set.")
    return resolved


def validated_file_identity(value: dict) -> dict:
    if (not isinstance(value, dict) or set(value) != {"path", "sha256", "bytes"}
            or type(value["path"]) is not str or not Path(value["path"]).is_absolute()
            or type(value["sha256"]) is not str or re.fullmatch(r"[a-f0-9]{64}", value["sha256"]) is None
            or type(value["bytes"]) is not int or value["bytes"] <= 0):
        raise ValueError("An activation input needs an absolute path, SHA-256 and byte count.")
    return value


def expectation_document(source: dict, generated: dict, activation: dict) -> dict:
    return {
        "schema_version": 1,
        "stage": EXPECTATION_STAGE,
        "source_plist": source,
        "generated_plist": generated,
        "activation": activation,
        "ios_runtime_executed": False,
        "kmp_factory_qualified": False,
    }


def generate_qualification(
    source_plist: Path, modes: str, output_plist: Path, expectation_path: Path
) -> dict:
    paths = (source_plist, output_plist, expectation_path)
    if (len({path.resolve() for path in paths}) != 3
            or any(first.exists() and second.exists() and first.samefile(second)
                   for index, first in enumerate(paths) for second in paths[index + 1:])):
        raise ValueError("The source plist, generated plist and expectation must be different files.")
    requested = requested_modes(modes)
    source, source_identity = read_plist(source_plist)
    if resolve_activation(source)["profile"] != "shipping":
        raise ValueError("Qualification must clone the checked-in shipping configuration.")
    generated = dict(source)
    generated[PROFILE_KEY] = "qualification"
    generated[REQUESTED_KEY] = requested
    generated_data = plistlib.dumps(generated, sort_keys=False)
    expectation = expectation_document(
        source_identity, file_identity(output_plist, generated_data), resolve_activation(generated)
    )
    output_plist.parent.mkdir(parents=True, exist_ok=True)
    expectation_path.parent.mkdir(parents=True, exist_ok=True)
    output_plist.write_bytes(generated_data)
    expectation_path.write_bytes(json_bytes(expectation))
    return expectation


def checked_activation(
    source_plist: Path, input_plist: Path, expectation_path: Optional[Path] = None
) -> dict:
    source, source_identity = read_plist(source_plist)
    source_activation = resolve_activation(source)
    if source_activation["profile"] != "shipping":
        raise ValueError("The checked-in app plist must remain a shipping configuration.")
    selected, input_identity = read_plist(input_plist)
    activation = resolve_activation(selected)
    expectation = None
    if expectation_path is None:
        if (activation["profile"] != "shipping"
                or any(input_identity[key] != source_identity[key] for key in ("sha256", "bytes"))):
            raise ValueError("A plist override requires its explicit generated qualification expectation.")
    else:
        if activation["profile"] != "qualification":
            raise ValueError("An explicit qualification expectation requires a qualification plist.")
        # Preserve both the accepted shipping list and every unrelated plist value,
        # including types (Python equality alone treats False and 0 as equal).
        clone = dict(source)
        clone[PROFILE_KEY] = "qualification"
        clone[REQUESTED_KEY] = activation["qualification_modes"]
        if plistlib.dumps(selected) != plistlib.dumps(clone):
            raise ValueError("The qualification plist may change only its profile and requested mode list.")
        data = expectation_path.read_bytes()
        document = json.loads(data, object_pairs_hook=unique_json_pairs, parse_constant=reject_json_constant)
        expected = expectation_document(source_identity, input_identity, activation)
        if json_bytes(document) != json_bytes(expected):
            raise ValueError("The qualification plist does not match its explicit activation expectation.")
        expectation = {"file": file_identity(expectation_path, data), "document": document}
    return {
        "source_plist": source_identity,
        "input_plist": input_identity,
        "configuration": activation,
        "expectation": expectation,
    }


def validated_staged_activation(value: dict) -> dict:
    if not isinstance(value, dict) or set(value) != {"source_plist", "input_plist", "configuration", "expectation"}:
        raise ValueError("Missing or unexpected activation binding in the production input receipt.")
    source = validated_file_identity(value["source_plist"])
    selected = validated_file_identity(value["input_plist"])
    activation = validated_configuration(value["configuration"])
    expectation = value["expectation"]
    if activation["profile"] == "shipping":
        if expectation is not None or any(source[key] != selected[key] for key in ("sha256", "bytes")):
            raise ValueError("Shipping activation must identify the checked-in source plist.")
    else:
        if not isinstance(expectation, dict) or set(expectation) != {"file", "document"}:
            raise ValueError("Qualification activation must retain its explicit expectation and file identity.")
        validated_file_identity(expectation["file"])
        if json_bytes(expectation["document"]) != json_bytes(expectation_document(source, selected, activation)):
            raise ValueError("The staged activation differs from its explicit qualification expectation.")
    return activation


def verify_packaged_activation(info: dict, staged: dict) -> dict:
    expected = validated_staged_activation(staged)
    actual = resolve_activation(info)
    # Xcode merges generated bundle fields; only activation fields must match the
    # selected input semantically. The caller records the actual built plist hash.
    if actual != expected:
        raise ValueError("The packaged application activation differs from the staged build expectation.")
    return actual


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-plist", type=Path, default=SOURCE_PLIST)
    parser.add_argument("--modes", required=True, help="Explicit qualification subset: 2d, 3d, or 2d,3d.")
    parser.add_argument("--output-plist", type=Path, required=True)
    parser.add_argument("--expectation", type=Path, required=True)
    args = parser.parse_args()
    result = generate_qualification(args.source_plist, args.modes, args.output_plist, args.expectation)
    print("Generated iOS qualification activation for "
          + ",".join(result["activation"]["configured_enabled_native_modes"])
          + "; runtime qualification remains pending.")


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, TypeError, OverflowError) as error:
        raise SystemExit(str(error)) from error
