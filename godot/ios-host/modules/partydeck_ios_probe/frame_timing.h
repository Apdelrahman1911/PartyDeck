#ifndef PARTYDECK_FRAME_TIMING_H
#define PARTYDECK_FRAME_TIMING_H

#include <array>
#include <cstddef>
#include <cmath>
#include <cstdint>
#include <limits>

// Fixed numeric diagnostics. This recorder has no engine, input, authority,
// lifecycle, allocation, clock or scheduling API. Callers supply clock samples.
namespace PDFrameTiming {
using std::size_t;
constexpr uint16_t Active = 1, Foreground = 2, Applied = 4, Ready = 8;
constexpr uint16_t Covered = 16, Maintenance = 32, Terminal = 64;
constexpr uint16_t ApplicationActive = 128, Retained = 256, KnownFlags = 511;
constexpr uint16_t EligibleFlags = Active | Foreground | Applied | Ready | ApplicationActive | Retained;
constexpr double SlowSeconds = 1.0; // Diagnostic filter; not a performance budget.
constexpr size_t Capacity = 4;
enum class Kind { Draw, Iterate };

struct Context {
	uint64_t presentation = 0, lifecycle = 0, input = 0, draw = 0;
	uint64_t presented = 0, iterations = 0, covers = 0;
	uint16_t flags = 0;
	bool eligible() const {
		return (flags & EligibleFlags) == EligibleFlags && !(flags & (Covered | Maintenance | Terminal));
	}
};

// A partition of ONE inclusive scope. Draw has 6 slots; Iterate has 8.
// Overlapping draw/iteration samples and pacing/sleep MUST NOT be added.
enum class PhaseStatus { Unavailable, Complete, Invalid };
struct Sleep {
	uint32_t calls = 0, requested_usec = 0;
	double seconds = 0;
};
struct Phases {
	PhaseStatus status = PhaseStatus::Unavailable;
	uint16_t seen = 0;
	std::array<double, 8> seconds{};
	std::array<Sleep, 2> sleeps{}; // fixed, dynamic; exact post-conversion requests
};
struct PhaseClock {
	Phases value;
	uint8_t current = 0;
	double last = 0, observed = 0, sleep_started = 0;
	int sleeping = -1;
	explicit PhaseClock(double now) : last(now), observed(now) {
		value.status = std::isfinite(now) && now >= 0 ? PhaseStatus::Complete : PhaseStatus::Invalid;
		value.seen = 1;
	}
	void invalidate() { value.status = PhaseStatus::Invalid; }
	void change(uint8_t next, double now) {
		if (value.status != PhaseStatus::Complete) { return; }
		if (next >= value.seconds.size() || sleeping != -1 || !std::isfinite(now) || now < observed ||
			!std::isfinite(value.seconds[current] + (now - last))) { invalidate(); return; }
		value.seconds[current] += now - last;
		last = observed = now; current = next; value.seen |= uint16_t(1) << next;
	}
	void begin_sleep(size_t kind, uint32_t request_usec, double now) {
		if (value.status != PhaseStatus::Complete) { return; }
		if (kind >= value.sleeps.size() || sleeping != -1 || current != 6 ||
			value.sleeps[kind].calls != 0 || !std::isfinite(now) || now < observed) { invalidate(); return; }
		value.sleeps[kind] = {1, request_usec, 0};
		sleeping = static_cast<int>(kind); sleep_started = observed = now;
	}
	void end_sleep(double now) {
		if (value.status != PhaseStatus::Complete) { return; }
		if (sleeping == -1 || !std::isfinite(now) || now < observed ||
			!std::isfinite(now - sleep_started)) { invalidate(); return; }
		value.sleeps[sleeping].seconds = now - sleep_started;
		sleeping = -1; observed = now;
	}
	Phases finish(double now) {
		change(current, now);
		if (sleeping != -1) { invalidate(); }
		return value;
	}
};

struct Sample {
	bool valid = false;
	uint64_t ordinal = 0, completed_ordinal = 0;
	double started = 0, completed = 0, seconds = 0;
	Context begin, end;
	Phases phases;
};

struct Stage {
	uint64_t started = 0, completed = 0, slow = 0, overwritten = 0, invalid = 0;
	bool exhausted = false;
	size_t retained = 0, next = 0;
	Sample last, maximum;
	std::array<Sample, Capacity> samples{};

