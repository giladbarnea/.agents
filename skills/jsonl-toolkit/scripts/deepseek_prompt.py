#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
import argparse
import json
from pathlib import Path
from urllib import error, request


def complete(prompt_path: Path) -> str:
    """Send the file's text to DeepSeek Flash and return its answer."""
    api_key = (Path.home() / ".openrouter-api-key").read_text().strip()
    body = {
        "model": "deepseek/deepseek-v4.1-flash",
        "messages": [{"role": "user", "content": prompt_path.read_text(encoding="utf-8")}],
        "reasoning": {"enabled": True},
        "provider": {"only": ["together"], "allow_fallbacks": False},
    }
    completion_request = request.Request(
        "https://openrouter.ai/api/v1/chat/completions",
        data=json.dumps(body).encode(),
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with request.urlopen(completion_request, timeout=120) as response:
            result = json.load(response)
    except error.HTTPError as failure:
        raise RuntimeError(f"OpenRouter HTTP {failure.code}: {failure.read().decode()}") from failure
    content = result["choices"][0]["message"]["content"]
    if not isinstance(content, str):
        raise TypeError("OpenRouter did not return assistant text.")
    return content


def main() -> None:
    """Print one answer for the text file named on the command line."""
    parser = argparse.ArgumentParser(description="Pass a text file to DeepSeek Flash through OpenRouter.")
    parser.add_argument("prompt_path", type=Path)
    arguments = parser.parse_args()
    print(complete(arguments.prompt_path))


if __name__ == "__main__":
    main()
