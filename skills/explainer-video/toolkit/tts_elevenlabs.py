#!/usr/bin/env -S uv run
# /// script
# requires-python = "==3.14.*"
# dependencies = ["httpx"]
# ///
"""Synthesize ElevenLabs narration and write the shared voice-led timeline."""
import json
import sys
import wave
from pathlib import Path
from typing import NotRequired, TypedDict

import httpx

SAMPLE_RATE = 24000
SPEED = 0.83
LEAD = 0.4
PAUSE = 2.3
VOICE_ID = 'hpp4J3VqNfWAUOO0d1Us'
MODEL_ID = 'eleven_multilingual_v2'


class ScriptLine(TypedDict):
    id: str
    caption: str
    say: NotRequired[str]
    source: str


class Scene(TypedDict):
    id: str
    caption: str
    start: float
    lead: float
    speech: float
    duration: float


Path('audio').mkdir(exist_ok=True)
key = Path('/Users/giladbarnea/.elevenlabs-gilad-barnea-com-basic-api-key').read_text().strip()
lines: list[ScriptLine] = json.loads(Path('script.json').read_text())
selected = set(sys.argv[1:])
timeline: list[Scene] = []
start = 0.0
with httpx.Client(base_url='https://api.elevenlabs.io', headers={'xi-api-key': key}, timeout=90) as client:
    for index, line in enumerate(lines):
        output = Path('audio') / f"{line['id']}.wav"
        if not selected or line['id'] in selected:
            response = client.post(
                f'/v1/text-to-speech/{VOICE_ID}',
                params={'output_format':'pcm_24000'},
                json={
                    'text':line.get('say',line['caption'].replace('\n',' ')),
                    'model_id':MODEL_ID,
                    'voice_settings':{'speed':SPEED,'stability':0.55,'similarity_boost':0.75,'style':0.12,'use_speaker_boost':True},
                    'seed':426 + index,
                },
            )
            response.raise_for_status()
            with wave.open(str(output), 'wb') as audio:
                audio.setnchannels(1)
                audio.setsampwidth(2)
                audio.setframerate(SAMPLE_RATE)
                audio.writeframes(response.content)
        with wave.open(str(output), 'rb') as audio:
            speech = round(audio.getnframes() / audio.getframerate(), 3)
        duration = round(LEAD + speech + PAUSE, 3)
        timeline.append({'id':line['id'],'caption':line['caption'],'start':round(start,3),'lead':LEAD,'speech':speech,'duration':duration})
        start += duration
        print(line['id'], speech, flush=True)
Path('speech.json').write_text(json.dumps(timeline,indent=1))
print(f'Total: {start:.3f} seconds', flush=True)
