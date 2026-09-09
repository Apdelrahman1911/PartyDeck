#!/usr/bin/env python3
"""Render review sheets and the opaque 1024px launcher from original vectors."""

from io import BytesIO
from pathlib import Path

import cairosvg
from PIL import Image, ImageCms, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[2]
ASSETS = ROOT / "assets"
FONT_DIR = ROOT / "composeApp/src/commonMain/composeResources/font"
PREVIEWS = ASSETS / "previews"
INK = "#191526"
SURFACE = "#252133"
PAPER = "#F4F0E8"
CITRON = "#D6EF82"
COPPER = "#F16B48"
MUTED = "#BAB5C4"


def font(name: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(FONT_DIR / f"{name}.ttf"), size)


def vector(path: Path, width: int, height: int | None = None, tint: str | None = None) -> Image.Image:
    data = path.read_text(encoding="utf-8")
    if tint:
        data = data.replace(INK, tint)
    png = cairosvg.svg2png(bytestring=data.encode(), output_width=width, output_height=height)
    return Image.open(BytesIO(png)).convert("RGBA")


def draw_text(draw: ImageDraw.ImageDraw, xy: tuple[int, int], text: str, size: int = 18, color: str = PAPER, weight: str = "regular") -> None:
    draw.text(xy, text, font=font("manrope_" + weight, size), fill=color)


