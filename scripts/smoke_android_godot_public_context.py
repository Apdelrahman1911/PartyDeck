#!/usr/bin/env python3
"""Collect one real 3D/font-2.0 short-pane context sweep per admitted APK.

Automated geometry/input assertions and public-text pixel acceptance are separate.
This runner uses real practice UI and never supplies a game view or gameplay hook.
"""

import argparse
import hashlib
import math
from pathlib import Path
import re
import sys
import time

import android_godot_adaptive_inputs as bound_inputs
import android_godot_session_observation as engine
import smoke_android_godot_adaptive as adaptive


MAX_SWIPES = 40
SWEEP_SECONDS = 720
MAX_STAGING_PLAYS = 4
STAGING_SECONDS = 600
RUNNER_PATH = "scripts/smoke_android_godot_public_context.py"
REQUIRED_CHECKS = ("installation", "3d.context-real-claim", "3d.context-short-split",
                   "3d.context-body-sweep", "3d.context-standard-return-end")
CLAIM = re.compile(r"(.+) claims ([1-3]) (Crown|Moon|Star)(s?)\.")
EXPECTED_VIEWPORT = (681 / 1.75, 377 / 1.75)
VIEWPORT_TOLERANCE = 2.0
TURN_EXHAUSTION = {
    "Practice ended before the human play could be exercised.",
    "Practice did not offer a human play within eight rounds.",
    "Practice did not offer a human play within 120 seconds.",
}
require = engine.require


def admit_inputs(args):
    """Rebind the existing same-run verifier's exact manifest, APK and activation."""
    current = bound_inputs.context()
    require(args.source_revision == current["sourceRevision"], "Focused source differs from this workflow.")
    require(bound_inputs.PINS.get(RUNNER_PATH) == adaptive.sha256(Path(__file__)),
            "The focused runner is not registered in the producer checker pins.")
    for relative, expected in bound_inputs.PINS.items():
        require(adaptive.sha256(bound_inputs.ROOT / relative) == expected,
                "An executed helper differs from its registered checker pin: " + relative)
    raw = (args.bundle / "inputs.json").read_bytes()
    require(len(raw) <= 65536, "Oversized producer manifest.")
    manifest = bound_inputs.verify_manifest(raw, args.manifest_sha256, args.bundle, current)
    require(args.package_inputs.name == "package-inputs.json" and args.package_inputs.is_file()
            and not args.package_inputs.is_symlink(), "The original verified package-input report is required.")
    report_raw = args.package_inputs.read_bytes()
    require(len(report_raw) <= 262144, "Oversized package-input report.")
    report = engine.strict_json(report_raw)
    require(type(report) is dict and report.get("command") == "verify" and report.get("verified") is True
            and report.get("consumerContext") == current and report.get("inputs") == manifest
            and report.get("producerManifestSha256") == args.manifest_sha256,
            "Focused input report is not the verified manifest from this consumer.")
    name = "androidApp-debug.apk" if args.variant == "debug" else "PartyDeck-release-ci-test-signed.apk"
    require(args.apk.resolve() == (args.bundle / name).resolve(), "Focused APK is outside its admitted variant input.")
    item = report.get("packages", {}).get(args.variant, {})
    require(item.get("verified") is True and item.get("apkSha256") == adaptive.sha256(args.apk)
            and item.get("packSha256") == item.get("embeddedPackSha256")
            == manifest["files"]["partydeck-last-light.pck"]["sha256"]
            and type(item.get("manifestExitCode")) is int and item["manifestExitCode"] == 0,
            "Focused APK/PCK/manifest did not pass the existing package verifier.")
    import android_godot_activation as activation
    expected_raw = (args.package_inputs.parent / "activation-build-expectation.json").read_bytes()
    packaged_raw = (args.package_inputs.parent / (args.variant + "-packaged-manifest.xml")).read_bytes()
    require(hashlib.sha256(expected_raw).hexdigest() == manifest["files"]["godot-activation-build.json"]["sha256"],
            "The build activation bytes differ from the admitted producer input.")
    require(hashlib.sha256(packaged_raw).hexdigest() == item.get("manifestSha256"),
            "The verified packaged manifest bytes changed.")
    expected = activation.parse_build_expectation(expected_raw)
    packaged = activation.parse_packaged_manifest(packaged_raw)
    activation.require_qualification_match(expected, packaged, "2d,3d")
    require(expected == report.get("activationExpectation") and packaged == item.get("packagedActivation"),
            "The verified activation documents disagree with the report.")
    return {"verified": True, "source": current, "producer_manifest_sha256": args.manifest_sha256,
            "package_report_sha256": adaptive.sha256(args.package_inputs), "variant": args.variant,
            "apk_sha256": item["apkSha256"], "pack_sha256": item["packSha256"],
            "checker_sha256": manifest["checkerSha256"]}


