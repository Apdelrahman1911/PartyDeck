#!/usr/bin/env python3
"""Run independent Godot controller/codec checks with real authority fixtures."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile


def encode(value: object) -> str:
    return json.dumps(value, ensure_ascii=True, separators=(",", ":"))


def cases(launch: dict, launch_3d: dict, prior_round: dict) -> list[dict]:
    result = [
        {"name": "real 2d launch", "document": encode(launch), "valid": True},
        {"name": "real 3d launch", "document": encode(launch_3d), "valid": True},
    ]

    def changed(name: str, path: list, value: object, valid: bool = False) -> None:
        document = copy.deepcopy(launch)
        parent = document
        for part in path[:-1]:
            parent = parent[part]
        parent[path[-1]] = value
        result.append({"name": name, "document": encode(document), "valid": valid})

    for counter in [
        "", "-0", "-1", "+1", "00", "01", "1.0", "1e0", " 1",
        "9223372036854775808", "18446744073709551615", "１",
    ]:
        changed("noncanonical revision " + repr(counter), ["revision"], counter)
    for counter in ["9007199254740993", "9223372036854775807"]:
        changed("exact large revision " + counter, ["revision"], counter, True)
    for counter in [0, 1.0, True, None]:
        changed("nonstrings cannot be revisions " + repr(counter), ["revision"], counter)
    for version in [1.0, "1", True, None, -1, 2]:
        changed("invalid protocol value " + repr(version), ["protocolVersion"], version)
    raw = encode(launch)
    result.append({
        "name": "protocol exponent is not an integer token",
        "document": raw.replace('"protocolVersion":1,', '"protocolVersion":1e0,', 1),
        "valid": False,
    })
    for path, value in [
        (["payload", "game", "roundNumber"], 1.0),
        (["payload", "game", "players", 0, "handCount"], 5.0),
        (["payload", "game", "availableActions", "maxPlayableCards"], 3.0),
        (["payload", "game", "forcedChallenge"], "false"),
        (["payload", "game", "players", 0, "eliminated"], "false"),
        (["payload", "controls", "isHost"], "true"),
        (["payload", "game", "roundNumber"], "1"),
        (["payload", "game", "tableRank"], "WILD"),
        (["payload", "game", "yourHand", 0, "rank"], "JOKER"),
        (["payload", "game", "viewerId"], None),
        (["preferences", "reduceMotion"], "true"),
        (["preferences", "textScale"], 2.1),
        (["payload", "game", "players", 0, "displayName"], "\ud800"),
    ]:
        changed("invalid field " + ".".join(map(str, path)), path, value)
    changed("fractional text scale remains allowed", ["preferences", "textScale"], 1.25, True)
    changed("duplicate own card", ["payload", "game", "yourHand", 1, "id"], launch["payload"]["game"]["yourHand"][0]["id"])

    for path in [
        ["payload", "game", "availableActions", "canChallenge"],
        ["payload", "game", "availableActions", "maxPlayableCards"],
        ["payload", "controls", "canSendAction"],
        ["payload", "game", "roundOutcome"],
        ["preferences", "soundEnabled"],
    ]:
        document = copy.deepcopy(launch)
        parent = document
        for part in path[:-1]:
            parent = parent[part]
        del parent[path[-1]]
        result.append({"name": "missing required " + ".".join(path), "document": encode(document), "valid": False})
    leaked = copy.deepcopy(launch)
    leaked["payload"]["game"]["players"][1]["hand"] = [{"id": "secret", "rank": "STAR"}]
    result.append({"name": "opponent hand field", "document": encode(leaked), "valid": False})
    leaked = copy.deepcopy(launch)
    leaked["payload"]["game"]["burnoutStep"] = 6
    result.append({"name": "future burnout field", "document": encode(leaked), "valid": False})
    old_proof = copy.deepcopy(launch)
    old_proof["revision"] = prior_round["revision"]
    old_proof["payload"] = prior_round["payload"]
    result.append({"name": "actual retained previous-round proof", "document": encode(old_proof), "valid": True})
    result.append({"name": "escaped duplicate protocol", "document": raw[:-1] + ',"\\u0070rotocolVersion":1}', "valid": False})
    return result


SCRIPT = r"""
extends SceneTree

const Controller = preload("res://scripts/renderer_controller.gd")
var _checks := 0
var _failures := 0

