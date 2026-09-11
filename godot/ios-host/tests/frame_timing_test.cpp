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
	// One scope is partitioned; observed delay wrappers remain nested in pacing.
	PhaseClock partition(10);
	partition.change(1, 11); partition.change(2, 12);
	partition.change(3, 13); partition.change(4, 14); partition.change(5, 15);
	partition.change(6, 16);
	partition.begin_sleep(0, UINT32_MAX, 16.1); partition.end_sleep(16.2);
	partition.begin_sleep(1, 0, 16.3); partition.end_sleep(16.5);
	partition.change(7, 17);
	auto parts = partition.finish(18);
	assert(parts.status == PhaseStatus::Complete && parts.seen == 255);
	for (double seconds : parts.seconds) { assert(seconds == 1); }
	assert(parts.sleeps[0].calls == 1 && parts.sleeps[0].requested_usec == UINT32_MAX);
	assert(parts.sleeps[1].calls == 1 && parts.sleeps[1].requested_usec == 0);
	assert(std::abs(parts.sleeps[0].seconds + parts.sleeps[1].seconds - 0.3) < 1e-9);
	// These are different observations: no pacing, pacing with no call, unknown.
	PhaseClock skipped(0), no_call(0);
	no_call.change(6, 1);
	auto skipped_value = skipped.finish(2), no_call_value = no_call.finish(2);
	assert(!(skipped_value.seen & 64) && (no_call_value.seen & 64));
	assert(no_call_value.sleeps[0].calls == 0 && no_call_value.sleeps[1].calls == 0);
	assert(Phases{}.status == PhaseStatus::Unavailable);
	// Clock reversals across sleep boundaries, repeated calls and missing ends
	// invalidate only the companion; they cannot fabricate zero elapsed time.
	PhaseClock repeated(0); repeated.change(6, 1);
	repeated.begin_sleep(0, 1000, 1); repeated.end_sleep(2); repeated.begin_sleep(0, 2000, 2);
	assert(repeated.finish(3).status == PhaseStatus::Invalid);
	PhaseClock reversed(0); reversed.change(6, 1);
	reversed.begin_sleep(1, 100, 2); reversed.end_sleep(3); reversed.change(7, 2.5);
	assert(reversed.finish(4).status == PhaseStatus::Invalid);
	PhaseClock missing_end(0); missing_end.change(6, 1); missing_end.begin_sleep(0, 1, 2);
	assert(missing_end.finish(3).status == PhaseStatus::Invalid);
	PhaseClock outside_pacing(0); outside_pacing.begin_sleep(0, 1, 1);
	assert(outside_pacing.finish(2).status == PhaseStatus::Invalid);
	PhaseClock nonfinite_phase(0); nonfinite_phase.change(1, std::numeric_limits<double>::infinity());
	assert(nonfinite_phase.finish(2).status == PhaseStatus::Invalid);
	PhaseClock bad_phase(0); bad_phase.change(8, 1);
	assert(bad_phase.finish(2).status == PhaseStatus::Invalid);
	// Sample-owned phase values follow the original nested/first-release joins.
	Recorder joined; joined.reset_presentation(1);
	auto parent = joined.begin(Kind::Draw); auto parent_begin = context(joined);
	PhaseClock parent_clock(10); parent_clock.change(1, 11);
	auto child = joined.begin(Kind::Draw); auto child_context = context(joined);
	PhaseClock child_clock(11); child_clock.change(3, 11.25);
	joined.finish(child, 11, 12, child_context, child_context, child_clock.finish(12));
	assert(joined.active_draw == parent.ordinal && joined.draw.last.phases.seconds[3] == 0.75);
	auto iter = joined.begin(Kind::Iterate); auto iter_context = context(joined);
	joined.finish(iter, 12, 20, iter_context, iter_context, parts);
	joined.mark_native_release(20.5, context(joined));
	joined.finish(parent, 10, 21, parent_begin, context(joined), parent_clock.finish(21));
	assert(joined.first_release_draw.ordinal == parent.ordinal);
	assert(joined.first_release_draw.phases.seconds[1] == 10);
	assert(joined.last_iteration_in_release_draw.ordinal == iter.ordinal);
	assert(joined.last_iteration_in_release_draw.phases.sleeps[0].requested_usec == UINT32_MAX);
	assert(joined.draw.ordered(0).ordinal == child.ordinal && joined.draw.ordered(0).phases.seconds[3] == 0.75);
	joined.reset_presentation(2);
	assert(!joined.first_release_draw.valid && joined.draw.maximum.phases.seconds[1] == 10);
	assert(joined.draw.maximum.begin.presentation == 1);
}
