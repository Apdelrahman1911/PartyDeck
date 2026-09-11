# Bounded iOS frame phases

This diagnostic companion preserves the existing frameTiming version 1. It
does not grant readiness, performance acceptance, first display, GPU completion,
or stable activity. Native/Apple compilation and execution require their own
evidence; portable tests alone do not qualify this candidate.

The maintained iteration-phases engine patch is pinned by its manifest to
Godot ed1daf0bf001b61586d9930840f2f1394092c079 (4.7.2-stable).
It changes only core/os/os.h, core/os/os.cpp and main/main.cpp under IOS_ENABLED.
The non-iOS preprocessed statements and original frame-delay arithmetic remain
unchanged. The calling thread has a scoped observer only during a native
iteration; nested native scopes restore their predecessor. Unscoped reentry
or repeated/unmatched sleep events invalidate the companion for that sample.

## Wire contract

The qualification native object may add both framePhasesStatus and framePhases.
Historical v1 objects have neither. Status is available, unavailable, invalid,
or payload_budget; only available has a non-null companion. The companion has
exact keys schemaVersion (1), draw and iterate. Each stage is a list of at most
7 records, one per unique sample retained as last, maximum, four slow samples
and the first-release association. Phase values live in those same Sample
copies; there is no separate rolling ring.

Every record has exact keys scopeOrdinal, completedOrdinal, status, seenMask,
seconds and sleeps. The two canonical uint64 decimal ordinals join exactly one
sample in that stage of frameTiming. They inherit its uptime interval, owning
draw and full begin/end context, including old/mixed presentations. Missing,
extra, colliding or duplicate joins fail validation. A retained record cannot
change while that sample survives between observations in the same process.
Summary reports preserve the complete joined sample and phase record.

Record status is complete, unavailable or invalid. The latter two use null
seenMask, seconds and sleeps. Complete means the observed elapsed scope has
been partitioned; it does not mean every phase ran. seconds is a fixed vector
of finite nonnegative durations whose sum matches the sample within 1 microsecond.
seenMask has one bit per visited phase; an unvisited slot must be zero.

| Draw index | Inclusive region |
| --- | --- |
| 0 | Remaining draw work and instrumentation boundaries |
| 1 | UIKit pump, including ready callbacks and any nested work |
| 2 | setupView call |
| 3 | renderOnView call, including its engine iteration |
| 4 | presentRenderbuffer call and error query |
| 5 | endDrawPresented, including cover handling |

| Iteration index | Inclusive region |
| --- | --- |
| 0 | OS_AppleEmbedded::iterate before Main::iteration, including input |
| 1 | Main preparation, XR, physics, and pre-process input flushing |
| 2 | Scene process, message queue flush and navigation process |
| 3 | RenderingServer::sync |
| 4 | Render decision/draw and frame counters |
| 5 | Extensions, languages, audio, debugger and remaining work before pacing |
| 6 | Main's OS::add_frame_delay call and its argument evaluation |
| 7 | Main/OS return work after pacing or the fixed-FPS return |

Iteration visited masks are 1 (Main did not run), 191 (fixed-FPS path without
add_frame_delay), or 255 (add_frame_delay entered). Draw masks are bounded to
six bits with residual bit 0 set. Durations are inclusive of instrumentation
and any reentrant work within their region. Do not sum draw with iteration or
sleep with pacing. Neither sync nor draw measures completed GPU execution.

Draw sleeps is null. Iteration sleeps has exactly two entries, fixed then
dynamic, each [callCount, requestedUsec, elapsedSeconds]. callCount is 0 or 1.
requestedUsec is the exact uint32 value passed to delay_usec, encoded as a
canonical decimal string; existing conversion/overflow behavior is preserved.
A zero-call entry is [0, "0", 0]. A real call may pass zero after conversion.
Elapsed seconds are measured around delay_usec on the same system-uptime
clock, including scheduling and wrapper overhead. They are nested in phase 6
and their sum cannot exceed it. No relationship between requested and actual
duration is assumed. A missing pacing phase is distinct from entered pacing
with no sleep call. Effective max-FPS/low-processor settings are not exported.

Swift projects only these fixed fields, types and enum strings. The existing
32 KiB limit drops the phase companion first, with payload_budget status,
before using the existing frameTiming fallback. Privacy fields and existing
timing fields are not traded for the new data.

## Source and validation

Source boundaries: [main iteration](https://github.com/godotengine/godot/blob/ed1daf0bf001b61586d9930840f2f1394092c079/main/main.cpp#L4921),
[frame delay](https://github.com/godotengine/godot/blob/ed1daf0bf001b61586d9930840f2f1394092c079/core/os/os.cpp#L708),
[actual Unix delay](https://github.com/godotengine/godot/blob/ed1daf0bf001b61586d9930840f2f1394092c079/drivers/unix/os_unix.cpp#L382).
No dependency or platform scheduling behavior is inferred from elapsed values.

Focused portable tests are frame_timing_test.cpp and
scripts/tests/test_ios_frame_timing_validator_v1.py. The candidate handoff also
contains a reproducible host harness for the exact patched observer/runtime
scope and original/patched OS pacing body, including TLS isolation and uint32
conversion. Native Swift/Objective-C++ compilation, XCTest and device timing
remain separate unexecuted checks until explicitly run.
