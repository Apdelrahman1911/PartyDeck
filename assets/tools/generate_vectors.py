#!/usr/bin/env python3
"""Original PartyDeck geometry, exported as SVG and Compose XML vectors.

No source artwork, icon font, external image, or third-party icon library is used.
The drawing recipes below are the canonical source; generated files are checked in.
"""

from dataclasses import dataclass, field
from math import cos, pi, sin
from pathlib import Path
from typing import Iterable
from xml.sax.saxutils import escape


ROOT = Path(__file__).resolve().parents[2]
VECTOR_DIR = ROOT / "assets/vectors"
LAUNCHER_DIR = ROOT / "assets/launcher"
DRAWABLE_DIR = ROOT / "composeApp/src/commonMain/composeResources/drawable"
INK = "#191526"
PAPER = "#F4F0E8"
CITRON = "#D6EF82"
COPPER = "#F16B48"
MUTED = "#A99CB8"


@dataclass
class PathShape:
    data: str
    fill: str = "none"
    stroke: str | None = None
    stroke_width: float = 1.75
    opacity: float = 1.0
    even_odd: bool = False


@dataclass
class Group:
    children: list["PathShape | Group"] = field(default_factory=list)
    rotation: float = 0
    pivot_x: float = 0
    pivot_y: float = 0
    translate_x: float = 0
    translate_y: float = 0
    scale_x: float = 1
    scale_y: float = 1


Shape = PathShape | Group


def number(value: float) -> str:
    return f"{value:.4f}".rstrip("0").rstrip(".") if value else "0"


def rect(x: float, y: float, w: float, h: float, radius: float = 0) -> str:
    r = radius
    return (
        f"M{number(x+r)} {number(y)} H{number(x+w-r)} "
        f"Q{number(x+w)} {number(y)} {number(x+w)} {number(y+r)} "
        f"V{number(y+h-r)} Q{number(x+w)} {number(y+h)} {number(x+w-r)} {number(y+h)} "
        f"H{number(x+r)} Q{number(x)} {number(y+h)} {number(x)} {number(y+h-r)} "
        f"V{number(y+r)} Q{number(x)} {number(y)} {number(x+r)} {number(y)} Z"
    )


def circle(x: float, y: float, radius: float) -> str:
    return (
        f"M{number(x-radius)} {number(y)} "
        f"a{number(radius)} {number(radius)} 0 1 0 {number(2*radius)} 0 "
        f"a{number(radius)} {number(radius)} 0 1 0 {number(-2*radius)} 0 Z"
    )


def light(x: float, y: float, outer: float, inner: float | None = None) -> str:
    """A four-point light with curved shoulders, distinct from the Star rank."""
    shoulder = inner if inner is not None else outer * 0.24
    return (
        f"M{number(x)} {number(y-outer)} "
        f"Q{number(x+shoulder)} {number(y-shoulder)} {number(x+outer)} {number(y)} "
        f"Q{number(x+shoulder)} {number(y+shoulder)} {number(x)} {number(y+outer)} "
        f"Q{number(x-shoulder)} {number(y+shoulder)} {number(x-outer)} {number(y)} "
        f"Q{number(x-shoulder)} {number(y-shoulder)} {number(x)} {number(y-outer)} Z"
    )


def star(x: float, y: float, outer: float, inner: float, points: int = 5) -> str:
    coords = []
    for index in range(points * 2):
        angle = -pi / 2 + index * pi / points
        radius = outer if index % 2 == 0 else inner
        coords.append(f"{number(x+cos(angle)*radius)} {number(y+sin(angle)*radius)}")
    return "M" + " L".join(coords) + " Z"


def ellipse(x: float, y: float, rx: float, ry: float) -> str:
    return (
        f"M{number(x-rx)} {number(y)} "
        f"a{number(rx)} {number(ry)} 0 1 0 {number(rx*2)} 0 "
        f"a{number(rx)} {number(ry)} 0 1 0 {number(-rx*2)} 0 Z"
    )