def asset_sheet() -> None:
    sheet = Image.new("RGB", (1440, 1320), INK)
    draw = ImageDraw.Draw(sheet)
    draw_text(draw, (64, 40), "PARTYDECK  /  ORIGINAL ASSET PROOF", 15, CITRON, "semibold")
    draw.text((60, 68), "A little nerve. A good story.", font=font("fraunces_semibold", 57), fill=PAPER)
    draw_text(draw, (64, 143), "An editorial card club. Clear shapes, warm paper, quiet detail.", 20, MUTED)
    for index, (name, color) in enumerate((("Ink", INK), ("Paper", PAPER), ("Citron", CITRON), ("Copper", COPPER))):
        x = 1120 + (index % 2) * 140
        y = 45 + (index // 2) * 68
        draw.ellipse((x, y, x + 27, y + 27), fill=color, outline="#888190", width=1)
        draw_text(draw, (x + 38, y - 1), name, 14, PAPER, "semibold")
        draw_text(draw, (x + 38, y + 18), color, 11, MUTED)

    rank_data = (("Crown", "crown"), ("Moon", "moon"), ("Star", "star"), ("Wild", "wild"))
    for index, (label, name) in enumerate(rank_data):
        x, y, w, h = 64 + index * 218, 218, 190, 285
        draw.rounded_rectangle((x, y, x + w, y + h), radius=14, fill=PAPER)
        draw_text(draw, (x + 17, y + 17), label.upper(), 15, INK, "semibold")
        symbol = vector(ASSETS / "vectors" / f"rank_{name}.svg", 100)
        sheet.paste(symbol, (x + 45, y + 86), symbol)
        draw.line((x + 22, y + 234, x + w - 22, y + 234), fill="#D6D0C4", width=1)
        draw_text(draw, (x + 22, y + 248), "LAST LIGHT", 11, INK, "medium")
        tiny = vector(ASSETS / "vectors" / f"rank_{name}.svg", 24)
        sheet.paste(tiny, (x + w - 44, y + 242), tiny)
        draw_text(draw, (x, y + h + 20), f"{name} / 64-unit vector", 14, MUTED)
    back = vector(ASSETS / "vectors/card_back.svg", 190, 285)
    sheet.paste(back, (936, 218), back)
    draw_text(draw, (936, 523), "Card back / 2:3", 14, MUTED)

    mark = vector(ASSETS / "vectors/partydeck_mark.svg", 164)
    sheet.paste(mark, (1200, 233), mark)
    draw.text((1170, 414), "PartyDeck", font=font("fraunces_semibold", 35), fill=PAPER)
    draw_text(draw, (1194, 463), "THE CLUB MARK", 12, MUTED, "semibold")

    draw.line((64, 586, 1376, 586), fill="#575163", width=1)
    draw_text(draw, (64, 617), "18 PURPOSE-DRAWN UI SYMBOLS", 14, CITRON, "semibold")
    icon_paths = sorted((ASSETS / "vectors").glob("icon_*.svg"))
    for index, path in enumerate(icon_paths):
        x = 64 + (index % 6) * 222
        y = 665 + (index // 6) * 96
        draw.rounded_rectangle((x, y, x + 56, y + 56), radius=12, fill=PAPER)
        icon = vector(path, 28)
        sheet.paste(icon, (x + 14, y + 14), icon)
        draw_text(draw, (x + 70, y + 9), path.stem.removeprefix("icon_").replace("_", " "), 14, PAPER, "medium")
        draw_text(draw, (x + 70, y + 31), "24 dp / tintable", 11, MUTED)
    draw.line((64, 972, 1376, 972), fill="#575163", width=1)

    draw_text(draw, (64, 1005), "FRAUNCES 72PT SEMIBOLD", 12, CITRON, "semibold")
    draw.text((60, 1041), "Last Light", font=font("fraunces_semibold", 70), fill=PAPER)
    draw.text((64, 1143), "Crown. Moon. Star. Wild.", font=font("fraunces_semibold", 29), fill=PAPER)

    draw_text(draw, (676, 1005), "MANROPE REGULAR / MEDIUM / SEMIBOLD", 12, CITRON, "semibold")
    draw_text(draw, (676, 1052), "Your hand. Your choice.", 31, PAPER, "semibold")
    draw_text(draw, (676, 1110), "Play one to three cards, then read the room.", 21, PAPER)
    draw_text(draw, (676, 1154), "0123456789  /  ÀÉÎÖÜ  /  αβγ  /  АБВ", 23, MUTED, "medium")
    draw_text(draw, (64, 1256), "Proof sheet only. App copy remains in translatable resources. All geometry and audio are original; fonts are bundled under OFL 1.1.", 13, MUTED)
    sheet.save(PREVIEWS / "asset_sheet.png", optimize=True)


def launcher() -> None:
    icon = vector(ASSETS / "launcher/partydeck_launcher.svg", 1024).convert("RGB")
    profile = ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB")).tobytes()
    icon.save(ASSETS / "launcher/partydeck_1024.png", icc_profile=profile, optimize=True)

    preview = Image.new("RGB", (1440, 620), PAPER)
    draw = ImageDraw.Draw(preview)
    draw_text(draw, (64, 42), "PARTYDECK / LAUNCHER MASK PROOF", 18, INK, "semibold")
    for index, shape in enumerate(("Square source", "Rounded mask", "Circular mask", "Monochrome")):
        x, y, size = 64 + index * 348, 117, 264
        layer = icon.resize((size, size), Image.Resampling.LANCZOS)
        mask = Image.new("L", (size, size), 0)
        mask_draw = ImageDraw.Draw(mask)
        if index == 0:
            mask_draw.rectangle((0, 0, size, size), fill=255)
        elif index in (1, 3):
            mask_draw.rounded_rectangle((0, 0, size, size), radius=58, fill=255)
        else:
            mask_draw.ellipse((0, 0, size, size), fill=255)
        if index == 3:
            layer = Image.new("RGB", (size, size), INK)
            mono = vector(ASSETS / "launcher/partydeck_monochrome.svg", size)
            layer.paste(mono, (0, 0), mono)
        preview.paste(layer, (x, y), mask)
        draw_text(draw, (x, y + size + 21), shape, 17, INK, "medium")
        for sample_index, sample_size in enumerate((64, 48, 32)):
            small = layer.resize((sample_size, sample_size), Image.Resampling.LANCZOS)
            small_mask = mask.resize((sample_size, sample_size), Image.Resampling.LANCZOS)
            preview.paste(small, (x + sample_index * 87, y + size + 80), small_mask)
    draw_text(draw, (64, 574), "The source has an opaque, square sRGB background. System masks are previewed here only; none is baked into the exported icon.", 14, INK)
    preview.save(PREVIEWS / "launcher_masks.png", optimize=True)


def main() -> None:
    PREVIEWS.mkdir(parents=True, exist_ok=True)
    asset_sheet()
    launcher()
    print("Rendered asset_sheet.png, launcher_masks.png, and opaque sRGB partydeck_1024.png.")


if __name__ == "__main__":
    main()
