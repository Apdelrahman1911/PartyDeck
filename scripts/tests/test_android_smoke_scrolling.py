"""Host-only scroll regressions: original XML plus explicitly synthetic transitions.

No Android command is executed. Synthetic frames prove checker control flow,
not that a native layout has been recovered or a device scenario has passed.
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
    "partydeck_scrolling_smoke", Path(__file__).resolve().parents[1] / "smoke-android-ui.py",
)
smoke = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = smoke
SPEC.loader.exec_module(smoke)
FIXTURES = Path(__file__).resolve().parent / "fixtures" / "android-landscape"
ORIGINALS = json.loads((FIXTURES / "originals.json").read_text())["fixtures"]
LEFT_VIEWPORT = (136, 280, 826, 699)
RIGHT_VIEWPORT = (826, 280, 1516, 699)
LEFT_SWIPE = ("shell", "input", "swipe", "481", "594", "481", "384", "250")
RIGHT_SWIPE = ("shell", "input", "swipe", "1171", "594", "1171", "384", "250")
SMALL_RIGHT_SWIPE = ("shell", "input", "swipe", "1063", "594", "1063", "384", "250")


def copy_tree(root):
    return ET.fromstring(ET.tostring(root))


def raw_node(root, tag):
    return next(node for node in root.iter("node") if node.get("resource-id") == tag)


def synthetic_visible_play(original):
    """Synthetic post-scroll frame; the retained original is never modified."""
    root = copy_tree(original)
    play = raw_node(root, "game-play")
    # Move the complete tagged subtree by a fixed amount, without changing its
    # enabled state. This frame exists only in memory as a host test transition.
    for node in play.iter("node"):
        left, top, right, bottom = smoke.node_bounds(node)
        node.set("bounds", f"[{left},{top - 100}][{right},{bottom - 100}]")
    return root


def synthetic_panes():
    """Synthetic landscape page with a larger left pane and smaller right pane."""
    return ET.fromstring('''<hierarchy rotation="1">
      <node package="dev.partydeck.app" bounds="[0,0][1600,720]">
        <node package="dev.partydeck.app" resource-id="synthetic-left"
              class="android.widget.ScrollView" bounds="[136,280][826,699]"
              scrollable="true" enabled="true" />
        <node package="dev.partydeck.app" resource-id="synthetic-right"
              class="android.widget.ScrollView" bounds="[826,280][1300,699]"
              scrollable="true" enabled="true">
          <node package="dev.partydeck.app" resource-id="game-play"
                bounds="[861,695][1265,720]" enabled="false" clickable="true" />
        </node>
      </node>
    </hierarchy>''')


def synthetic_next_round(bottom=699, enabled="true", include_play=False):
    """Synthetic zero-clearance round action in the smaller right pane."""
    root = synthetic_panes()
    action = raw_node(root, "game-play")
    action.set("resource-id", "game-next-round")
    action.set("enabled", enabled)
    action.set("bounds", f"[861,{bottom - 57}][1265,{bottom}]")
    if include_play:
        ET.SubElement(raw_node(root, "synthetic-left"), "node", {
            "package": smoke.PACKAGE, "resource-id": "game-play",
            "bounds": "[171,695][791,720]", "enabled": "false", "clickable": "true",
        })
    return root


class Clock:
    def __init__(self):
        self.now = 0.0

    def monotonic(self):
        return self.now

    def sleep(self, seconds):
        # Exact millisecond-scale steps keep the 120-second boundary stable.
        self.now = round(self.now + seconds, 9)


class Replay(smoke.AndroidSmoke):
    def __init__(self, output, frames=(), advance_on=()):
        output.mkdir()
        super().__init__("host-only-scroll-replay", output)
        self.display_size = (720, 1600)
        self.frames = frames
        self.frame = 0
        self.advance_on = advance_on
        self.commands = []
        self.dumps = []

    def dump_ui(self, deadline=None):
        self.dumps.append((smoke.time.monotonic(), deadline))
        root = copy_tree(self.frames[self.frame])
        self.bind_ui(root)
        return root

    def adb(self, *arguments, timeout=20, binary=False):
        self.commands.append(arguments)
        # Only the specified real input coordinates unlock the next synthetic
        # frame. A swipe in the wrong pane cannot advance the replay.
        if self.frame < len(self.advance_on) and arguments == self.advance_on[self.frame]:
            self.frame += 1
        return ""

    def record(self, message):
        self.steps.append(message)

    def input_records(self):
        path = self.output / "input-geometry.log"
        return [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []


class ScrollingSmokeTest(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="partydeck-scrolling-host-test-")
        self.addCleanup(temporary.cleanup)
        self.output = Path(temporary.name)
        self.device_number = 0
        self.clock = Clock()
        self.enterContext(patch.object(smoke.time, "monotonic", self.clock.monotonic))
        self.enterContext(patch.object(smoke.time, "sleep", self.clock.sleep))
        self.enterContext(patch.object(
            smoke.subprocess, "run", side_effect=AssertionError("Host tests must not execute subprocesses."),
        ))

    def replay(self, frames=(), advance_on=()):
        self.device_number += 1
        return Replay(self.output / str(self.device_number), frames, advance_on)

    def test_original_fixtures_reproduce_clipping_and_target_the_right_pane(self):
        for original in ORIGINALS:
            with self.subTest(fixture=original["file"]):
                data = (FIXTURES / original["file"]).read_bytes()
                self.assertEqual(original["sha256"], hashlib.sha256(data).hexdigest())
                self.assertEqual(original["bytes"], len(data))
                root = ET.fromstring(data)
                device = self.replay()
                self.assertIsNone(device.find(root, "game-play", enabled=None))
                play = raw_node(root, "game-play")
                self.assertEqual((861, 695, 1162, 720), smoke.node_bounds(play))
                self.assertEqual(RIGHT_VIEWPORT, device.viewport(play))
                with self.assertRaisesRegex(RuntimeError, "current visible viewport"):
                    device.tap_node(play, "game-play")
                self.assertEqual([], device.commands)
                device.swipe("down", root)
                device.swipe("down", root, target_tags=("game-next-round", "game-play"))
                self.assertEqual([LEFT_SWIPE, RIGHT_SWIPE], device.commands)
                self.assertEqual(
                    [list(LEFT_VIEWPORT), list(RIGHT_VIEWPORT)],
                    [record["viewport"] for record in device.input_records()],
                )
                self.assertIsNone(device.find(root, "game-play", enabled=None))

    def test_human_turn_requires_a_right_pane_swipe_before_synthetic_play_is_visible(self):
        for original in ORIGINALS:
            with self.subTest(fixture=original["file"]):
                initial = ET.parse(FIXTURES / original["file"]).getroot()
                visible = synthetic_visible_play(initial)
                device = self.replay([initial, visible], [RIGHT_SWIPE])
                device.wait_for_human_turn()
                self.assertEqual([RIGHT_SWIPE], device.commands)
                self.assertEqual(2, len(device.dumps))
                play = device.find(device.ui_root, "game-play", enabled=None)
                self.assertIsNotNone(play)
                self.assertEqual("false", play.get("enabled"))
                self.assertEqual("[861,695][1162,720]", raw_node(initial, "game-play").get("bounds"))

    def test_absent_targets_preserve_generic_largest_pane_and_direction(self):
        for targets in ((), ("missing",), ("game-next-round", "missing")):
            with self.subTest(targets=targets):
                device = self.replay()
                root = synthetic_panes()
                device.swipe("down", root, target_tags=targets)
                device.swipe("up", root, target_tags=targets)
                self.assertEqual([
                    LEFT_SWIPE,
                    ("shell", "input", "swipe", "481", "384", "481", "594", "250"),
                ], device.commands)

    def test_foreign_targets_do_not_redirect_or_ambiguitize_app_scrolling(self):
        root = synthetic_panes()
        raw_node(root, "game-play").set("package", "android")
        device = self.replay()
        device.swipe("down", root, target_tags=("game-play",))
        self.assertEqual([LEFT_SWIPE], device.commands)
        foreign = copy_tree(raw_node(root, "game-play"))
        raw_node(root, "synthetic-left").append(foreign)
        raw_node(root, "synthetic-right")[0].set("package", smoke.PACKAGE)
        device.swipe("down", root, target_tags=("game-play",))
        self.assertEqual([LEFT_SWIPE, SMALL_RIGHT_SWIPE], device.commands)

    def test_disabled_offscreen_namespaced_target_selects_its_smaller_pane(self):
        root = synthetic_panes()
        target = raw_node(root, "game-play")
        target.set("resource-id", smoke.PACKAGE + ":id/game-play")
        target.set("bounds", "[861,750][1265,807]")
        device = self.replay()
        self.assertIsNone(device.find(root, "game-play", enabled=None))
        device.swipe("down", root, target_tags=("game-play",))
        self.assertEqual([SMALL_RIGHT_SWIPE], device.commands)
        self.assertIsNone(device.find(root, "game-play", enabled=None))

    def test_duplicate_app_targets_reject_without_input(self):
        for safe_panes in (True, False):
            with self.subTest(safe_panes=safe_panes):
                root = synthetic_panes()
                raw_node(root, "synthetic-left").append(copy_tree(raw_node(root, "game-play")))
                if not safe_panes:
                    for node in root.iter("node"):
                        node.set("scrollable", "false")
                device = self.replay()
                with self.assertRaisesRegex(RuntimeError, "ambiguous"):
                    device.swipe("down", root, target_tags=("game-play",))
                self.assertEqual([], device.commands)
                self.assertEqual([], device.input_records())

    def test_present_target_without_a_safe_current_ancestor_rejects_without_input(self):
        for attribute, value in (
            ("enabled", "false"), ("package", "android"),
            ("scrollable", "false"), ("bounds", "[826,650][1300,699]"),
            ("bounds", "[826,750][1300,900]"),
        ):
            with self.subTest(attribute=attribute, value=value):
                root = synthetic_panes()
                raw_node(root, "synthetic-right").set(attribute, value)
                device = self.replay()
                with self.assertRaisesRegex(RuntimeError, "no current safe scroll pane"):
                    device.swipe("down", root, target_tags=("game-play",))
                self.assertEqual([], device.commands)
                self.assertEqual([], device.input_records())
        root = synthetic_panes()
        for node in root.iter("node"):
            node.set("scrollable", "false")
        device = self.replay()
        with self.assertRaisesRegex(RuntimeError, "no current safe scroll pane"):
            device.swipe("down", root, target_tags=("game-play",))
        self.assertEqual([], device.commands)

    def test_missing_targets_and_no_eligible_app_pane_preserve_no_input(self):
        for foreign in (False, True):
            with self.subTest(foreign=foreign):
                root = synthetic_panes()
                for node in root.iter("node"):
                    node.set("package", "android" if foreign else smoke.PACKAGE)
                    if not foreign:
                        node.set("scrollable", "false")
                device = self.replay()
                device.swipe("down", root)
                device.swipe("down", root, target_tags=("missing",))
                self.assertEqual([], device.commands)
                self.assertEqual([], device.input_records())

    def test_target_ancestry_is_rebound_from_the_current_dump(self):
        initial = synthetic_panes()
        moved = copy_tree(initial)
        target = raw_node(moved, "game-play")
        raw_node(moved, "synthetic-right").remove(target)
        raw_node(moved, "synthetic-left").append(target)
        target.set("bounds", "[171,695][791,720]")
        device = self.replay()
        device.swipe("down", initial, target_tags=("game-play",))
        device.swipe("down", moved, target_tags=("game-play",))
        self.assertEqual([SMALL_RIGHT_SWIPE, LEFT_SWIPE], device.commands)
        self.assertEqual([1, 2], [record["ui_sequence"] for record in device.input_records()])

    def test_observed_next_round_edge_contact_requires_normal_action_clearance(self):
        # Synthetic tree using debug input sequence 10's recorded action/viewport
        # geometry. It is not a retained XML dump of that intermediate screen.
        root = synthetic_next_round()
        raw_node(root, "synthetic-right").set("bounds", "[284,259][1369,720]")
        action = raw_node(root, "game-next-round")
        action.set("bounds", "[319,663][1334,720]")
        device = self.replay()
        self.assertIs(action, device.find(root, "game-next-round"))
        self.assertIsNone(device.find_action(root, "game-next-round"))
        self.assertEqual((284, 259, 1369, 720), device.viewport(action))
        for clearance in (0, 7, 8):
            with self.subTest(clearance=clearance):
                root = synthetic_next_round(bottom=699 - clearance)
                self.assertIsNotNone(device.find(root, "game-next-round"))
                self.assertEqual(clearance >= 8, device.find_action(root, "game-next-round") is not None)

    def test_next_round_scrolls_its_own_pane_then_taps_only_fresh_clear_action(self):
        initial = synthetic_next_round(include_play=True)
        ready = synthetic_next_round(bottom=637, include_play=True)
        human = synthetic_visible_play(synthetic_panes())
        ready_tap = ("shell", "input", "tap", "1063", "608")
        device = self.replay([initial, ready, human], [SMALL_RIGHT_SWIPE, ready_tap])
        previous = device.dump_ui()
        rejected = device.find(previous, "game-next-round")
        self.assertIsNotNone(rejected)
        self.assertIsNone(device.find_action(previous, "game-next-round"))
        device.wait_for_human_turn()
        self.assertEqual([SMALL_RIGHT_SWIPE, ready_tap], device.commands)
        swipe, tap = device.input_records()
        self.assertEqual([826, 280, 1300, 699], swipe["viewport"])
        self.assertEqual("synthetic-right", swipe["resource_id"])
        self.assertEqual("game-next-round", tap["label"])
        self.assertEqual([861, 580, 1265, 637], tap["bounds"])
        self.assertGreater(tap["ui_sequence"], swipe["ui_sequence"])
        with self.assertRaisesRegex(RuntimeError, "current visible viewport"):
            device.tap_node(rejected, "game-next-round")
        self.assertEqual([SMALL_RIGHT_SWIPE, ready_tap], device.commands)

    def test_unready_next_round_never_taps_or_extends_the_human_turn_deadline(self):
        for bottom, enabled in ((720, "true"), (699, "true"), (637, "false")):
            with self.subTest(bottom=bottom, enabled=enabled):
                started = self.clock.now
                device = self.replay([synthetic_next_round(bottom, enabled)])
                with self.assertRaisesRegex(RuntimeError, "within 120 seconds"):
                    device.wait_for_human_turn()
                self.assertAlmostEqual(120, self.clock.now - started)
                self.assertTrue(device.commands)
                self.assertTrue(all(command == SMALL_RIGHT_SWIPE for command in device.commands))
                self.assertTrue(all(
                    started <= dumped_at < started + 120 and deadline == started + 120
                    for dumped_at, deadline in device.dumps
                ))

    def test_permanently_clipped_play_does_not_count_as_a_human_turn(self):
        original = ET.parse(FIXTURES / ORIGINALS[0]["file"]).getroot()
        device = self.replay([original])
        with self.assertRaisesRegex(RuntimeError, "within 120 seconds"):
            device.wait_for_human_turn()
        self.assertEqual(120, self.clock.now)
        self.assertTrue(device.commands)
        self.assertTrue(all(command == RIGHT_SWIPE for command in device.commands))

    def test_round_limit_and_winner_rejection_remain_bounded(self):
        device = self.replay([synthetic_next_round(bottom=637)])
        with self.assertRaisesRegex(RuntimeError, "within eight rounds"):
            device.wait_for_human_turn()
        self.assertEqual(8, len(device.commands))
        self.assertTrue(all(command[:3] == ("shell", "input", "tap") for command in device.commands))
        root = synthetic_next_round(bottom=637)
        raw_node(root, "game-next-round").set("resource-id", "game-winner")
        device = self.replay([root])
        with self.assertRaisesRegex(RuntimeError, "ended before the human play"):
            device.wait_for_human_turn()
        self.assertEqual([], device.commands)


if __name__ == "__main__":
    unittest.main()
