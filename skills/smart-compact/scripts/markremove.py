#!/usr/bin/env python3
"""Mark one transcript message for removal by stable original_index."""

import argparse
import json
import pathlib


def flatten_content(content: list[object]) -> str:
    return "\n".join(
        item if isinstance(item, str) else json.dumps(item, ensure_ascii=False)
        for item in content
    )


def mark_message(
    messages: list[dict[str, object]], original_index: int, safeguard: str
) -> dict[str, object]:
    """Mark the uniquely matching message after proving its content."""
    matches = [message for message in messages if message.get("original_index") == original_index]
    if len(matches) != 1:
        raise ValueError(
            f"expected one message with original_index={original_index}, found {len(matches)}"
        )
    message = matches[0]
    content = message.get("content")
    if not isinstance(content, list):
        raise ValueError(f"message {original_index} has no content array")
    if safeguard not in flatten_content(content):
        raise ValueError(f"safeguard not found in message original_index={original_index}")
    message["remove"] = True
    return message


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", type=pathlib.Path)
    parser.add_argument("--original-index", type=int, required=True)
    parser.add_argument("--safeguard", required=True)
    arguments = parser.parse_args()

    raw = json.loads(arguments.path.read_text(encoding="utf-8"))
    if not isinstance(raw, list) or not all(isinstance(message, dict) for message in raw):
        raise ValueError("expected a JSON array of message objects")
    messages = [message for message in raw if isinstance(message, dict)]
    message = mark_message(messages, arguments.original_index, arguments.safeguard)
    arguments.path.write_text(
        json.dumps(messages, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"marked original_index={arguments.original_index}: {message.get('type')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