def standard_claim(root, session, visible):
    """Read the current public claim's real Standard semantics, excluding history/results."""
    for tag in ("problem-panel", "game-round-result", "game-winner", "game-next-round"):
        require(session.tagged_node(root, tag) is None, "A problem/result cannot stage a current claim.")
    table = session.tagged_node(root, "game-table")
    if table is None:
        return None
    all_text = [node.get("text", "") for node in table.iter("node") if node.get("package") == session.PACKAGE]
    require(not any(re.fullmatch(r"Hide round [0-9]+ reveal", text) for text in all_text),
            "Expanded previous-round history cannot stage a current claim.")
    texts = [node.get("text", "") for node in table.iter("node")
             if node.get("package") == session.PACKAGE and visible(node)]
    all_matches = [match for text in all_text if (match := CLAIM.fullmatch(text))]
    matches = [match for text in texts if (match := CLAIM.fullmatch(text))]
    require(len(all_matches) <= 1 and all_text.count("THE LAST CLAIM") <= 1,
            "Current claim semantics are ambiguous.")
    if "Set the tone." in all_text:
        require(all_text.count("Set the tone.") == 1 and not all_matches and "THE LAST CLAIM" not in all_text,
                "Opening and current-claim semantics are ambiguous.")
        return {"kind": "opening"} if "Set the tone." in texts else None
    if "THE LAST CLAIM" not in texts or not matches:
        return None
    require(texts.count("THE LAST CLAIM") == 1 and len(matches) == 1, "Current claim semantics are ambiguous.")
    claimant, count, rank, suffix = matches[0].groups()
    require(suffix == ("" if count == "1" else "s"), "Current claim has inconsistent count/rank wording.")
    return {"kind": "claim", "claimant": claimant, "card_count": int(count), "table_rank": rank,
            "standard_sentence": matches[0].group(0)}


def concealed(value):
    return value["handConcealed"] and all(value[field] == 0 for field in
        ("selectedCount", "privateFaceCount", "privateLabelCount")) and not any(
        control["role"] == "select" for control in value["controls"])


def ended_practice(root, session):
    """Positive current Standard semantics; unknown-viewer spectators are not elimination."""
    require(session.tagged_node(root, "problem-panel") is None, "A session problem is not staging exhaustion.")
    table = session.tagged_node(root, "game-table")
    if table is None or session.tagged_node(table, "game-play") is not None:
        return None
    if session.tagged_node(table, "game-winner") is not None:
        return "observed match end"
    texts = [node.get("text", "") for node in table.iter("node") if node.get("package") == session.PACKAGE]
    if ("Stay for the showdown." in texts
            and "You’re out of this match. Keep watching to see who keeps their last light." in texts):
        return "observed human elimination"
    return None


def context_control(value):
    require(concealed(value), "Context sweep must keep every private binding and selection concealed.")
    play = engine.find_control(value, "play")
    require(not play["enabled"] and not play["selected"], "Concealed context Play must remain unselected and disabled.")
    target, clip = play["rect"], play["clip"]
    require(clip[2] >= 32 and clip[3] >= 32 and 0 < target[2] <= clip[2] and 0 < target[3] <= clip[3]
            and clip[0] <= target[0] and target[0] + target[2] <= clip[0] + clip[2],
            "The real body clip has no usable space for a complete Play rectangle.")
    return play


