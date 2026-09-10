"""Host-only Rules checker regressions; these do not execute Android or gameplay."""

import importlib.util
from pathlib import Path
import struct
import sys
import tempfile
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET
import zlib


SPEC = importlib.util.spec_from_file_location(
    "partydeck_rules_smoke", Path(__file__).resolve().parents[1] / "smoke-android-ui.py",
)
smoke = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = smoke
SPEC.loader.exec_module(smoke)
LABEL = "Try a practice table"


def rules_tree(action_bounds="[42,1355][678,1453]", label_bounds="[232,1385][488,1423]"):
    # Bounds and ancestry come from run 34421746656's paired Rules captures.
    root = ET.fromstring('''<hierarchy rotation="0">
      <node package="dev.partydeck.app" bounds="[0,0][720,1600]">
        <node package="dev.partydeck.app" class="android.widget.ScrollView"
              bounds="[0,136][720,1516]" scrollable="true" enabled="true">
          <node package="dev.partydeck.app" text="Know the table."
                bounds="[42,200][400,250]" enabled="true" />
          <node package="dev.partydeck.app" text="Be the last light."
                bounds="[42,400][500,450]" enabled="true" />
          <node package="dev.partydeck.app" class="android.view.View"
                clickable="true" enabled="true">
            <node package="dev.partydeck.app" class="android.widget.TextView"
                  text="Try a practice table" clickable="false" enabled="true" />
          </node>
        </node>
      </node>
    </hierarchy>''')
    label = next(node for node in root.iter("node") if node.get("text") == LABEL)
    parent = next(node for node in root.iter("node") if label in list(node))
    parent.set("bounds", action_bounds)
    label.set("bounds", label_bounds)
    return root


def page_tree(*tags):
    root = ET.Element("hierarchy", rotation="0")
    for number, tag in enumerate(tags):
        ET.SubElement(root, "node", {
            "package": smoke.PACKAGE, "resource-id": tag,
            "text": LABEL if tag == "home-practice" else "",
            "bounds": f"[42,{300 + number * 120}][678,{400 + number * 120}]",
            "enabled": "true", "clickable": "true",
        })
    return root


def png():
    def chunk(kind, content):
        return struct.pack(">I", len(content)) + kind + content + struct.pack(">I", zlib.crc32(kind + content))
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(b"\x00\xff\xff\xff")) + chunk(b"IEND", b""))


class Clock:
    def __init__(self):
        self.now = 0.0

    def monotonic(self):
        return self.now

    def sleep(self, seconds):
        self.now += seconds


class Replay(smoke.AndroidSmoke):
    def __init__(self, output, frames=None, enter_game=True, return_home=True, second_rules_entry=True):
        super().__init__("host-only-replay", output)
        self.display_size = (720, 1600)
        self.frames = frames
        self.frame = 0
        self.screen = "home"
        self.enter_game = enter_game
        self.return_home = return_home
        self.second_rules_entry = second_rules_entry
        self.rules_entries = 0
        self.commands = []
        self.actions = []

    def dump_ui(self, deadline=None):
        if self.frames is not None:
            root = ET.fromstring(ET.tostring(self.frames[self.frame]))
        elif self.screen == "rules":
            root = rules_tree()
        else:
            root = page_tree(*{
                "home": ("home-how-to", "home-practice"),
                "game": ("game-table",), "leave": ("leave-confirm",),
            }[self.screen])
        self.bind_ui(root)
        self.write_text("last-ui.xml", ET.tostring(root, encoding="unicode"))
        return root

    def adb(self, *arguments, **kwargs):
        self.commands.append(arguments)
        if arguments[:3] == ("shell", "input", "swipe") and self.frames is not None:
            self.frame = min(self.frame + 1, len(self.frames) - 1)
        if arguments == ("exec-out", "screencap", "-p"):
            return png()
        if arguments == ("shell", "input", "keyevent", "KEYCODE_BACK"):
            self.actions.append(("back", self.screen))
            self.screen = {"rules": "home", "game": "leave"}[self.screen]
        return ""

    def tap_node(self, node, label, height_fraction=0.5):
        super().tap_node(node, label, height_fraction)
        self.actions.append(("tap", label))
        if label == "home-how-to":
            self.rules_entries += 1
            if self.rules_entries == 1 or self.second_rules_entry:
                self.screen = "rules"
        elif label == "rules-practice" and self.enter_game:
            self.screen = "game"
        elif label == "leave-confirm" and self.return_home:
            self.screen = "home"

    def record(self, message):
        self.steps.append(message)


