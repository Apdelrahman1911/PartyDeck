"""Host regressions for the Standard UI evidence checker; no Android/AT execution.

Original fixtures are byte-for-byte native XML. Mutations and interaction
replays below are explicitly synthetic negative/flow tests, not device proof.
"""

from contextlib import ExitStack
import copy
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
    "partydeck_standard_accessibility_smoke", Path(__file__).resolve().parents[1] / "smoke-android-godot-session.py",
)
smoke = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = smoke
SPEC.loader.exec_module(smoke)
FIXTURES = Path(__file__).with_name("fixtures") / "android-standard"
UNSELECTED = "session-unselected-34475047307.xml"
SELECTED = "session-selected-34475047307.xml"
ROUND_RESULT = "round-after-play-34456441354.xml"
BASELINE = {"public": {"round": 1, "table_rank": "Star", "turn": "Your turn"},
            "first_card": {"index": 0, "rank": "Crown", "hand_count": 5}}


def original(name):
    return (FIXTURES / name).read_bytes()


def tree(name=UNSELECTED):
    return ET.fromstring(original(name))


def remove(root, node):
    next(parent for parent in root.iter() if node in list(parent)).remove(node)


class OriginalReplay(smoke.GodotSessionSmoke):
    """No adb subprocesses: retain original bytes and replay bounded UI queries."""

    def __init__(self, output, raw=None):
        super().__init__("host-only-standard-replay", output)
        self.display_size = (720, 1600)
        self.raw = raw or original(UNSELECTED)
        self.frames = []
        self.inputs = []
        self.swipes = []
        self.last_input = None

    def record(self, message):
        self.steps.append(message)

    def dump_ui(self, deadline=None):
        if self.frames:
            self.raw = self.frames.pop(0)
        root = ET.fromstring(self.raw)
        self.bind_ui(root)
        self.last_xml_bytes = self.raw
        self.last_xml_time = "2026-09-10T00:00:00.000+00:00"
        return root

    def wait_until(self, description, predicate, seconds=45, scroll=None, *, target_tags=()):
        # Timing/adb acquisition is tested by the existing session/helper suite.
        # Keep a broken UI observation deterministic and fast in these replays.
        for _ in range(8):
            root = self.dump_ui()
            value = predicate(root)
            if value is not None and value is not False:
                return value
            if scroll:
                self.swipe(scroll, root)
        raise smoke.CheckFailure(description)

    def record_input(self, action, label, node, viewport, coordinates):
        super().record_input(action, label, node, viewport, coordinates)
        self.last_input = {"action": action, "label": label, "viewport": viewport, "coordinates": coordinates}

    def adb(self, *arguments, **kwargs):
        if arguments[:3] == ("shell", "input", "tap"):
            self.inputs.append(self.last_input["label"])
            self.on_input(self.last_input["label"])
            return ""
        if arguments[:3] == ("shell", "input", "swipe"):
            self.swipes.append(self.last_input)
            return ""
        raise AssertionError(f"Unexpected native command in host replay: {arguments}")

    def on_input(self, label):
        pass