def admit_native_geometry(owner, value):
    configuration = owner["configuration"]
    require(configuration["windowing_mode"] == "multi-window" and configuration["font_scale"] == 2.0,
            "Focused native Activity is not actually multi-window at font scale 2.0.")
    require(all(abs(actual - expected) <= VIEWPORT_TOLERANCE
                for actual, expected in zip(value["viewport"], EXPECTED_VIEWPORT)),
            "The directly observed Godot viewport is outside the reproduced short-pane interval.")
    context_control(value)


def same_context(before, after):
    for field in ("mode", "command", "projectionRevision", "surface", "viewport"):
        require(after[field] == before[field], "Native owner/projection/surface changed during the context sweep: " + field)
    first, second = context_control(before), context_control(after)
    require(first["clip"] == second["clip"] and first["rect"][0] == second["rect"][0]
            and first["rect"][2:] == second["rect"][2:], "The body/action geometry reflowed during scrolling.")


def body_swipe(value):
    """Scroll only; disabled Play is a geometry anchor and is never tapped or relabelled."""
    play = context_control(value)
    target, clip = play["rect"], play["clip"]
    distance = min(clip[3] * 0.4, 200)
    gap = target[1] + target[3] - clip[1] - clip[3]
    if gap > 0:
        # Aim inside Play's full-fit interval rather than jumping over it.
        distance = min(distance, gap + (clip[3] - target[3]) / 2)
    require(distance >= 12, "There is insufficient bounded drag room in the real body clip.")
    start = [clip[0] + clip[2] / 2, clip[1] + clip[3] / 2 + distance / 2]
    end = [start[0], start[1] - distance]
    surface, viewport = value["surface"], value["viewport"]
    scales = [surface[index + 2] / viewport[index] for index in (0, 1)]
    start, end = ([int(surface[index] + point[index] * scales[index]) for index in (0, 1)]
                  for point in (start, end))
    actual = (start[1] - end[1]) / scales[1]
    require(0 < actual <= clip[3] / 2 and all(surface[index] < point[index] < surface[index] + surface[index + 2]
                for point in (start, end) for index in (0, 1)), "Mapped body swipe is empty or outside its native surface.")
    return {"start": start, "end": end, "duration_ms": max(600, math.ceil(actual / 100 * 1000))}


def measured_displacement(before, after):
    same_context(before, after)
    first, second = context_control(before), context_control(after)
    displacement = first["rect"][1] - second["rect"][1]
    require(displacement >= 0, "Body moved in the opposite direction to the admitted swipe.")
    require(displacement <= first["clip"][3] / 2,
            "Actual content jump leaves a gap in the required half-page capture overlap.")
    return displacement


