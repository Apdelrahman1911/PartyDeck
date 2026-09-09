#!/usr/bin/env python3
"""Synthesize PartyDeck's original, sample-free interface and game sound cues.

Uses only the Python standard library. No audio is downloaded or recorded.
All output is mono PCM16 WAVE, at 44.1 kHz, with bounded peaks and clean tails.
"""

from array import array
from hashlib import sha256
import json
from math import cos, exp, log, log10, pi, sin, sqrt
from pathlib import Path
import random
import sys
import wave


ROOT = Path(__file__).resolve().parents[2]
DESTINATION = ROOT / "composeApp/src/commonMain/composeResources/files/audio"
SAMPLE_RATE = 44_100


def buffer(duration: float) -> list[float]:
    return [0.0] * round(duration * SAMPLE_RATE)


def edge(time: float, length: float, attack: float = 0.004, release: float = 0.020) -> float:
    """Smooth envelope edges prevent clicks without erasing the tactile attack."""
    if time < 0 or time >= length:
        return 0.0
    rise = 0.5 - 0.5 * cos(pi * min(1.0, time / attack))
    fall = 0.5 - 0.5 * cos(pi * min(1.0, (length - time) / release))
    return rise * fall


def struck(
    out: list[float],
    start: float,
    length: float,
    frequency: float,
    gain: float,
    *,
    decay: float = 8.0,
    partials: tuple[tuple[float, float], ...] = ((1.0, 1.0), (2.02, 0.26), (3.91, 0.07)),
) -> None:
    offset = round(start * SAMPLE_RATE)
    count = min(round(length * SAMPLE_RATE), len(out) - offset)
    for sample in range(max(0, count)):
        t = sample / SAMPLE_RATE
        sound = sum(
            strength * sin(2 * pi * frequency * ratio * t) * exp(-decay * (1 + 0.15 * index) * t)
            for index, (ratio, strength) in enumerate(partials)
        )
        out[offset + sample] += gain * sound * edge(t, length)


def brush(
    out: list[float],
    start: float,
    length: float,
    gain: float,
    seed: int,
    *,
    low: float = 800,
    high: float = 5_800,
    swell: bool = False,
) -> None:
    rng = random.Random(seed)
    offset = round(start * SAMPLE_RATE)
    count = min(round(length * SAMPLE_RATE), len(out) - offset)
    low_state = high_state = 0.0
    low_alpha = 1 - exp(-2 * pi * low / SAMPLE_RATE)
    high_alpha = 1 - exp(-2 * pi * high / SAMPLE_RATE)
    for sample in range(max(0, count)):
        t = sample / SAMPLE_RATE
        noise = rng.uniform(-1, 1)
        low_state += low_alpha * (noise - low_state)
        high_state += high_alpha * (noise - high_state)
        envelope = sin(pi * t / length) ** 1.7 if swell else exp(-32 * t)
        out[offset + sample] += gain * (high_state - low_state) * envelope * edge(t, length, 0.003, 0.018)


def falling_tone(out: list[float], start: float, length: float, gain: float) -> None:
    offset = round(start * SAMPLE_RATE)
    count = min(round(length * SAMPLE_RATE), len(out) - offset)
    start_hz, end_hz = 340.0, 146.83
    ratio = log(end_hz / start_hz) / length
    for sample in range(max(0, count)):
        t = sample / SAMPLE_RATE
        phase = 2 * pi * start_hz * (exp(ratio * t) - 1) / ratio
        tone = sin(phase) + 0.12 * sin(phase * 2)
        out[offset + sample] += gain * tone * exp(-6.5 * t) * edge(t, length, 0.012, 0.08)


