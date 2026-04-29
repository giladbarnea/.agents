#!/usr/bin/env -S uv run
# /// script
# requires-python = "==3.12.*"
# dependencies = ["jinja2"]
# ///
from pathlib import Path
from jinja2 import Environment, FileSystemLoader

agents_dir = Path("~/.agents").expanduser()
env = Environment(
    loader=FileSystemLoader(str(agents_dir)),
    keep_trailing_newline=True,
    trim_blocks=True,
    lstrip_blocks=True,
)

agent_dirs = [
    Path("~/.claude").expanduser(),
    Path("~/.codex").expanduser(),
    Path("~/.gemini").expanduser(),
]

for agent_dir in agent_dirs:
    for src in sorted(agent_dir.glob("*.md.j2")):
        template = env.from_string(src.read_text())
        output = src.with_suffix("")
        output.write_text(template.render())
        print(f"  {src} → {output}")
