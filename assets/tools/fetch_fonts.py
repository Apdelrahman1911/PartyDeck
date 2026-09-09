#!/usr/bin/env python3
"""Restore unmodified, pinned OFL font files. Builds never need network access."""

from hashlib import sha256
import json
from pathlib import Path
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[2]
RESOURCES = ROOT / "composeApp/src/commonMain/composeResources"
SOURCES = (
    (
        "fraunces_semibold.ttf",
        "https://raw.githubusercontent.com/undercasetype/Fraunces/"
        "7ccdec31c6028118dce3e47fe864e3744460371d/fonts/ttf/Fraunces72pt-SemiBold.ttf",
        "ea45a557b4dd7e9fee6e263211b72986879d6bde518dbe18338d0478b91ab93c",
    ),
    (
        "manrope_regular.ttf",
        "https://raw.githubusercontent.com/aaronbell/manrope/"
        "6f81ebecdf65e4463b798cc07b16a4f8d5216917/fonts/ttf/manrope-regular.ttf",
        "2d9a9960fd191a7f1d9060768818074dd2b76ba84a64a35efd2c22bf39030903",
    ),
    (
        "manrope_medium.ttf",
        "https://raw.githubusercontent.com/aaronbell/manrope/"
        "6f81ebecdf65e4463b798cc07b16a4f8d5216917/fonts/ttf/manrope-medium.ttf",
        "42133571c5f19b6d5ded5e3935a92c1dd40721fd8ca2529719eabfa58c123aec",
    ),
    (
        "manrope_semibold.ttf",
        "https://raw.githubusercontent.com/aaronbell/manrope/"
        "6f81ebecdf65e4463b798cc07b16a4f8d5216917/fonts/ttf/manrope-semibold.ttf",
        "e80a2c37e47ec09bff5a9960257bf9001e87d5fb7bf35719ef4958763a0c70ac",
    ),
    (
        "fraunces_ofl.txt",
        "https://raw.githubusercontent.com/undercasetype/Fraunces/"
        "7ccdec31c6028118dce3e47fe864e3744460371d/OFL.txt",
        "bdf4c22802eaf804f998195871c6b8938aac2ac14b2d78a8bd66a6f1eced833b",
    ),
    (
        "manrope_ofl.txt",
        "https://raw.githubusercontent.com/aaronbell/manrope/"
        "6f81ebecdf65e4463b798cc07b16a4f8d5216917/OFL.txt",
        "e01b637272e0cbdfb240184dd98ea5cc671556d9894dae2668d92ab2c906787c",
    ),
)


def main() -> None:
    manifest = []
    for name, url, expected_digest in SOURCES:
        destination = (
            RESOURCES / "font" / name
            if name.endswith(".ttf")
            else ROOT / "assets/licenses" / name
        )
        if destination.exists() and sha256(destination.read_bytes()).hexdigest() == expected_digest:
            data = destination.read_bytes()
        else:
            request = Request(url, headers={"User-Agent": "PartyDeck-asset-restore"})
            with urlopen(request, timeout=45) as response:
                data = response.read()
            actual_digest = sha256(data).hexdigest()
            if actual_digest != expected_digest:
                raise ValueError(f"Refusing changed source {name}: {actual_digest}")
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(data)
        if name.endswith("_ofl.txt"):
            bundled_notice = RESOURCES / "files/licenses" / name
            bundled_notice.parent.mkdir(parents=True, exist_ok=True)
            bundled_notice.write_bytes(data)
        manifest.append(
            {
                "file": str(destination.relative_to(ROOT)),
                "bytes": len(data),
                "sha256": expected_digest,
                "source": url,
                "license": "SIL Open Font License 1.1",
                "modified": False,
            }
        )
        print(f"Verified {name}: {len(data):,} bytes")
    (ROOT / "assets/font_sources.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()
