#!/usr/bin/env -S uv run
# /// script
# requires-python = "==3.12.*"
# dependencies = ["numpy", "soundfile"]
# ///
"""Build narration.wav (voice lines on the video timeline) and music.wav (a soft generated pad and arpeggio)."""
import json
import pathlib

import numpy as np
import soundfile as sf

HERE = pathlib.Path(__file__).parent
RATE = 48000
LEAD, TAIL = 0.3, 0.55
NOTE = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}
CHORDS = [["C3", "E4", "G4", "B4"], ["A2", "C4", "E4", "G4"], ["F2", "A3", "C4", "E4"], ["G2", "B3", "D4", "A4"]]
BEAT = 60 / 72


def frequency(name: str) -> float:
    """>>> round(frequency('A4'))
    440
    """
    midi = 12 * (int(name[1]) + 1) + NOTE[name[0]]
    return 440 * 2 ** ((midi - 69) / 12)


def narration() -> tuple[np.ndarray, float]:
    lines = json.loads((HERE / "speech.json").read_text())
    total = sum(LEAD + line["speech"] + TAIL for line in lines)
    track = np.zeros(int(total * RATE) + RATE)
    start = 0.0
    for line in lines:
        voice, voice_rate = sf.read(HERE / "audio" / f"{line['id']}.wav")
        resampled = np.interp(np.arange(0, len(voice), voice_rate / RATE), np.arange(len(voice)), voice)
        offset = int((start + LEAD) * RATE)
        track[offset:offset + len(resampled)] += resampled
        start += LEAD + line["speech"] + TAIL
    return track / np.abs(track).max() * 0.9, total


def music(total: float) -> np.ndarray:
    track = np.zeros(int(total * RATE) + RATE)
    bar = BEAT * 4
    time_in_bar = np.arange(int(bar * 2 * RATE)) / RATE
    envelope = np.minimum(1, time_in_bar / 1.2) * np.minimum(1, (bar * 2 - time_in_bar) / 1.2)
    pluck_time = np.arange(int(1.6 * RATE)) / RATE
    for index, start in enumerate(np.arange(0, total, bar * 2)):
        chord = CHORDS[index % len(CHORDS)]
        pad = sum(np.sin(2 * np.pi * frequency(note) * detune * time_in_bar) for note in chord for detune in (0.998, 1.002))
        segment = slice(int(start * RATE), int(start * RATE) + len(pad))
        track[segment] += (pad * envelope * 0.05)[: len(track[segment])]
        for step in range(16):
            note = frequency(chord[[1, 2, 3, 2][step % 4]]) * 2
            pluck = (np.sin(2 * np.pi * note * pluck_time) + 0.3 * np.sin(4 * np.pi * note * pluck_time)) * np.exp(-pluck_time * 5)
            at = int((start + step * BEAT / 2) * RATE)
            if at >= len(track):
                break
            end = min(len(track), at + len(pluck))
            track[at:end] += pluck[: end - at] * 0.06
    delay = int(0.36 * RATE)
    for _ in range(3):
        track[delay:] += track[:-delay] * 0.35
    kernel = np.ones(6) / 6
    track = np.convolve(track, kernel, mode="same")
    fade = int(3 * RATE)
    track[:fade] *= np.linspace(0, 1, fade)
    track[-fade:] *= np.linspace(1, 0, fade)
    return track / np.abs(track).max() * 0.5


(HERE / "build").mkdir(exist_ok=True)
voice, total = narration()
sf.write(HERE / "build" / "narration.wav", voice, RATE)
sf.write(HERE / "build" / "music.wav", music(total), RATE)
print(f"total={total:.2f}s")