class RulesSmokeTest(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="partydeck-rules-host-test-")
        self.addCleanup(temporary.cleanup)
        self.output = Path(temporary.name)
        clock = Clock()
        self.enterContext(patch.object(smoke.time, "monotonic", clock.monotonic))
        self.enterContext(patch.object(smoke.time, "sleep", clock.sleep))

    def test_retained_clipped_labels_do_not_make_their_buttons_ready(self):
        device = Replay(self.output)
        for bounds, label in (
            ("[42,1481][678,1565]", "[232,1511][488,1516]"),
            ("[42,1462][678,1546]", "[137,1490][584,1516]"),
        ):
            with self.subTest(label=label):
                root = rules_tree(bounds, label)
                self.assertIsNotNone(device.find(root, "rules-practice", LABEL))
                self.assertIsNone(device.find_action(root, "rules-practice", LABEL))

    def test_complete_normal_and_large_text_buttons_are_ready(self):
        device = Replay(self.output)
        for bounds, label in (
            ("[42,1355][678,1453]", "[232,1385][488,1423]"),
            ("[42,1347][678,1470]", "[137,1375][584,1442]"),
        ):
            with self.subTest(label=label):
                action = device.find_action(rules_tree(bounds, label), "rules-practice", LABEL)
                self.assertIsNotNone(action)
                self.assertEqual("true", action.get("clickable"))
                self.assertEqual(bounds, action.get("bounds"))

    def test_disabled_foreign_and_nonclickable_ancestors_are_rejected(self):
        device = Replay(self.output)
        for attribute, value in (("enabled", "false"), ("package", "android"), ("clickable", "false")):
            with self.subTest(attribute=attribute):
                root = rules_tree()
                action = next(node for node in root.iter("node") if node.get("clickable") == "true")
                action.set(attribute, value)
                self.assertIsNone(device.find_action(root, "rules-practice", LABEL))

    def test_capture_scrolls_before_saving_the_complete_button(self):
        device = Replay(self.output, frames=[
            rules_tree("[42,1481][678,1565]", "[232,1511][488,1516]"), rules_tree(),
        ])
        device.capture("rules-action", "rules-practice", LABEL, scroll="down", action=True)
        self.assertEqual("swipe", device.commands[0][2])
        self.assertEqual(("exec-out", "screencap", "-p"), device.commands[-1])
        saved = ET.parse(self.output / "rules-action.xml").getroot()
        self.assertIsNotNone(device.find_action(saved, "rules-practice", LABEL))

    def test_permanently_clipped_button_times_out_without_a_capture(self):
        device = Replay(self.output, frames=[rules_tree("[42,1481][678,1565]", "[232,1511][488,1516]")])
        with self.assertRaisesRegex(RuntimeError, "fully visible enabled action"):
            device.capture("rules-action", "rules-practice", LABEL, scroll="down", action=True)
        self.assertEqual(16, sum(command[:3] == ("shell", "input", "swipe") for command in device.commands))
        self.assertFalse((self.output / "rules-action.png").exists())
        self.assertNotIn(("exec-out", "screencap", "-p"), device.commands)

    def test_rules_cta_enters_game_and_confirms_leave_at_both_scales(self):
        for prefix in ("rules", "large-text-rules"):
            with self.subTest(prefix=prefix):
                device = Replay(self.output)
                device.rules(prefix)
                self.assertEqual([
                    ("tap", "home-how-to"), ("back", "rules"), ("tap", "home-how-to"),
                    ("tap", "rules-practice"), ("back", "game"), ("tap", "leave-confirm"),
                ], device.actions)
                self.assertEqual("home", device.screen)
                self.assertTrue((self.output / f"{prefix}-practice-entered.png").exists())
                self.assertTrue((self.output / f"{prefix}-returned-home.png").exists())

    def test_practice_started_behind_rules_cannot_pass_or_be_rescued_with_back(self):
        device = Replay(self.output, enter_game=False)
        with self.assertRaisesRegex(RuntimeError, "game-table"):
            device.rules()
        self.assertEqual(("tap", "rules-practice"), device.actions[-1])
        self.assertFalse((self.output / "rules-practice-entered.png").exists())
        self.assertFalse((self.output / "rules-returned-home.png").exists())

    def test_noop_second_rules_entry_cannot_substitute_the_home_practice_button(self):
        device = Replay(self.output, second_rules_entry=False)
        with self.assertRaisesRegex(RuntimeError, "rules-first-step"):
            device.rules()
        self.assertEqual(("tap", "home-how-to"), device.actions[-1])
        self.assertFalse((self.output / "rules-practice-action.png").exists())
        self.assertFalse((self.output / "rules-practice-entered.png").exists())

    def test_failed_leave_cannot_claim_a_clean_return(self):
        device = Replay(self.output, return_home=False)
        with self.assertRaisesRegex(RuntimeError, "home-practice"):
            device.rules()
        self.assertEqual(("tap", "leave-confirm"), device.actions[-1])
        self.assertFalse((self.output / "rules-returned-home.png").exists())


if __name__ == "__main__":
    unittest.main()
