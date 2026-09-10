#include "../modules/partydeck_ios_probe/strict_json.h"

#include <cstdlib>
#include <iostream>
#include <string>

using partydeck::ios_probe::StrictJson;

int main() {
	int checks = 0;
	auto check = [&](const std::string &document, bool expected, size_t limit = 4096) {
		++checks;
		if (StrictJson(document).valid_object(limit) != expected) {
			std::cerr << "Strict JSON case " << checks << " failed\n";
			std::exit(1);
		}
	};
	check(R"({"protocolVersion":1,"sequence":"9223372036854775807","type":"ready"})", true);
	check(R"({"x":[true,false,null,-1.25e+3],"y":{"x":"\uD83C\uDCC1"}})", true);
	check(R"({"a":1,"\u0061":2})", false);
	check(R"({"x":{"a":1,"a":2}})", false);
	check(R"({"x":1,"x":1})", false);
	check(R"({"x":1,})", false);
	check(R"({"x":[1,]})", false);
	check(R"({"x":NaN})", false);
	check(R"({"x":+1})", false);
	check(R"({"x":01})", false);
	check(R"({"x":.5})", false);
	check(R"({"x":1.})", false);
	check(R"({"x":1e})", false);
	check(R"({"x":true false})", false);
	check(R"({"x":"\uD800"})", false);
	check(R"({"x":"\uDC00"})", false);
	check(R"({"x":"\uD800\u0041"})", false);
	check(R"({"🃁":1,"\uD83C\uDCC1":2})", false);
	check(R"({"x":"\q"})", false);
	check("{\"x\":\"\n\"}", false);
	check(std::string("{\"x\":\"") + char(0xC0) + char(0xAF) + "\"}", false);
	check(std::string("{\"x\":\"") + char(0xED) + char(0xA0) + char(0x80) + "\"}", false);
	check(std::string("{\"x\":\"") + char(0xF4) + char(0x90) + char(0x80) + char(0x80) + "\"}", false);
	check("{}{}", false);
	check("[]", false);
	check(" \r\n{\"x\":0}\t", true);
	check("{}", true, 2);
	check("{}", false, 1);
	check("{\"x\":\"" + std::string(4088, 'x') + "\"}", true);
	check("{\"x\":\"" + std::string(4089, 'x') + "\"}", false);
	std::string nested = "0";
	for (int i = 0; i < 15; ++i) {
		nested = "[" + nested + "]";
	}
	check("{\"x\":" + nested + "}", true);
	check("{\"x\":[" + nested + "]}", false);
	std::string many_values = "{\"x\":[0";
	for (int i = 0; i < 4094; ++i) {
		many_values += ",0";
	}
	check(many_values + "]}", false, 65536);
	std::cout << "Strict JSON boundary cases passed: " << checks << '\n';
}
