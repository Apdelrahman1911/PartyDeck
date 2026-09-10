"""Host-only scenario regressions for concealment during fallback rotation."""

import copy
from contextlib import contextmanager
from pathlib import Path
import sys
import unittest
import xml.etree.ElementTree as ET

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import smoke_android_godot_adaptive as runner

session = runner.load_session(Path(__file__).resolve().parents[1] / "smoke-android-godot-session.py")


class PortraitScenarioReplay(session.GodotSessionSmoke):
    """Synthetic Activity transitions with the real conceal/card/continuity helpers.

    Every synthetic control fits in its viewport. Waits evaluate the current
    synthetic state once; no device, timing or gesture success is claimed.
    """

    def __init__(self, recorder_available=False, private_leak=False, public_drift=False,
                 unavailable_after_rotation=False):
        self.session = session
        self.recorder_available = recorder_available
        self.private_leak = private_leak
        self.public_drift = public_drift
        self.unavailable_after_rotation = unavailable_after_rotation
        self.display_size = (720, 1600)
        self.ui_root, self.ui_parents, self.ui_sequence = None, {}, 0
        self.rotation = self.actual_rotation = 0
        self.component = session.MAIN_COMPONENT
        self.renderer_pid = None
        self.hand_shown = self.card_selected = self.leaking = False
        self.checks, self.captures, self.launches = {}, [], []
        self.finished = False
        self.stage = "synthetic"
        self.public = {"round": 1, "table_rank": "Crown", "turn": "Your turn"}
        self.baseline = {"public": copy.deepcopy(self.public),
                         "first_card": {"index": 0, "rank": "Crown", "hand_count": 5}}

    @contextmanager
    def check(self, name):
        self.stage = name
        entry = self.checks[name] = {"status": "running"}
        try:
            yield entry
        except runner.Unavailable as error:
            entry.update(status="unsupported", reason=str(error))
        except Exception:
            entry["status"] = "failed"
            raise
        else:
            entry["status"] = "passed"

    def state(self):
        return {"foreground": {"component": self.component},
                "display": {"landscape": 1, "seascape": 3, "portrait": 0,
                            "rotation": self.actual_rotation}}

    def wait_activity(self, component, child_absent=False):
        if self.component != component or (child_absent and self.renderer_pid is not None):
            raise RuntimeError("Synthetic Activity/process return is incomplete")
        return self.state()

    def stable_activity(self, target, orientation, rotation, mode):
        if self.component != target or self.actual_rotation != rotation:
            raise RuntimeError("Synthetic Activity configuration is wrong")
        return self.state()

    def set_rotation(self, rotation, target, orientation):
        self.wait_activity(target)
        if rotation == self.actual_rotation:
            return self.state()
        self.actual_rotation = rotation
        self.hand_shown = self.card_selected = False
        if rotation == 0:
            self.leaking = self.private_leak
            if self.public_drift:
                self.public["round"] += 1
        return self.state()

    def begin_practice(self, prefix):
        self.hand_shown = self.card_selected = True
        return copy.deepcopy(self.baseline)

    def enter_native(self, mode, prefix):
        if not self.hand_shown or not self.card_selected:
            raise RuntimeError("Native re-entry requires a fresh visible card selection")
        self.component = session.NATIVE_COMPONENT
        self.renderer_pid = 600 + len(self.launches)
        self.launches.append((mode, self.actual_rotation, self.renderer_pid))
        self.hand_shown = self.card_selected = False
        return self.renderer_pid, 8, None

    def rotate_while_held(self, pid, native, rotation, prefix):
        if not self.recorder_available and not self.unavailable_after_rotation:
            raise runner.Unavailable("Synthetic recorder startup unavailable")
        self.component, self.renderer_pid = session.MAIN_COMPONENT, None
        self.set_rotation(rotation, session.MAIN_COMPONENT, "port")
        if self.unavailable_after_rotation:
            raise runner.Unavailable("Synthetic input clock unavailable after rotation")
        return {"scope": "Synthetic held-rotation branch only"}

    def dump_ui(self, deadline=None):
        width, height = self.display_size
        if self.actual_rotation % 2:
            width, height = height, width
        root = ET.Element("hierarchy", rotation=str(self.actual_rotation))
        frame = ET.SubElement(root, "node", {
            "package": session.PACKAGE, "class": "android.widget.FrameLayout",
            "bounds": f"[0,0][{width},{height}]", "enabled": "true"})
        hand = ET.SubElement(frame, "node", {
            "package": session.PACKAGE, "class": "android.view.View",
            "resource-id": "game-hand", "bounds": f"[20,300][{width - 20},520]",
            "enabled": "true"})

        def control(parent, tag, top, bottom, enabled=True, checked=None):
            attrs = {"package": session.PACKAGE, "class": "android.view.View",
                     "resource-id": tag, "bounds": f"[40,{top}][{width - 40},{bottom}]",
                     "clickable": "true", "enabled": str(enabled).lower()}
            if checked is not None:
                attrs.update(checkable="true", checked=str(checked).lower(),
                             selected=str(checked).lower())
            return ET.SubElement(parent, "node", attrs)

        if not self.hand_shown:
            control(hand, "game-reveal-hand", 350, 430)
        if self.hand_shown or self.leaking:
            card = control(hand, "game-card-0", 350, 430, checked=self.card_selected)
            ET.SubElement(card, "node", {
                "package": session.PACKAGE, "class": "android.view.View",
                "bounds": "[50,365][250,405]", "content-desc": "Crown. Card 1 of 5."})
        control(frame, "game-play", height - 170, height - 70,
                enabled=self.hand_shown and self.card_selected)
        self.bind_ui(root)
        return root

    def wait_until(self, description, predicate, seconds=45, scroll=None):
        value = predicate(self.dump_ui())
        if value is None or value is False:
            raise RuntimeError(description)
        return value

    def swipe(self, direction, root, timeout=10, target_tags=()):
        # Scrolling cannot turn a concealed synthetic hand into revealed cards.
        pass

    def tap_action(self, tag, text=None, scroll="down"):
        if tag == "native-standard-table":
            self.component, self.renderer_pid = session.MAIN_COMPONENT, None
            self.hand_shown = self.card_selected = False
            return
        self.tap_node(self.wait_for_action(tag, text, scroll), tag)

    def tap_node(self, node, label, height_fraction=0.5):
        if not self.visible(node):
            raise RuntimeError("Synthetic action is not fully visible")
        if label == "game-reveal-hand":
            self.hand_shown = True
        elif label == "game-card-0":
            self.card_selected = not self.card_selected
        else:
            raise AssertionError(f"Unexpected synthetic action: {label}")

    def capture_evidence(self, name, component, ui_assertion=None):
        self.wait_activity(component)
        root = self.dump_ui()
        if ui_assertion is not None:
            ui_assertion(root)
        self.captures.append(name)
        return {"status": "captured", "scope": "Synthetic host fixture"}

    def observe_match(self, prefix):
        self.tap_action("game-reveal-hand")
        card = self.wait_for_card(0, checked=False)
        return {"public": copy.deepcopy(self.public), "first_card": session.first_card_sample(card)}

    def finish_practice(self, mode, baseline, prefix):
        self.finished = True