func _initialize() -> void:
    var corpus = JSON.parse_string(FileAccess.get_file_as_string("res://cases.json"))
    for fixture in corpus:
        var controller = Controller.new()
        var accepted: bool = controller.receive_document(fixture.document)
        _check(accepted == fixture.valid, fixture.name)
        if accepted:
            var source = JSON.parse_string(fixture.document)
            _check(controller.revision == source.revision, "accepted revision stays exact")
            _check(not _has_rank(controller.presentation_state().game.yourHand), "accepted launch starts concealed")
        controller.free()
    _controller_flow()
    _large_revision_flow()
    print("Bridge renderer review: %d checks, %d failures." % [_checks, _failures])
    quit(1 if _failures > 0 else 0)

func _controller_flow() -> void:
    var launch_text := FileAccess.get_file_as_string("res://launch-2d.json")
    var launch: Dictionary = JSON.parse_string(launch_text)
    var controller = Controller.new()
    var events: Array = []
    controller.bridge_event.connect(func(document: String): events.append(JSON.parse_string(document)))
    _check(controller.receive_document(launch_text), "flow launch")
    _check(events.size() == 1 and events[0].type == "ready" and events[0].sequence == "0", "one initial ready")
    _check(not controller.receive_document(launch_text), "duplicate launch rejected")
    var card_id: String = launch.payload.game.yourHand[0].id
    controller.toggle_card(card_id)
    _check(controller.presentation_state().selectedCardIds.is_empty(), "concealed hand cannot select")
    controller.reveal_hand()
    controller.toggle_card(card_id)
    _check(events.size() == 1, "local reveal and selection emit no authority event")
    _check(_has_rank(controller.presentation_state().game.yourHand), "deliberate reveal exposes own ranks")
    controller.hide_hand()
    _check(controller.presentation_state().selectedCardIds.is_empty(), "hide clears selection")
    _check(not _has_rank(controller.presentation_state().game.yourHand), "hide removes private ranks")
    controller.reveal_hand()
    controller.toggle_card(card_id)
    controller.play_selected()
    var state: Dictionary = controller.presentation_state()
    _check(events.size() == 2 and events[1].type == "intent", "play emits one intent")
    _check(events[1].payload == {"type": "play", "cardIds": [card_id]}, "play nominates cards but no actor or outcome")
    _check(events[1].expectedRevision == launch.revision, "intent uses displayed revision")
    _check(state.selectedCardIds.is_empty(), "submission clears selection immediately")
    _check(not state.controls.canSendAction, "pending submission disables action")
    _check(state.game.yourHand.size() == launch.payload.game.yourHand.size(), "renderer does not apply its own play")

    _check(controller.receive_document(_command(launch.presentationId, "foreground", {"isForeground": false})), "native foreground loss")
    state = controller.presentation_state()
    _check(not state.handVisible and state.selectedCardIds.is_empty() and not _has_rank(state.game.yourHand), "background conceals private state")
    var count := events.size()
    controller.reveal_hand()
    controller.toggle_card(card_id)
    controller.play_selected()
    _check(events.size() == count, "background input emits no event")
    _check(controller.receive_document(_command(launch.presentationId, "foreground", {"isForeground": true})), "native foreground return")
    _check(controller.presentation_state().controls.canSendAction, "native resume clears uncertain pending state")
    _check(not controller.presentation_state().handVisible, "resume stays concealed")
    controller.reveal_hand()
    controller.toggle_card(card_id)
    controller.play_selected()
    controller.set_window_foreground(false)
    controller.set_window_foreground(true)
    _check(controller.presentation_state().controls.canSendAction, "window focus recovery clears pending state")
    _check(not controller.presentation_state().handVisible, "window recovery stays concealed")

    var after_play := FileAccess.get_file_as_string("res://after-play.json")
    _check(controller.receive_document(after_play), "new authoritative projection accepted")
    _check(not controller.receive_document(after_play), "same revision cannot replace projection")
    _check(controller.presentation_state().game.yourHand.size() == launch.payload.game.yourHand.size() - 1, "only authoritative view removes played card")
    _check(controller.receive_document(FileAccess.get_file_as_string("res://round-ended.json")), "actual round proof accepted")
    _check(controller.presentation_state().game.yourHand.is_empty(), "round result has no private hand presentation")
    _check(controller.receive_document(FileAccess.get_file_as_string("res://round-playing.json")), "redeal with prior proof accepted")
    state = controller.presentation_state()
    _check(state.game.roundOutcome.roundNumber < state.game.roundNumber, "proof retains its own historical round")
    _check(not state.handVisible and state.selectedCardIds.is_empty(), "redeal clears local reveal and selection")
    _check(controller.receive_document(FileAccess.get_file_as_string("res://finished.json")), "actual winner projection accepted")
    _check(controller.presentation_state().game.yourHand.is_empty(), "winner has no private hand presentation")
    _check(controller.receive_document(_command(launch.presentationId, "close")), "close accepted")
    _check(controller.presentation_state().closed and controller.presentation_state().game.is_empty(), "close purges presentation state")
    count = events.size()
    controller.reveal_hand()
    controller.play_selected()
    controller.request_exit()
    _check(events.size() == count, "closed presentation cannot emit later input")
    _check(not controller.receive_document(after_play), "closed presentation rejects delayed view")

    var replacement = Controller.new()
    _check(replacement.receive_document(FileAccess.get_file_as_string("res://replacement-launch.json")), "fresh presentation opens")
    _check(not replacement.receive_document(after_play), "old view cannot target replacement")
    _check(not replacement.receive_document(_command(launch.presentationId, "foreground", {"isForeground": false})), "old lifecycle callback cannot target replacement")
    _check(replacement.presentation_state().foreground, "old callback leaves replacement active")
    controller.free()
    replacement.free()

