"""Focused false-acceptance cases for native/renderer qualification evidence."""

import copy
import json
import struct
import unittest
import zlib

from evidence import (
    CheckFailure, concealed, control_named, counter, parse_document,
    read_png, require_rendered_pixels, scroll_points, touch_point, validate_diagnostics,
)


def diagnostics():
    return {
        "schemaVersion": 1, "requestId": "3", "sequence": "5", "presentationId": "entry-a",
        "revision": "9007199254740993", "presentationMode": "2d", "coordinateSpace": "root_viewport",
        "foreground": True, "viewport": {"width": 720, "height": 1200}, "handConcealed": False,
        "selectedCount": 1, "privateFaceCount": 2, "privateLabelCount": 2,
        "controls": [
            {"group": "partydeck_hand_card", "cardIndex": 0, "rect": [20, 300, 100, 200],
             "clipRect": [0, 0, 720, 1200],
             "visible": True, "enabled": True, "selected": True},
            {"group": "partydeck_action_hide", "cardIndex": -1, "rect": [500, 800, 120, 70],
             "clipRect": [0, 0, 720, 1200],
             "visible": True, "enabled": True, "selected": False},
        ],
    }


def hidden():
    value = diagnostics()
    value.update(handConcealed=True, selectedCount=0, privateFaceCount=0, privateLabelCount=0)
    value["controls"][0].update(visible=False, selected=False)
    return value


def png_fixture(width, height, rgb):
    def chunk(kind, payload):
        return struct.pack(">I", len(payload)) + kind + payload + struct.pack(">I", zlib.crc32(kind + payload))
    rows = b"".join(b"\0" + rgb[y * width * 3:(y + 1) * width * 3] for y in range(height))
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(rows)) + chunk(b"IEND", b""))


