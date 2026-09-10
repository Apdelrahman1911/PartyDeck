# iOS CoreAudio dormancy patch

[coreaudio-dormancy.patch](coreaudio-dormancy.patch) adds native observations and
closed-playback retirement for the retained-engine contract in
[DORMANCY.md](../DORMANCY.md). Its exact base is Godot 4.7.2 commit
`ed1daf0bf001b61586d9930840f2f1394092c079`. The patch changes four files under
`IOS_ENABLED`: the CoreAudio driver header/implementation and the AudioServer
header/implementation. The API is private to native integration and has no
ClassDB bindings.

[coreaudio-dormancy.json](coreaudio-dormancy.json) records the patch SHA-256,
the original and patched SHA-256 of every file, and full Git blob hashes. Build
tooling must verify all original hashes before applying the patch to an
isolated engine copy, then verify all patched hashes. The shared `build/upstream`
checkout is a read-only reference. A changed upstream commit requires another
source review even when patch context still applies.

The public driver API is:

```cpp
AudioDriverCoreAudio::PartyDeckOutputState get_partydeck_output_state() const;
Error partydeck_retire_closed_playbacks(PartyDeckRetirement &r_result);
// AudioDriverCoreAudio::PartyDeckRetirement aliases AudioServer::PartyDeckRetirement.
```

Both result types contain only scalar fields. Call both methods on the main
thread. The native owner must serialize output/input unit lifetime with these
calls; the getter does not read unit pointers from another thread. Callback
counts and the actual driver `active` flag are lock-free atomics. Compile-time
assertions require lock-free `bool`, `uint32_t`, `uint64_t` and `OSStatus` atomics
for the selected iOS target.

| Output-state field | Meaning |
| --- | --- |
| `observed_on_main_thread` | False means the observation is invalid; the other fields remain zero. |
| `output_unit_present`, `input_unit_present` | Presence of the driver's actual AudioUnit instances. |
| `active` | The actual atomic driver flag. Interpret it with unit presence and OSStatus. |
| `output_callback_entries` | Every output callback entry, including inactive and failed-try-lock paths that return silence. |
| `output_callbacks_in_flight` | Incremented at entry and decremented by a stack guard on every return path. |
| `start_attempts`, `stop_attempts` | Counters increment around actual output `AudioOutputUnitStart` / `AudioOutputUnitStop` calls. Zero means unattempted. |
| `last_start_status`, `last_stop_status` | OSStatus from the most recent corresponding call. A default zero status with zero attempts is not a successful attempt. |
| `stopped_start_attempt` | Start-attempt counter captured by the latest successful stop for this output unit. It is cleared when a new output unit is created. |

The getter is a set of atomic observations, not a transaction across fields.
The native owner must compare callback counts across a real covered native-shell
interval before reporting dormancy. A completed hook call cannot guarantee that
no later callback will arrive.

The added output-callback work consists only of lock-free atomic increments and
the stack guard's decrement. It adds no allocation, logging, Godot calls, mutex
waits or callback dispatch. The existing output callback continues to use
`try_lock()`. Input is unsupported by this retirement path. The iOS terminal
`finish()` path calls the instrumented output `stop()` before taking the driver
mutex, so an output stop never waits for callbacks while holding that mutex.
Other platforms retain their original source behavior.

Before calling retirement, the native owner must establish all of these facts:

- Its old presentation/authority gates and input producers are closed, and the
  surface remains covered.
- The call is outside draw, engine iteration, delivery and deferred-flush
  scopes. The complete old scene has been destroyed, including its audio nodes.
- No engine, worker, script or native producer can mutate AudioServer lists or
  resume audio until retirement and the subsequent dormancy interval finish.
- The selected driver is this CoreAudio instance. Existing `stop()` has returned
  successfully for the current start interval, the output unit remains present,
  `active` is false, and no output callback is in flight.
- Audio input remains disabled in project configuration and AudioServer, with
  no input unit present.

The driver's recursive mutex does not serialize every lock-free list producer.
These owner guarantees are required even though the hook rechecks driver state,
selection, input configuration and callback counters under the mutex. The hook
does not call `stop()` or wait for callbacks itself.

Under that mutex, the AudioServer phase first validates one Master bus, its
matching map entry, the expected channel/buffer shape, default send/volume/solo/
bypass settings, and empty effect/effect-instance arrays. Master mute may vary.
All live mix, update and listener callbacks and all native sample playbacks must
be absent.

It then preflights every current live playback-list node, up to 64, before any
mutation. Each must have valid distinct bus-detail pointers and be an exact
builtin `AudioStreamPlaybackWAV` with no script instance, native sample flag or
sample handle. Only `FADE_OUT_TO_DELETION` and `AWAITING_DELETION` are accepted.
Playing, paused and pause-fading nodes are rejected. The imported `.sample`
resource suffix is compatible with an ordinary builtin WAV; native sample mode
is checked through the playback API.

After the complete preflight, the patch reuses the unchanged
`_delete_stream_playback_list_node()` helper. It clears Master channel samples,
`used`/`active`/last-audio metadata, peak values to the upstream silence value,
the mixer scratch buffers, and `to_mix`. It also clears the driver's retained
output sample vector. These buffers are read back to confirm neutrality.
Resetting `to_mix` matters because `_driver_process()` can otherwise copy an
already-mixed portion of the previous bus buffer after playback removal.