def svg_shape(shape: Shape, indent: str = "  ") -> str:
    if isinstance(shape, Group):
        transforms = []
        if shape.translate_x or shape.translate_y:
            transforms.append(f"translate({number(shape.translate_x)} {number(shape.translate_y)})")
        if shape.scale_x != 1 or shape.scale_y != 1:
            transforms.append(f"scale({number(shape.scale_x)} {number(shape.scale_y)})")
        if shape.rotation:
            transforms.append(
                f"rotate({number(shape.rotation)} {number(shape.pivot_x)} {number(shape.pivot_y)})"
            )
        attr = f' transform="{" ".join(transforms)}"' if transforms else ""
        children = "\n".join(svg_shape(child, indent + "  ") for child in shape.children)
        return f"{indent}<g{attr}>\n{children}\n{indent}</g>"
    attributes = [f'd="{escape(shape.data)}"', f'fill="{shape.fill}"']
    if shape.stroke:
        attributes += [
            f'stroke="{shape.stroke}"',
            f'stroke-width="{number(shape.stroke_width)}"',
            'stroke-linecap="round"',
            'stroke-linejoin="round"',
        ]
    if shape.opacity != 1:
        attributes.append(f'opacity="{number(shape.opacity)}"')
    if shape.even_odd:
        attributes.append('fill-rule="evenodd"')
    return indent + "<path " + " ".join(attributes) + "/>"


def xml_shape(shape: Shape, indent: str = "    ") -> str:
    if isinstance(shape, Group):
        attrs = []
        for attr, value, default in (
            ("rotation", shape.rotation, 0),
            ("pivotX", shape.pivot_x, 0),
            ("pivotY", shape.pivot_y, 0),
            ("translateX", shape.translate_x, 0),
            ("translateY", shape.translate_y, 0),
            ("scaleX", shape.scale_x, 1),
            ("scaleY", shape.scale_y, 1),
        ):
            if value != default:
                attrs.append(f'android:{attr}="{number(value)}"')
        attr = " " + " ".join(attrs) if attrs else ""
        children = "\n".join(xml_shape(child, indent + "    ") for child in shape.children)
        return f"{indent}<group{attr}>\n{children}\n{indent}</group>"
    attrs = [
        f'android:pathData="{escape(shape.data)}"',
        f'android:fillColor="{shape.fill if shape.fill != "none" else "#00000000"}"',
    ]
    if shape.stroke:
        attrs += [
            f'android:strokeColor="{shape.stroke}"',
            f'android:strokeWidth="{number(shape.stroke_width)}"',
            'android:strokeLineCap="round"',
            'android:strokeLineJoin="round"',
        ]
    if shape.opacity != 1:
        attrs += [
            f'android:fillAlpha="{number(shape.opacity)}"',
            f'android:strokeAlpha="{number(shape.opacity)}"',
        ]
    if shape.even_odd:
        attrs.append('android:fillType="evenOdd"')
    return indent + "<path\n" + "\n".join(indent + "    " + attr for attr in attrs) + " />"


def export(
    name: str,
    width: int,
    height: int,
    shapes: Iterable[Shape],
    *,
    source_dir: Path = VECTOR_DIR,
    resource_dir: Path = DRAWABLE_DIR,
) -> None:
    shapes = list(shapes)
    source_dir.mkdir(parents=True, exist_ok=True)
    resource_dir.mkdir(parents=True, exist_ok=True)
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}">\n'
        "  <!-- Original PartyDeck geometry. Source: assets/tools/generate_vectors.py -->\n"
        + "\n".join(svg_shape(shape) for shape in shapes)
        + "\n</svg>\n"
    )
    xml = (
        '<?xml version="1.0" encoding="utf-8"?>\n'
        '<!-- Original PartyDeck geometry. Source: assets/tools/generate_vectors.py -->\n'
        '<vector xmlns:android="http://schemas.android.com/apk/res/android"\n'
        f'    android:width="{width}dp" android:height="{height}dp"\n'
        f'    android:viewportWidth="{width}" android:viewportHeight="{height}">\n'
        + "\n".join(xml_shape(shape) for shape in shapes)
        + "\n</vector>\n"
    )
    (source_dir / f"{name}.svg").write_text(svg, encoding="utf-8")
    (resource_dir / f"{name}.xml").write_text(xml, encoding="utf-8")


