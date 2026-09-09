#!/usr/bin/env python3
"""Bundle verified third-party notices into one offline, readable app resource."""

from hashlib import sha256
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DESTINATION = ROOT / "composeApp/src/commonMain/composeResources/files/licenses"


def main() -> None:
    font_sources = json.loads((ROOT / "assets/font_sources.json").read_text())
    notices = []
    for source in font_sources:
        if source["file"].endswith("_ofl.txt"):
            family = "Fraunces" if "fraunces" in source["file"] else "Manrope"
            notices.append({**source, "title": f"{family} — SIL Open Font License 1.1"})
    notices += json.loads((ROOT / "assets/software_notice_sources.json").read_text())
    sections = [
        "PartyDeck — Third-party notices\n\n"
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
    ]
    DESTINATION.mkdir(parents=True, exist_ok=True)
    for source in notices:
        path = ROOT / source["file"]
        data = path.read_bytes()
        digest = sha256(data).hexdigest()
        if digest != source["sha256"]:
            raise ValueError(f"Notice differs from its verified source: {source['file']}")
        # Individual files remain byte-for-byte copies for easy provenance checks.
        (DESTINATION / path.name).write_bytes(data)
        sections.append("\n" + "=" * 72 + "\n" + source["title"] + "\n" + "=" * 72 + "\n\n" + data.decode("utf-8"))
    aggregate = "\n".join(sections) + "\n"
    (DESTINATION / "third_party_notices.txt").write_text(aggregate, encoding="utf-8")
    print(f"Bundled {len(notices)} verified notices ({len(aggregate.encode('utf-8')):,} bytes).")


if __name__ == "__main__":
    main()
