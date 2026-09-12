#!/usr/bin/env python3
"""Prepare the shared Godot art pack from PartyDeck's audited local sources.

Uses the development-only dependencies in assets/tools/requirements.txt. Never
downloads artwork, fonts, audio, Godot, or export templates.
"""

import argparse
from collections import Counter
from hashlib import sha256
from io import BytesIO
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import wave
from xml.etree import ElementTree

import cairosvg
from PIL import Image, ImageColor, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[2]
DESTINATION = ROOT / "godot/renderer/assets"
COMMON = ROOT / "composeApp/src/commonMain/composeResources"
GENERATOR = "godot/tools/prepare_assets.py"
RANKS = ("crown", "moon", "star", "wild")
PALETTE = {"ink": "#191526", "paper": "#F4F0E8", "citron": "#D6EF82", "copper": "#F16B48"}
DOCUMENTATION = [
    "https://raw.githubusercontent.com/godotengine/godot-docs/4.7/tutorials/assets_pipeline/importing_images.rst",
    "https://raw.githubusercontent.com/godotengine/godot-docs/4.7/tutorials/assets_pipeline/importing_audio_samples.rst",
    "https://raw.githubusercontent.com/godotengine/godot-docs/4.7/tutorials/ui/gui_using_fonts.rst",
    "https://raw.githubusercontent.com/godotengine/godot/4.7.2-stable/doc/classes/ResourceImporterTexture.xml",
    "https://raw.githubusercontent.com/godotengine/godot/4.7.2-stable/doc/classes/Image.xml",
    "https://raw.githubusercontent.com/godotengine/godot/4.7.2-stable/core/io/image.cpp",
    "https://raw.githubusercontent.com/godotengine/godot/4.7.2-stable/modules/webp/webp_common.cpp",
    "https://raw.githubusercontent.com/godotengine/godot/4.7.2-stable/doc/classes/ResourceImporterDynamicFont.xml",
    "https://raw.githubusercontent.com/godotengine/godot/4.7.2-stable/doc/classes/ResourceImporterWAV.xml",
    "https://raw.githubusercontent.com/godotengine/godot/4.7.2-stable/doc/classes/HashingContext.xml",
]


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def source_record(path: Path) -> dict:
    data = path.read_bytes()
    return {"file": path.relative_to(ROOT).as_posix(), "bytes": len(data), "sha256": sha256(data).hexdigest()}


def import_options(entry: dict) -> dict:
    kind = entry["kind"]
    if kind in ("vector", "rank_texture", "card_texture"):
        options = {"compress/mode": 0, "mipmaps/generate": kind != "vector", "process/fix_alpha_border": True, "detect_3d/compress_to": 0}
        if kind == "vector":
            options["svg/scale"] = 4.0
        return options
    if kind == "audio":
        return {"compress/mode": 0, "force/8_bit": False, "force/mono": False, "force/max_rate": False, "edit/trim": False, "edit/normalize": False, "edit/loop_mode": 1}
    return {}