def mark(monochrome: bool = False) -> list[Shape]:
    if monochrome:
        # Draw only the visible rear edge. A full rear outline would show through
        # the front card's transparent light cutout in a monochrome launcher.
        rear = PathShape(
            "M44 19 H30 Q23 19 23 26 V76 Q23 83 30 83 H58 Q65 83 65 76",
            stroke="#FFFFFF", stroke_width=4,
        )
        front = PathShape(rect(34, 12, 43, 64, 7) + " " + light(55.5, 44, 14), "#FFFFFF", even_odd=True)
        front_detail = []
    else:
        rear = PathShape(rect(23, 19, 42, 64, 7), COPPER)
        front = PathShape(rect(34, 12, 43, 64, 7), PAPER, INK, 2.5)
        front_detail = [
            PathShape(light(55.5, 44, 14), INK),
            PathShape(circle(42, 21, 1.75) + " " + circle(69, 67, 1.75), INK),
        ]
    return [
        Group([rear], rotation=-14, pivot_x=44, pivot_y=51),
        Group([front, *front_detail], rotation=10, pivot_x=55.5, pivot_y=44),
    ]


def ranks() -> None:
    export(
        "rank_crown", 64, 64,
        [PathShape(
            "M9 17 L22 26 L32 10 L42 26 L55 17 L48 46 H16 Z "
            "M27.5 34 L32 29.5 L36.5 34 L32 38.5 Z " + rect(17, 49, 30, 5, 1.5),
            INK, even_odd=True,
        )],
    )
    export(
        "rank_moon", 64, 64,
        [
            PathShape(
                "M46 9 C33 4 18 10 11 23 C3 38 12 55 27 58 "
                "C41 61 53 52 57 41 C45 46 33 40 29 29 "
                "C25 19 34 10 46 9 Z", INK,
            ),
            PathShape(light(48, 24, 6, 1.25), INK),
        ],
    )
    export(
        "rank_star", 64, 64,
        [PathShape(star(32, 33, 27, 12) + " " + circle(32, 33, 3.4), INK, even_odd=True)],
    )
    export(
        "rank_wild", 64, 64,
        [
            Group([PathShape(ellipse(32, 32, 25, 11), stroke=INK, stroke_width=5.5)], rotation=45, pivot_x=32, pivot_y=32),
            Group([PathShape(ellipse(32, 32, 25, 11), stroke=INK, stroke_width=5.5)], rotation=-45, pivot_x=32, pivot_y=32),
            PathShape(circle(32, 32, 3.1), INK),
        ],
    )


def card_back() -> None:
    shapes: list[Shape] = [
        PathShape(rect(0, 0, 160, 240, 12), INK),
        PathShape(rect(8, 8, 144, 224, 7), stroke=PAPER, stroke_width=1, opacity=0.72),
        PathShape(rect(13, 13, 134, 214, 4), stroke=PAPER, stroke_width=0.65, opacity=0.24),
    ]
    corner = [
        PathShape("M24 53 V30 Q24 24 30 24 H53", stroke=PAPER, stroke_width=1.2, opacity=0.8),
        PathShape("M31 46 V34 Q31 31 34 31 H46", stroke=PAPER, stroke_width=0.75, opacity=0.4),
        PathShape(light(24, 24, 3.5), COPPER),
        PathShape(circle(59, 24, 1.3) + " " + circle(24, 59, 1.3), PAPER, opacity=0.8),
    ]
    shapes += [Group(corner), Group(corner, rotation=180, pivot_x=80, pivot_y=120)]
    shapes += [
        PathShape("M80 55 L127 120 L80 185 L33 120 Z", stroke=PAPER, stroke_width=1, opacity=0.62),
        PathShape("M80 66 L118 120 L80 174 L42 120 Z", stroke=PAPER, stroke_width=0.7, opacity=0.26),
        PathShape(ellipse(80, 120, 42, 31), stroke=PAPER, stroke_width=0.9, opacity=0.76),
        PathShape(ellipse(80, 120, 24, 43), stroke=PAPER, stroke_width=0.9, opacity=0.76),
        PathShape(circle(80, 120, 17), INK, PAPER, 0.9),
        PathShape(light(80, 120, 26, 6), CITRON),
        PathShape(light(80, 120, 9, 2), INK),
        PathShape(circle(80, 54, 2) + " " + circle(80, 186, 2), COPPER),
        PathShape("M20 113 V127 M140 113 V127", stroke=PAPER, stroke_width=1, opacity=0.56),
        PathShape("M58 204 H72 M88 204 H102 M58 36 H72 M88 36 H102", stroke=PAPER, stroke_width=0.8, opacity=0.4),
        PathShape(light(80, 36, 4) + " " + light(80, 204, 4), COPPER),
    ]
    export("card_back", 160, 240, shapes)


