class_name LastLightRendererController
extends Node

signal state_changed(state: Dictionary)
signal bridge_event(document: String)

const StrictJson = preload("res://scripts/strict_json.gd")
const Validator = preload("res://scripts/view_validator.gd")
const PROTOCOL := 1
const VIEW_SCHEMA := "last-light-view-v1"
const INTENT_SCHEMA := "last-light-intent-v1"

var presentation_id := ""
var presentation_mode := "3d"
var revision := "0"
var _sequence := 0
var _launched := false
var _closed := false
var _host_foreground := true
var _window_foreground := true
var _hand_visible := false
var _pending := false
var _selected: Array[String] = []
var _game: Dictionary = {}
var _controls := {"isHost": false, "canSendAction": false, "canAdvanceRound": false, "canReturnToLobby": false}
var _preferences := {"reduceMotion": false, "soundEnabled": true, "textScale": 1.0}
var _status := "Waiting for the table."


func receive_document(document: String) -> bool:
	if _closed:
		return false
	var decoded: Dictionary = StrictJson.decode(document)
	if not decoded.ok or not decoded.value is Dictionary:
		return false
	for field in decoded.nonIntegerFields:
		if field in ["protocolVersion", "roundNumber", "handCount", "penaltyAttempts", "cardCount", "maxPlayableCards", "penaltyAttempt"]:
			return false
	var message: Dictionary = decoded.value
	if not message.get("protocolVersion") is float and not message.get("protocolVersion") is int:
		return false
	if message.protocolVersion != PROTOCOL or not Validator.text(message.get("presentationId"), 128):
		return false
	if message.get("type") == "launch":
		return _launch(message)
	if not _launched or message.presentationId != presentation_id:
		return false
	match message.get("type"):
		"view":
			if not Validator.fields(message, ["protocolVersion", "presentationId", "type", "revision", "schemaId", "payload"]) \
				or message.schemaId != VIEW_SCHEMA or not Validator.counter(message.revision) \
				or message.revision.to_int() <= revision.to_int() or not Validator.payload(message.payload):
				return false
			_set_view(message.payload, message.revision)
			return true
		"foreground":
			if not Validator.fields(message, ["protocolVersion", "presentationId", "type", "isForeground"]) \
				or not message.isForeground is bool:
				return false
			_host_foreground = message.isForeground
			if not _host_foreground:
				_pending = false
				_conceal()
			_publish()
			return true
		"close":
			if not Validator.fields(message, ["protocolVersion", "presentationId", "type"]):
				return false
			_close()
			return true
	return false


func _launch(message: Dictionary) -> bool:
	if _launched or not Validator.fields(message, ["protocolVersion", "presentationId", "type", "gameId",
		"presentationMode", "revision", "schemaId", "payload", "preferences"]):
		return false
	if message.gameId != "last-light" or message.schemaId != VIEW_SCHEMA \
		or message.presentationMode not in ["2d", "3d"] or not Validator.counter(message.revision) \
		or not Validator.payload(message.payload) or not Validator.preferences(message.preferences):
		return false
	presentation_id = message.presentationId
	presentation_mode = message.presentationMode
	_preferences = message.preferences.duplicate(true)
	_launched = true
	_set_view(message.payload, message.revision)
	if not _closed:
		_emit({"type": "ready"})
	return not _closed


func _set_view(payload: Dictionary, new_revision: String) -> void:
	revision = new_revision
	_game = payload.game.duplicate(true)
	_controls = payload.controls.duplicate(true)
	_pending = false
	_status = ""
	_conceal()
	_publish()


func presentation_state() -> Dictionary:
	var game := _game.duplicate(true)
	var visible := _hand_visible and _foreground() and not _closed and _has_hand()
	if not game.is_empty():
		if game.phase != "PLAYING":
			game.yourHand = []
		elif not visible:
			for card in game.yourHand:
				card.erase("rank")
	var controls := _controls.duplicate(true)
	controls.canSendAction = controls.canSendAction and _foreground() and not _closed and not _pending
	return {
		"game": game, "controls": controls, "handVisible": visible,
		"selectedCardIds": _selected.duplicate(), "foreground": _foreground(), "closed": _closed,
		"status": _status, "reduceMotion": _preferences.reduceMotion,
		"soundEnabled": _preferences.soundEnabled and _foreground() and not _closed,
		"textScale": float(_preferences.textScale), "presentationMode": presentation_mode,
	}