def write_manifest(manifest: dict) -> None:
    (DESTINATION / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")


def record_sidecars(manifest: dict) -> None:
    paths = sorted(DESTINATION.rglob("*.import"))
    if paths:
        manifest["import_sidecars"] = [source_record(path) for path in paths]
        manifest["total_bytes_with_import_settings"] = manifest["total_file_bytes"] + sum(item["bytes"] for item in manifest["import_sidecars"])


def write_asset(entries: list, relative: str, data: bytes, kind: str, sources: list[Path], transformation: str, **metadata) -> None:
    path = DESTINATION / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.is_file() or path.read_bytes() != data:
        path.write_bytes(data)
    entries.append({
        "file": relative,
        "resource": None if relative.startswith("sources/") else "res://assets/" + relative,
        "kind": kind,
        "bytes": len(data),
        "sha256": sha256(data).hexdigest(),
        "sources": [source_record(source) for source in sources],
        "transformation": transformation,
        **metadata,
    })


def raster(svg: bytes, size: tuple[int, int], *, transparent_rgb: str | None = None) -> bytes:
    rendered = cairosvg.svg2png(bytestring=svg, output_width=size[0], output_height=size[1])
    with Image.open(BytesIO(rendered)) as image:
        image = image.convert("RGBA")
        if transparent_rgb is not None:
            # Godot's alpha-edge fix only reaches four pixels into transparency.
            # Fill the remaining hidden RGB too, so mipmaps retain the card's
            # base color at the rounded opaque mesh edge. Preserve all alpha
            # and every pixel with visible coverage from the SVG raster.
            transparent = image.getchannel("A").point(lambda alpha: 255 if alpha == 0 else 0)
            image.paste((*ImageColor.getrgb(transparent_rgb), 0), mask=transparent)
        output = BytesIO()
        image.save(output, format="PNG", optimize=True)
        return output.getvalue()


def card_face(rank: str) -> bytes:
    """Compose wordless card artwork from the existing border and rank paths."""
    back = ElementTree.fromstring((ROOT / "assets/vectors/card_back.svg").read_bytes())
    outline = back[0].attrib["d"]
    border = back[1].attrib["d"]
    rank_svg = (ROOT / f"assets/vectors/rank_{rank}.svg").read_text(encoding="utf-8")
    symbol = rank_svg.split(">", 1)[1].rsplit("</svg>", 1)[0].strip()
    corner = f'<g transform="translate(13 12) scale(0.4375)">{symbol}</g>'
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" width="512" height="768" viewBox="0 0 160 240">\n'
        '  <!-- Original PartyDeck card composition; source rank and border paths are retained. -->\n'
        f'  <path d="{outline}" fill="{PALETTE["paper"]}"/>\n'
        f'  <path d="{border}" fill="none" stroke="#D6D0C4" stroke-width="0.7"/>\n'
        f'  {corner}\n'
        f'  <g transform="rotate(180 80 120)">{corner}</g>\n'
        f'  <g transform="translate(28 72) scale(1.625)">{symbol}</g>\n'
        '  <path d="M51 183 H109" fill="none" stroke="#D6D0C4" stroke-width="0.7"/>\n'
        '</svg>\n'
    ).encode("utf-8")


