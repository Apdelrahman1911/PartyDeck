"""Host-only malformed-container and recorder-gate regressions; no device claims."""
import json
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import smoke_android_godot_adaptive as runner


def atom(kind, data):
    return struct.pack(">I4s", len(data) + 8, kind) + data


def winscope(frames=3, version=2):
    times = struct.pack("<" + "Q" * frames, *(1_000_000 + n * 1000 for n in range(frames)))
    if version == 0:
        return b"#VV1NSC0PET1ME!#" + struct.pack("<I", frames) + times
    return b"#VV1NSC0PET1ME2#" + struct.pack("<IqI", version, 123456, frames) + times


def metadata_movie(path, legacy=None, modern=None, mime=b"application/octet-stream\0", offset_override=None):
    """Only metadata structures are source-shaped; this is not a real video."""
    legacy = winscope(version=0) if legacy is None else legacy
    modern = winscope() if modern is None else modern

    def track(track_id, payload=None, offset=0):
        header = atom(b"tkhd", struct.pack(">IIIIII", 0, 0, 0, track_id, 0, 0))
        if payload is None:
            return atom(b"trak", header)
        tables = atom(b"stsd", struct.pack(">II", 0, 1) + atom(b"mett", mime * 2))
        tables += atom(b"stsc", struct.pack(">IIIII", 0, 1, 1, 1, 1))
        tables += atom(b"stsz", struct.pack(">IIII", 0, 0, 1, len(payload)))
        tables += atom(b"co64", struct.pack(">IIQ", 0, 1, offset if offset_override is None else offset_override))
        return atom(b"trak", header + atom(b"mdia", atom(b"minf", atom(b"stbl", tables))))

    path.write_bytes(atom(b"mdat", legacy + modern) + atom(b"moov", track(1) + track(2, legacy, 8) + track(3, modern, 8 + len(legacy))))


def streams():
    return [dict(index=0, id="0x1", codec_type="video", codec_tag_string="avc1", width=1600, height=720, nb_read_frames="3"),
            dict(index=1, id="0x2", codec_type="data", codec_tag_string="mett"),
            dict(index=2, id="0x3", codec_type="data", codec_tag_string="mett")]


class ScreenrecordMetadataTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="partydeck-screenrecord-host-")
        self.addCleanup(temporary.cleanup)
        self.path = Path(temporary.name) / "synthetic-metadata-only.mp4"
        metadata_movie(self.path)

    def probe(self, observed=None, duration="1.0"):
        return subprocess.CompletedProcess([], 0, json.dumps(dict(streams=streams() if observed is None else observed,
                                                                  format=dict(duration=duration))), "")

    def test_only_exact_legacy_and_version_two_payloads_match_decoded_frame_count(self):
        result = runner.screenrecord_metadata(self.path, streams(), 3)
        self.assertEqual(["winscope_legacy", "winscope_v2"], [item["kind"] for item in result])
        self.assertEqual([44, 56], [item["sample_bytes"] for item in result])
        self.assertEqual([2, 3], [item["track_id"] for item in result])

    def test_audio_unknown_missing_or_additional_video_and_extra_data_are_rejected(self):
        cases = [streams() + [dict(codec_type="audio")], streams() + [dict(codec_type="unknown")],
                 streams()[1:], streams() + [dict(codec_type="video")], streams()[:2],
                 streams() + [dict(index=3, id="0x4", codec_type="data", codec_tag_string="mett")]]
        for observed in cases:
            with self.subTest(observed=observed), patch.object(runner.subprocess, "run", return_value=self.probe(observed)) as invoke:
                with self.assertRaises(runner.ObservationFailure):
                    runner.verify_video(self.path, 1600, 720, self.path.with_suffix(""))
                self.assertEqual(1, invoke.call_count)

    def test_arbitrary_mett_payloads_versions_mime_and_frame_counts_are_rejected(self):
        for change in [dict(legacy=b"not-winscope-data" + b"x" * 28), dict(modern=winscope(version=3)),
                       dict(modern=winscope(frames=4)), dict(modern=winscope()[:-1]),
                       dict(modern=winscope(version=0)), dict(mime=b"application/unknown\0")]:
            with self.subTest(change=change):
                metadata_movie(self.path, **change)
                original = self.path.read_bytes()
                with self.assertRaises(runner.ObservationFailure):
                    runner.screenrecord_metadata(self.path, streams(), 3)
                self.assertEqual(original, self.path.read_bytes())

    def test_track_binding_out_of_bounds_and_escaping_boxes_are_rejected(self):
        wrong = streams(); wrong[2]["id"] = "0x2"
        with self.assertRaises(runner.ObservationFailure): runner.screenrecord_metadata(self.path, wrong, 3)
        wrong = streams(); wrong[2]["codec_tag_string"] = "other"
        with self.assertRaises(runner.ObservationFailure): runner.screenrecord_metadata(self.path, wrong, 3)
        metadata_movie(self.path, offset_override=2**40)
        with self.assertRaises(runner.ObservationFailure): runner.screenrecord_metadata(self.path, streams(), 3)
        metadata_movie(self.path)
        self.path.write_bytes(struct.pack(">I", 0xffffffff) + self.path.read_bytes()[4:])
        with self.assertRaises(runner.ObservationFailure): runner.screenrecord_metadata(self.path, streams(), 3)

    def test_decode_preserves_demux_timing_and_retains_error_and_dimension_gates(self):
        success = subprocess.CompletedProcess([], 0, "", "")
        with patch.object(runner.subprocess, "run", side_effect=[self.probe(), success]) as invoke:
            result = runner.verify_video(self.path, 1600, 720, self.path.with_suffix(""))
        self.assertEqual(3, result["frames"])
        command = invoke.call_args_list[1].args[0]
        for option, value in [("-map", "0:v:0"), ("-fps_mode", "passthrough"), ("-enc_time_base", "demux")]:
            self.assertEqual(value, command[command.index(option) + 1])
        self.assertEqual([45, 45], [call.kwargs["timeout"] for call in invoke.call_args_list])
        for failed in [subprocess.CompletedProcess([], 1, "", ""), subprocess.CompletedProcess([], 0, "", "decoder error")]:
            original = self.path.read_bytes()
            with patch.object(runner.subprocess, "run", side_effect=[self.probe(), failed]), self.assertRaises(runner.ObservationFailure):
                runner.verify_video(self.path, 1600, 720, self.path.with_suffix(""))
            self.assertEqual(original, self.path.read_bytes())
        with patch.object(runner.subprocess, "run", return_value=self.probe()), self.assertRaises(runner.ObservationFailure):
            runner.verify_video(self.path, 720, 1600, self.path.with_suffix(""))
        with patch.object(runner.subprocess, "run", return_value=self.probe(duration="inf")), self.assertRaises(runner.ObservationFailure):
            runner.verify_video(self.path, 1600, 720, self.path.with_suffix(""))


