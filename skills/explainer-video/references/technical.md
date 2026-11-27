## Papertalk Video

Papertalk is an open-source narrated explainer-video maker for any source.

1. Clone the repo (https://github.com/AmirMakir/papertalk) to a /tmp dir.
2. Create a video for the given content.
    - Use the ElevenLabs API key in `~/.elevenlabs-api-key`, or a local high-quality voice model if ElevenLabs is failing.
3. Load the cleanup skill, and create a shell script that cleans up everything (including the local models) for after the video is consumed. Removing the video itself is opt-in, with `--remove-video`.
4. Return the paths of the video and the script.
