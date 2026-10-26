#!/usr/bin/env -S uv run
# /// script
# requires-python = "==3.12.*"
# dependencies = ["playwright"]
# ///
"""Render renderer.html frame by frame. Modes: `stills` (one PNG per scene) or `video START END OUT` (frame range to an MP4 segment)."""
import json
import pathlib
import subprocess
import sys

from playwright.sync_api import sync_playwright

FPS = 24
LEAD = 0.3
TAIL = 0.55
HERE = pathlib.Path(__file__).parent


def timeline() -> list[dict]:
    entries, start = [], 0.0
    for line in json.loads((HERE / "speech.json").read_text()):
        duration = round(LEAD + line["speech"] + TAIL, 3)
        entries.append({"id": line["id"], "caption": line["caption"], "start": round(start, 3), "duration": duration})
        start += duration
    return entries


def open_page(playwright):
    browser = playwright.chromium.launch(channel="chrome")
    page = browser.new_page(viewport={"width": 1080, "height": 1080})
    page.goto((HERE / "renderer.html").as_uri())
    page.evaluate("Promise.all(['40px Andika', '700 40px Andika', '40px \\'IBM Plex Mono\\'', '600 40px \\'IBM Plex Mono\\''].map(font => document.fonts.load(font)))")
    page.wait_for_function("document.fonts.check('40px Andika') && document.fonts.check('40px \"IBM Plex Mono\"')")
    page.evaluate("entries => { TIMELINE = entries; }", timeline())
    return page


def stills(fraction: float) -> None:
    out = HERE / "build" / "stills"
    out.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as playwright:
        page = open_page(playwright)
        for entry in timeline():
            page.evaluate("t => renderFrame(t)", entry["start"] + entry["duration"] * fraction)
            page.screenshot(path=str(out / f"{entry['id']}.png"))


def video(first_frame: int, last_frame: int, output: str) -> None:
    encoder = subprocess.Popen(
        ["ffmpeg", "-v", "error", "-y", "-f", "image2pipe", "-framerate", str(FPS), "-i", "-",
         "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p", output],
        stdin=subprocess.PIPE,
    )
    with sync_playwright() as playwright:
        page = open_page(playwright)
        for frame in range(first_frame, last_frame):
            page.evaluate("t => renderFrame(t)", frame / FPS)
            encoder.stdin.write(page.screenshot(type="jpeg", quality=95))
    encoder.stdin.close()
    encoder.wait()


if __name__ == "__main__":
    if sys.argv[1] == "stills":
        stills(float(sys.argv[2]) if len(sys.argv) > 2 else 0.97)
    elif sys.argv[1] == "total":
        last = timeline()[-1]
        print(round(last["start"] + last["duration"], 3))
    else:
        video(int(sys.argv[2]), int(sys.argv[3]), sys.argv[4])