def ui_icons() -> None:
    icons = {
        "arrow_back": ["M14.5 5.5 L8 12 L14.5 18.5", "M8 12 H21"],
        "arrow_forward": ["M9.5 5.5 L16 12 L9.5 18.5", "M3 12 H16"],
        "check": ["M5 12.5 L9.5 17 L19 7"],
        "close": ["M6 6 L18 18 M18 6 L6 18"],
        "plus": ["M12 5 V19 M5 12 H19"],
        "people": [circle(9, 7, 3), "M3 20 V18 C3 14 6 12 9 12 C12 12 15 14 15 18 V20", "M16 4.5 C18 4.5 19.5 6 19.5 8 C19.5 10 18 11.5 16 11.5 M18 14 C20 15 21 16.5 21 19"],
        "nearby": [circle(12, 18, 1), "M8 13.5 C10.3 11.5 13.7 11.5 16 13.5 M4.5 9.5 C8.6 5.8 15.4 5.8 19.5 9.5 M1.8 5.5 C7.3 0.8 16.7 0.8 22.2 5.5"],
        "settings": ["M5 3 V7 M5 13 V21 M12 3 V13 M12 19 V21 M19 3 V5 M19 11 V21", circle(5, 10, 3), circle(12, 16, 3), circle(19, 8, 3)],
        "sound": ["M4 9 H8 L13 5 V19 L8 15 H4 Z", "M16 9 C18 10.5 18 13.5 16 15 M18.5 5.5 C22.5 9 22.5 15 18.5 18.5"],
        "sound_off": ["M4 9 H8 L13 5 V19 L8 15 H4 Z", "M17 9 L22 14 M22 9 L17 14"],
        "haptics": [rect(7, 3.5, 10, 17, 2), "M3.5 7 L2 10 L3.5 13 L2 16 M20.5 7 L22 10 L20.5 13 L22 16", "M10.5 17.5 H13.5"],
        "motion": ["M4 8 H9 M2 12 H7 M4 16 H9", "M13 5 C17 5 20 8 20 12 C20 16 17 19 13 19", "M11 9 C13 9 15 10.3 15 12 C15 13.7 13 15 11 15"],
        "copy": [rect(8, 8, 12, 13, 2), "M15 8 V5 C15 3.9 14.1 3 13 3 H5 C3.9 3 3 3.9 3 5 V15 C3 16.1 3.9 17 5 17 H8"],
        "qr_scan": ["M3 8 V5 C3 3.9 3.9 3 5 3 H8 M16 3 H19 C20.1 3 21 3.9 21 5 V8 M21 16 V19 C21 20.1 20.1 21 19 21 H16 M8 21 H5 C3.9 21 3 20.1 3 19 V16", "M3 12 H21"],
        "share": ["M12 15 V3 M8 7 L12 3 L16 7", "M5 11 V19 C5 20.1 5.9 21 7 21 H17 C18.1 21 19 20.1 19 19 V11"],
        "info": [circle(12, 12, 9), "M12 11 V17", circle(12, 7.4, 0.3)],
        "lock": [rect(5, 10, 14, 11, 2), "M8 10 V7 C8 1.7 16 1.7 16 7 V10", "M12 14 V17"],
        "exit": ["M10 4 H5 C3.9 4 3 4.9 3 6 V18 C3 19.1 3.9 20 5 20 H10", "M10 12 H21 M17 8 L21 12 L17 16"],
    }
    for name, paths in icons.items():
        export("icon_" + name, 24, 24, [PathShape(path, stroke=INK) for path in paths])


def launcher() -> None:
    layer = Group(mark(), translate_x=16.56, translate_y=16.56, scale_x=0.78, scale_y=0.78)
    mono_layer = Group(mark(True), translate_x=16.56, translate_y=16.56, scale_x=0.78, scale_y=0.78)
    background = PathShape(rect(0, 0, 108, 108), INK)
    for name, shapes in (
        ("partydeck_foreground", [layer]),
        ("partydeck_background", [background]),
        ("partydeck_monochrome", [mono_layer]),
        ("partydeck_launcher", [background, layer]),
    ):
        export(name, 108, 108, shapes, source_dir=LAUNCHER_DIR, resource_dir=LAUNCHER_DIR)


def main() -> None:
    ranks()
    card_back()
    ui_icons()
    export("partydeck_mark", 96, 96, mark())
    launcher()
    print(f"Exported {len(list(DRAWABLE_DIR.glob('*.xml')))} common vectors and launcher layers.")


if __name__ == "__main__":
    main()