Every SafeList iterator scope and the driver mutex end before cleanup.
Main-thread cleanup checks the return value of `maybe_cleanup()` for the
playback list and all three callback lists. It retires and checks both live
bus-detail graveyard generations without calling the normal one-generation
transfer helper. Failed playback/callback cleanup prevents that later bus-detail
mutation. There is no generic SafeList or MessageQueue clear operation.

| Retirement-result field | Meaning |
| --- | --- |
| `preflight_passed`, `live_playbacks_before` | The complete supported live list passed preflight; the count is valid when the flag is true. |
| `unlinked_playbacks` | Nodes sent through the existing logical deletion helper during this call. |
| `retired_playbacks` | Those live nodes whose registered cleanup callbacks completed, including release of the AudioServer playback reference. Assigned only after successful playback cleanup. |
| `playback_cleanup_succeeded` | The playback SafeList accepted and completed cleanup. |
| `callback_cleanup_succeeded` | All three callback SafeLists accepted and completed cleanup. |
| `bus_details_cleanup_succeeded`, `old_bus_details_cleanup_succeeded` | Both bus-detail generations accepted and completed cleanup. |
| `residuals_observed` | The final live-list and buffer observations were reached. |
| `playbacks_remaining`, `callbacks_remaining`, `bus_details_remaining`, `sample_playbacks_remaining` | Final observed live entries. Hidden SafeList graveyards are covered by the cleanup results. |
| `server_buffers_neutral`, `driver_buffer_neutral` | Current retained output samples and the described metadata were zeroed/reset and checked. |
| `driver_quiescent` | The final observed driver state still qualifies, with unchanged callback/start/stop counters across the hook's checks. |

`retired_playbacks` counts newly retired live AudioServer nodes. Cleanup may also
destroy nodes already in a hidden graveyard; those are not included in this
count. Releasing the server's reference does not prove that arbitrary external
references were absent. The fixed-content lifetime contract rules out historical
custom playback classes, scripted resources, persistent recipient-bearing
holders and new work during cleanup. The live preflight cannot inspect private
SafeList graveyards. The 64-node cap is therefore neither a total-work cap nor a
deadline for all pending destructor/history work.

Any non-`OK` result requires the native owner to quarantine the retained engine
and refuse re-entry. A failure can occur after logical retirement or some
destructors have completed, so callers must not treat it as an unchanged state.
`ERR_INVALID_PARAMETER` covers the wrong thread or invalid cleanup phase;
`ERR_UNAVAILABLE` covers unsupported driver/content/configuration;
`ERR_INVALID_DATA` covers invalid data/buffer shape; and `ERR_BUSY` covers active,
unqualified or changing driver/playback state or incomplete cleanup. Receipt
flags identify which observations completed.

Linux structural validation applied and reversed the deterministic patch with
zero fuzz, checked every resulting byte hash and full-index identity, confirmed
that the existing deletion/normal-cleanup helpers are unchanged, and compared
the non-iOS source projection with pristine upstream. Evidence is retained in
`build/audio-patch-draft/validation-v2/`. The first validator run rejected Git's
expected no-index difference exit code; its log remains in `validation-v1/`.
Independent security review accepted the frozen patch source and all four
original/patched file hashes under the documented fixed-content and excluded-producer
contract. Apple SDK compilation, actual AudioUnit results/callback timing, native
owner enforcement and retained-engine re-entry still require the native owner's
build and qualification. Buffer neutralization is a no-replay measure;
it does not promise secure heap/GPU erasure, zero retained memory or hardware
power measurements.

Checked sources are pinned to the same engine commit:

- [CoreAudio driver](https://github.com/godotengine/godot/blob/ed1daf0bf001b61586d9930840f2f1394092c079/drivers/coreaudio/audio_driver_coreaudio.mm)
  and [header](https://github.com/godotengine/godot/blob/ed1daf0bf001b61586d9930840f2f1394092c079/drivers/coreaudio/audio_driver_coreaudio.h): output/input callbacks, actual start/stop/finish and mutex behavior.
- [AudioServer](https://github.com/godotengine/godot/blob/ed1daf0bf001b61586d9930840f2f1394092c079/servers/audio/audio_server.cpp)
  and [header](https://github.com/godotengine/godot/blob/ed1daf0bf001b61586d9930840f2f1394092c079/servers/audio/audio_server.h): playback states, deletion ownership, mixing buffers, sample/callback lists and cleanup generations.
- [SafeList](https://github.com/godotengine/godot/blob/ed1daf0bf001b61586d9930840f2f1394092c079/core/templates/safe_list.h): logical erase, iterator lifetime and checked destructor pass.
- [WAV playback](https://github.com/godotengine/godot/blob/ed1daf0bf001b61586d9930840f2f1394092c079/scene/resources/audio_stream_wav.cpp)
  and [header](https://github.com/godotengine/godot/blob/ed1daf0bf001b61586d9930840f2f1394092c079/scene/resources/audio_stream_wav.h): builtin class and independent sample flag/handle.
- [Object type/script lookup](https://github.com/godotengine/godot/blob/ed1daf0bf001b61586d9930840f2f1394092c079/core/object/object.cpp),
  [thread identity](https://github.com/godotengine/godot/blob/ed1daf0bf001b61586d9930840f2f1394092c079/core/os/thread.h)
  and [recursive mutex](https://github.com/godotengine/godot/blob/ed1daf0bf001b61586d9930840f2f1394092c079/core/os/mutex.h): exact builtin-class filtering and main-thread/lock preconditions.