class HandReplay(OriginalReplay):
    """Synthetic responses using the original parent/child XML shape."""

    def __init__(self, output, defect=None):
        super().__init__(output)
        self.selection = set()
        self.hidden = False
        self.feedback = False
        self.defect = defect

    def dump_ui(self, deadline=None):
        root = tree()
        hand = smoke.tagged_node(root, "game-hand")
        for index in range(5):
            card = smoke.tagged_node(root, f"game-card-{index}")
            if self.hidden and self.defect != "hide-leaks" or self.defect == "missing-fifth" and index == 4:
                remove(root, card)
            else:
                card.set("checked", str(index in self.selection).lower())
        for node in hand.iter("node"):
            if node.get("text") == "0 of 3 selected":
                node.set("text", "5 cards" if self.hidden else f"{len(self.selection)} of 3 selected")
        hide = smoke.tagged_node(root, "game-hide-hand")
        if self.hidden:
            hide.set("resource-id", "game-reveal-hand")
            next(child for child in hide.iter("node") if child.get("text")).set("text", "Reveal hand")
        play = smoke.tagged_node(root, "game-play")
        count = 0 if self.hidden else len(self.selection)
        play.set("enabled", str(count > 0).lower())
        label = "Select cards" if count == 0 else f"Play {count} {'card' if count == 1 else 'cards'}"
        if self.defect == "wrong-play-count" and count == 3:
            label = "Play 4 cards"
        next(child for child in play.iter("node") if child.get("text")).set("text", label)
        if self.feedback and not self.hidden and self.defect != "missing-feedback":
            text = smoke.SELECTION_LIMIT + (" Moon." if self.defect == "rank-feedback" else "")
            ET.SubElement(hand, "node", {"package": smoke.PACKAGE, "text": text, "content-desc": "",
                                       "class": "android.widget.TextView", "bounds": "[35,1096][500,1112]"})
        self.raw = ET.tostring(root)
        return super().dump_ui(deadline)

    def on_input(self, label):
        if label.startswith("game-card-"):
            index = int(label.rsplit("-", 1)[-1])
            if index in self.selection:
                if self.defect != "deselect-ignored":
                    self.selection.remove(index)
                self.feedback = False
            elif len(self.selection) < 3:
                self.selection.add(index)
                self.feedback = False
            else:
                self.feedback = True
                if self.defect == "fourth-accepted":
                    self.selection.add(index)
                if self.defect == "first-replaced":
                    self.selection = {1, 2, 3}
        elif label == "game-hide-hand":
            self.hidden = True
            self.feedback = False
            if self.defect != "reveal-restores-selection":
                self.selection.clear()
        elif label == "game-reveal-hand":
            self.hidden = False
        else:
            raise AssertionError(f"Unexpected synthetic hand action: {label}")


class StandardAccessibilityTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="partydeck-standard-host-test-")
        self.addCleanup(temporary.cleanup)
        self.output = Path(temporary.name)
        self.next_output = 0

    def device(self, kind=OriginalReplay, **kwargs):
        self.next_output += 1
        output = self.output / str(self.next_output)
        output.mkdir()
        return kind(output, **kwargs)

    def test_original_native_fixture_bytes_are_bound_to_provenance(self):
        expected = {
            UNSELECTED: "64a3f5cf467f29ef312b29b641836b9327edf4962f1b4189bffce22febf50f5c",
            SELECTED: "a33e514ccd3200cb635cd5a5d22f5921717b3e554965711ce110dd5eaea9dc2c",
            "large-text-private-hand-34456441354.xml": "9b71644f46f7d2a408cf8bd8c836d1d8c0aeba4c042484975bf3ac63b4b10ba3",
            "large-text-play-action-34456441354.xml": "3eaf036cf9d3802b7abf8441e5d0d9d71fa3c07bb888345227a21a97c1e2d584",
            ROUND_RESULT: "665c4aeea24f59e5ad9e2e55d1b09e5751d6dd7d45a6fbffa770452107dd0eeb",
        }
        manifest = json.loads((FIXTURES / "originals.json").read_text())
        self.assertEqual(expected, {entry["file"]: entry["sha256"] for entry in manifest})
        for name, digest in expected.items():
            with self.subTest(name=name):
                self.assertEqual(digest, hashlib.sha256(original(name)).hexdigest())

    def test_all_five_original_labels_are_on_checkable_parents_with_child_descriptions(self):
        device = self.device()
        root = device.dump_ui()
        expected_ranks = ["Crown", "Moon", "Moon", "Crown", "Star"]
        for index, rank in enumerate(expected_ranks):
            node = device.card_control(root, index)
            self.assertEqual("", node.get("content-desc"))
            self.assertEqual({"index": index, "rank": rank, "hand_count": 5,
                              "checked": False, "checkable": True, "clickable": True},
                             smoke.card_toggle_sample(node, index))
        self.assertEqual(BASELINE["public"], smoke.public_anchor(root, device.visible))

    def test_original_checked_selection_does_not_require_selected_attribute_true(self):
        device = self.device(raw=original(SELECTED))
        card = device.card_control(device.dump_ui(), 0)
        self.assertEqual("false", card.get("selected"))
        self.assertTrue(smoke.card_toggle_sample(card, 0)["checked"])

    def test_missing_or_contradictory_toggle_state_cannot_pass(self):
        for field, value in (("checkable", "false"), ("checked", "unknown"), ("checked", ""),
                             ("selected", "true"), ("enabled", "false"), ("clickable", "false")):
            root = tree()
            card = smoke.tagged_node(root, "game-card-0")
            card.set(field, value)
            with self.subTest(field=field, value=value), self.assertRaises(smoke.CheckFailure):
                smoke.card_toggle_sample(card, 0)

    def test_malformed_ambiguous_or_wrong_index_descriptions_cannot_pass(self):
        for description in ("Moon. Card 2 of 5.", "Moon. Card 1 of 0.", "Joker. Card 1 of 5.",
                            "Moon", "Selected. Moon. Card 1 of 5."):
            card = smoke.tagged_node(tree(), "game-card-0")
            next(child for child in card.iter("node") if child.get("content-desc")).set("content-desc", description)
            with self.subTest(description=description), self.assertRaises(smoke.CheckFailure):
                smoke.card_sample(card, 0)
        card = smoke.tagged_node(tree(), "game-card-0")
        card.append(copy.deepcopy(next(child for child in card if child.get("content-desc"))))
        with self.assertRaises(smoke.CheckFailure):
            smoke.card_sample(card, 0)

    def test_duplicate_or_displaced_card_tags_cannot_identify_an_action(self):
        device = self.device()
        for duplicate in (True, False):
            root = tree()
            card = smoke.tagged_node(root, "game-card-0")
            if not duplicate:
                remove(root, card)
            root.append(copy.deepcopy(card))
            with self.subTest(duplicate=duplicate), self.assertRaises(smoke.CheckFailure):
                device.card_control(root, 0)

    def test_original_large_text_fifth_card_requires_scroll_clearance(self):
        device = self.device()
        clipped = tree("large-text-private-hand-34456441354.xml")
        reached = tree("large-text-play-action-34456441354.xml")
        self.assertIsNone(device.card_control(clipped, 4))
        self.assertIsNotNone(device.card_control(reached, 4))
        self.assertFalse(device.visible(smoke.tagged_node(clipped, "game-card-4")))  # Old dump geometry.

    def test_horizontal_reachability_uses_only_the_scoped_private_rail(self):
        # Synthetic narrow-screen mutation of an original hierarchy.
        root = tree()
        card = smoke.tagged_node(root, "game-card-4")
        rail = next(parent for parent in root.iter() if card in list(parent))
        rail.set("scrollable", "true")
        rail.set("bounds", "[0,1096][600,1314]")
        reached = copy.deepcopy(root)
        for index in range(5):
            for node in smoke.tagged_node(reached, f"game-card-{index}").iter("node"):
                left, top, right, bottom = smoke.ui.node_bounds(node)
                node.set("bounds", f"[{left - 126},{top}][{right - 126},{bottom}]")
        device = self.device()
        device.frames = [ET.tostring(root), ET.tostring(reached)]
        node = device.wait_for_card(4, checked=False)
        self.assertEqual(4, smoke.card_toggle_sample(node, 4)["index"])
        self.assertEqual(1, len(device.swipes))
        swipe = device.swipes[0]
        self.assertEqual("game-hand-end", swipe["label"])
        self.assertEqual((0, 1096, 600, 1314), swipe["viewport"])
        self.assertGreater(swipe["coordinates"]["start"][0], swipe["coordinates"]["end"][0])

    def test_original_bytes_and_timestamps_are_retained_without_reserializing(self):
        device = self.device()
        root = device.dump_ui()
        receipt = device.retain_standard_ui("first", smoke.card_toggle_sample(device.card_control(root, 0), 0))
        self.assertEqual(original(UNSELECTED), (device.output / receipt["file"]).read_bytes())
        self.assertEqual(hashlib.sha256(original(UNSELECTED)).hexdigest(), receipt["sha256"])
        self.assertEqual(device.last_xml_time, receipt["received_utc"])
        self.assertIn("no screenshot, speech or focus", receipt["provenance"])
        with self.assertRaises(smoke.CheckFailure):
            device.retain_standard_ui("first", {})

    def test_full_synthetic_hand_flow_requires_actual_fifth_toggle_rejection_and_hide(self):
        device = self.device(HandReplay)
        result = device.exercise_standard_hand(BASELINE, "hand")
        self.assertEqual(["game-card-4", "game-card-4", "game-card-0", "game-card-1", "game-card-2",
                          "game-card-3", "game-hide-hand", "game-reveal-hand"], device.inputs)
        self.assertEqual(set(), device.selection)
        self.assertEqual([0, 1, 2], result["fourth_choice_preserved_selected_indices"])
        self.assertEqual(list(range(5)), result["reachable_card_indices"])
        self.assertEqual(smoke.SELECTION_LIMIT, result["feedback"]["text"])
        self.assertIn("no TalkBack", result["limit"])
        hidden = ET.parse(device.output / "captures/hand-hidden.xml").getroot()
        smoke.GodotSessionSmoke.assert_no_private_semantics(hidden)

    def test_missing_behavior_fails_even_when_taps_and_other_controls_succeed(self):
        failures = {
            "missing-fifth": "fully reachable card 5", "deselect-ignored": "fully reachable card 5",
            "fourth-accepted": "observed hand selection", "first-replaced": "observed hand selection",
            "missing-feedback": "fourth-choice rejection feedback", "rank-feedback": "exposes a rank",
            "wrong-play-count": "Play label/enabled state", "hide-leaks": "concealed hand still exposes",
            "reveal-restores-selection": "observed hand selection",
        }
        for defect, message in failures.items():
            device = self.device(HandReplay, defect=defect)
            with self.subTest(defect=defect), self.assertRaisesRegex(RuntimeError, message):
                device.exercise_standard_hand(BASELINE, "hand")

    def test_feedback_rejects_private_rank_in_a_separate_non_card_node(self):
        device = self.device(HandReplay)
        device.feedback = True
        root = device.dump_ui()
        hand = smoke.tagged_node(root, "game-hand")
        ET.SubElement(hand, "node", {"package": smoke.PACKAGE, "content-desc": "Selected Moon", "bounds": "[35,900][500,950]"})
        with self.assertRaises(smoke.CheckFailure):
            device.selection_limit_feedback(root)

    def test_unchanged_hand_or_opponent_only_count_changes_are_not_accepted_play(self):
        device = self.device()
        for name in (UNSELECTED, SELECTED):
            root = tree(name)
            for node in root.iter("node"):
                if "Moxie." in node.get("content-desc", ""):
                    node.set("content-desc", node.get("content-desc").replace("5 cards", "4 cards"))
            device.bind_ui(root)
            self.assertIsNone(smoke.standard_action_outcome(root, device.visible, BASELINE))

    def test_visible_recipient_hand_decrease_is_required_and_count_must_be_consistent(self):
        device = self.device()
        root = tree(SELECTED)
        remove(root, smoke.tagged_node(root, "game-card-4"))
        for node in root.iter("node"):
            if smoke.CARD.fullmatch(node.get("content-desc", "")):
                node.set("content-desc", node.get("content-desc").replace("of 5.", "of 4."))
        device.bind_ui(root)
        result = smoke.standard_action_outcome(root, device.visible, BASELINE)
        self.assertEqual((5, 4), (result["before_count"], result["after_count"]))
        label = next(child for child in smoke.tagged_node(root, "game-card-1").iter("node") if child.get("content-desc"))
        label.set("content-desc", "Moon. Card 2 of 5.")
        with self.assertRaises(smoke.CheckFailure):
            smoke.standard_action_outcome(root, device.visible, BASELINE)

    def test_original_public_round_result_is_a_meaningful_post_play_observation(self):
        device = self.device(raw=original(ROUND_RESULT))
        result = smoke.standard_action_outcome(device.dump_ui(), device.visible, BASELINE)
        self.assertEqual({"kind": "same-round public result", "round": 1, "verdict": "Bluff caught.",
                          "challenge": "Orbit challenged Pip.", "claim": "Pip claimed 3 Stars."}, result)

    def test_synthetic_winner_needs_the_same_round_and_a_real_winner_heading(self):
        device = self.device()
        # Source-derived shape/strings for a terminal outcome; no native fixture
        # or TalkBack delivery is claimed for this synthetic branch test.
        root = ET.fromstring(f'''<hierarchy rotation="0"><node package="{smoke.PACKAGE}"
            resource-id="game-table" bounds="[0,346][720,1516]">
          <node package="{smoke.PACKAGE}" resource-id="game-winner" bounds="[0,346][720,1516]">
            <node package="{smoke.PACKAGE}" text="LAST LIGHT STANDING" bounds="[35,390][680,440]"/>
            <node package="{smoke.PACKAGE}" text="Guest wins." bounds="[35,460][680,540]"/>
            <node package="{smoke.PACKAGE}" text="ROUND 1" bounds="[35,560][200,600]"/>
          </node></node></hierarchy>''')
        device.bind_ui(root)
        self.assertEqual("same-round match result", smoke.standard_action_outcome(root, device.visible, BASELINE)["kind"])
        winner = next(node for node in root.iter("node") if node.get("text") == "Guest wins.")
        winner.set("text", "Waiting")
        self.assertIsNone(smoke.standard_action_outcome(root, device.visible, BASELINE))

    def test_result_tag_alone_wrong_round_or_problem_cannot_pass(self):
        for defect in ("tag-only", "wrong-round", "problem"):
            device = self.device()
            root = tree(ROUND_RESULT)
            if defect == "tag-only":
                for node in root.iter("node"):
                    if node.get("text") not in ("ROUND 1", ""):
                        node.set("text", "")
            elif defect == "wrong-round":
                next(node for node in root.iter("node") if node.get("text") == "ROUND 1").set("text", "ROUND 2")
            else:
                ET.SubElement(root, "node", {"package": smoke.PACKAGE, "resource-id": "problem-panel"})
            device.bind_ui(root)
            with self.subTest(defect=defect):
                if defect == "tag-only":
                    self.assertIsNone(smoke.standard_action_outcome(root, device.visible, BASELINE))
                else:
                    with self.assertRaises(smoke.CheckFailure):
                        smoke.standard_action_outcome(root, device.visible, BASELINE)

    def test_play_flow_preserves_original_result_bytes_and_rejects_tap_without_outcome(self):
        for changes in (True, False):
            device = self.device(raw=original(SELECTED))
            device.on_input = lambda label: setattr(device, "raw", original(ROUND_RESULT) if changes else original(SELECTED))
            with patch.object(device, "wait_activity"), patch.object(device, "select_first_card"), \
                    patch.object(device, "capture_evidence"), self.subTest(changes=changes):
                if not changes:
                    with self.assertRaises(smoke.CheckFailure):
                        device.play_standard_card(BASELINE, "play")
                    continue
                result = device.play_standard_card(BASELINE, "play")
                self.assertEqual(["game-play"], device.inputs)
                receipt = result["outcome_xml"]
                self.assertEqual(original(ROUND_RESULT), (device.output / receipt["file"]).read_bytes())
                self.assertIn("no authority receipt/revision", result["limit"])

    def test_intentional_standard_action_follows_every_no_action_continuity_check(self):
        device = self.device()
        trace = []
        control = ET.Element("node")
        device.last_xml_bytes = b"<hierarchy/>"
        methods = {
            "tap_action": lambda *args, **kwargs: trace.append(("tap", args[0])),
            "wait_for_human_turn": lambda: None,
            "assert_concealed": lambda: None,
            "observe_match": lambda prefix: BASELINE,
            "exercise_standard_hand": lambda *args: {},
            "select_first_card": lambda prefix: trace.append(("select", prefix)),
            "enter_native": lambda mode, prefix, ready=True: (602, 19, {"status": smoke.READY, "leave": control}),
            "interrupt_native": lambda *args, **kwargs: None,
            "require_concealed_return": lambda baseline, prefix: trace.append(("continuity", prefix)) or baseline,
            "leave_dialog": lambda *args: None,
            "play_standard_card": lambda *args: trace.append(("authority-play", args[1])) or {},
            "tap_node": lambda *args: None,
            "wait_for_action": lambda *args, **kwargs: None,
            "wait_activity": lambda *args, **kwargs: None,
            "dump_ui": lambda: ET.fromstring("<hierarchy/>"),
            "capture_evidence": lambda *args, **kwargs: None,
        }
        with ExitStack() as stack:
            for name, implementation in methods.items():
                stack.enter_context(patch.object(device, name, side_effect=implementation))
            device.run_mode("2d", skip_renderer_death=True)
        action = next(index for index, entry in enumerate(trace) if entry[0] == "authority-play")
        self.assertTrue(all(index < action for index, entry in enumerate(trace) if entry[0] == "continuity"))
        self.assertIn(("continuity", "2d-action-return"), trace)
        self.assertNotIn(("select", "2d-leave-end"), trace)
        self.assertEqual("passed", device.checks["2d.standard-action"]["status"])
        self.assertEqual("passed", device.checks["2d.leave-end"]["status"])


if __name__ == "__main__":
    unittest.main()