def build_cues() -> list[tuple[str, str, list[float], float, str]]:
    tap = buffer(0.070)
    brush(tap, 0, 0.044, 0.32, 4101, low=1_000, high=6_400)
    struck(tap, 0, 0.060, 1_160, 0.17, decay=90, partials=((1, 1), (1.72, 0.14)))

    card = buffer(0.240)
    brush(card, 0, 0.140, 0.34, 4102, low=600, high=5_800, swell=True)
    brush(card, 0.082, 0.115, 0.29, 4103, low=330, high=3_400)
    struck(card, 0.080, 0.155, 205, 0.14, decay=34, partials=((1, 1), (2.35, 0.42), (4.1, 0.12)))
    struck(card, 0.117, 0.092, 760, 0.034, decay=60)

    challenge = buffer(0.480)
    for start, gain, frequency in ((0.010, 0.21, 196), (0.157, 0.32, 174.61)):
        struck(challenge, start, 0.27, frequency, gain, decay=19, partials=((1, 1), (2.47, 0.27), (4.62, 0.08)))
        brush(challenge, start, 0.055, gain * 0.7, 5100 + round(start * 1_000), low=1_200, high=5_200)
    struck(challenge, 0.160, 0.315, 130.81, 0.065, decay=13, partials=((1, 1),))

    safe = buffer(0.640)
    struck(safe, 0.010, 0.570, 523.25, 0.16, decay=7.0)
    struck(safe, 0.095, 0.540, 698.46, 0.145, decay=7.5)
    struck(safe, 0.050, 0.585, 349.23, 0.09, decay=8.0, partials=((1, 1), (2, 0.08)))

    light_out = buffer(0.520)
    falling_tone(light_out, 0.010, 0.410, 0.18)
    brush(light_out, 0.030, 0.410, 0.17, 4104, low=150, high=1_450, swell=True)
    struck(light_out, 0.040, 0.320, 174.61, 0.085, decay=12, partials=((1, 1), (2, 0.14)))

    victory = buffer(1.280)
    for start, frequency, gain in (
        (0.010, 349.23, 0.16),
        (0.110, 440.00, 0.135),
        (0.210, 523.25, 0.125),
        (0.340, 698.46, 0.12),
    ):
        struck(victory, start, 1.270-start, frequency, gain, decay=4.2)
    struck(victory, 0.345, 0.930, 174.61, 0.06, decay=4.3, partials=((1, 1), (2, 0.08)))
    brush(victory, 0.340, 0.220, 0.07, 4105, low=2_000, high=7_200, swell=True)

    return [
        ("ui_tap", "CLICK", tap, -16.0, "Dry, restrained selection tick."),
        ("card_place", "CARD_PLAY", card, -13.0, "Soft paper brush settling onto a tabletop."),
        ("challenge", "CHALLENGE", challenge, -10.5, "Two muted wooden knocks to mark the challenge."),
        ("safe", "ROUND_END", safe, -13.0, "Warm resolving chime for a safe round result."),
        ("light_out", "LIGHT_OUT", light_out, -13.0, "Soft descending tone and breath as a light goes out."),
        ("victory", "WIN", victory, -10.5, "A short ascending F-major chord with a rounded tail."),
    ]


def write_cue(name: str, signal: list[float], peak_dbfs: float) -> tuple[Path, dict[str, float | int | str]]:
    # Remove accumulated DC, set the designed headroom, then taper the whole cue.
    # Per-cue peak targets preserve hierarchy; none is normalized to full scale.
    dc = sum(signal) / len(signal)
    signal = [sample - dc for sample in signal]
    peak = max(abs(sample) for sample in signal)
    gain = (10 ** (peak_dbfs / 20)) / peak
    duration = len(signal) / SAMPLE_RATE
    signal = [
        sample * gain * edge(index / SAMPLE_RATE, duration, 0.0015, 0.018)
        for index, sample in enumerate(signal)
    ]
    signal[0] = signal[-1] = 0.0
    pcm = array("h", (round(max(-1.0, min(1.0, sample)) * 32767) for sample in signal))
    if sys.byteorder != "little":
        pcm.byteswap()
    destination = DESTINATION / f"{name}.wav"
    with wave.open(str(destination), "wb") as writer:
        writer.setnchannels(1)
        writer.setsampwidth(2)
        writer.setframerate(SAMPLE_RATE)
        writer.writeframes(pcm.tobytes())
    measured_peak = max(abs(sample) for sample in signal)
    rms = sqrt(sum(sample * sample for sample in signal) / len(signal))
    return destination, {
        "duration_ms": round(duration * 1_000),
        "sample_frames": len(signal),
        "sample_rate_hz": SAMPLE_RATE,
        "channels": 1,
        "bits_per_sample": 16,
        "encoding": "WAVE / signed little-endian linear PCM",
        "peak_dbfs": round(20 * log10(measured_peak), 2),
        "rms_dbfs": round(20 * log10(rms), 2),
        "dc_offset": round(sum(signal) / len(signal), 8),
        "file_bytes": destination.stat().st_size,
        "sha256": sha256(destination.read_bytes()).hexdigest(),
    }


def main() -> None:
    DESTINATION.mkdir(parents=True, exist_ok=True)
    manifest = []
    for name, cue, signal, peak_dbfs, description in build_cues():
        destination, metadata = write_cue(name, signal, peak_dbfs)
        manifest.append(
            {
                "name": name,
                "feedback_cue": cue,
                "resource_path": f"files/audio/{name}.wav",
                "description": description,
                "origin": "Original programmatic synthesis; no external samples.",
                **metadata,
            }
        )
        print(f"{destination.name}: {metadata['duration_ms']} ms, {metadata['peak_dbfs']} dBFS peak")
    (ROOT / "assets/audio_manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()