	uint64_t increment(uint64_t &value) {
		if (value == std::numeric_limits<uint64_t>::max()) { exhausted = true; return 0; }
		return ++value;
	}
	Sample finish(uint64_t ordinal, double started_at, double completed_at, Context begin, Context end, Phases phases = {}) {
		Sample value;
		value.ordinal = ordinal;
		value.completed_ordinal = increment(completed);
		value.valid = ordinal != 0 && value.completed_ordinal != 0 &&
			std::isfinite(started_at) && std::isfinite(completed_at) && started_at >= 0 &&
			completed_at >= started_at && std::isfinite(completed_at - started_at);
		if (!value.valid) { increment(invalid); last = value; return value; }
		value.started = started_at; value.completed = completed_at;
		value.seconds = completed_at - started_at;
		value.begin = begin; value.end = end; value.phases = phases;
		last = value;
		if (!maximum.valid || value.seconds > maximum.seconds) { maximum = value; }
		if (value.seconds >= SlowSeconds) {
			increment(slow);
			if (retained == Capacity) { increment(overwritten); }
			else { ++retained; }
			samples[next] = value;
			next = (next + 1) % Capacity;
		}
		return value;
	}
	const Sample &ordered(size_t index) const {
		return samples[(next + Capacity - retained + index) % Capacity];
	}
};

struct Marker {
	bool valid = false;
	double uptime = 0;
	Context context;
};

struct Token {
	Kind kind;
	uint64_t ordinal = 0, previous_draw = 0;
};

struct Recorder {
	Stage draw, iterate;
	uint64_t active_draw = 0, presentation = 0;
	Marker ready, first_native_release;
	Sample first_release_draw, last_iteration_in_release_draw;

	Stage &stage(Kind kind) { return kind == Kind::Draw ? draw : iterate; }
	Token begin(Kind kind) {
		Token token{kind, 0, active_draw};
		Stage &value = stage(kind);
		token.ordinal = value.increment(value.started);
		if (kind == Kind::Draw) { active_draw = token.ordinal; }
		return token;
	}
	void finish(Token token, double started_at, double completed_at, Context begin, Context end, Phases phases = {}) {
		Sample sample = stage(token.kind).finish(token.ordinal, started_at, completed_at, begin, end, phases);
		if (token.kind == Kind::Draw) {
			// A nested UIKit call can change lifetime while the scope is open.
			// A closing/old scope must never fill the next presentation's marker.
			if (sample.valid && first_native_release.valid && !first_release_draw.valid &&
				begin.presentation == presentation && end.presentation == presentation &&
				token.ordinal == first_native_release.context.draw) {
				first_release_draw = sample;
			}
			active_draw = token.previous_draw;
		}
	}
	void reset_presentation(uint64_t generation) {
		presentation = generation;
		ready = {}; first_native_release = {};
		first_release_draw = {}; last_iteration_in_release_draw = {};
		// Lifetime counters and bounded samples keep their own begin/end IDs.
		// Do not reset active_draw: an old scope may still have to restore it.
	}
	void mark_ready(double now, Context context) {
		if (!ready.valid && presentation != 0 && context.presentation == presentation &&
			(context.flags & (Active | Ready)) == (Active | Ready) && std::isfinite(now) && now >= 0) {
			ready = {true, now, context};
		}
	}
	void mark_native_release(double now, Context context) {
		if (first_native_release.valid || presentation == 0 || context.presentation != presentation ||
			context.draw == 0 || !context.eligible() || !std::isfinite(now) || now < 0) { return; }
		first_native_release = {true, now, context};
		const Sample &last = iterate.last;
		if (last.valid && last.begin.presentation == presentation && last.end.presentation == presentation &&
			last.begin.draw == context.draw && last.end.draw == context.draw) {
			last_iteration_in_release_draw = last;
		}
		// The owning draw is still in flight here. finish() publishes it later.
	}
};
} // namespace PDFrameTiming
#endif