class PortraitReentryTests(unittest.TestCase):
    def test_unavailable_recorder_reenters_after_shell_rotation_conceals(self):
        for mode in ("2d", "3d"):
            for direction, rotation in (("landscape", 1), ("seascape", 3)):
                with self.subTest(mode=mode, direction=direction):
                    replay = PortraitScenarioReplay()
                    runner.AdaptiveScenarios.landscape_scenario(replay, mode, direction)
                    self.assertTrue(replay.finished)
                    self.assertEqual([(mode, rotation, 600), (mode, 0, 601)], replay.launches)
                    self.assertEqual("unsupported", replay.checks[f"{mode}-{direction}.held-rotation"]["status"])
                    self.assertEqual("passed", replay.checks[f"{mode}-{direction}.portrait-reentry-standard"]["status"])

    def test_supported_rotation_keeps_its_existing_revealed_return_path(self):
        replay = PortraitScenarioReplay(recorder_available=True)
        runner.AdaptiveScenarios.landscape_scenario(replay, "2d", "landscape")
        self.assertTrue(replay.finished)
        self.assertEqual(2, len(replay.launches))
        self.assertEqual("passed", replay.checks["2d-landscape.held-rotation"]["status"])

    def test_late_unavailability_preserves_the_already_portrait_revealed_hand(self):
        replay = PortraitScenarioReplay(unavailable_after_rotation=True)
        runner.AdaptiveScenarios.landscape_scenario(replay, "2d", "landscape")
        self.assertTrue(replay.finished)
        self.assertEqual([("2d", 1, 600), ("2d", 0, 601)], replay.launches)
        self.assertEqual("unsupported", replay.checks["2d-landscape.held-rotation"]["status"])

    def test_portrait_private_semantics_are_rejected_before_reentry(self):
        replay = PortraitScenarioReplay(private_leak=True)
        with self.assertRaisesRegex(RuntimeError, "concealed hand still exposes private card semantics"):
            runner.AdaptiveScenarios.landscape_scenario(replay, "2d", "landscape")
        self.assertEqual(1, len(replay.launches))
        self.assertFalse(replay.finished)

    def test_portrait_public_state_drift_is_rejected_before_reentry(self):
        replay = PortraitScenarioReplay(public_drift=True)
        with self.assertRaisesRegex(session.CheckFailure, "Public match state changed"):
            runner.AdaptiveScenarios.landscape_scenario(replay, "2d", "landscape")
        self.assertEqual(1, len(replay.launches))
        self.assertFalse(replay.finished)


if __name__ == "__main__":
    unittest.main()