class ContextSweep:
    def __init__(self, smoke, probe):
        self.smoke, self.probe = smoke, probe
        self.positions, self.swipes = [], []

    def capture(self, observation, deadline):
        name = f"3d-context-position-{len(self.positions):02d}"
        self.probe._owner()

        def current(root):
            value = self.probe._parse(self.probe._node(root).get("content-desc"))
            engine.fresh_for_input(observation, value, time.monotonic())

        capture = self.smoke.capture_evidence(name, self.smoke.session.NATIVE_COMPONENT, self.probe.pid,
                                              ui_assertion=current)
        following = self.probe.refresh(deadline)
        require(engine.stable_state(observation["value"]) == engine.stable_state(following["value"]),
                "Renderer state/geometry changed around the sequential original screenshot.")
        play = context_control(following["value"])
        position = {"capture": capture, "before": observation["receipt"], "after": following["receipt"],
                    "play_rect": play["rect"], "clip": play["clip"],
                    "play_fully_enclosed": play["visible"] and engine.encloses(play["clip"], play["rect"])}
        self.positions.append(position)
        return following

    def run(self):
        deadline = time.monotonic() + SWEEP_SECONDS
        current = self.probe.settled(concealed)
        baseline = current["value"]
        admit_native_geometry(self.probe.owner, baseline)
        current = self.capture(current, deadline)
        play_reached = self.positions[-1]["play_fully_enclosed"]
        moved = 0.0
        for index in range(MAX_SWIPES):
            require(time.monotonic() < deadline, "Context sweep exceeded its finite time budget.")
            before = current["value"]
            gesture = body_swipe(before)
            receipt = self.probe._before_input(current, "play", -1, gesture, "context-swipe")
            swipe = {"index": index, "input": receipt, "gesture": gesture, "status": "requested"}
            self.swipes.append(swipe)
            self.smoke.adb("shell", "input", "swipe", *(str(part) for part in
                (*gesture["start"], *gesture["end"], gesture["duration_ms"])), timeout=10)
            swipe["status"] = "transport-completed"
            current = self.probe.settled(concealed, seconds=min(60, max(0, deadline - time.monotonic())))
            same_context(baseline, current["value"])
            input_delta = engine.counter(current["value"]["input"]) - engine.counter(before["input"])
            generation_delta = engine.counter(current["value"]["generation"]) - engine.counter(before["generation"])
            # Native inputChanged() invalidates the publication once per delivered event.
            # Expiry can invalidate it too; generation is not renderer lifetime identity.
            require(input_delta > 0 and generation_delta >= input_delta,
                    "Native input/invalidation stamps did not advance consistently after the actual body swipe.")
            # Preserve the reached screenshot before rejecting a gap or unexpected movement.
            current = self.capture(current, deadline)
            swipe.update(status="sampled", after=current["receipt"],
                         content_displacement=context_control(before)["rect"][1]
                         - context_control(current["value"])["rect"][1])
            displacement = measured_displacement(before, current["value"])
            moved += displacement
            play_reached |= self.positions[-1]["play_fully_enclosed"]
            swipe.update(status="observed", content_displacement=displacement,
                         after=current["receipt"])
            if displacement < 1:
                require(play_reached and moved >= 1, "Body scrolling stopped before meaningful movement and full Play enclosure.")
                return {"automated_geometry": "passed", "body_displacement": moved,
                        "play_fully_enclosed": True, "positions": self.positions, "swipes": self.swipes,
                        "termination": "settled-no-progress-after-play; body bottom is not established",
                        "public_context_pixel_acceptance": "pending-independent-review",
                        "max_swipes": MAX_SWIPES, "sweep_budget_seconds": SWEEP_SECONDS}
        raise engine.ObservationFailure("Context sweep exhausted its finite swipe budget; collection is incomplete.")


