#!/usr/bin/env -S uv run
# /// script
# requires-python = "==3.12.*"
# dependencies = ["kokoro", "soundfile", "pip"]
# ///
"""Synthesize one WAV per script.json line into audio/ and write speech.json: the single timeline that render.py and audio.py follow."""
import json
import pathlib
import numpy as np
import soundfile as sf
from kokoro import KPipeline

SAMPLE_RATE = 24000
SPEED = 0.82  # Kokoro speaking rate. 0.98 felt rushed to the viewer; this is 1.2 times slower.
LEAD = 0.4  # Silence before the voice starts, while the scene first appears.
PAUSE = 2.3  # Silence after the voice ends, so the viewer can take in the picture.
pathlib.Path("audio").mkdir(exist_ok=True)
pipeline = KPipeline(lang_code="a")
lines = json.load(open("script.json"))
timeline = []
start = 0.0
for line in lines:
    text = line.get("say", line["caption"].replace("\n", " "))
    audio = np.concatenate([chunk for _, _, chunk in pipeline(text, voice="af_heart", speed=SPEED)])
    sf.write(f"audio/{line['id']}.wav", audio, SAMPLE_RATE)
    speech = round(len(audio) / SAMPLE_RATE, 3)
    duration = round(LEAD + speech + PAUSE, 3)
    timeline.append({"id": line["id"], "caption": line["caption"], "start": round(start, 3), "lead": LEAD, "speech": speech, "duration": duration})
    start += duration
    print(line["id"], timeline[-1]["speech"])
json.dump(timeline, open("speech.json", "w"), indent=1)
