#!/usr/bin/env python3
"""Focused release checks for asset provenance, resource portability, and media."""

from array import array
from hashlib import sha256
from io import BytesIO
import json
from math import log10, sqrt
from pathlib import Path
import sys
import wave
from xml.etree import ElementTree

import cairosvg
from fontTools.ttLib import TTFont
from PIL import Image, ImageCms


ROOT = Path(__file__).resolve().parents[2]
ASSETS = ROOT / "assets"
RESOURCES = ROOT / "composeApp/src/commonMain/composeResources"
ANDROID = "{http://schemas.android.com/apk/res/android}"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def check_sources() -> dict:
    fonts = json.loads((ASSETS / "font_sources.json").read_text())
    notices = json.loads((ASSETS / "software_notice_sources.json").read_text())
    runtime = json.loads((ASSETS / "licenses/runtime/software_notice_sources.json").read_text())
    notices += runtime
    aggregate = (RESOURCES / "files/licenses/third_party_notices.txt").read_bytes()
    font_details = []
    notice_hashes = set()
    notice_count = 0
    for source in fonts + notices:
        path = ROOT / source["file"]
        data = path.read_bytes()
        require(sha256(data).hexdigest() == source["sha256"], f"Source integrity failed: {path}")
        if path.suffix.lower() != ".ttf":
            bundled = RESOURCES / "files/licenses" / source.get("resource_file", path.name)
            require(bundled.read_bytes() == data, f"Changed bundled license: {path.name}")
            require(data in aggregate, f"Aggregate omits complete notice: {path.name}")
            for field in ("title", "component"):
                if field in source:
                    require(source[field].encode("utf-8") in aggregate, f"Aggregate omits {field}: {path.name}")
            notice_count += 1
            notice_hashes.add(source["sha256"])
        else:
            with TTFont(path) as face:
                mapping = face.getBestCmap()
                probe = "The quick brown fox jumps over the lazy dog. 0123456789 !?:,;–—’“”ÀÉÎÖÜàéîöü"
                missing = sorted({char for char in probe if ord(char) not in mapping})
                require(not missing, f"Missing English/Latin probe characters: {path.name}: {missing}")
                font_details.append(
                    {
                        "resource": path.name,
                        "family": face["name"].getDebugName(1),
                        "weight_class": face["OS/2"].usWeightClass,
                        "unicode_glyphs": len(mapping),
                        "english_and_accented_latin_probe": "pass",
                    }
                )
    runtime_root = RESOURCES / "files/licenses/runtime"
    expected_runtime = {source["resource_file"] for source in runtime}
    actual_runtime = {
        path.relative_to(RESOURCES / "files/licenses").as_posix()
        for path in runtime_root.rglob("*") if path.is_file()
    }
    require(actual_runtime == expected_runtime, f"Runtime notice resource inventory differs: {sorted(actual_runtime ^ expected_runtime)}")
    acknowledgments = [source for source in runtime if source["resource_file"] == "runtime/required_acknowledgments.txt"]
    require(len(acknowledgments) == 1, "Missing required native acknowledgment source")
    acknowledgment_bytes = (ROOT / acknowledgments[0]["file"]).read_bytes()
    require(0 <= aggregate.find(acknowledgment_bytes) < 512, "Required native acknowledgments must appear prominently at the beginning")
    return {
        "pinned_files_verified": len(fonts) + len(notices),
        "fonts": font_details,
        "complete_notices_bundled": notice_count,
        "distinct_notice_texts": len(notice_hashes),
        "runtime_notice_resources": len(actual_runtime),
        "runtime_resources_match_manifest": True,
        "required_acknowledgments_prominent": True,
        "aggregate_bytes": len(aggregate),
        "aggregate_sha256": sha256(aggregate).hexdigest(),
    }