class DiagnosticsEvidenceTest(unittest.TestCase):
    def test_valid_control_maps_into_native_surface(self):
        value = validate_diagnostics(diagnostics(), "entry-a", "2d")
        self.assertEqual(counter(value["revision"], "revision"), 9007199254740993)
        self.assertEqual(touch_point(value, control_named(value, "card", 0),
                                    {"x": 0, "y": 200, "width": 720, "height": 1200}, (720, 1600)), (70, 600))

    def test_wrong_lifetime_mode_and_coordinate_space_rejected(self):
        for key, wrong in (("presentationId", "closed-entry"), ("presentationMode", "3d"),
                           ("coordinateSpace", "canvas_without_transform"), ("schemaVersion", True)):
            with self.subTest(key=key), self.assertRaises(CheckFailure):
                value = diagnostics()
                value[key] = wrong
                validate_diagnostics(value, "entry-a", "2d")

    def test_counter_precision_cannot_be_silently_lost(self):
        for wrong in (9007199254740993, 9007199254740992.0, "01", "1e3", "-1", "9223372036854775808"):
            with self.subTest(value=wrong), self.assertRaises(CheckFailure):
                counter(wrong, "revision")

    def test_duplicate_and_nonfinite_json_rejected(self):
        for document in ('{"revision":"1","revision":"2"}',
                         '{"revision":"1","revisio\\u006e":"2"}', '{"x":NaN}', '[]'):
            with self.subTest(document=document), self.assertRaises(CheckFailure):
                parse_document(document)
        self.assertEqual(parse_document(json.dumps(diagnostics()))["revision"], "9007199254740993")

    def test_hidden_but_retained_private_bindings_do_not_pass(self):
        self.assertTrue(concealed(validate_diagnostics(hidden(), "entry-a", "2d")))
        for key in ("privateFaceCount", "privateLabelCount"):
            with self.subTest(key=key):
                value = hidden()
                value[key] = 1
                self.assertFalse(concealed(validate_diagnostics(value, "entry-a", "2d")))

    def test_hidden_selection_is_counted_and_rejected(self):
        value = hidden()
        value["controls"][0]["selected"] = True
        with self.assertRaises(CheckFailure):
            validate_diagnostics(value, "entry-a", "2d")
        value["selectedCount"] = 1
        self.assertFalse(concealed(validate_diagnostics(value, "entry-a", "2d")))

    def test_ambiguous_controls_rejected(self):
        value = diagnostics()
        value["controls"].append(copy.deepcopy(value["controls"][0]))
        with self.assertRaises(CheckFailure):
            validate_diagnostics(value, "entry-a", "2d")

    def test_hidden_disabled_and_offscreen_controls_cannot_be_tapped(self):
        surface = {"x": 0, "y": 200, "width": 720, "height": 1200}
        for change in ({"visible": False}, {"enabled": False}, {"rect": [0, 1300, 100, 100]}):
            with self.subTest(change=change), self.assertRaises(CheckFailure):
                value = diagnostics()
                value["controls"][0].update(change)
                touch_point(value, value["controls"][0], surface, (720, 1600))

    def test_native_bounds_and_scale_must_match(self):
        value = diagnostics()
        for surface in ({"x": 0, "y": 500, "width": 720, "height": 1200},
                        {"x": 0, "y": 200, "width": 720, "height": 600}):
            with self.subTest(surface=surface), self.assertRaises(CheckFailure):
                touch_point(value, value["controls"][0], surface, (720, 1600))

    def test_partially_visible_control_cannot_hide_its_clipped_target(self):
        value = diagnostics()
        value["controls"][0]["rect"] = [20, -50, 100, 100]
        with self.assertRaises(CheckFailure):
            touch_point(value, value["controls"][0],
                        {"x": 0, "y": 200, "width": 720, "height": 1200}, (720, 1600))

    def test_nested_clip_controls_safe_scroll_coordinates(self):
        value = diagnostics()
        card = value["controls"][0]
        card["rect"], card["clipRect"] = [20, 700, 100, 200], [0, 200, 720, 600]
        surface = {"x": 0, "y": 200, "width": 720, "height": 1200}
        with self.assertRaises(CheckFailure):
            touch_point(value, card, surface, (720, 1600))
        self.assertEqual(scroll_points(value, card, surface, (720, 1600)), ((360, 850), (360, 550)))

    def test_android_density_maps_logical_rectangles_without_double_scaling(self):
        value = diagnostics()
        value["viewport"] = {"width": 400, "height": 700}
        value["controls"][0].update(rect=[20, 300, 100, 200], clipRect=[0, 0, 400, 700])
        surface = {"x": 10, "y": 150, "width": 700, "height": 1225}
        self.assertEqual(touch_point(value, value["controls"][0], surface, (720, 1600)), (132, 850))

    def test_noninteger_logical_width_is_not_falsely_treated_as_clipping(self):
        value = diagnostics()
        value["viewport"] = {"width": 411.4286, "height": 700}
        value["controls"][0].update(rect=[237.7143, 300.2, 125.2857, 50.142857], clipRect=[0, 0, 411.4286, 700])
        point = touch_point(value, value["controls"][0],
                            {"x": 0, "y": 150, "width": 720, "height": 1225}, (720, 1600))
        self.assertEqual(point, (525, 719))


class CaptureEvidenceTest(unittest.TestCase):
    def test_engine_crop_contains_rendered_pixels(self):
        rgb = bytes(part for pixel in range(64) for part in (pixel * 3, pixel * 2, pixel))
        picture = read_png(png_fixture(8, 8, rgb))
        crop = picture.crop({"x": 2, "y": 2, "width": 4, "height": 5})
        self.assertEqual(crop, b"".join(rgb[(y * 8 + 2) * 3:(y * 8 + 6) * 3] for y in range(2, 7)))
        require_rendered_pixels(crop)

    def test_flat_engine_surface_is_not_render_evidence(self):
        picture = read_png(png_fixture(8, 8, b"\0\0\0" * 64))
        with self.assertRaises(CheckFailure):
            require_rendered_pixels(picture.rgb)

    def test_truncated_corrupt_and_non_png_capture_rejected(self):
        valid = png_fixture(2, 2, b"\x12\x34\x56" * 4)
        corrupt = bytearray(valid)
        corrupt[44] ^= 1
        for data in (valid[:-4], bytes(corrupt), b"adb command failed"):
            with self.subTest(data=data[:8]), self.assertRaises(CheckFailure):
                read_png(data)

    def test_capture_cannot_include_a_different_native_surface(self):
        picture = read_png(png_fixture(8, 8, b"\0\0\0" * 64))
        with self.assertRaises(CheckFailure):
            picture.crop({"x": 4, "y": 4, "width": 8, "height": 8})


if __name__ == "__main__":
    unittest.main()
