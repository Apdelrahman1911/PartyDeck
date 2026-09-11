#include "../modules/partydeck_ios_probe/frame_timing.h"
#include <cassert>
#include <limits>

using namespace PDFrameTiming;
static Context context(Recorder &r, uint64_t presentation = 1, uint64_t lifecycle = 1) {
	Context c; c.presentation = presentation; c.lifecycle = lifecycle;
	c.input = lifecycle; c.draw = r.active_draw; c.flags = EligibleFlags;
	return c;
}
int main() {
	Recorder r; r.reset_presentation(1);
	auto outer = r.begin(Kind::Draw); auto begin = context(r);
	auto nested = r.begin(Kind::Draw); assert(r.active_draw == nested.ordinal);
	r.finish(nested, 1.0, 1.1, context(r), context(r));
	assert(r.active_draw == outer.ordinal);
	auto iteration = r.begin(Kind::Iterate);
	r.finish(iteration, 1.2, 2.3, context(r), context(r));
	r.mark_ready(2.31, context(r)); r.mark_native_release(2.32, context(r));
	assert(!r.first_release_draw.valid);
	r.finish(outer, 1.0, 2.4, begin, context(r));
	assert(r.first_release_draw.valid && r.first_release_draw.started < r.first_native_release.uptime);
	assert(r.first_release_draw.completed > r.first_native_release.uptime);
	assert(r.last_iteration_in_release_draw.ordinal == iteration.ordinal && r.active_draw == 0);
	// Equal-duration recurrence leaves maximum unchanged, but is counted.
	Recorder recurring; recurring.reset_presentation(1);
	for (int i = 0; i < 5; ++i) {
		auto t = recurring.begin(Kind::Draw); auto c = context(recurring);
		recurring.finish(t, 10.0 + i * 2, 11.0 + i * 2, c, c);
	}
	assert(recurring.draw.slow == 5 && recurring.draw.retained == 4 && recurring.draw.overwritten == 1);
	assert(recurring.draw.maximum.ordinal == 1 && recurring.draw.ordered(0).ordinal == 2);
	// Lifecycle changes are retained as two identities, not rewritten to the end identity.
	auto mixed = recurring.begin(Kind::Draw); auto old_context = context(recurring, 1, 1);
	auto next_context = context(recurring, 1, 2);
	recurring.finish(mixed, 30, 32, old_context, next_context);
	assert(recurring.draw.last.begin.lifecycle == 1 && recurring.draw.last.end.lifecycle == 2);
	// Even a marker supplied for a new presentation cannot adopt an old in-flight draw.
	Recorder transition; transition.reset_presentation(1);
	auto old = transition.begin(Kind::Draw); auto old_begin = context(transition, 1);
	transition.reset_presentation(2); auto new_end = context(transition, 2);
	transition.mark_native_release(41, new_end);
	transition.finish(old, 40, 42, old_begin, new_end);
	assert(!transition.first_release_draw.valid);
	assert(transition.draw.last.begin.presentation == 1 && transition.draw.last.end.presentation == 2);
	// Invalid clocks and exhausted diagnostic counters do not become zero-duration passes.
	auto invalid = transition.begin(Kind::Iterate); auto c = context(transition, 2);
	transition.finish(invalid, 5, 4, c, c);
	assert(!transition.iterate.last.valid && transition.iterate.invalid == 1);
	auto nonfinite = transition.begin(Kind::Iterate);
	transition.finish(nonfinite, 5, std::numeric_limits<double>::infinity(), c, c);
	assert(!transition.iterate.last.valid && transition.iterate.invalid == 2);
	auto nan_start = transition.begin(Kind::Iterate);
	transition.finish(nan_start, std::numeric_limits<double>::quiet_NaN(), 6, c, c);
	assert(!transition.iterate.last.valid && transition.iterate.invalid == 3);
	transition.iterate.started = std::numeric_limits<uint64_t>::max();
	auto exhausted = transition.begin(Kind::Iterate);
	assert(exhausted.ordinal == 0 && transition.iterate.exhausted);
	transition.finish(exhausted, 6, 7, c, c);
	assert(!transition.iterate.last.valid && transition.iterate.invalid == 4);
	// Ineligible contexts cannot create a first native release marker.
	Recorder covered; covered.reset_presentation(1);
	auto covered_draw = covered.begin(Kind::Draw); auto covered_context = context(covered);
	covered_context.flags |= Covered;
	covered.mark_native_release(8, covered_context);
	assert(!covered.first_native_release.valid);
	covered.finish(covered_draw, 7, 9, covered_context, covered_context);
}
