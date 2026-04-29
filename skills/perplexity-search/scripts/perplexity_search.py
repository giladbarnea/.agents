#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "requests",
#     "diskcache",
# ]
# ///
import requests
import json
import os
from pathlib import Path
import diskcache

API_KEY = os.getenv("OPENROUTER_API_KEY")
if not API_KEY:
    api_key_path = Path.home() / ".openrouter-api-key-personal"
    if api_key_path.exists():
        API_KEY = api_key_path.read_text().strip()
        os.environ["OPENROUTER_API_KEY"] = API_KEY

# Initialize cache in a local directory
cache = diskcache.Cache(".cache/perplexity")


@cache.memoize(expire=3600 * 24 * 7)  # Cache for 7 days
def fetch_perplexity_response(prompt, model):
    response = requests.post(
        url="https://openrouter.ai/api/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {API_KEY}",
            "Content-Type": "application/json",
        },
        data=json.dumps(
            {
                "model": f"perplexity/{model}",
                "messages": [
                    {"role": "user", "content": [{"type": "text", "text": prompt}]}
                ],
                "reasoning": {"enabled": model == "sonar-pro-search"},
            }
        ),
    )
    response.raise_for_status()
    return response.json()


def main(prompt, model="sonar-pro"):
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        api_key_path = Path.home() / ".openrouter-api-key-personal"
        if api_key_path.exists():
            api_key = api_key_path.read_text().strip()
            os.environ["OPENROUTER_API_KEY"] = api_key
        else:
            raise ValueError(
                "OPENROUTER_API_KEY not found in environment and ~/.openrouter-api-key-personal does not exist"
            )

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
        description="Search using Perplexity API via OpenRouter"
    )
    parser.add_argument("prompt", help="Search prompt")
    parser.add_argument(
        "--model",
        default="sonar-pro",
        help="Perplexity model to use (default: sonar-pro)",
    )
    args = parser.parse_args()
    main(prompt=args.prompt, model=args.model)