func _large_revision_flow() -> void:
    var controller = Controller.new()
    var events: Array = []
    controller.bridge_event.connect(func(document: String): events.append(JSON.parse_string(document)))
    _check(controller.receive_document(FileAccess.get_file_as_string("res://large-launch.json")), "large exact revision launch")
    _check(controller.receive_document(FileAccess.get_file_as_string("res://large-next.json")), "adjacent revision above double precision accepted")
    _check(controller.revision == "9007199254740993", "adjacent large revision preserved exactly")
    var cards: Array = controller.presentation_state().game.yourHand
    controller.reveal_hand()
    controller.toggle_card(cards[0].id)
    controller.play_selected()
    _check(events.back().expectedRevision == "9007199254740993", "large revision echoed exactly")
    controller.free()

func _command(id: String, kind: String, extras: Dictionary = {}) -> String:
    var value := {"protocolVersion": 1, "presentationId": id, "type": kind}
    value.merge(extras)
    return JSON.stringify(value)

func _has_rank(cards: Array) -> bool:
    for card in cards:
        if card.has("rank"):
            return true
    return false

func _check(condition: bool, label: String) -> void:
    _checks += 1
    if not condition:
        _failures += 1
        push_error("Renderer boundary review: " + label)
"""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--godot", default=os.environ.get("PARTYDECK_GODOT_BINARY", "/opt/partydeck-godot/godot"))
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    fixtures = root / "bridge/fixtures"
    launch = json.loads((fixtures / "launch-2d.json").read_text())
    prior = json.loads((fixtures / "round-playing.json").read_text())
    inputs = cases(launch, json.loads((fixtures / "launch-3d.json").read_text()), prior)
    with tempfile.TemporaryDirectory(prefix="partydeck-renderer-boundary-review-") as directory:
        project = Path(directory)
        (project / "scripts").mkdir()
        (project / "project.godot").write_text('config_version=5\n[application]\nconfig/name="Renderer boundary review"\n')
        for name in ["strict_json.gd", "view_validator.gd", "renderer_controller.gd"]:
            data = (root / "renderer/scripts" / name).read_bytes()
            (project / "scripts" / name).write_bytes(data)
            print(f"{name} SHA-256: {hashlib.sha256(data).hexdigest()}", flush=True)
        for name in ["launch-2d.json", "after-play.json", "round-ended.json", "round-playing.json", "finished.json"]:
            data = (fixtures / name).read_bytes()
            (project / name).write_bytes(data)
            print(f"{name} SHA-256: {hashlib.sha256(data).hexdigest()}", flush=True)
        replacement = copy.deepcopy(launch)
        replacement["presentationId"] = "independent-replacement"
        (project / "replacement-launch.json").write_text(encode(replacement))
        large = copy.deepcopy(launch)
        large["revision"] = "9007199254740992"
        (project / "large-launch.json").write_text(encode(large))
        large_view = {key: value for key, value in large.items() if key in ["protocolVersion", "presentationId", "schemaId", "payload"]}
        large_view.update(type="view", revision="9007199254740993")
        (project / "large-next.json").write_text(encode(large_view))
        (project / "cases.json").write_text(encode(inputs))
        (project / "review.gd").write_text(SCRIPT)
        completed = subprocess.run(
            [args.godot, "--headless", "--path", directory, "--script", "res://review.gd"],
            timeout=45, check=False, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        )
        print(completed.stdout, end="")
        if "SCRIPT ERROR:" in completed.stdout or "Bridge renderer review:" not in completed.stdout:
            return 1
        return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