class PublicContextScenarios:
    def staging_time(self):
        deadline = getattr(self, "context_staging_deadline", None)
        if deadline is not None and time.monotonic() >= deadline:
            action = getattr(self, "context_staging_action", None)
            require(action is None or action["status"] not in ("input-requested", "input-acknowledged"),
                    "Staging deadline expired before the submitted Standard Play outcome was confirmed.")
            raise adaptive.Unavailable("The finite real-practice staging deadline expired without a qualifying context.")

    def adb(self, *arguments, **kwargs):
        is_input = arguments[:2] == ("shell", "input")
        require(not is_input or not self.input_incomplete, "Uncertain prior input forbids another UI input.")
        if is_input:
            self.staging_time()
        try:
            return super().adb(*arguments, **kwargs)
        except BaseException as error:
            if is_input:
                self.input_incomplete = True  # Never retry or perform cleanup UI after uncertain input transport.
                if isinstance(error, Exception):
                    # Pinned UI waits retry transport errors; uncertain input must escape that retry path.
                    raise engine.ObservationFailure("UI input transport did not complete; further input is forbidden.") from error
            raise

    def tap_node(self, node, label, *args, **kwargs):
        if getattr(self, "context_staging_deadline", None) is None or label not in ("game-play", "game-next-round"):
            return super().tap_node(node, label, *args, **kwargs)
        self.staging_time()
        if label == "game-play":
            event = self.context_staging_action
            require(event is not None and event["status"] == "preparing", "An unconfirmed staged Play must never be repeated.")
            event["input_xml"] = self.observations["standard_ui"][event["prefix"] + "-input"]
        else:
            prefix = self.context_staging_prefix + f"-round-advance-{len(self.context_staging_records):02d}"
            event = {"kind": "round-advance", "prefix": prefix,
                     "input_xml": self.retain_standard_ui(prefix, {"action": "Next round", "scope": "bounded context staging"})}
            self.context_staging_records.append(event)
        event["status"] = "input-requested"
        result = super().tap_node(node, label, *args, **kwargs)
        event["status"] = "input-acknowledged"
        return result

    def wait_context_turn(self, prefix):
        self.staging_time()
        self.context_staging_prefix = prefix
        event = {"kind": "human-turn-progression", "prefix": prefix, "status": "waiting",
                 "helper_max_round_advances": 8, "helper_budget_seconds": 120}
        self.context_staging_records.append(event)
        try:
            self.wait_for_human_turn()
        except RuntimeError as error:
            event["status"] = "unconfirmed"
            if type(error) is not RuntimeError or str(error) not in TURN_EXHAUSTION or self.input_incomplete:
                raise
            self.wait_activity(self.session.MAIN_COMPONENT, child_absent=True)
            root = self.dump_ui()
            self.reject_crash_dialog(root)
            reason = ended_practice(root, self.session)
            if reason is None:
                raise
            event.update(status="observed-staging-exhaustion", reason=reason,
                         final_ui=self.retain_standard_ui(prefix + "-exhausted", {"reason": reason}))
            raise adaptive.Unavailable("A real practice " + reason + " prevented context staging.") from error
        event.update(status="human-play-observed",
                     final_ui=self.retain_standard_ui(prefix + "-human-play", {"projected_play": True}))
        self.staging_time()

    def observe_context(self, prefix, allow_opening=False):
        self.wait_activity(self.session.MAIN_COMPONENT, child_absent=True)
        self.assert_concealed()
        anchor = self.wait_until("Expected the current human-turn round and rank",
            lambda root: self.session.public_anchor(root, self.visible), scroll="up")
        anchor_xml = self.retain_standard_ui(prefix + "-anchor", anchor)
        claim = self.wait_until("Expected the actual current-claim section or opening instruction",
            lambda root: standard_claim(root, self.session, self.visible), scroll="up")
        claim_xml = self.retain_standard_ui(prefix + "-claim", claim)
        if claim["kind"] == "opening":
            require(allow_opening, "The focused scenario has no current claim after its bounded staging action.")
            return {"public": anchor, "claim": claim, "anchor_xml": anchor_xml, "claim_xml": claim_xml}
        require(claim["table_rank"] == anchor["table_rank"], "Claim rank differs from its current round's rank.")
        self.wait_for_tag("game-play", enabled=False, scroll="down")
        play_xml = self.retain_standard_ui(prefix + "-play", {"projected": True, "enabled": False})
        challenge = self.wait_for_action("game-challenge", scroll="down")
        require([node.get("text") for node in challenge.iter("node") if node.get("text")]
                == ["Challenge " + claim["claimant"]], "Enabled Challenge does not identify the current claimant.")
        challenge_xml = self.retain_standard_ui(prefix + "-challenge", {"enabled": True, "claimant": claim["claimant"]})
        self.capture_evidence(prefix + "-actions", self.session.MAIN_COMPONENT,
            ui_assertion=lambda root: require(self.find_action(root, "game-challenge") is not None,
                                              "Current Challenge changed before its original Standard capture."))
        again = self.wait_until("Expected the same current public claim before native entry",
            lambda root: standard_claim(root, self.session, self.visible), scroll="up")
        require(again == claim, "The current claim changed while preparing its context observation.")
        self.retain_standard_ui(prefix + "-claim-rechecked", again)
        return {"public": anchor, "claim": claim, "anchor_xml": anchor_xml, "claim_xml": claim_xml,
                "play_xml": play_xml, "challenge_xml": challenge_xml}

    def stage_context(self, records=None):
        self.context_staging_records = [] if records is None else records
        self.context_staging_deadline = time.monotonic() + STAGING_SECONDS
        self.context_staging_action = None
        plays = []
        try:
            self.tap_action("home-practice")
            self.context_practice_active = True
            self.wait_for_tag("game-table")
            self.wait_context_turn("3d-context-initial")
            current = self.observe_context("3d-context-initial", allow_opening=True)
            self.context_staging_records.append({"kind": "observed-context", "context": current})
            while True:
                self.staging_time()
                if current["claim"]["kind"] == "claim":
                    return current, plays
                if len(plays) >= MAX_STAGING_PLAYS:
                    raise adaptive.Unavailable("Four confirmed Standard staging Plays ended at fresh openings without a qualifying claim.")
                prefix = f"3d-context-stage-{len(plays) + 1:02d}"
                baseline = self.observe_match(prefix + "-baseline")
                require(baseline["public"] == current["public"], "The observed opening changed before staging its real Play.")
                event = {"kind": "standard-staging-play", "prefix": prefix + "-play", "status": "preparing", "before": baseline}
                self.context_staging_records.append(event)
                self.context_staging_action = event
                # Every new action needs a fresh opening and the unchanged action-specific oracle.
                outcome = self.play_standard_card(baseline, prefix + "-play")
                event.update(status="confirmed", outcome=outcome)
                plays.append(event)
                self.context_staging_action = None
                self.wait_context_turn(prefix)
                root = self.dump_ui()
                if self.session.tagged_node(root, "game-hide-hand") is not None:
                    self.tap_action("game-hide-hand", scroll="up")
                current = self.observe_context(prefix + "-after", allow_opening=True)
                self.context_staging_records.append({"kind": "observed-context", "context": current})
                require(current["public"]["round"] >= baseline["public"]["round"], "Staging moved to an older round.")
                if current["claim"]["kind"] == "opening":
                    require(current["public"]["round"] > baseline["public"]["round"],
                            "A confirmed Play lost its claim without a new observed round.")
        finally:
            self.context_staging_deadline = None
            self.context_staging_action = None

    def enter_context_split(self):
        queries = {}
        for label, arguments in (("multiwindow", ("shell", "am", "supports-multiwindow")),
                                ("split_screen", ("shell", "am", "supports-split-screen-multi-window")),
                                ("help", ("shell", "wm", "shell", "help"))):
            result = self.command(*arguments)
            queries[label] = {"returncode": result.returncode, "stdout": result.stdout, "stderr": result.stderr}
        self.save_observation("context-split-capability", queries=queries)
        if any(item["returncode"] != 0 for item in queries.values()):
            raise adaptive.Unavailable("Verified split capability queries are unavailable.")
        adaptive.split_capability(queries["multiwindow"]["stdout"], queries["split_screen"]["stdout"], queries["help"]["stdout"])
        resolved = self.adb("shell", "cmd", "package", "resolve-activity", "--brief", "-a", "android.settings.DISPLAY_SETTINGS")
        self.save_observation("context-companion-resolved", raw=resolved)
        matches = re.findall(r"^([A-Za-z0-9_.]+/[A-Za-z0-9_.$]+)$", resolved, re.M)
        if len(matches) != 1:
            raise adaptive.Unavailable("No unambiguous display Settings companion resolves.")
        self.adb("shell", "am", "start", "-W", "-a", "android.settings.DISPLAY_SETTINGS")
        companion = self.state()["foreground"]
        require(companion is not None and companion["component"].split("/", 1)[0]
                == adaptive.component(matches[0]).split("/", 1)[0] and companion["task_id"] != self.shell_task,
                "The resolved Settings companion is not focused in its own task.")
        self.companion_task = companion["task_id"]
        self.focus_shell_task()
        self.split_owned = True
        self.save_observation("context-split-entry-request", companion_task=self.companion_task)
        self.adb("shell", "wm", "shell", "splitscreen", "moveToSideStage", str(self.companion_task), "1")
        _, panes = self.wait_split()
        require(panes[0]["component"] == self.session.MAIN_COMPONENT, "Split setup did not retain the Standard Activity.")
        self.focus_shell_task()
        actual, _ = self.wait_split()
        return actual

    def end_context_practice(self):
        require(not self.input_incomplete, "Uncertain input transport forbids practice cleanup UI.")
        require(not getattr(self, "context_cleanup_attempted", False), "Owned practice cleanup cannot repeat an incomplete attempt.")
        self.context_cleanup_attempted = True
        if self.split_owned:
            self.restore_split_window()
        else:
            self.require_shell(self.state())
            self.focus_shell_task()
        self.wait_activity(self.session.MAIN_COMPONENT, child_absent=True)
        self.dismiss_split_picker("3d-context-cleanup")
        root = self.dump_ui()
        if self.session.tagged_node(root, "game-hide-hand") is not None:
            self.tap_action("game-hide-hand", scroll="up")
            self.assert_concealed()
            root = self.dump_ui()
        self.assert_no_private_semantics(root)
        if self.find_action(root, "home-practice") is None:
            require(self.session.tagged_node(root, "game-table") is not None,
                    "The owned practice cannot be attributed for its bounded cleanup.")
            self.back()
            self.leave_dialog("3d-context-end")
            self.tap_action("leave-confirm", "Leave table")
            self.wait_for_action("home-practice", scroll="down")
            self.wait_activity(self.session.MAIN_COMPONENT, child_absent=True)
        self.context_practice_active = False
        self.capture_evidence("3d-context-home", self.session.MAIN_COMPONENT)

    def run_public_context(self):
        with self.check("3d.context-real-claim") as entry:
            self.set_rotation(self.state()["display"]["landscape"], self.session.MAIN_COMPONENT, "land")
            records = []
            entry["staging"] = {"max_confirmed_plays": MAX_STAGING_PLAYS, "budget_seconds": STAGING_SECONDS, "records": records}
            baseline, staging = self.stage_context(records)
            entry.update(baseline=baseline, staging_actions=staging)
        if self.checks["3d.context-real-claim"]["status"] != "passed":
            return
        with self.check("3d.context-short-split") as entry:
            entry["split"] = self.enter_context_split()
            preentry = self.observe_context("3d-context-pane-standard")
            require(preentry["public"] == baseline["public"] and preentry["claim"] == baseline["claim"],
                    "The real public context changed during split setup.")
            pid, task, _ = self.enter_native("3d", "3d-context-pane")
            self.stable_activity(self.session.NATIVE_COMPONENT, mode="multi-window")
            native, panes = self.wait_split(child_absent=False)
            require(panes[0]["component"] == self.session.NATIVE_COMPONENT,
                    "Native context is not inside the actually paired split pane.")
            entry.update(native=native, preentry=preentry)
        if self.checks["3d.context-short-split"]["status"] != "passed":
            return
        with self.check("3d.context-body-sweep") as entry:
            probe = engine.EngineObservationProbe(self, adaptive, "3d", pid, task)
            sweep = ContextSweep(self, probe)
            entry.update(expected_context=baseline, positions=sweep.positions, swipes=sweep.swipes,
                         public_context_pixel_acceptance="pending-independent-review")
            claim = baseline["claim"]
            entry["required_pixel_words"] = {"round": f"ROUND {baseline['public']['round']}",
                "claim": f"{claim['claimant']} claimed {claim['card_count']} {claim['table_rank']}{'' if claim['card_count'] == 1 else 's'}.",
                "guidance": "Challenge or play on.", "play": "Select cards", "challenge": "Challenge " + claim["claimant"]}
            entry.update(sweep.run())
        with self.check("3d.context-standard-return-end") as entry:
            self.tap_action("native-standard-table", "Standard table", scroll=None)
            returned = self.observe_context("3d-context-return")
            require(returned["public"] == baseline["public"] and returned["claim"] == baseline["claim"],
                    "The context sweep changed the real Standard round or claim.")
            entry["unchanged_public_context"] = returned
            self.end_context_practice()