def prepare() -> dict:
    DESTINATION.mkdir(parents=True, exist_ok=True)
    entries = []
    font_manifest = json.loads((ROOT / "assets/font_sources.json").read_text())
    notices = []
    for source in font_manifest:
        path = ROOT / source["file"]
        data = path.read_bytes()
        require(sha256(data).hexdigest() == source["sha256"], f"Font source integrity failed: {path}")
        is_font = path.suffix == ".ttf"
        relative = ("fonts/" if is_font else "licenses/") + path.name
        metadata = {"license": source["license"], "upstream_source": source["source"]}
        if is_font:
            family = "fraunces" if "fraunces" in path.name else "manrope"
            metadata["license_notice"] = f"res://assets/licenses/{family}_ofl.txt"
        else:
            notices.append((path, data))
        write_asset(entries, relative, data, "font" if is_font else "license", [path], "Byte-exact copy.", **metadata)

    credits = [
        b"PartyDeck fonts\n\n"
        b"Fraunces: The Fraunces Project Authors; design by Undercase Type, Phaedra Charles, and Flavia Zimbardi.\n"
        b"Manrope: The Manrope Project Authors; design by Mikhail Sharanda.\n\n"
        b"Both fonts are unmodified and distributed under SIL Open Font License 1.1.\n"
    ]
    credits += [b"\n" + b"=" * 72 + b"\n" + path.name.encode() + b"\n\n" + data for path, data in notices]
    write_asset(entries, "licenses/font_notices.txt", b"\n".join(credits) + b"\n", "font_credits", [path for path, _ in notices], "Font credits followed by each complete, byte-exact OFL notice.")

    for path in sorted((ROOT / "assets/vectors").glob("*.svg")):
        data = path.read_bytes()
        svg = ElementTree.fromstring(data)
        require(not any(node.tag.rsplit("}", 1)[-1] in ("text", "image", "script") for node in svg.iter()), f"Unexpected SVG dependency: {path}")
        write_asset(entries, "vectors/" + path.name, data, "vector", [path, ROOT / "assets/tools/generate_vectors.py"], "Byte-exact original SVG copy.", size=[int(svg.attrib["width"]), int(svg.attrib["height"])], origin="Original PartyDeck geometry.")

    for rank in RANKS:
        source = ROOT / f"assets/vectors/rank_{rank}.svg"
        svg = source.read_bytes()
        for mask in (False, True):
            data = svg.replace(PALETTE["ink"].encode(), b"#FFFFFF") if mask else svg
            name = rank + ("_mask" if mask else "")
            write_asset(entries, f"textures/ranks/{name}.png", raster(data, (256, 256)), "rank_texture", [source, ROOT / GENERATOR], "Rasterized original SVG at 256 square; ink changed to white for multiplicative tinting." if mask else "Rasterized original SVG at 256 square; colors preserved.", size=[256, 256], tint_mask=mask, origin="Original PartyDeck geometry.")

        face = card_face(rank)
        sources = [source, ROOT / "assets/vectors/card_back.svg", ROOT / GENERATOR]
        write_asset(entries, f"sources/cards/face_{rank}.svg", face, "editable_card_source", sources, "Original composition reusing existing rank and card-border paths; no text or lighting.", size=[512, 768], origin="Original PartyDeck geometry.")
        editable = DESTINATION / f"sources/cards/face_{rank}.svg"
        write_asset(entries, f"textures/cards/face_{rank}.png", raster(face, (512, 768), transparent_rgb=PALETTE["paper"]), "card_texture", [editable, *sources], "Rasterized wordless original card composition; transparent rounded corners, no baked lighting or shadows. RGB beneath zero alpha retains the paper base for clean mipmap edges.", size=[512, 768], rank=rank, transparent_rgb=PALETTE["paper"], origin="Original PartyDeck geometry.")
    back = ROOT / "assets/vectors/card_back.svg"
    write_asset(entries, "textures/cards/back.png", raster(back.read_bytes(), (512, 768), transparent_rgb=PALETTE["ink"]), "card_texture", [back, ROOT / GENERATOR], "Rasterized original card back at 512 by 768; original colors and transparent corners retained. RGB beneath zero alpha retains the ink base for clean mipmap edges.", size=[512, 768], transparent_rgb=PALETTE["ink"], origin="Original PartyDeck geometry.")

    for clip in json.loads((ROOT / "assets/audio_manifest.json").read_text()):
        path = COMMON / clip["resource_path"]
        data = path.read_bytes()
        require(sha256(data).hexdigest() == clip["sha256"], f"Audio source integrity failed: {path}")
        with wave.open(BytesIO(data), "rb") as reader:
            pcm = reader.readframes(reader.getnframes())
        write_asset(entries, "audio/" + path.name, data, "audio", [path, ROOT / "assets/tools/generate_audio.py"], "Byte-exact original PCM WAVE copy.", cue=clip["feedback_cue"], duration_ms=clip["duration_ms"], sample_frames=clip["sample_frames"], sample_rate_hz=clip["sample_rate_hz"], channels=clip["channels"], bits_per_sample=clip["bits_per_sample"], pcm_sha256=sha256(pcm).hexdigest(), origin=clip["origin"])

    (DESTINATION / "sources/.gdignore").write_text("Editable source compositions are excluded from runtime imports.\n")
    for entry in entries:
        entry["import_options"] = import_options(entry)
    manifest = {
        "schema": 1,
        "engine_release": "4.7.2-stable",
        "generator": source_record(ROOT / GENERATOR),
        "palette": PALETTE,
        "files": entries,
        "counts": dict(sorted(Counter(entry["kind"] for entry in entries).items())),
        "total_file_bytes": sum(entry["bytes"] for entry in entries),
        "documentation": DOCUMENTATION,
        "scope": "Shared artwork, fonts, and short cues only. Engine and exported native-library notices are tracked by the renderer packaging owner.",
    }
    record_sidecars(manifest)
    write_manifest(manifest)
    return manifest


