extends RefCounted

## Godot's JSON parser deliberately accepts several non-JSON forms. Reject them before parsing,
## including duplicate decoded keys, excessive nesting, non-finite numbers, and bad Unicode.
const MAX_BYTES := 65_536
const MAX_DEPTH := 16
const MAX_VALUES := 4_096

var _document := ""
var _cursor := 0
var _values := 0
var _valid := true
var _non_integer_fields: Array[String] = []


static func decode(document: String) -> Dictionary:
	if document.length() > MAX_BYTES or document.to_utf8_buffer().size() > MAX_BYTES:
		return {"ok": false}
	var scanner = new()
	scanner._document = document
	scanner._value(0)
	scanner._space()
	if not scanner._valid or scanner._cursor != document.length():
		return {"ok": false}
	var parser := JSON.new()
	if parser.parse(document) != OK:
		return {"ok": false}
	return {"ok": true, "value": parser.data, "nonIntegerFields": scanner._non_integer_fields}


func _value(depth: int, field: String = "") -> void:
	_values += 1
	if depth > MAX_DEPTH or _values > MAX_VALUES:
		_valid = false
		return
	_space()
	match _peek():
		"{": _object(depth)
		"[": _array(depth)
		"\"": _string()
		"t": _literal("true")
		"f": _literal("false")
		"n": _literal("null")
		_: _number(field)


func _object(depth: int) -> void:
	_cursor += 1
	_space()
	if _consume("}"):
		return
	var keys := {}
	while _valid:
		_space()
		if _peek() != "\"":
			_valid = false
			return
		var key := _string()
		if not _valid or keys.has(key):
			_valid = false
			return
		keys[key] = true
		_space()
		if not _consume(":"):
			_valid = false
			return
		_value(depth + 1, key)
		_space()
		if _consume("}"):
			return
		if not _consume(","):
			_valid = false
			return


func _array(depth: int) -> void:
	_cursor += 1
	_space()
	if _consume("]"):
		return
	while _valid:
		_value(depth + 1)
		_space()
		if _consume("]"):
			return
		if not _consume(","):
			_valid = false
			return


func _string() -> String:
	var start := _cursor
	_cursor += 1
	while _cursor < _document.length():
		var code := _document.unicode_at(_cursor)
		_cursor += 1
		if code == 34:
			return JSON.parse_string(_document.substr(start, _cursor - start))
		if code < 32 or (code >= 0xD800 and code <= 0xDFFF):
			_valid = false
			return ""
		if code != 92:
			continue
		var escape := _peek()
		_cursor += 1
		if escape in ["\"", "\\", "/", "b", "f", "n", "r", "t"]:
			continue
		if escape != "u":
			_valid = false
			return ""
		var point := _hex_quad()
		if not _valid:
			return ""
		if point >= 0xDC00 and point <= 0xDFFF:
			_valid = false
			return ""
		if point >= 0xD800 and point <= 0xDBFF:
			if not _consume("\\") or not _consume("u"):
				_valid = false
				return ""
			var low := _hex_quad()
			if low < 0xDC00 or low > 0xDFFF:
				_valid = false
				return ""
	_valid = false
	return ""


func _hex_quad() -> int:
	var result := 0
	for unused in range(4):
		var digit := "0123456789abcdef".find(_peek().to_lower())
		if _cursor >= _document.length() or digit < 0:
			_valid = false
			return -1
		result = result * 16 + digit
		_cursor += 1
	return result


func _number(field: String) -> void:
	var start := _cursor
	_consume("-")
	if not _consume("0"):
		if not _digit(_peek(), true):
			_valid = false
			return
		while _digit(_peek()):
			_cursor += 1
	if _consume("."):
		if not _digit(_peek()):
			_valid = false
			return
		while _digit(_peek()):
			_cursor += 1
	if _peek() in ["e", "E"]:
		_cursor += 1
		if _peek() in ["+", "-"]:
			_cursor += 1
		if not _digit(_peek()):
			_valid = false
			return
		while _digit(_peek()):
			_cursor += 1
	var token := _document.substr(start, _cursor - start)
	if not field.is_empty() and (token.contains(".") or token.contains("e") or token.contains("E")):
		_non_integer_fields.append(field)
	if not is_finite(token.to_float()):
		_valid = false


func _literal(value: String) -> void:
	if _document.substr(_cursor, value.length()) != value:
		_valid = false
		return
	_cursor += value.length()


func _space() -> void:
	while _peek() in [" ", "\t", "\r", "\n"]:
		_cursor += 1


func _consume(value: String) -> bool:
	if _peek() != value:
		return false
	_cursor += 1
	return true


func _peek() -> String:
	return _document.substr(_cursor, 1) if _cursor < _document.length() else ""


func _digit(value: String, nonzero: bool = false) -> bool:
	return value.length() == 1 and value >= ("1" if nonzero else "0") and value <= "9"
