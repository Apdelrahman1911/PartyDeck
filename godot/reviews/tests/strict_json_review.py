#!/usr/bin/env python3
"""Independent adversarial corpus for the actual renderer JSON preflight.

Run with Python 3. The production parser is copied into an isolated temporary
Godot project so this review does not import or modify the renderer's cache.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile


def corpus() -> list[dict[str, object]]:
    cases: list[dict[str, object]] = []

    def case(name: str, document: str, valid: bool) -> None:
        cases.append({"name": name, "document": document, "valid": valid})

    for name, document in [
        ("empty object", "{}"),
        ("empty array", "[]"),
        ("scalar null", "null"),
        ("scalar false", "false"),
        ("standard whitespace", ' \t\r\n{"x":true}\t\r\n'),
        ("finite number grammar", "[-0,0,1,-1,1.25,-1.25,1e2,1E+2,1e-2,1.7e308]"),
        ("large integer is grammar-valid", "9007199254740993"),
        ("distinct escaped keys", r'{"x":1,"\u0079":2}'),
        ("escaped controls", r'["\b\f\n\r\t","\/\\\""]'),
        ("valid surrogate pair", r'{"emoji":"\ud83d\ude00"}'),
        ("Unicode scalar strings", '{"emoji":"😀","name":"Léa","separator":"\u2028"}'),
    ]:
        case(name, document, True)

    for name, document in [
        ("empty input", ""),
        ("whitespace without value", " \r\n\t "),
        ("truncated object", '{"x":'),
        ("duplicate key", '{"x":1,"x":2}'),
        ("escaped duplicate key", r'{"x":1,"\u0078":2}'),
        ("nested duplicate key", '{"safe":{"x":1,"x":2}}'),
        ("surrogate pair duplicate key", '{"😀":1,"\\ud83d\\ude00":2}'),
        ("trailing object comma", '{"x":1,}'),
        ("trailing array comma", "[1,]"),
        ("leading comma", "[,1]"),
        ("missing comma", "[1 2]"),
        ("missing colon", '{"x" 1}'),
        ("unquoted key", "{x:1}"),
        ("single quoted string", "{'x':1}"),
        ("line comment", '{"x":1// comment\n}'),
        ("block comment", '{"x":/* comment */1}'),
        ("raw newline", '{"x":"a\nb"}'),
        ("raw tab", '{"x":"a\tb"}'),
        ("unknown escape", r'{"x":"\q"}'),
        ("short Unicode escape", r'{"x":"\u123"}'),
        ("nonhex Unicode escape", r'{"x":"\u12xz"}'),
        ("lone high surrogate", r'{"x":"\ud800"}'),
        ("lone low surrogate", r'{"x":"\udc00"}'),
        ("high surrogate followed by scalar", r'{"x":"\ud800\u0041"}'),
        ("reversed surrogate pair", r'{"x":"\udc00\ud800"}'),
        ("high surrogate followed by high surrogate", r'{"x":"\ud800\ud801"}'),
        ("leading zero", "01"),
        ("negative leading zero", "-01"),
        ("leading plus", "+1"),
        ("leading decimal point", ".5"),
        ("trailing decimal point", "1."),
        ("missing exponent", "1e"),
        ("missing signed exponent", "1e+"),
        ("bare minus", "-"),
        ("NaN", "NaN"),
        ("positive infinity", "Infinity"),
        ("negative infinity", "-Infinity"),
        ("numeric overflow", "1e309"),
        ("non-JSON whitespace", "\u00a0{}"),
        ("byte order mark", "\ufeff{}"),
        ("second root object", "{}{}"),
        ("trailing primitive text", "falsex"),
    ]:
        case(name, document, False)

    case("maximum ASCII byte length", '"' + "a" * 65_534 + '"', True)
    case("oversized ASCII document", '"' + "a" * 65_535 + '"', False)
    case("maximum UTF-8 byte length", '"' + "é" * 32_767 + '"', True)
    case("UTF-8 overflow below character limit", '"' + "é" * 32_768 + '"', False)
    case("maximum accepted nesting", "[" * 16 + "0" + "]" * 16, True)
    case("excessive nesting", "[" * 17 + "0" + "]" * 17, False)
    case("maximum value count", "[" + ",".join(["0"] * 4_095) + "]", True)
    case("excessive value count", "[" + ",".join(["0"] * 4_096) + "]", False)
    return cases


SCRIPT = """
extends SceneTree

const StrictJson = preload("res://strict_json.gd")

func _initialize() -> void:
    var cases = JSON.parse_string(FileAccess.get_file_as_string("res://cases.json"))
    if typeof(cases) != TYPE_ARRAY:
        push_error("Invalid reviewer fixture data.")
        quit(2)
        return
    var failures := 0
    for fixture in cases:
        var result: Dictionary = StrictJson.decode(fixture.document)
        if result.get("ok", false) != fixture.valid:
            failures += 1
            push_error("Unexpected parser decision: " + fixture.name)
    print("Bridge strict JSON review: %d cases, %d failures." % [cases.size(), failures])
    quit(1 if failures > 0 else 0)
"""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--godot",
        default=os.environ.get("PARTYDECK_GODOT_BINARY", "/opt/partydeck-godot/godot"),
    )
    args = parser.parse_args()
    source = Path(__file__).resolve().parents[2] / "renderer/scripts/strict_json.gd"
    source_bytes = source.read_bytes()
    print(f"Parser SHA-256: {hashlib.sha256(source_bytes).hexdigest()}", flush=True)
    with tempfile.TemporaryDirectory(prefix="partydeck-bridge-json-review-") as directory:
        project = Path(directory)
        (project / "project.godot").write_text(
            'config_version=5\n[application]\nconfig/name="Bridge JSON review"\n',
            encoding="utf-8",
        )
        (project / "strict_json.gd").write_bytes(source_bytes)
        (project / "cases.json").write_text(json.dumps(corpus()), encoding="utf-8")
        (project / "review.gd").write_text(SCRIPT, encoding="utf-8")
        completed = subprocess.run(
            [args.godot, "--headless", "--path", directory, "--script", "res://review.gd"],
            timeout=45,
            check=False,
        )
        return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