def argument_parser():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("session-checker", "apk", "bundle", "package-inputs", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    for name in ("serial", "source-revision", "manifest-sha256"):
        parser.add_argument("--" + name, required=True)
    parser.add_argument("--variant", choices=("debug", "optimized-test-signed"), required=True)
    return parser


def main(argv=None):
    parser = argument_parser()
    args = parser.parse_args(argv)
    if not re.fullmatch(r"[0-9a-f]{40}", args.source_revision) or not re.fullmatch(r"[0-9a-f]{64}", args.manifest_sha256):
        parser.error("Exact workflow source and producer manifest hashes are required")
    session = adaptive.load_session(args.session_checker)
    session.fresh_output(args.output)
    runner = type("PublicContextSmoke", (PublicContextScenarios, adaptive.AdaptiveScenarios, session.GodotSessionSmoke), {})
    smoke = runner(session, args.serial, args.output, args.variant, "2.0", 30000)
    smoke.identity.update(input_apk=str(args.apk.resolve()), input_apk_sha256=adaptive.sha256(args.apk),
                          input_apk_bytes=args.apk.stat().st_size, focused_runner_sha256=adaptive.sha256(Path(__file__)))
    result = {"schema_version": 1, "started_utc": session.utc_now(), "scenario": "short-public-context",
              "modes": ["3d"], "font_scale": "2.0", "variant": args.variant, "source_revision": args.source_revision,
              "identity": smoke.identity, "checks": smoke.checks, "captures": smoke.captures,
              "observations": smoke.adaptive_observations, "steps": smoke.steps,
              "public_context_pixel_acceptance": "pending-independent-review",
              "limits": ["Automated assertions cover observed body motion and full Play geometry; public words and Challenge require pixel review.",
                         "A no-progress collection endpoint does not prove the body's bottom or complete text coverage.",
                         "Screenshots, UI XML and fresh geometry are sequential, not atomic or continuous privacy evidence.",
                         "Up to four confirmed Standard staging Plays may occur on fresh opening rounds; no native gameplay action, screen reader or physical-network qualification is claimed."]}
    failed = unsupported = False
    try:
        smoke.identity["admitted_inputs"] = admit_inputs(args)
        smoke.saved_rotation = smoke.adb("shell", "wm", "user-rotation", "-d", "0").strip()
        require(re.fullmatch(r"free|lock [0-3]", smoke.saved_rotation), "Cannot save the exact original rotation policy.")
        smoke.save_observation("context-original-rotation", policy=smoke.saved_rotation)
        smoke.setup_session(args.apk)
        smoke.run_public_context()
    except (adaptive.Unavailable, session.UnsupportedCheck) as error:
        unsupported = True
        result.update(unsupported_reason=session.ui.redacted(str(error)), stopped_stage=smoke.stage)
    except BaseException as error:
        failed = True
        result.update(error=session.ui.redacted(str(error) or type(error).__name__), failed_stage=smoke.stage)
        if not isinstance(error, Exception):
            raise
    finally:
        errors = []
        try:
            if smoke.logcat_started:
                errors.extend(smoke.diagnostics())
        except Exception as error:
            errors.append(str(error))
        if (getattr(smoke, "context_practice_active", False) and not smoke.input_incomplete
                and not getattr(smoke, "context_cleanup_attempted", False)):
            try:
                smoke.end_context_practice()
            except Exception as error:
                errors.append("Owned practice cleanup: " + str(error))
        try:
            errors.extend(smoke.restore_adaptive())
        except Exception as error:
            errors.append("Cleanup: " + str(error))
        if errors:
            failed = True
            result["diagnostic_or_restore_errors"] = [session.ui.redacted(error) for error in errors]
        unsupported |= any(check["status"] == "unsupported" for check in smoke.checks.values())
        failed |= any(check["status"] in ("failed", "running") for check in smoke.checks.values())
        if not (failed or unsupported) and not all(smoke.checks.get(name, {}).get("status") == "passed"
                                                  for name in REQUIRED_CHECKS):
            failed = True
            result["error"] = "The required installation, geometry and Standard return/end checks did not all complete."
        result.update(status="failed" if failed else "unsupported" if unsupported else "passed-automated-geometry-awaiting-pixel-review",
                      ended_utc=session.utc_now())
        result["artifacts"] = [{"file": str(path.relative_to(args.output)), "bytes": path.stat().st_size,
                                "sha256": adaptive.sha256(path)} for path in sorted(args.output.rglob("*")) if path.is_file()]
        smoke.write_json("godot-public-context-result.json", result)
    print(f"Android focused context: {result['status']}; {args.output / 'godot-public-context-result.json'}", flush=True)
    return 1 if failed else 2 if unsupported else 0


if __name__ == "__main__":
    sys.exit(main())
