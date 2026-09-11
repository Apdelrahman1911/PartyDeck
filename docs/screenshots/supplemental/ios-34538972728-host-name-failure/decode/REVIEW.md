The ordinary iOS failure recording shows the field eventually reaching **Native Host**. A typing tutorial covers the normal keyboard area throughout the key checkpoints. The retained sequence contains **Guest → Gues → Native Host**, with an end caret visible in each inspected text state. This establishes eventual visual replacement; the overlay alone does not establish permanent input blocking.

Source: Validate run **34538972728**, attempt1, commit **dd6df8a530d71b51ae4c3b0f4a05246f2e58402f**, `PartyDeckUITests/testSharedControllerHostsANativeTableAndShowsItsInvitation()`. The original line59 assertion read `Gues` while expecting `Native Host`; its failed result is unchanged. The original3,255,255-byte movie SHA-256 is `2c86f1c16af32595a022327f3e059d8f4e131043406ce941cf28d289b8820e9d`.

Use `frame-manifest-v3.json` for image identities and original packet times. The v1 files retain the failed initial metadata-parser diagnostics; v2 is the explicitly provisional showinfo-only binding. The twelve images below were directly viewed by ui_game. Other reviewers share these exact immutable derivatives.

| PNG ordinal | Decoded source frame n | Original packet PTS /600 | Media seconds | Visible checkpoint |
| --- | --- | --- | --- | --- |
| 002 | 143 | 5610/600 | 9.350000 | Home screen. |
| 003 | 144 | 5618/600 | 9.363333 | Home screen. |
| 004 | 148 | 10047/600 | 16.745000 | Guest; unfocused outline; keyboard absent. |
| 006 | 176 | 11068/600 | 18.446667 | Guest; focused outline; iOS typing tutorial sheet with Continue covers normal keyboard area. |
| 007 | 182 | 12247/600 | 20.411667 | Guest; focused outline; tutorial remains. |
| 008 | 183 | 12266/600 | 20.443333 | Guest; focused outline; tutorial remains. |
| 012 | 187 | 12809/600 | 21.348333 | Guest; visible caret after t; tutorial remains. |
| 040 | 215 | 14899/600 | 24.831667 | Gues; visible caret after s; tutorial remains. |
| 053 | 228 | 15283/600 | 25.471667 | Native Host; visible caret at end; tutorial remains. |
| 065 | 240 | 15519/600 | 25.865000 | Native Host; visible caret at end; tutorial remains. |
| 078 | 253 | 15708/600 | 26.180000 | Native Host; caret not visible in this image; tutorial remains. |
| 083 | 258 | 15906/600 | 26.510000 | Final decoded source frame: Native Host with end caret; tutorial remains. |

The movie is1206×2622, H.264 High, variable frame rate, time base1/600, and26.54 seconds long. FFmpeg/ffprobe are6.1.1-3ubuntu5. Exactly one video decode ran, producing84 full-resolution RGB PNGs totaling39,638,112 bytes. The shared V5 lease used owner `engine_ci`, actor `ui_game`, a64 MiB output allowance, and a256 MiB memory reserve. The additional in-lease `/tmp` floor check passed. Original movie bytes stayed in place and rehashed unchanged.

The actual decode completed with exit0. Its wrapper returned1 only because the initial postprocessing parser expected an older showinfo format and the wrong frame-rate field. Reparsing the existing log repaired metadata; no video decode was repeated. All259 decoded source frames,84 selected log entries,84 complete PNG CRCs and84 file hashes were checked. Rounded output-muxer timestamp warnings did not lose images; retain image ordinal and manifest times rather than encoder DTS.

A timestamp correction was necessary. FFmpeg selects `best_effort_timestamp` before the filter; duplicate original packet PTS caused the filter to use mostly DTS-based values. The time-based sampling therefore retained source frames0,1,143,144,148,156,176 and182–258, rather than every original-media frame from14–22 seconds. Both filter timestamps and original packet PTS are preserved. The original packet-to-frame mapping was recovered by parsing H.264 SPS/PPS and picture-order headers only:9 IDR epochs with unique contiguous POC, no wrap, and matching picture type/keyframe flags for all259 decoded frames. `verify-picture-metadata.py` reproduces this check without invoking a video decoder. The upstream FFmpeg6.1.1 source explanations and hashes are retained in `upstream-ffmpeg-6.1.1/`.

No authoritative media-PTS-to-XCTest or media-PTS-to-UTC anchor has been established. Attachment timestamps and coarse container creation time are context only. The pictures demonstrate eventual replacement, but do not establish exactly when the failed assertion read relative to that replacement. This review does not claim a rerun pass or physical-device qualification.