def verify(manifest: dict) -> dict:
    credits = (DESTINATION / "licenses/font_notices.txt").read_bytes()
    for entry in manifest["files"]:
        path = DESTINATION / entry["file"]
        data = path.read_bytes()
        require(len(data) == entry["bytes"] and sha256(data).hexdigest() == entry["sha256"], f"Asset changed: {path}")
        for source in entry["sources"]:
            require(source_record(ROOT / source["file"]) == source, f"Source mapping changed: {source['file']}")
        if entry["kind"] == "license":
            require(data in credits, f"Font credits omit the full license: {path}")
        if entry["kind"] in ("rank_texture", "card_texture"):
            with Image.open(path) as image:
                require(image.mode == "RGBA" and list(image.size) == entry["size"], f"Unexpected texture format: {path}")
                require(image.getchannel("A").getextrema() == (0, 255), f"Texture alpha range changed: {path}")
                require(image.getpixel((0, 0))[3] == 0, f"Opaque outer corner: {path}")
                if entry["kind"] == "card_texture":
                    expected_rgb = bytes(ImageColor.getrgb(entry["transparent_rgb"]))
                    pixels = image.tobytes()
                    require(all(pixels[index:index + 3] == expected_rgb
                                for index in range(0, len(pixels), 4) if pixels[index + 3] == 0),
                            f"Card base color missing beneath transparent corners: {path}")
    require(source_record(ROOT / GENERATOR) == manifest["generator"], "Regenerate the manifest after changing the asset tool")
    sidecars = manifest.get("import_sidecars", [])
    if sidecars:
        expected = {entry["file"] + ".import" for entry in manifest["files"] if entry["kind"] in ("font", "vector", "rank_texture", "card_texture", "audio")}
        actual = {path.relative_to(DESTINATION).as_posix() for path in DESTINATION.rglob("*.import")}
        require(actual == expected, "Unexpected or missing Godot import settings")
    for sidecar in sidecars:
        require(source_record(ROOT / sidecar["file"]) == sidecar, f"Import settings changed: {sidecar['file']}")
    return {"source_hashes": "pass", "asset_hashes": "pass", "font_licenses_complete": True, "rgba_texture_sizes_and_corners": "pass", "files": len(manifest["files"]), "total_file_bytes": manifest["total_file_bytes"]}


