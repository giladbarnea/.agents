#!/usr/bin/env -S uv run
# /// script
# requires-python = "==3.12.*"
# dependencies = ["faster-whisper", "soundfile", "numpy"]
# ///
"""Transcribe a few voice lines to prove the TTS says what the script says. Pass line ids as arguments."""
import sys
import numpy as np
import soundfile as sf
from faster_whisper import WhisperModel

model = WhisperModel("base.en", compute_type="int8")
for line_id in sys.argv[1:]:
    audio, rate = sf.read(f"audio/{line_id}.wav")
    audio16 = np.interp(np.arange(0, len(audio), rate / 16000), np.arange(len(audio)), audio).astype(np.float32)
    segments, _ = model.transcribe(audio16)
    print(line_id, " ".join(segment.text.strip() for segment in segments))