class StartupObservationTests(unittest.TestCase):
    def exercise(self, sizes, has_identity=True):
        temporary = tempfile.TemporaryDirectory(prefix="partydeck-recorder-start-host-")
        self.addCleanup(temporary.cleanup)
        output = Path(temporary.name); (output / "videos").mkdir()
        clock = types.SimpleNamespace(value=0.0)
        identity = dict(pid=777, uid=2000, start_ticks=1234, name="/system/bin/screenrecord")
        seen_sizes = iter(sizes)
        state = dict(last_size=sizes[-1])
        recorder = None

        def command(*args, **kwargs):
            if args[:3] == ("shell", "test", "-e"):
                return subprocess.CompletedProcess(args, 1, "", "")
            if args[:2] == ("exec-out", "cat"):
                return subprocess.CompletedProcess(args, 0, b"\0".join(value.encode() for value in recorder.argv) + b"\0", b"")
            if args[:3] == ("shell", "stat", "-c"):
                state["last_size"] = next(seen_sizes, state["last_size"])
                return subprocess.CompletedProcess(args, 0, str(state["last_size"]), "")
            self.fail(f"Unexpected host-only recorder command: {args}")

        smoke = types.SimpleNamespace(output=output, serial="host-only", videos=[], command=command,
            pids=lambda name, **kwargs: [777] if has_identity else [], adb=lambda *args, **kwargs: "2000" if args == ("shell", "id", "-u") else "source-shaped synthetic process record",
            session=types.SimpleNamespace(utc_now=lambda: "host-only-time", parse_proc_identity=lambda *args: dict(identity)))
        recorder = runner.OriginalRecording(smoke, "startup", [1600, 720])
        self.addCleanup(lambda: [handle.close() for handle in recorder.handles])
        def sleep(seconds): clock.value += seconds
        with patch.object(runner.subprocess, "Popen", return_value=types.SimpleNamespace(poll=lambda: None)), \
             patch.object(runner.time, "monotonic", side_effect=lambda: clock.value), patch.object(runner.time, "sleep", side_effect=sleep):
            try:
                recorder.start()
                error = None
            except runner.Unavailable as caught:
                error = caught
        return recorder, clock.value, error

    def test_known_identity_and_stable_output_still_fail_at_existing_eight_seconds(self):
        recorder, elapsed, error = self.exercise([100])
        self.assertIsInstance(error, runner.Unavailable)
        self.assertEqual(8, elapsed)
        self.assertFalse(recorder.started_successfully)
        self.assertEqual("growth-not-observed", recorder.entry["startup_unavailable_condition"])
        self.assertEqual(32, len(recorder.entry["startup_observations"]))
        self.assertTrue(all(sample["identity"] == recorder.identity and sample["output_bytes"] == 100
                            for sample in recorder.entry["startup_observations"]))

    def test_missing_identity_is_separate_and_zero_to_positive_is_insufficient(self):
        recorder, elapsed, error = self.exercise([100], has_identity=False)
        self.assertIsInstance(error, runner.Unavailable)
        self.assertEqual((8, "identity-not-observed"), (elapsed, recorder.entry["startup_unavailable_condition"]))
        self.assertTrue(all(sample["identity"] is None for sample in recorder.entry["startup_observations"]))
        recorder, elapsed, error = self.exercise([0, 100])
        self.assertIsInstance(error, runner.Unavailable)
        self.assertEqual(8, elapsed)

    def test_two_positive_increasing_sizes_keep_existing_start_gate(self):
        recorder, elapsed, error = self.exercise([100, 101])
        self.assertIsNone(error)
        self.assertTrue(recorder.started_successfully)
        self.assertEqual([100, 101], recorder.entry["initial_file_sizes"])
        self.assertEqual(0.25, elapsed)


if __name__ == "__main__":
    unittest.main()