GODOT_CHECK = r'''extends SceneTree

var failures: Array[String] = []

func expect(condition: bool, message: String) -> bool:
    if not condition:
        failures.append(message)
        push_error(message)
    return condition

func digest(data: PackedByteArray) -> String:
    var context := HashingContext.new()
    expect(context.start(HashingContext.HASH_SHA256) == OK, "Cannot initialize SHA-256")
    expect(context.update(data) == OK, "Cannot hash imported bytes")
    return context.finish().hex_encode()

func _initialize() -> void:
    var manifest: Dictionary = JSON.parse_string(FileAccess.get_file_as_string("res://assets/manifest.json"))
    var imported: Array[Dictionary] = []
    for entry: Dictionary in manifest["files"]:
        var kind: String = entry["kind"]
        if kind not in ["font", "vector", "rank_texture", "card_texture", "audio"]:
            continue
        var path: String = entry["resource"]
        var resource: Resource = ResourceLoader.load(path)
        if not expect(resource != null, "Unable to import " + path):
            continue
        var result: Dictionary = {"resource": path, "class": resource.get_class(), "kind": kind}
        if kind == "font":
            if not expect(resource is FontFile, "Expected FontFile: " + path):
                continue
            var font: FontFile = resource as FontFile
            expect(digest(font.data) == entry["sha256"], "Font bytes changed on import: " + path)
            for character: String in "Crown Moon Star Wild Last Light 0123456789 ÀÉÎÖÜàéîöü":
                expect(font.has_char(character.unicode_at(0)), "Missing font glyph: " + path + " " + character)
            expect(font.get_string_size("Last Light", HORIZONTAL_ALIGNMENT_LEFT, -1, 32).x > 0, "Empty font metrics: " + path)
            result["font_name"] = font.get_font_name()
            result["glyph_probe"] = "English and accented Latin"
        elif kind == "audio":
            if not expect(resource is AudioStreamWAV, "Expected AudioStreamWAV: " + path):
                continue
            var audio: AudioStreamWAV = resource as AudioStreamWAV
            expect(audio.format == AudioStreamWAV.FORMAT_16_BITS, "Audio must retain PCM16: " + path)
            expect(audio.mix_rate == 44100 and not audio.stereo, "Changed audio format: " + path)
            expect(audio.loop_mode == AudioStreamWAV.LOOP_DISABLED, "Looping cue: " + path)
            expect(digest(audio.data) == entry["pcm_sha256"], "PCM samples changed on import: " + path)
            expect(abs(audio.get_length() * 1000.0 - float(entry["duration_ms"])) < 0.001, "Changed cue duration: " + path)
            result["pcm_samples_unchanged"] = true
            result["duration_ms"] = entry["duration_ms"]
        else:
            if not expect(resource is Texture2D, "Expected Texture2D: " + path):
                continue
            var texture: Texture2D = resource as Texture2D
            var scale: int = 4 if kind == "vector" else 1
            var expected_size := Vector2i(int(entry["size"][0]) * scale, int(entry["size"][1]) * scale)
            expect(Vector2i(texture.get_size()) == expected_size, "Wrong texture size: " + path)
            var image: Image = texture.get_image()
            if expect(image != null and not image.is_empty(), "Empty imported image: " + path):
                expect(image.has_mipmaps() == (kind != "vector"), "Unexpected mipmaps: " + path)
                if kind in ["rank_texture", "card_texture"]:
                    expect(image.get_pixel(0, 0).a == 0.0, "Opaque texture corner: " + path)
                if kind == "card_texture":
                    var base_color := Color(entry["transparent_rgb"])
                    base_color.a = 0.0
                    expect(image.get_pixel(0, 0).is_equal_approx(base_color), "Card corner RGB changed on import: " + path)
                result["image_format"] = image.get_format()
                result["mipmap_levels"] = image.get_mipmap_count()
                result["decoded_bytes_with_mipmaps"] = image.get_data().size()
                if kind == "vector":
                    expect(image.save_png("res://raster_" + path.get_file().get_basename() + ".png") == OK, "Cannot save imported SVG raster: " + path)
            result["size"] = [expected_size.x, expected_size.y]
            result["mipmaps"] = kind != "vector"
        imported.append(result)
    var report: Dictionary = {"resources": imported, "failures": failures}
    var file := FileAccess.open("res://asset_import_result.json", FileAccess.WRITE)
    file.store_string(JSON.stringify(report, "  ") + "\n")
    print("Asset import verification: ", imported.size(), " resources, ", failures.size(), " failures.")
    quit(0 if failures.is_empty() else 1)
'''


def run_godot(binary: Path, arguments: list[str]) -> subprocess.CompletedProcess:
    environment = dict(os.environ)
    environment["GODOT_SILENCE_ROOT_WARNING"] = "1"
    result = subprocess.run([str(binary), *arguments], capture_output=True, text=True, env=environment, timeout=60)
    require(result.returncode == 0, f"Godot exited with {result.returncode}:\n{result.stdout}\n{result.stderr}")
    require("SCRIPT ERROR:" not in result.stderr and "ERROR:" not in result.stderr, f"Godot reported an error:\n{result.stderr}")
    return result