func reveal_hand() -> void:
	if _closed or not _foreground() or not _has_hand():
		return
	_hand_visible = true
	_status = ""
	_publish()


func hide_hand() -> void:
	if _closed:
		return
	_conceal()
	_publish()


func toggle_card(card_id: String) -> void:
	if not _can_play() or not _hand_visible or card_id not in _hand_ids():
		return
	if card_id in _selected:
		_selected.erase(card_id)
		_status = ""
	elif _selected.size() < int(_game.availableActions.maxPlayableCards):
		_selected.append(card_id)
		_status = ""
	else:
		_status = "Choose up to %d cards." % int(_game.availableActions.maxPlayableCards)
	_publish()


func play_selected() -> void:
	if not _can_play() or not _hand_visible or _selected.is_empty():
		return
	var cards: Array[String] = []
	for card_id in _hand_ids():
		if card_id in _selected:
			cards.append(card_id)
	if cards.is_empty() or cards.size() > int(_game.availableActions.maxPlayableCards):
		return
	_send_intent({"type": "play", "cardIds": cards}, "Sending play…")


func challenge() -> void:
	if not _can_send() or _game.get("phase") != "PLAYING" or not _game.availableActions.canChallenge:
		return
	_send_intent({"type": "challenge"}, "Calling challenge…")


func next_round() -> void:
	if not _can_send() or not _controls.isHost or not _controls.canAdvanceRound or _game.get("phase") != "ROUND_ENDED":
		return
	_send_intent({"type": "advance_round"}, "Dealing the next round…")


func return_to_lobby() -> void:
	if not _can_send() or not _controls.isHost or not _controls.canReturnToLobby:
		return
	_send_intent({"type": "return_to_lobby"}, "Returning to the room…")


func request_exit() -> void:
	if _closed or not _launched:
		return
	_close()
	_emit({"type": "exit"})


func set_window_foreground(active: bool) -> void:
	if _closed:
		return
	_window_foreground = active
	if not active:
		_pending = false
		_conceal()
	_publish()


func fail(reason: String) -> void:
	if _closed:
		return
	_close()
	if _launched:
		_emit({"type": "failed", "reason": reason if reason in ["INITIALIZATION_FAILED", "INVALID_PAYLOAD", "RENDERER_LOST", "INTERNAL_ERROR"] else "INTERNAL_ERROR"})


func _send_intent(payload: Dictionary, status: String) -> void:
	_pending = true
	_selected.clear()
	_status = status
	_publish()
	_emit({"type": "intent", "expectedRevision": revision, "schemaId": INTENT_SCHEMA, "payload": payload})


func _emit(body: Dictionary) -> void:
	if _sequence == 9_223_372_036_854_775_807:
		_close()
		return
	var event := {"protocolVersion": PROTOCOL, "presentationId": presentation_id, "sequence": str(_sequence)}
	_sequence += 1
	event.merge(body)
	bridge_event.emit(JSON.stringify(event))


func _close() -> void:
	_closed = true
	_conceal()
	_game.clear()
	_controls = {"isHost": false, "canSendAction": false, "canAdvanceRound": false, "canReturnToLobby": false}
	_status = "Table closed."
	_publish()


func _conceal() -> void:
	_hand_visible = false
	_selected.clear()
	if not _pending:
		_status = ""


func _publish() -> void:
	state_changed.emit(presentation_state())


func _foreground() -> bool:
	return _host_foreground and _window_foreground and not _closed


func _has_hand() -> bool:
	return _game.get("phase") == "PLAYING" and not _game.get("yourHand", []).is_empty()


func _can_send() -> bool:
	return _launched and not _closed and _foreground() and not _pending and _controls.canSendAction


func _can_play() -> bool:
	return _can_send() and _has_hand() and _game.availableActions.canPlay


func _hand_ids() -> Array[String]:
	var result: Array[String] = []
	for card in _game.get("yourHand", []):
		result.append(card.id)
	return result
