"""Host parser regressions using original API 36 help; no native split claim."""

import json
from pathlib import Path
import sys
import unittest

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import adaptive_observations as obs


MOVE = "moveToSideStage <taskId> <SideStagePosition>"
EXIT = "exitSplitScreen <taskId>"
PLAIN_HELP = ("Window Manager Shell commands:\n  splitscreen\n"
              f"    {MOVE}\n    {EXIT}\n  transitions\n  help\n")
FIXTURES = Path(__file__).parent / "fixtures/android-split"


class SplitCapabilityTests(unittest.TestCase):
    def assert_unavailable(self, help_text, multi="true", split="true"):
        with self.assertRaises(obs.Unavailable):
            obs.split_capability(multi, split, help_text)

    def test_both_original_api36_capability_responses_are_supported(self):
        for name in ("0010-split-capability.json", "0019-split-capability.json"):
            with self.subTest(original=name):
                queries = json.loads((FIXTURES / name).read_text())["queries"]
                self.assertTrue(all(query["returncode"] == 0 for query in queries.values()))
                self.assertEqual({"platform_support": True, "automation_route": "wm shell splitscreen"},
                                 obs.split_capability(queries["multiwindow"]["stdout"],
                                                      queries["split_screen"]["stdout"], queries["help"]["stdout"]))

    def test_source_relative_indentation_survives_the_outer_help_prefix(self):
        for prefix in ("", "  "):
            with self.subTest(prefix=repr(prefix)):
                help_text = "\n".join(prefix + line for line in PLAIN_HELP.splitlines()) + "\n"
                self.assertTrue(obs.split_capability("true\n", "true\n", help_text)["platform_support"])

    def test_both_platform_booleans_are_still_required(self):
        for multi, split in (("false", "true"), ("true", "false"), ("false", "false")):
            with self.subTest(multi=multi, split=split):
                self.assert_unavailable(PLAIN_HELP, multi, split)
        for invalid in ("Error true", "true\nfalse", "TRUE", "", "1"):
            with self.subTest(invalid=invalid), self.assertRaises(obs.ObservationFailure):
                obs.split_capability(invalid, "true", PLAIN_HELP)
            with self.subTest(invalid_split=invalid), self.assertRaises(obs.ObservationFailure):
                obs.split_capability("true", invalid, PLAIN_HELP)

    def test_complete_exact_signatures_are_required(self):
        for original, replacement in ((MOVE, ""), (EXIT, ""),
                                      (MOVE, "moveToSideStage <taskId>"),
                                      (MOVE, "moveToSideStage <taskId> <position>"),
                                      (EXIT, "exitSplitScreen <otherId>"),
                                      (EXIT, EXIT + " extra"), (EXIT, "do " + EXIT)):
            with self.subTest(replacement=replacement):
                self.assert_unavailable(PLAIN_HELP.replace(original, replacement))

    def test_sibling_or_parent_sections_cannot_supply_a_missing_command(self):
        for boundary in ("  transitions\n", "Other command help:\n"):
            with self.subTest(boundary=boundary):
                self.assert_unavailable("Window Manager Shell commands:\n  splitscreen\n    "
                                        + MOVE + "\n" + boundary + "    " + EXIT + "\n")
        self.assert_unavailable(PLAIN_HELP.replace("  splitscreen\n", "  split-screen\n"))

    def test_nested_unrelated_split_heading_cannot_advertise_a_route(self):
        nested = ("Window Manager Shell commands:\n  unrelated\n    splitscreen\n"
                  f"      {MOVE}\n      {EXIT}\n")
        for prefix in ("", "  "):
            with self.subTest(prefix=repr(prefix)):
                self.assert_unavailable("\n".join(prefix + line for line in nested.splitlines()) + "\n")

    def test_parent_boundary_excludes_later_split_sections(self):
        outside = ("Window Manager Shell commands:\n  unrelated\nOther command help:\n"
                   f"  splitscreen\n    {MOVE}\n    {EXIT}\n")
        for prefix in ("", "  "):
            with self.subTest(prefix=repr(prefix)):
                self.assert_unavailable("\n".join(prefix + line for line in outside.splitlines()) + "\n")

    def test_one_exact_root_help_heading_is_required(self):
        for text in (PLAIN_HELP.split("\n", 1)[1],
                     PLAIN_HELP.replace("Window Manager Shell commands:", "Other command help:"),
                     PLAIN_HELP + "Window Manager Shell commands:\n",
                     "\t" + PLAIN_HELP,
                     "Other command help:\n" + "\n".join("  " + line for line in PLAIN_HELP.splitlines())):
            with self.subTest(text=text):
                self.assert_unavailable(text)

    def test_split_heading_must_be_a_direct_child_at_two_spaces(self):
        for depth in (1, 3, 4, 6):
            text = ("Window Manager Shell commands:\n" + " " * depth + "splitscreen\n"
                    + " " * (depth + 2) + MOVE + "\n" + " " * (depth + 2) + EXIT + "\n")
            with self.subTest(depth=depth):
                self.assert_unavailable(text)

    def test_nested_descriptions_do_not_advertise_commands(self):
        for text in ("      " + EXIT, "      Use " + EXIT, "    Use " + EXIT,
                     "    \t" + EXIT, "    \u00a0" + EXIT):
            with self.subTest(text=text):
                self.assert_unavailable(PLAIN_HELP.replace("    " + EXIT, text))

    def test_duplicate_headings_are_ambiguous(self):
        self.assert_unavailable(PLAIN_HELP + "  splitscreen\n    " + MOVE + "\n    " + EXIT + "\n")

    def test_missing_or_unrecognized_section_indentation_stays_unavailable(self):
        for text in ("Unknown command", PLAIN_HELP.replace("  splitscreen", "splitscreen"),
                     PLAIN_HELP.replace("  splitscreen", "\tsplitscreen")):
            with self.subTest(text=text):
                self.assert_unavailable(text)

    def test_blank_lines_and_trailing_ascii_space_preserve_the_section(self):
        text = "\n" + PLAIN_HELP.replace("commands:\n", "commands: \t\n\n").replace(
            "  splitscreen\n", "  splitscreen \t\n\n").replace(EXIT + "\n", EXIT + " \t\n")
        self.assertTrue(obs.split_capability("true", "true", text)["platform_support"])


if __name__ == "__main__":
    unittest.main()