def compare_svg_rasters(fixture: Path, manifest: dict) -> list[dict]:
    report = []
    for entry in manifest["files"]:
        if entry["kind"] != "vector":
            continue
        size = tuple(value * 4 for value in entry["size"])
        reference_data = raster((DESTINATION / entry["file"]).read_bytes(), size)
        imported_path = fixture / ("raster_" + Path(entry["file"]).stem + ".png")
        with Image.open(BytesIO(reference_data)) as reference, Image.open(imported_path) as imported:
            reference_alpha = reference.convert("RGBA").getchannel("A")
            imported_alpha = imported.convert("RGBA").getchannel("A")
            expected_bounds = reference_alpha.getbbox()
            actual_bounds = imported_alpha.getbbox()
            require(expected_bounds is not None and actual_bounds is not None, f"Blank SVG raster: {entry['file']}")
            require(all(abs(a - b) <= 2 for a, b in zip(expected_bounds, actual_bounds)), f"Godot changed SVG bounds: {entry['file']}")
            expected = reference_alpha.tobytes()
            actual = imported_alpha.tobytes()
            error = sum(abs(a - b) for a, b in zip(expected, actual)) / sum(expected)
            require(error < 0.08, f"Godot SVG alpha differs substantially from source rendering: {entry['file']}: {error}")
            report.append({"resource": entry["resource"], "bounds": list(actual_bounds), "alpha_error_relative_to_source_coverage": round(error, 5)})
    return report


def check_imports(binary: Path, manifest: dict, write_sidecars: bool) -> dict:
    require(binary.is_file(), "Pass the existing verified Godot executable; this tool never downloads it")
    version = run_godot(binary, ["--version"]).stdout.strip()
    require(version.startswith("4.7.2."), f"Expected Godot 4.7.2, found {version}")
    with tempfile.TemporaryDirectory(prefix="partydeck-godot-assets-") as directory:
        fixture = Path(directory)
        shutil.copytree(DESTINATION, fixture / "assets")
        (fixture / "project.godot").write_text('config_version=5\n[application]\nconfig/name="PartyDeck asset verification"\n[rendering]\nrenderer/rendering_method="gl_compatibility"\n')
        (fixture / "check_assets.gd").write_text(GODOT_CHECK)
        run_godot(binary, ["--headless", "--editor", "--path", str(fixture), "--import"])
        expected_sidecars = set()
        for entry in manifest["files"]:
            if entry["kind"] not in ("font", "vector", "rank_texture", "card_texture", "audio"):
                continue
            relative = entry["file"] + ".import"
            expected_sidecars.add(relative)
            path = fixture / "assets" / relative
            text = path.read_text()
            for option, value in entry["import_options"].items():
                pattern = r"(?m)^" + re.escape(option) + r"=.*$"
                require(re.search(pattern, text) is not None, f"Godot importer does not expose {option}: {relative}")
                text = re.sub(pattern, option + "=" + json.dumps(value), text)
            path.write_text(text)
        actual_sidecars = {path.relative_to(fixture / "assets").as_posix() for path in (fixture / "assets").rglob("*.import")}
        require(actual_sidecars == expected_sidecars, "Godot imported files outside the declared runtime asset set")
        run_godot(binary, ["--headless", "--editor", "--path", str(fixture), "--import"])
        run_godot(binary, ["--headless", "--path", str(fixture), "--script", "check_assets.gd"])
        result = json.loads((fixture / "asset_import_result.json").read_text())
        require(not result["failures"] and len(result["resources"]) == len(expected_sidecars), "Incomplete Godot resource verification")
        result["decoded_texture_bytes_by_kind"] = {
            kind: sum(resource["decoded_bytes_with_mipmaps"] for resource in result["resources"] if resource["kind"] == kind)
            for kind in ("card_texture", "rank_texture", "vector")
        }
        result["svg_raster_comparison"] = compare_svg_rasters(fixture, manifest)
        for relative in sorted(expected_sidecars):
            data = (fixture / "assets" / relative).read_bytes()
            target = DESTINATION / relative
            if write_sidecars:
                if not target.is_file() or target.read_bytes() != data:
                    target.write_bytes(data)
            else:
                require(target.read_bytes() == data, f"Importer settings need regeneration: {relative}")
        record_sidecars(manifest)
        if write_sidecars:
            write_manifest(manifest)
        result.update({"godot_version": version, "godot_binary_sha256": sha256(binary.read_bytes()).hexdigest(), "manifest_sha256": sha256((DESTINATION / "manifest.json").read_bytes()).hexdigest(), "isolated_import": True, "import_settings_verified": len(expected_sidecars), "limits": ["Headless import does not establish rendered 2D/3D scene quality or physical speaker playback.", "Decoded texture data totals exclude scene-generated resources, geometry, render targets, and driver/resource overhead.", "The shared asset/font audit does not cover Godot engine or exported native-library licenses."]})
        (DESTINATION / "proofs").mkdir(exist_ok=True)
        (DESTINATION / "proofs/.gdignore").write_text("Review evidence is excluded from runtime imports.\n")
        (DESTINATION / "proofs/import_verification.json").write_text(json.dumps(result, indent=2) + "\n")
        imported_ranks = Image.new("RGB", (1152, 360), PALETTE["paper"])
        for index, rank in enumerate(RANKS):
            with Image.open(fixture / f"raster_rank_{rank}.png") as icon:
                imported_ranks.paste(icon, (32 + index * 280, 52), icon)
        imported_ranks.save(DESTINATION / "proofs/godot_rank_imports.png", optimize=True)
        return {"godot_version": version, "runtime_resources": len(result["resources"]), "import_settings_verified": len(expected_sidecars), "failures": result["failures"]}


