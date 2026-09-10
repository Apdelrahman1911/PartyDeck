#pragma once

#include <cstddef>
#include <set>
#include <string>
#include <string_view>

namespace partydeck::ios_probe {

// Foundation and Godot both accept JSON forms the wire contract rejects. This
// bounded preflight checks the original bytes, including decoded duplicate keys.
class StrictJson {
	std::string_view input;
	size_t position = 0;
	size_t values = 0;

	char peek() const { return position < input.size() ? input[position] : '\0'; }
	bool take(char expected) {
		if (position == input.size() || input[position] != expected) {
			return false;
		}
		++position;
		return true;
	}
	void whitespace() {
		while (position < input.size() && (peek() == ' ' || peek() == '\t' || peek() == '\r' || peek() == '\n')) {
			++position;
		}
	}
	bool hex4(char32_t &value) {
		value = 0;
		for (int i = 0; i < 4; ++i) {
			if (position == input.size()) {
				return false;
			}
			char digit = input[position++];
			int number = digit >= '0' && digit <= '9' ? digit - '0' : digit >= 'a' && digit <= 'f' ? digit - 'a' + 10 : digit >= 'A' && digit <= 'F' ? digit - 'A' + 10 : -1;
			if (number < 0) {
				return false;
			}
			value = value * 16 + number;
		}
		return true;
	}
	bool string(std::u32string &decoded) {
		if (!take('"')) {
			return false;
		}
		while (position < input.size()) {
			unsigned char first = input[position++];
			if (first == '"') {
				return true;
			}
			char32_t scalar = first;
			if (first == '\\') {
				if (position == input.size()) {
					return false;
				}
				switch (input[position++]) {
					case '"': scalar = '"'; break;
					case '\\': scalar = '\\'; break;
					case '/': scalar = '/'; break;
					case 'b': scalar = '\b'; break;
					case 'f': scalar = '\f'; break;
					case 'n': scalar = '\n'; break;
					case 'r': scalar = '\r'; break;
					case 't': scalar = '\t'; break;
					case 'u': {
						if (!hex4(scalar)) {
							return false;
						}
						if (scalar >= 0xD800 && scalar <= 0xDBFF) {
							char32_t low;
							if (!take('\\') || !take('u') || !hex4(low) || low < 0xDC00 || low > 0xDFFF) {
								return false;
							}
							scalar = 0x10000 + ((scalar - 0xD800) << 10) + low - 0xDC00;
						} else if (scalar >= 0xDC00 && scalar <= 0xDFFF) {
							return false;
						}
						break;
					}
					default: return false;
				}
			} else if (first < 0x20) {
				return false;
			} else if (first >= 0x80) {
				int trailing;
				char32_t minimum;
				if (first >= 0xC2 && first <= 0xDF) {
					trailing = 1;
					minimum = 0x80;
					scalar &= 0x1F;
				} else if (first >= 0xE0 && first <= 0xEF) {
					trailing = 2;
					minimum = 0x800;
					scalar &= 0x0F;
				} else if (first >= 0xF0 && first <= 0xF4) {
					trailing = 3;
					minimum = 0x10000;
					scalar &= 0x07;
				} else {
					return false;
				}
				for (int i = 0; i < trailing; ++i) {
					if (position == input.size()) {
						return false;
					}
					unsigned char byte = input[position++];
					if ((byte & 0xC0) != 0x80) {
						return false;
					}
					scalar = (scalar << 6) | (byte & 0x3F);
				}
				if (scalar < minimum || scalar > 0x10FFFF || (scalar >= 0xD800 && scalar <= 0xDFFF)) {
					return false;
				}
			}
			decoded.push_back(scalar);
		}
		return false;
	}
	bool number() {
		take('-');
		if (!take('0')) {
			if (peek() < '1' || peek() > '9') {
				return false;
			}
			while (peek() >= '0' && peek() <= '9') {
				++position;
			}
		}
		if (take('.')) {
			if (peek() < '0' || peek() > '9') {
				return false;
			}
			while (peek() >= '0' && peek() <= '9') {
				++position;
			}
		}
		if (take('e') || take('E')) {
			if (!take('+')) {
				take('-');
			}
			if (peek() < '0' || peek() > '9') {
				return false;
			}
			while (peek() >= '0' && peek() <= '9') {
				++position;
			}
		}
		return true;
	}
	bool value(unsigned depth) {
		if (++values > 4096) {
			return false;
		}
		whitespace();
		if (peek() == '{' || peek() == '[') {
			if (depth == 16) {
				return false;
			}
			bool object = take('{');
			if (!object) {
				take('[');
			}
			char end = object ? '}' : ']';
			whitespace();
			if (take(end)) {
				return true;
			}
			std::set<std::u32string> keys;
			do {
				whitespace();
				if (object) {
					std::u32string key;
					if (!string(key) || !keys.insert(key).second) {
						return false;
					}
					whitespace();
					if (!take(':')) {
						return false;
					}
				}
				if (!value(depth + 1)) {
					return false;
				}
				whitespace();
				if (take(end)) {
					return true;
				}
			} while (take(','));
			return false;
		}
		if (peek() == '"') {
			std::u32string decoded;
			return string(decoded);
		}
		for (std::string_view literal : { "true", "false", "null" }) {
			if (input.substr(position, literal.size()) == literal) {
				position += literal.size();
				return true;
			}
		}
		return number();
	}

public:
	explicit StrictJson(std::string_view bytes) : input(bytes) {}
	bool valid_object(size_t maximum_bytes) {
		if (input.empty() || input.size() > maximum_bytes) {
			return false;
		}
		whitespace();
		if (peek() != '{' || !value(0)) {
			return false;
		}
		whitespace();
		return position == input.size();
	}
};

} // namespace partydeck::ios_probe
