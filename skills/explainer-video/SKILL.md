---
name: explainer-video
description: Make a narrated, captioned, illustrated explainer video (square, flat risograph editorial style, one narrated sentence per animated panel) that explains a design, system, session or document. Use when asked for an explainer video, an animated explanation, or "a video like the Bend one".
---

# Explainer videos

You will make a square video, about 3:30–4:30 long. Each scene is one animated illustration with one narrated sentence pair, shown as a caption under it. After each line, the scene stays on screen in silence for a moment, so the viewer can take it in. A soft music bed plays under the voice. You draw every frame yourself with an SVG renderer and record it with Chrome. This is code, not a video tool. The working pipeline is in `toolkit/`.

Look at the contact sheets of the two worked examples before you start. They are the quality bar:

1. `examples/one-scope-design/` (Claude): the remotes-automation "one scope" design, from Pi session `01a16893-…`. It has the full 39-scene `renderer.html`.
2. `examples/two-trees-latest/` (Codex, made from this skill, then revised once after the user's feedback): the same system two days later, with four open decisions. This is the stronger example. It runs 4:15 with 28 scenes, at the current pace, with an ElevenLabs voice. Copy its moves: a fact record (`FACTS.md`), a scene kicker that defines the scene's term ("RETURN = SEND BACK FOR REVISION"), "OPEN n/4" markers, decision options drawn side by side, and a "TODAY" strip that shows the current build's behavior.

Example 1 ran at the old, faster pace. The user found that pace too fast. The toolkit now speaks 1.2 times slower and pauses after each line, which makes each scene about 1.5 times longer.

`reference/kevin-ngo-bend-contact-sheet.jpg` is the style source: Kevin Ngo's "Why agents might prefer Bend" (x.com/kevin_t_ngo/status/2113663060888203642). Claude made that video too.

## What done means

1. A 1080×1080, 24 fps H.264 MP4 with AAC audio. The audio and video durations match.
2. 22–30 scenes. At the toolkit's pace, a scene lasts about 8–10 seconds, so the video runs about 3:30–4:30. When the video is too long, cut scenes. Never shorten the pause. Keep the background story to 2–3 scenes.
3. Each scene explains one idea with a picture of the mechanism, such as who sends what to whom, what blocks what, or what changes state. No decorative scenes.
4. Every term that is not everyday language is explained, in words or in a picture, before or when it first appears.
5. Every caption is a true statement about the current source, and each one is checked against it.
6. The user got the file in the conversation. If it is over 30 MB, send a 720p copy and give the path to the full file.

## Workflow

Work in a folder in your scratchpad. Copy `toolkit/` into it. Run every command from that folder.

### 1. Find the content in its final form

A session transcript is a history, not a spec. Most of it describes states that were later replaced. "The final form" is the newest written design, and it usually lives in files that the session wrote.

1. Redirect the transcript to a file (`ch <id> > transcript.md`). Read all of it, because it can be 150 KB or more. Note every file path in the last few assistant messages.
2. Open those files in their repository. Check the frontmatter (`status`, `last_updated`, `supersedes`) and the `git log`. Make sure that nothing newer exists.
3. Write a short fact list: the components, who can do what, the order of steps, lifetimes, the open status ("proposal, not built"), and the acceptance test. Every caption must trace to this list.
4. Use the transcript for two things only. First, the motivating problem, which gives the first 2–3 scenes. Second, the user's own words and names for things. Use their names in the video.

### 2. Write the script (`script.json`)

```json
[{"id": "s01", "caption": "Line one,\nline two.", "say": "optional spoken text when it differs"}]
```

1. Use one sentence or two short ones per scene, at most about 90 characters, broken into two caption lines with `\n`. The caption is the narration, word for word.
2. Use plain, literal language. Use one name for each thing in the whole video, because the viewer learns the names from the captions.
3. Address the viewer as "you" when the user is the viewer. A video for the user's own design works as a recall aid, so give the motivating problem first.
4. Use the arc: problem (2–3 scenes) → the parts → one pass through the flow → the rules that hold it together → edge cases (lifetimes, failures, async input) → how it will be tested → status and next step.
5. Introduce every term before you rely on it. List each term that is not everyday language, such as a component name, a project name, or jargon like "RPC" or "lock". For each one, either give it a scene (or half a scene) that shows what it is, or replace it with plain words. A viewer who was not in the sessions must be able to follow the video.
6. Give an open decision 2–3 scenes: what is at stake, what each option does, and what the build does today. Say plainly that it waits for the user.
7. Add a `say` field when TTS would misread the caption. Spell out version numbers ("Pi one point four"), hyphenated names ("pi simple team"), large numbers, and tool names that are not words ("ntfy" → "a notification").
8. Proofread the script against the fact list before you synthesize anything. A wrong line costs a re-render later.

### 3. Synthesize the voice first, and let it set the timing

`uv run tts_elevenlabs.py` (ElevenLabs) or `uv run tts.py` (Kokoro) writes `audio/<id>.wav` and `speech.json`. To re-synthesize only some lines after a script fix, pass their ids: `uv run tts_elevenlabs.py s04 s17`. This saves API cost. Each scene lasts `0.4 s lead + speech + 2.3 s pause`, and the voice speaks at about 0.82–0.83 of its normal speed. These constants live only at the top of the two TTS scripts. It writes each scene's `start`, `lead` and `duration` into `speech.json`, and `render.py` and `audio.py` only read them, so picture and voice cannot drift. Change the pace there and nowhere else.

The pace is the user's choice. At speed 0.98 with a 0.55 s tail, the user found the video too fast. Keep the slower pace unless the user asks for a different one.

Voice options, from best to worst:

1. **ElevenLabs, the default.** The reference video used it. The API key is in `/Users/giladbarnea/.elevenlabs-gilad-barnea-com-basic-api-key`. Read it from that file at run time, and never print it or copy it into another file. `toolkit/tts_elevenlabs.py` does all of this: it reads the key, uses the voice from the approved revision at speed 0.83, and keeps the same timeline contract as `tts.py`.
2. **Kokoro (`af_heart`), local and free.** `tts.py` uses it. It is clear and natural, but plainer than ElevenLabs. Use it as the fallback, or for quick drafts.
3. **Do not** use a cloud TTS that bills a gcloud or AWS project you found in the config. The active gcloud project on this Mac belongs to a client.

The user said the voice can be replaced later. The visuals matter more. Do not spend time on voice quality.

### 4. Design the scenes (`renderer.html`)

The toolkit renderer has the primitives, the frame pipeline and three sample scenes. Delete the samples and write one `S.<id> = (t, d) => svgString` per script line. `t` is the time in seconds since the scene started. Each scene is a pure function of `t`, with no CSS animation, timers or randomness without a seed. This lets parallel workers render any frame in any order.

**Visual language.** Decide this before you write any scene:

1. Pick 4–6 recurring glyphs, one for each core concept, and never change their meaning. In the example, a red disk with a wrench is a fixer agent, and a navy disk with a magnifier is a reviewer agent. A second ring marks a "main" agent. A striped 3D box is a repository clone. A paper with red and green lines is a patch. A tilted stamp is a verdict, a dark terminal shows logs, a phone shows Telegram, and a tag shows a version.
2. Color means role, not decoration. Red is for one actor and for failure, navy for the other actor, green for success, and mustard for the system, gates and highlights.
3. Change the panel background color from scene to scene for rhythm. Use cream, sky, mustard, pink, green, navy and red.
4. Keep the same layout when consecutive scenes contrast with each other, so that only the point changes. In the example, "fixer sees all" and "reviewer sees one" share one layout.
5. Use short mono labels inside the art. The caption carries the sentence, so the art must not repeat it.
6. Make things appear on the beat of the narration. Use `rise` and `pop` for entrances, `line(d, k)` to draw paths, `stamp` for verdicts and `terminal` for typed logs. Elements should land roughly when the voice names them. Read each scene's `lead` and `speech` from `speech.json` to place the beats.
7. Finish every entrance before the voice ends. During the pause, the picture stays complete and still, apart from slow ambient motion such as a ticking clock hand or a looping envelope. Nothing new appears in the pause.
8. Draw each option of a decision as a mechanism, not as a list of words. Show what happens to the item under each option: side-by-side before and after states, or the same path with a different branch taken. Mark the current build's behavior and the "OPEN" status.
9. Copy the reference's signature moves: a big title card with a drop-shadow word, a typed terminal with a red error line, a tag like `Pi 1.4.0`, a tree of thick curved branches, halftone shading on 3D shapes, and an end card that says "every frame of this film was drawn by an SVG renderer Claude wrote". Codex added a good one: a small uppercase mono kicker at the top left that names the scene's topic, such as "THE FIX GATE".

**Style constants.** These are already in the toolkit:

- Canvas 1080×1080. The panel is `x 24–1056, y 24–864`, with rounded corners and no stroke. Captions are centered under it at y 940 and 992 (y 960 for one line), in Andika 40 px, ink color.
- Fonts: Andika for prose, IBM Plex Mono for labels and code. Both come from Google Fonts.
- Palette: cream `#ECE5D3`, paper `#F7F2E6`, ink `#1E2340`, navy `#26368C`, night `#1B1F3B`, red `#C8352B`, pink `#E6A99F`, mustard `#E5B53A`, green `#2E9A5E`, sky `#AFC6D8`, blue `#A6BFE0`.
- Texture: a displacement filter on the art gives a slight hand-drawn line boil, with the seed changing 8 times a second. A multiplied noise layer gives paper grain. The captions are not filtered.

### 5. Check stills before you render video

```bash
uv run render.py stills 0.5 && ./sheets.sh     # mid-animation
uv run render.py stills 0.97 && ./sheets.sh    # end state
```

Read every `build/sheet_*.jpg` image. Each one shows 12 scenes with their captions. Look for text that collides with tokens, labels that cross arcs, overflowing card titles, art that crowds the caption band (keep art above y ≈ 850), empty panels in the middle of a scene, and a picture that does not show what the caption says. Fix, then check again. The first pass of the example had six such problems.

Send one end-state sheet to the user with `SendUserFile` as a progress update. It is cheap, and the user can redirect you before the final render.

### 6. Render, mix and deliver

```bash
./render_all.sh            # 6 parallel Chrome workers, about 1 minute for 4 minutes of video
uv run audio.py            # build/narration.wav + build/music.wav (a generated pad and arpeggio)
./finish.sh my-video       # ducks the music under the voice, muxes, writes my-video.mp4 and my-video-720.mp4
uv run check_voice.py s03 s17 s30   # Whisper transcripts of lines with tricky words
```

Check that the `ffprobe` durations of the audio and video streams match. Grab 4–5 frames across the timeline (`ffmpeg -ss <t> -frames:v 1`) and look at them. Then send the 720p file with `SendUserFile`. The upload limit is 30 MB, and the full 1080p file is about 50 MB for 4 minutes.

## Pitfalls already paid for

1. **Fonts that never load.** Web fonts load only when text uses them, so `document.fonts.check` alone times out. `render.py` calls `document.fonts.load(...)` for each face first. Keep that line.
2. **Playwright's browser download.** Use `channel="chrome"` to drive the installed Google Chrome.
3. **`faster-whisper` crashes with `av.open(... metadata_errors)`.** The installed `av` version breaks file decoding. `check_voice.py` decodes with soundfile and passes a 16 kHz array.
4. **Music crashes on short videos.** Notes were placed past the end of the track. This is fixed in `audio.py` and caught by a 3-scene smoke test.
5. **Kokoro needs Python 3.12 and `pip`** (spaCy downloads its English model on the first run). The PEP 723 header in `tts.py` handles both.
6. **Downloading the reference video.** `https://cdn.syndication.twimg.com/tweet-result?id=<tweet id>&token=4` returns JSON with MP4 variants under `mediaDetails[0].video_info.variants`. No login is needed. A contact sheet: `ffmpeg -i ref.mp4 -vf "fps=1/4,scale=540:540" frames/f_%03d.png`, then `tile=6x5`.
7. **Long silent stretches.** The harness reminds you when the user has not heard from you. During long builds, post one line per stage, such as "script written, synthesizing voice" or "stills look clean, rendering".

## Lessons for any "make an artifact that explains X" task

1. **Find the style bar before you build, and capture it as a picture.** A contact sheet of the reference taught more than any description. Save your own contact sheet for the next agent.
2. **Treat the newest written artifact as the truth, and the conversation as background.** Conversations hold replaced states. Docs with `status` and `last_updated` frontmatter are the spec.
3. **Let the hardest constraint set the timeline.** Here the voice length set the scene length, so the two could never drift. Find the one input that everything else must follow, and build from it.
4. **Make rendering a pure function of time.** Then frames can be checked at any moment, rendered in parallel, and re-rendered for one fix without side effects.
5. **Check with contact sheets at two moments.** End frames hide entrance bugs, and mid frames hide end-state collisions. One glance at 12 scenes beats watching the video.
6. **Smoke-test the toolkit on a tiny input from a clean folder.** That run found a crash that the full-length run never reached.
7. **Check facts by falsification.** For each caption, ask "which line of the source says this?". For the audio, transcribe it back and compare.
8. **Cut length on purpose.** A complete explanation can still be too long. Aim for the fewest scenes that cover the mechanism, then stop.
9. **Pace for the viewer, not the speaker.** A viewer needs time to look after each point. Silence after a line is part of the explanation. Cut content before you cut that time.
10. **Explain to someone who was not there.** You know every term from the sources, but the viewer does not. Introduce each term before you use it.