def proof_sheet() -> None:
    directory = DESTINATION / "proofs"
    directory.mkdir(exist_ok=True)
    (directory / ".gdignore").write_text("Review images are excluded from runtime imports.\n")
    image = Image.new("RGB", (1440, 960), PALETTE["ink"])
    draw = ImageDraw.Draw(image)
    heading = ImageFont.truetype(str(DESTINATION / "fonts/fraunces_semibold.ttf"), 46)
    body = ImageFont.truetype(str(DESTINATION / "fonts/manrope_medium.ttf"), 18)
    small = ImageFont.truetype(str(DESTINATION / "fonts/manrope_regular.ttf"), 14)
    draw.text((48, 30), "Last Light / shared card artwork", font=heading, fill=PALETTE["paper"])
    draw.text((50, 100), "512 × 768 RGBA · original wordless geometry · localized labels remain in each presentation", font=body, fill=PALETTE["citron"])
    names = ["face_" + rank for rank in RANKS] + ["back"]
    for index, name in enumerate(names):
        x = 48 + index * 274
        with Image.open(DESTINATION / f"textures/cards/{name}.png") as card:
            large = card.resize((248, 372), Image.Resampling.LANCZOS)
            image.paste(large, (x, 156), large)
            draw.text((x, 545), name.replace("face_", "").upper(), font=body, fill=PALETTE["paper"])
            for j, width in enumerate((88, 136)):
                preview = card.resize((width, width * 3 // 2), Image.Resampling.LANCZOS)
                px = x + j * 108
                image.paste(preview, (px, 596), preview)
                draw.text((px, 820), f"{width}px wide", font=small, fill="#BAB5C4")
    draw.text((50, 910), "Asset proof only. Godot import and rendered 2D/3D scene checks are recorded separately.", font=small, fill="#BAB5C4")
    image.save(directory / "cards.png", optimize=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Verify checked-in assets without regenerating them")
    parser.add_argument("--godot", type=Path, help="Check imports using an existing verified Godot 4.7.2 executable")
    parser.add_argument("--no-proof", action="store_true", help="Leave the existing card contact sheet untouched")
    args = parser.parse_args()
    manifest = json.loads((DESTINATION / "manifest.json").read_text()) if args.check else prepare()
    result = verify(manifest)
    if not args.check and not args.no_proof:
        proof_sheet()
    if args.godot:
        result["godot"] = check_imports(args.godot, manifest, write_sidecars=not args.check)
        verify(manifest)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
