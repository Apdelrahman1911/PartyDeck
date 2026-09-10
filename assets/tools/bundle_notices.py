#!/usr/bin/env python3
"""Bundle verified third-party notices into one offline, readable app resource."""

from hashlib import sha256
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DESTINATION = ROOT / "composeApp/src/commonMain/composeResources/files/licenses"
ACKNOWLEDGMENTS = "runtime/required_acknowledgments.txt"


def main() -> None:
    font_sources = json.loads((ROOT / "assets/font_sources.json").read_text())
    notices = []
    for source in font_sources:
        if source["file"].endswith("_ofl.txt"):
            family = "Fraunces" if "fraunces" in source["file"] else "Manrope"
            notices.append({**source, "title": f"{family} — SIL Open Font License 1.1"})
    notices += json.loads((ROOT / "assets/software_notice_sources.json").read_text())
    runtime = json.loads((ROOT / "assets/licenses/runtime/software_notice_sources.json").read_text())
    acknowledgments = [source for source in runtime if source["resource_file"] == ACKNOWLEDGMENTS]
    if len(acknowledgments) != 1:
        raise ValueError("Runtime notices must include exactly one required acknowledgment file")
    notices = acknowledgments + notices + [source for source in runtime if source["resource_file"] != ACKNOWLEDGMENTS]
    introduction = (
        "Godot Engine: Godot Engine contributors, Juan Linietsky, and Ariel Manzur. "
        "MIT License. Engine notices, Android C++ runtime notices, and the bundled "
        "Mozilla CA certificate source are reproduced below.\n\n"
        "Fraunces: The Fraunces Project Authors. Design by Undercase Type, "
        "Phaedra Charles, and Flavia Zimbardi. SIL Open Font License 1.1.\n\n"
        "Manrope: The Manrope Project Authors. Design by Mikhail Sharanda. "
        "SIL Open Font License 1.1.\n\n"
        "QRose: Copyright 2023 Alexander Zhirkevich. MIT License.\n\n"
        "AndroidX / CameraX: The Android Open Source Project. Apache License 2.0. "
        "CameraX includes LibYuv code under the BSD 3-Clause License.\n\n"
        "ZXing: ZXing authors. Apache License 2.0 and the upstream notices reproduced below.\n\n"
        "LibYuv: Copyright 2011 The LibYuv Project Authors. BSD 3-Clause License "
        "and Additional IP Rights Grant.\n\n"
        "PartyDeck's card artwork, interface symbols, launcher, and sound cues "
        "were created for this project. No external artwork or sound samples are included.\n"
    )
    DESTINATION.mkdir(parents=True, exist_ok=True)
    groups = {}
    for source in notices:
        path = ROOT / source["file"]
        data = path.read_bytes()
        digest = sha256(data).hexdigest()
        if digest != source["sha256"]:
            raise ValueError(f"Notice differs from its verified source: {source['file']}")
        # Individual files remain byte-for-byte copies for easy provenance checks.
        resource = Path(source.get("resource_file", path.name))
        if resource.is_absolute() or ".." in resource.parts:
            raise ValueError(f"Invalid notice resource path: {resource}")
        destination = DESTINATION / resource
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(data)
        # Group by actual bytes, retaining every title and component attribution.
        groups.setdefault(data, []).append(source)
    sections = ["PartyDeck — Third-party notices\n"]
    for index, (data, sources) in enumerate(groups.items()):
        attributions = []
        for source in sources:
            attribution = source["title"]
            component = source.get("component")
            if component and component != attribution:
                attribution += "\nComponent: " + component
            if attribution not in attributions:
                attributions.append(attribution)
        sections.append("\n" + "=" * 72 + "\n" + "\n\n".join(attributions) + "\n" + "=" * 72 + "\n\n" + data.decode("utf-8"))
        if index == 0:
            sections.append(introduction)
    aggregate = ("\n".join(sections) + "\n").encode("utf-8")
    (DESTINATION / "third_party_notices.txt").write_bytes(aggregate)
    print(f"Bundled {len(notices)} verified notices in {len(groups)} distinct text groups ({len(aggregate):,} bytes).")
    print(f"Aggregate SHA-256: {sha256(aggregate).hexdigest()}")


if __name__ == "__main__":
    main()
