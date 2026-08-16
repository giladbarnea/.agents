#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "requests",
#     "diskcache",
# ]
# ///
import os
from pathlib import Path

import diskcache
import requests

OPENROUTER_API_KEY_PATH = Path.home() / ".openrouter-api-key"
PERPLEXITY_API_KEY_PATH = Path.home() / ".perplexity-api-key"
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY") or (
    OPENROUTER_API_KEY_PATH.read_text().strip()
    if OPENROUTER_API_KEY_PATH.exists()
    else None
)
PERPLEXITY_API_KEY = os.getenv("PERPLEXITY_API_KEY") or (
    PERPLEXITY_API_KEY_PATH.read_text().strip()
    if PERPLEXITY_API_KEY_PATH.exists()
    else None
)

# Initialize cache in a local directory
cache = diskcache.Cache(".cache/perplexity")


@cache.memoize(expire=3600 * 24 * 7)  # Cache for 7 days
def fetch_perplexity_response(prompt, model):
    providers = (
        (
            "OpenRouter",
            OPENROUTER_API_KEY,
            "https://openrouter.ai/api/v1/chat/completions",
            {
                "model": f"perplexity/{model}",
                "messages": [
                    {"role": "user", "content": [{"type": "text", "text": prompt}]}
                ],
                "reasoning": {"enabled": model == "sonar-pro-search"},
            },
        ),
        (
            "Perplexity",
            PERPLEXITY_API_KEY,
            "https://api.perplexity.ai/chat/completions",
            {"model": model, "messages": [{"role": "user", "content": prompt}]},
        ),
    )
    latest_error = None

    for _, api_key, url, payload in providers:
        if not api_key:
            continue

        try:
            response = requests.post(
                url=url,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
            response.raise_for_status()
            return response.json()
        except requests.RequestException as error:
            latest_error = error

    raise RuntimeError(
        "Neither the OpenRouter nor Perplexity API key worked. Try Brave Search."
    ) from latest_error


def main(prompt, model="sonar-pro"):
    response_data = fetch_perplexity_response(prompt, model)

    print("## Results")
    message = response_data["choices"][0]["message"]
    print(message["content"])

    if "annotations" in message:
        print("\n## Sources")
        print(
            "\n".join(
                f"- [{ann['url_citation']['title']}]({ann['url_citation']['url']})"
                for ann in message["annotations"]
                if "url_citation" in ann
            )
        )
    else:
        # Check for citations list which some models provide instead
        citations = response_data.get("citations", [])
        if citations:
            print("\n## Sources")
            for i, url in enumerate(citations):
                print(f"- [Source {i + 1}]({url})")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Search Perplexity through OpenRouter, then the Perplexity API"
    )
    parser.add_argument("prompt", help="Search prompt")
    parser.add_argument(
        "--model",
        default="sonar-pro",
        help="Perplexity model to use (default: sonar-pro)",
    )
    args = parser.parse_args()
    main(prompt=args.prompt, model=args.model)
