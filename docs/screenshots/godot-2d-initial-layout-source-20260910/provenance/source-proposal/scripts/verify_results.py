#!/usr/bin/env python3
"""Check full containment, source/native agreement and unchanged comparison layouts."""
from pathlib import Path
import hashlib
import json

WORK = Path(__file__).resolve().parent.parent
RESULTS = WORK / "results"


def load(name):
    return json.loads((RESULTS / name).read_text())


def final(case):
    return case["frames"][-1]["measurement"]


def control(measurement, group="partydeck_action_reveal"):
    return next(c for c in measurement["diagnostics"]["controls"] if c["group"] == group)


def contains(outer, inner):
    return (inner[0] >= outer[0] and inner[1] >= outer[1]
            and inner[0] + inner[2] <= outer[0] + outer[2]
            and inner[1] + inner[3] <= outer[1] + outer[3])


baseline = {r["case"]["name"]: r for r in load("baseline-layout.json")["cases"]}
candidate = {r["case"]["name"]: r for r in load("candidate-v2-layout.json")["cases"]}
wrapped = load("candidate-v2-wrap-layout.json")["cases"]
checks = []
summaries = []

for name, native_clip in [("378x655-normal", [16, 118, 346, 391]),
                          ("378x691-normal", [16, 118, 346, 427])]:
    reveal = control(final(baseline[name]))
    assert reveal["rect"] == [32, 514, 306, 56], (name, reveal)
    assert reveal["clipRect"] == native_clip, (name, reveal)
    checks.append(f"Archived source reproduces native initial Reveal and clip exactly: {name}")

for name, row in candidate.items():
    settings = row["case"]
    measured = final(row)
    diagnostic = measured["diagnostics"]
    reveal = control(measured)
    assert diagnostic["handConcealed"] and diagnostic["sceneStateApplied"], name
    assert diagnostic["privateFaceCount"] == diagnostic["privateLabelCount"] == diagnostic["selectedCount"] == 0, name
    assert measured["components"]["_body_scroll"]["scrollVertical"] == 0, name
    if settings["textScale"] == 1:
        assert contains(reveal["clipRect"], reveal["rect"]), (name, reveal)
        assert reveal["rect"][3] >= 56, (name, reveal)
    compact = settings["width"] < 860 and 500 <= settings["height"] < 800 and settings["textScale"] < 1.5
    if not compact:
        base_measurement = final(baseline[name])
        assert diagnostic["controls"] == base_measurement["diagnostics"]["controls"], name
        assert measured["components"]["_body_scroll"] == base_measurement["components"]["_body_scroll"], name
    for frame in row["frames"]:
        if frame["frame"] >= 2:
            assert frame["measurement"]["diagnostics"]["controls"] == diagnostic["controls"], (name, frame["frame"])
    base_reveal = control(final(baseline[name]))
    summaries.append({"case": name, "baselineReveal": base_reveal["rect"], "candidateReveal": reveal["rect"],
                      "clipRect": reveal["clipRect"], "fullyContained": contains(reveal["clipRect"], reveal["rect"]),
                      "candidateBottomMargin": reveal["clipRect"][1] + reveal["clipRect"][3] - reveal["rect"][1] - reveal["rect"][3],
                      "initialScroll": measured["components"]["_body_scroll"]["scrollVertical"]})

checks.extend(["All nine normal-text initial controls fully contained, with at least 56 units of height and no automatic scroll",
               "All four 200% control geometry and scroll measurements unchanged from baseline",
               "Tall portrait, short landscape, 900-wide and desktop comparison control geometry unchanged",
               "All initial concealed cases have zero private faces, labels and selection",
               "Initial control measurements stable from observed frame 2 through frame 12"])

for row in wrapped:
    measured = final(row)
    reveal = control(measured)
    assert contains(reveal["clipRect"], reveal["rect"]), row["case"]
    body = measured["components"]["_body_scroll"]["rect"]
    for key in ["_rank", "_claim"]:
        assert measured["components"][key]["visible"], (row["case"], key)
        assert contains(body, measured["components"][key]["rect"]), (row["case"], key)
    viewport = measured["diagnostics"]["viewport"]
    assert contains([0, 0, viewport["width"], viewport["height"]], measured["components"]["_turn"]["rect"]), row["case"]
    summaries.append({"case": row["case"]["name"], "candidateReveal": reveal["rect"], "clipRect": reveal["clipRect"],
                      "fullyContained": True, "candidateBottomMargin": reveal["clipRect"][1] + reveal["clipRect"][3] - reveal["rect"][1] - reveal["rect"][3]})
checks.append("Nine valid 24-character duplicate-name/opponent/latest-claim cases retain full Reveal and public context, including combined 320×568 case")

input_reports = []
for width, height, scale in [(378, 655, 1), (320, 568, 1), (320, 568, 2)]:
    directory = RESULTS / f"source-input-{width}x{height}-text-{scale}"
    report = json.loads((directory / "report.json").read_text())
    execution = json.loads((directory / "execution.json").read_text())
    assert report["result"] == "passed" and execution["exitCode"] == 0
    assert execution["inputs"][-1]["sha256"] == hashlib.sha256((WORK / "candidate/presentations/two_d/table.gd").read_bytes()).hexdigest()
    inputs = [o for o in report["observations"] if "input" in o]
    page = next(o for o in inputs if o["input"] == "emulated-touch-page-drag")
    hand = next(o for o in inputs if o["input"] == "emulated-touch-hand-drag")
    tiny = next(o for o in inputs if o["input"] == "emulated-touch-small-tap")
    assert page["after"] > page["before"] and not page["handVisible"] and page["eventCount"] == 1
    assert hand["after"] > hand["before"] and hand["selectedCount"] == 0
    assert tiny["after"] == tiny["before"] and tiny["selectedCount"] == 1
    for label in ["01-concealed", "03-covered-again", "04-resumed-covered"]:
        diagnostic = json.loads((directory / f"{label}.json").read_text())
        assert diagnostic["privateFaceCount"] == diagnostic["privateLabelCount"] == diagnostic["selectedCount"] == 0
    first = json.loads((directory / "01-concealed.json").read_text())
    reveal = next(c for c in first["controls"] if c["group"] == "partydeck_action_reveal")
    if scale == 1:
        assert contains(reveal["clipRect"], reveal["rect"])
        assert page["before"] == 0
    else:
        assert page["before"] > 0
    input_reports.append({"path": str(directory / "report.json"), "result": report["result"],
                          "initialRevealFullyContained": contains(reveal["clipRect"], reveal["rect"]),
                          "pageScrollBeforeDrag": page["before"], "pageScrollAfterDrag": page["after"]})
checks.append("Three archived source OpenGL checks passed actual reveal/select/cover inputs, emulated page/hand drag, tiny-motion tap and concealment after foreground loss/close")

report = {"result": "passed", "checks": checks, "geometryCases": summaries, "inputReports": input_reports,
          "limits": ["Headless/source fixture and Linux OpenGL evidence only; no new candidate PCK or native acceptance.",
                     "Normal text cases establish tested viewports/content, not every possible name/glyph or native accessibility.",
                     "The unchanged 320×568 200% initial Reveal requires scrolling; the source input check executes that scrolling."]}
(RESULTS / "validation-summary.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
print(json.dumps({"result": report["result"], "checks": len(checks), "candidateGeometryCases": len(summaries), "sourceInputChecks": len(input_reports)}))
