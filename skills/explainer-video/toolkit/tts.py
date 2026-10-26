#!/usr/bin/env -S uv run
# /// script
# requires-python = "==3.12.*"
# dependencies = ["kokoro", "soundfile", "pip"]
# ///
"""Synthesize one WAV per script.json line into audio/ and write speech.json with each line's spoken length."""
import json
import pathlib
import numpy as np
import soundfile as sf
from kokoro import KPipeline

SAMPLE_RATE = 24000
pathlib.Path("audio").mkdir(exist_ok=True)
pipeline = KPipeline(lang_code="a")
lines = json.load(open("script.json"))
timeline = []
for line in lines:
    text = line.get("say", line["caption"].replace("\n", " "))
    audio = np.concatenate([chunk for _, _, chunk in pipeline(text, voice="af_heart", speed=0.98)])
    sf.write(f"audio/{line['id']}.wav", audio, SAMPLE_RATE)
    timeline.append({"id": line["id"], "caption": line["caption"], "speech": round(len(audio) / SAMPLE_RATE, 3)})
    print(line["id"], timeline[-1]["speech"])
json.dump(timeline, open("speech.json", "w"), indent=1)
