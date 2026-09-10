"""Read-only concealment regressions using synthetic geometry, not native proof."""

import copy
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import adaptive_observations as obs
import smoke_android_godot_adaptive as runner


PACKAGE = "dev.partydeck.app"
MAIN = PACKAGE + "/" + PACKAGE + ".MainActivity"
NATIVE = PACKAGE + "/" + PACKAGE + ".godot.SessionGodotActivity"


class ConcealedObservationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.session = runner.load_session(Path(__file__).resolve().parents[1] / "smoke-android-godot-session.py")

    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="partydeck-concealed-observation-host-test-")
        self.addCleanup(temporary.cleanup)
        session = self.session

        class HostOnly(runner.AdaptiveScenarios, session.GodotSessionSmoke):
            def adb(self, *args, **kwargs):
                raise AssertionError("Read-only observation must not issue device commands")

            def command(self, *args, **kwargs):
                raise AssertionError("Read-only observation must not issue device commands")

        self.smoke = HostOnly(session, "host-only", Path(temporary.name), "debug", "2.0", 30000)
        self.smoke.shell_task = 8
        self.smoke.display_size = (720, 1600)
        self.state = dict(foreground=dict(component=MAIN, task_id=8), renderer_pids=[],
                          activities=[dict(component=MAIN, lifecycle_state="RESUMED", app_pid=2987)])

    def tree(self, bounds="[63,1472][657,1556]", viewport="[0,358][720,1516]",
             package=PACKAGE, tag="game-reveal-hand", enabled="true", rotation="0"):
        # Matches the clipped geometry in the debug 2x final diagnostic, with
        # synthetic public content. This fixture is not a before-UP capture.
        root = self.session.ET.Element("hierarchy", rotation=rotation)
        scroll = self.session.ET.SubElement(root, "node", {
            "package": PACKAGE, "resource-id": "game-table", "scrollable": "true",
            "class": "android.widget.ScrollView", "bounds": viewport,
        })
        hand = self.session.ET.SubElement(scroll, "node", {
            "package": PACKAGE, "resource-id": "game-hand", "bounds": "[0,1069][720,1516]",
        })
        self.session.ET.SubElement(hand, "node", {
            "package": package, "resource-id": tag, "bounds": bounds,
            "enabled": enabled, "clickable": "true", "text": "Show hand",
        })
        return root

    def test_clipped_concealed_marker_is_observable_without_becoming_an_action(self):
        root = self.tree()
        self.assertTrue(self.smoke.concealed_readonly(self.state, root))
        marker = self.session.tagged_node(root, "game-reveal-hand")
        self.assertEqual((63, 1472, 657, 1516), self.session.ui.intersect_bounds(
            self.session.ui.node_bounds(marker), self.smoke.viewport(marker)))
        self.assertFalse(self.smoke.visible(marker))
        self.assertIsNone(self.smoke.find(root, "game-reveal-hand"))
        self.assertIsNone(self.smoke.find_action(root, "game-reveal-hand"))
        self.assertIsNone(self.smoke.find_action(root, "game-reveal-hand", "Show hand"))

    def test_complete_visible_marker_keeps_existing_action_behavior(self):
        root = self.tree(bounds="[63,1400][657,1484]")
        self.assertTrue(self.smoke.concealed_readonly(self.state, root))
        marker = self.session.tagged_node(root, "game-reveal-hand")
        self.assertIs(marker, self.smoke.find(root, "game-reveal-hand"))
        self.assertIs(marker, self.smoke.find_action(root, "game-reveal-hand"))

    def test_edge_contact_and_seven_pixels_still_fail_eight_pixel_action_clearance(self):
        self.assertEqual(8, self.session.ui.ACTION_VIEWPORT_CLEARANCE_PX)
        for gap in (0, 1, 7, 8):
            with self.subTest(gap=gap):
                root = self.tree(bounds=f"[63,{1432 - gap}][657,{1516 - gap}]")
                self.assertTrue(self.smoke.concealed_readonly(self.state, root))
                self.assertIsNotNone(self.smoke.find(root, "game-reveal-hand"))
                self.assertEqual(gap >= 8, self.smoke.find_action(root, "game-reveal-hand") is not None)

    def test_offscreen_edge_only_zero_area_and_invalid_bounds_are_rejected(self):
        for bounds in ("[63,1516][657,1600]", "[63,1601][657,1685]", "[63,200][657,358]",
                       "[720,1472][804,1556]", "[-100,1472][0,1556]", "[63,1472][63,1556]",
                       "[63,1472][657,1472]", "[657,1472][63,1556]", "[63,1556][657,1472]",
                       "", "not-a-rectangle"):
            with self.subTest(bounds=bounds):
                self.assertFalse(self.smoke.concealed_readonly(self.state, self.tree(bounds=bounds)))

    def test_display_bounds_intersect_scroll_bounds(self):
        root = self.tree(bounds="[63,1600][657,1684]", viewport="[0,358][720,1800]")
        self.assertFalse(self.smoke.concealed_readonly(self.state, root))
        root = self.tree(bounds="[63,1576][657,1660]", viewport="[0,358][720,1800]")
        self.assertTrue(self.smoke.concealed_readonly(self.state, root))
        marker = self.session.tagged_node(root, "game-reveal-hand")
        self.assertEqual((0, 358, 720, 1600), self.smoke.viewport(marker))
        self.assertIsNone(self.smoke.find_action(root, "game-reveal-hand"))

    def test_invalid_or_disjoint_scroll_viewports_are_rejected(self):
        for viewport in ("", "[0,358][720,358]", "[0,1700][720,1800]", "[0,358][720,1450]"):
            with self.subTest(viewport=viewport):
                self.assertFalse(self.smoke.concealed_readonly(self.state, self.tree(viewport=viewport)))

    def test_each_nested_scroll_viewport_constrains_the_marker(self):
        for bottom, expected in ((1450, False), (1500, True)):
            with self.subTest(bottom=bottom):
                root = self.tree()
                hand = self.session.tagged_node(root, "game-hand")
                hand.set("class", "androidx.core.widget.NestedScrollView")
                hand.set("bounds", f"[0,1069][720,{bottom}]")
                self.assertEqual(expected, self.smoke.concealed_readonly(self.state, root))

    def test_current_tree_replaces_old_geometry_and_old_node_becomes_unusable(self):
        old = self.tree()
        self.assertTrue(self.smoke.concealed_readonly(self.state, old))
        old_marker = self.session.tagged_node(old, "game-reveal-hand")
        sequence = self.smoke.ui_sequence
        current = self.tree(viewport="[0,358][720,1450]")
        self.assertFalse(self.smoke.concealed_readonly(self.state, current))
        self.assertIs(self.smoke.ui_root, current)
        self.assertEqual(sequence + 1, self.smoke.ui_sequence)
        self.assertIsNone(self.smoke.viewport(old_marker))
        self.assertFalse(self.smoke.concealed_readonly(self.state, self.session.ET.fromstring("<hierarchy />")))

    def test_new_dump_rotation_refreshes_current_display_geometry(self):
        self.assertTrue(self.smoke.concealed_readonly(self.state, self.tree(rotation="0")))
        self.assertFalse(self.smoke.concealed_readonly(self.state, self.tree(rotation="1")))
        self.assertEqual(1, self.smoke.rotation)

    def test_only_exact_app_owned_tag_can_identify_concealment(self):
        for package, tag in (("other.app", "game-reveal-hand"), ("", "game-reveal-hand"),
                             (PACKAGE, "other-game-reveal-hand"), (PACKAGE, "game-reveal-hand-extra"),
                             (PACKAGE, "other-tag")):
            with self.subTest(package=package, tag=tag):
                self.assertFalse(self.smoke.concealed_readonly(self.state, self.tree(package=package, tag=tag)))
        self.assertTrue(self.smoke.concealed_readonly(self.state, self.tree(tag=PACKAGE + ":id/game-reveal-hand")))

    def test_disabled_marker_cannot_prove_concealed_return(self):
        self.assertFalse(self.smoke.concealed_readonly(self.state, self.tree(enabled="false")))

    def test_duplicate_app_marker_is_rejected_even_when_one_copy_is_offscreen(self):
        root = self.tree()
        duplicate = copy.deepcopy(self.session.tagged_node(root, "game-reveal-hand"))
        duplicate.set("bounds", "[0,1700][100,1800]")
        root.append(duplicate)
        with self.assertRaisesRegex(self.session.CheckFailure, "Duplicate app-owned game-reveal-hand"):
            self.smoke.concealed_readonly(self.state, root)

    def test_private_semantics_are_rejected_across_the_whole_tree(self):
        private_values = [{"resource-id": "game-card-0"}, {"resource-id": "other:id/game-card-4"}]
        private_values += [{"content-desc": f"{rank}. Card 1 of 5."} for rank in ("Crown", "Moon", "Star", "Wild")]
        for values in private_values:
            for package in (PACKAGE, "other.app"):
                with self.subTest(values=values, package=package):
                    root = self.tree()
                    self.session.ET.SubElement(root, "node", dict(
                        values, package=package, enabled="false", bounds="[0,1700][100,1800]"))
                    with self.assertRaisesRegex(self.session.CheckFailure, "Private hand semantics"):
                        self.smoke.concealed_readonly(self.state, root)

    def test_clipped_marker_does_not_bypass_native_foreground_or_task_guards(self):
        root = self.tree()
        for changed in (dict(renderer_pids=[4266]), dict(foreground=None),
                        dict(foreground=dict(component=NATIVE, task_id=8)),
                        dict(activities=[dict(component=NATIVE, lifecycle_state="DESTROYED", visible=False)])):
            with self.subTest(changed=changed):
                self.assertFalse(self.smoke.concealed_readonly(self.state | changed, root))
        with self.assertRaisesRegex(obs.ObservationFailure, "retained shell task"):
            self.smoke.concealed_readonly(self.state | dict(foreground=dict(component=MAIN, task_id=9)), root)

    def test_clipped_marker_does_not_hide_a_stale_leave_dialog(self):
        root = self.tree()
        self.session.ET.SubElement(root, "node", {
            "package": PACKAGE, "text": "Leave the table?", "bounds": "[10,10][500,100]",
        })
        with self.assertRaisesRegex(obs.ObservationFailure, "stale Leave dialog"):
            self.smoke.concealed_readonly(self.state, root)

    def test_observation_never_requests_a_new_dump_or_any_ui_action(self):
        blocked = AssertionError("Concealment observation must use only the supplied current tree")
        with patch.object(self.smoke, "dump_ui", side_effect=blocked), \
                patch.object(self.smoke, "tap_action", side_effect=blocked), \
                patch.object(self.smoke, "swipe", side_effect=blocked), \
                patch.object(self.smoke, "wait_until", side_effect=blocked), \
                patch.object(self.smoke, "find_action", side_effect=blocked):
            self.assertTrue(self.smoke.concealed_readonly(self.state, self.tree()))


if __name__ == "__main__":
    unittest.main()