def check_audio() -> dict:
    clips = json.loads((ASSETS / "audio_manifest.json").read_text())
    report = []
    total = 0
    for clip in clips:
        path = RESOURCES / clip["resource_path"]
        data = path.read_bytes()
        require(sha256(data).hexdigest() == clip["sha256"], f"Audio manifest mismatch: {path.name}")
        with wave.open(str(path), "rb") as reader:
            require(reader.getnchannels() == 1 and reader.getsampwidth() == 2, f"Unexpected PCM layout: {path.name}")
            require(reader.getframerate() == 44_100 and reader.getcomptype() == "NONE", f"Unexpected PCM format: {path.name}")
            samples = array("h", reader.readframes(reader.getnframes()))
            if sys.byteorder != "little":
                samples.byteswap()
            duration_ms = round(reader.getnframes() / reader.getframerate() * 1_000)
        require(duration_ms == clip["duration_ms"], f"Native cue duration contract changed: {path.name}")
        require(len(samples) * 2 < 1_000_000, f"Exceeds short-cue decoded size budget: {path.name}")
        require(samples[0] == samples[-1] == 0, f"Nonzero cue boundary: {path.name}")
        peak = max(abs(value) for value in samples) / 32768
        dc = sum(samples) / len(samples) / 32768
        rms = sqrt(sum((value / 32768) ** 2 for value in samples) / len(samples))
        require(0.01 < peak <= 0.32, f"Unexpected sound headroom/silence: {path.name}")
        require(abs(dc) < 0.001, f"Excessive DC offset: {path.name}")
        total += len(data)
        report.append({"resource": path.name, "duration_ms": duration_ms, "peak_dbfs": round(20 * log10(peak), 2), "rms_dbfs": round(20 * log10(rms), 2), "zero_endpoints": True})
    require(total < 1_000_000, "Cue bundle exceeds the 1 MB target")
    return {"total_file_bytes": total, "clips": report}


def check_vectors() -> dict:
    common_files = sorted((RESOURCES / "drawable").glob("*.xml"))
    path_count = 0
    for path in common_files:
        text = path.read_text()
        root = ElementTree.fromstring(text)
        require(root.tag == "vector", f"Not a VectorDrawable: {path.name}")
        require("@" not in text and "?attr" not in text and "<aapt:" not in text, f"Android-only resource reference: {path.name}")
        for element in root.iter():
            require(element.tag in ("vector", "group", "path"), f"Unexpected vector feature: {path.name}: {element.tag}")
            if element.tag == "path":
                require(bool(element.get(ANDROID + "pathData")), f"Empty vector path: {path.name}")
                path_count += 1
        source = ASSETS / "vectors" / (path.stem + ".svg")
        require(source.exists(), f"Missing editable vector source: {path.name}")
        # Independently exercise the SVG parser/rasterizer at a realistic small size.
        height = 96 if path.stem == "card_back" else 24
        width = 64 if path.stem == "card_back" else 24
        raster = cairosvg.svg2png(url=str(source), output_width=width, output_height=height)
        with Image.open(BytesIO(raster)) as rendered:
            require(rendered.convert("RGBA").getchannel("A").getbbox() is not None, f"Blank rendered asset: {path.name}")
    return {"common_vectors": len(common_files), "paths": path_count, "android_resource_references": 0, "small_svg_renders": "pass"}


def check_launcher() -> dict:
    path = ASSETS / "launcher/partydeck_1024.png"
    with Image.open(path) as icon:
        require(icon.size == (1024, 1024), "Launcher must be exactly 1024 square")
        require(icon.mode == "RGB", "Flattened launcher must be opaque RGB")
        profile = ImageCms.ImageCmsProfile(BytesIO(icon.info.get("icc_profile", b"")))
        require("sRGB" in ImageCms.getProfileName(profile), "Launcher must include an sRGB profile")
    bounds = {}
    for name in ("partydeck_foreground", "partydeck_monochrome"):
        raster = cairosvg.svg2png(url=str(ASSETS / "launcher" / f"{name}.svg"), output_width=1080, output_height=1080)
        with Image.open(BytesIO(raster)) as layer:
            box = layer.convert("RGBA").getchannel("A").getbbox()
        require(box is not None, f"Empty launcher layer: {name}")
        require(box[0] >= 210 and box[1] >= 210 and box[2] <= 870 and box[3] <= 870, f"Mark exceeds central 66dp safe square: {name}: {box}")
        bounds[name] = [round(value / 10, 1) for value in box]
    return {"size_px": [1024, 1024], "opaque": True, "embedded_color_profile": "sRGB", "layer_bounds_dp_in_108dp_canvas": bounds}


def main() -> None:
    report = {
        "source_integrity": check_sources(),
        "audio": check_audio(),
        "vectors": check_vectors(),
        "launcher": check_launcher(),
        "limits": [
            "SVG rendering does not prove Android/iOS VectorDrawable runtime rendering.",
            "Waveform checks do not prove speaker loudness, mix quality, audio focus, or device latency.",
            "Font probes are not a claim of complete translated-language or script coverage.",
        ],
    }
    (ASSETS / "verification.json").write_text(json.dumps(report, indent=2) + "\n")
    print(f"PASS: {report['source_integrity']['pinned_files_verified']} pinned source files; {report['vectors']['common_vectors']} vectors; six cues; launcher format and safe bounds.")
    print(f"Audio bundle: {report['audio']['total_file_bytes']:,} bytes. Device checks remain explicitly separate.")


if __name__ == "__main__":
    main()
