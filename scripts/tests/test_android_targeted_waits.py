"""Awaited-tag scrolling with original XML and explicit host-only transitions.

No Android command runs. Moving between original observations is a synthetic
control-flow probe, not evidence that a device scroll or recovery succeeded.
"""

import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET


SPEC = importlib.util.spec_from_file_location(
    "partydeck_targeted_wait_tests", Path(__file__).resolve().parents[1] / "smoke-android-ui.py",
)
ui = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = ui
SPEC.loader.exec_module(ui)
FIXTURES = Path(__file__).resolve().parent / "fixtures/android-targeted-wait-34506161751"
ORIGINALS = json.loads((FIXTURES / "originals.json").read_text())
VARIANTS = ("debug", "optimized-test-signed")
RIGHT_SWIPE = ("shell", "input", "swipe", "1171", "594", "1171", "384", "250")
LEFT_SWIPE = ("shell", "input", "swipe", "481", "594", "481", "384", "250")


def original(variant, state):
    return (FIXTURES / f"{variant}-{state}.xml").read_bytes()


def play_node(root):
    return next(node for node in root.iter("node") if node.get("resource-id") == "game-play")


def synthetic_clearance(pixels):
    """Move the complete enabled action subtree in memory; originals stay exact."""
    root = ET.fromstring(original("debug", "visible-enabled"))
    play = play_node(root)
    displacement = 699 - pixels - ui.node_bounds(play)[3]
    for node in play.iter("node"):
        left, top, right, bottom = ui.node_bounds(node)
        node.set("bounds", f"[{left},{top + displacement}][{right},{bottom + displacement}]")
    return ET.tostring(root)


class Clock:
    def __init__(self):
        self.now = 0.0

    def monotonic(self):
        return self.now

    def sleep(self, seconds):
        self.now = round(self.now + seconds, 9)


class Replay(ui.AndroidSmoke):
    def __init__(self, output, frames, advance_on):
        output.mkdir()
        super().__init__("host-only-targeted-wait", output)
        self.display_size = (720, 1600)
        self.frames, self.advance_on = frames, advance_on
        self.frame = 0
        self.commands, self.deadlines, self.roots = [], [], []

    def dump_ui(self, deadline=None):
        self.deadlines.append(deadline)
        root = ET.fromstring(self.frames[self.frame])
        self.bind_ui(root)
        self.roots.append(root)
        return root

    def adb(self, *arguments, timeout=20, binary=False):
        if arguments[:3] != ("shell", "input", "swipe"):
            raise AssertionError("A read-only wait must not tap or run another command.")
        self.commands.append(arguments)
        if self.frame < len(self.advance_on) and arguments == self.advance_on[self.frame]:
            self.frame += 1
        return ""


class TargetedWaitTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="partydeck-targeted-wait-host-")
        self.addCleanup(temporary.cleanup)
        self.output = Path(temporary.name)
        self.number = 0
        self.clock = Clock()
        self.enterContext(patch.object(ui.time, "monotonic", self.clock.monotonic))
        self.enterContext(patch.object(ui.time, "sleep", self.clock.sleep))
        self.enterContext(patch.object(
            ui.subprocess, "run", side_effect=AssertionError("Host tests must not execute subprocesses."),
        ))

    def replay(self, frames, advance_on=()):
        self.number += 1
        return Replay(self.output / str(self.number), frames, advance_on)

    def test_original_fixtures_bind_both_variants_and_reproduce_disabled_clipping(self):
        self.assertEqual(34506161751, ORIGINALS["run_id"])
        for item in ORIGINALS["fixtures"]:
            raw = (FIXTURES / item["file"]).read_bytes()
            self.assertEqual(item["bytes"], len(raw))
            self.assertEqual(item["sha256"], hashlib.sha256(raw).hexdigest())
        for variant in VARIANTS:
            with self.subTest(variant=variant):
                device = self.replay([original(variant, "clipped")])
                root = device.dump_ui()
                play = play_node(root)
                self.assertEqual("false", play.get("enabled"))
                self.assertEqual((826, 280, 1516, 699), device.viewport(play))
                self.assertEqual((695, 720), (ui.node_bounds(play)[1], ui.node_bounds(play)[3]))
                self.assertIsNone(device.find(root, "game-play", enabled=False))
                self.assertIsNone(device.find_action(root, "game-play"))

    def test_disabled_tag_wait_scrolls_its_own_pane_and_requires_a_fresh_visible_observation(self):
        for variant in VARIANTS:
            with self.subTest(variant=variant):
                self.clock.now = 0.0
                device = self.replay([original(variant, "clipped"), original(variant, "visible-disabled")],
                                     [RIGHT_SWIPE])
                node = device.wait_for_tag("game-play", enabled=False, scroll="down")
                self.assertEqual([RIGHT_SWIPE], device.commands)
                self.assertEqual("false", node.get("enabled"))
                self.assertTrue(device.visible(node))
                self.assertIs(node, play_node(device.roots[-1]))
                self.assertIsNot(node, play_node(device.roots[0]))
                self.assertEqual([45.0, 45.0], device.deadlines)

    def test_action_wait_keeps_enabled_full_visibility_and_eight_pixel_clearance(self):
        clipped = ET.fromstring(original("debug", "clipped"))
        play_node(clipped).set("enabled", "true")
        device = self.replay([ET.tostring(clipped), synthetic_clearance(7), synthetic_clearance(8)],
                             [RIGHT_SWIPE, RIGHT_SWIPE])
        action = device.wait_for_action("game-play", scroll="down")
        self.assertEqual([RIGHT_SWIPE, RIGHT_SWIPE], device.commands)
        self.assertEqual(3, len(device.roots))
        self.assertTrue(device.visible(action))
        self.assertEqual("true", action.get("enabled"))
        self.assertEqual(8, device.viewport(action)[3] - ui.node_bounds(action)[3])
        self.assertIs(action, play_node(device.roots[-1]))
        self.assertEqual({45.0}, set(device.deadlines))

    def test_permanently_clipped_target_cannot_pass_or_extend_the_original_budget(self):
        device = self.replay([original("debug", "clipped")])
        with self.assertRaisesRegex(RuntimeError, "Expected visible 'game-play' within 45 seconds"):
            device.wait_for_tag("game-play", enabled=False, scroll="down")
        self.assertEqual(45.0, self.clock.now)
        self.assertEqual({45.0}, set(device.deadlines))
        self.assertEqual(16, len(device.commands))
        self.assertTrue(all(command[3] == command[5] == "1171" for command in device.commands))
        self.assertIsNone(device.find(device.roots[-1], "game-play", enabled=False))

    def test_missing_tag_preserves_the_existing_generic_scroll_fallback(self):
        absent = ET.fromstring(original("debug", "clipped"))
        parents = {child: parent for parent in absent.iter() for child in parent}
        target = play_node(absent)
        parents[target].remove(target)
        device = self.replay([ET.tostring(absent), original("debug", "visible-disabled")], [LEFT_SWIPE])
        node = device.wait_for_tag("game-play", enabled=False, scroll="down")
        self.assertEqual([LEFT_SWIPE], device.commands)
        self.assertTrue(device.visible(node))

    def test_waits_without_known_targets_keep_the_existing_generic_behavior(self):
        device = self.replay([original("debug", "clipped"), original("debug", "visible-disabled")],
                             [LEFT_SWIPE])
        node = device.wait_until("Generic predicate", lambda root: device.find(root, "game-play", enabled=False),
                                 scroll="down")
        self.assertEqual([LEFT_SWIPE], device.commands)
        self.assertTrue(device.visible(node))


if __name__ == "__main__":
    unittest.main()
