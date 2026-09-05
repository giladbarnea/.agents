#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.12"
# ///
"""Export a public ChatGPT shared conversation as clean Markdown.

Usage:
  chatgpt_share_to_markdown.py https://chatgpt.com/share/<id> > conversation.md
"""

from __future__ import annotations

import argparse
import datetime
import html.parser
import json
import re
import urllib.request


class ScriptCollector(html.parser.HTMLParser):
    """Collect inline script bodies from an HTML document."""

    def __init__(self) -> None:
        super().__init__()
        self.in_script = False
        self.scripts: list[str] = []
        self.current_script: list[str] = []

    def handle_starttag(self, tag: str, attributes: list[tuple[str, str | None]]) -> None:
        if tag == "script":
            self.in_script = True
            self.current_script = []

    def handle_data(self, data: str) -> None:
        if self.in_script:
            self.current_script.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "script" and self.in_script:
            self.scripts.append("".join(self.current_script))
            self.in_script = False


def fetch_page(url: str) -> str:
    """Fetch a public shared-conversation page."""
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(request, timeout=30) as response:
        return response.read().decode(response.headers.get_content_charset() or "utf-8")


def hydrate(values: list[object]) -> object:
    """Expand React Router's indexed server-data representation."""
    hydrated_values: dict[int, object] = {}

    def hydrate_index(index: int) -> object:
        if index < 0:
            return index
        if index >= len(values):
            raise ValueError("Shared-conversation payload references an unknown value")
        if index in hydrated_values:
            return hydrated_values[index]

        value = values[index]
        if not isinstance(value, list | dict):
            hydrated_values[index] = value
            return value

        if isinstance(value, list):
            hydrated_list: list[object] = []
            hydrated_values[index] = hydrated_list
            hydrated_list.extend(
                hydrate_index(item) if isinstance(item, int) else item for item in value
            )
            return hydrated_list

        hydrated_dict: dict[str, object] = {}
        hydrated_values[index] = hydrated_dict
        for encoded_key, encoded_value in value.items():
            if not encoded_key.startswith("_"):
                raise ValueError("Unexpected key in shared-conversation payload")
            key = hydrate_index(int(encoded_key[1:]))
            if not isinstance(key, str):
                raise ValueError("Shared-conversation payload has a non-string object key")
            hydrated_dict[key] = (
                hydrate_index(encoded_value) if isinstance(encoded_value, int) else encoded_value
            )
        return hydrated_dict

    return hydrate_index(0)


def shared_conversation_data(page: str) -> dict[str, object]:
    """Extract the shared conversation's server-rendered payload."""
    collector = ScriptCollector()
    collector.feed(page)

    for script in collector.scripts:
        if "streamController.enqueue" not in script:
            continue
        match = re.search(r"enqueue\((.*)\);$", script)
        if match is None:
            continue
        try:
            values = json.loads(json.loads(match.group(1)))
        except json.JSONDecodeError:
            continue
        if not isinstance(values, list):
            continue
        payload = hydrate(values)
        if not isinstance(payload, dict):
            continue
        loader_data = payload.get("loaderData")
        if not isinstance(loader_data, dict):
            continue
        route_data = next(
            (
                value
                for route, value in loader_data.items()
                if route.startswith("routes/share.") and isinstance(value, dict)
            ),
            None,
        )
        if route_data is None:
            continue
        server_response = route_data.get("serverResponse")
        if not isinstance(server_response, dict):
            continue
        data = server_response.get("data")
        if isinstance(data, dict):
            return data

    raise ValueError("The page did not contain a public ChatGPT shared-conversation payload")


DISPLAY_ROLES = frozenset({"user", "assistant"})
INTERNAL_ROLES = frozenset({"system", "tool"})
DISPLAY_CONTENT_TYPES = frozenset({"text", "multimodal_text"})
INTERNAL_ASSISTANT_CONTENT_TYPES = frozenset({"code", "thoughts", "reasoning_recap"})
MULTIMODAL_PART_TYPES = frozenset({"image_asset_pointer", "audio_transcription"})


def part_text(part: object) -> str:
    """Return a part's readable text: string parts verbatim, voice parts' transcript, else empty.

    >>> part_text("hello")
    'hello'
    >>> part_text({"content_type": "audio_transcription", "text": "spoken"})
    'spoken'
    >>> part_text({"content_type": "image_asset_pointer"})
    ''
    """
    if isinstance(part, str):
        return part
    if isinstance(part, dict) and part.get("content_type") == "audio_transcription":
        text = part.get("text")
        if not isinstance(text, str):
            raise ValueError("An audio transcription part has no text")
        return text
    return ""


UI_SENTINEL_TOKEN = re.compile("([^]*)(.*?)", re.DOTALL)


def genui_title(payload: str) -> str | None:
    """Return the title of an inline interactive widget, or None if the payload is opaque."""
    try:
        block = json.loads(payload).get("app_block")
    except (json.JSONDecodeError, AttributeError):
        return None
    return block.get("title") if isinstance(block, dict) else None


def clean_url(url: str) -> str:
    """Drop ChatGPT's tracking parameter from a source URL.

    >>> clean_url("https://nhs.uk/vertigo/?utm_source=chatgpt.com")
    'https://nhs.uk/vertigo/'
    """
    return re.sub(r"[?&]utm_source=chatgpt\.com", "", url)


def citation_links(message: dict[str, object]) -> dict[str, str]:
    """Map each inline citation token to a Markdown ``[cite: ...]`` string of its linked sources.

    Reads the message's ``content_references``, where ChatGPT records the web pages behind each
    citation as ``{url, attribution, title}`` items keyed by the token's ``matched_text``.
    """
    metadata = message.get("metadata")
    references = metadata.get("content_references") if isinstance(metadata, dict) else None
    links: dict[str, str] = {}
    for reference in references or []:
        if reference.get("type") != "grouped_webpages":
            continue
        matched_text = reference.get("matched_text")
        sources: list[str] = []
        seen: set[str] = set()
        for item in reference.get("items") or []:
            url = clean_url(item.get("url", ""))
            if not url or url in seen:
                continue
            seen.add(url)
            name = item.get("attribution") or item.get("title") or url
            sources.append(f"[{name}]({url})")
        if isinstance(matched_text, str) and sources:
            links[matched_text] = f"[cite: {', '.join(sources)}]"
    return links


def strip_ui_sentinels(text: str, citations: dict[str, str] | None = None) -> str:
    """Replace ChatGPT's private-use inline UI tokens with plain Markdown.

    Tokens are delimited as ``typepayload``. Interactive ``genui`` widgets
    become a titled placeholder; a ``cite`` token becomes its linked sources from ``citations``
    (a bare ``[cite]`` when absent); any other token drops out.

    >>> strip_ui_sentinels("as shownciteturn0search1.")
    'as shown[cite].'
    """
    citations = citations or {}

    def replace(match: re.Match[str]) -> str:
        token_type, payload = match.group(1), match.group(2)
        if token_type == "genui":
            title = genui_title(payload)
            label = f'Interactive visualization: "{title}"' if title else "Interactive visualization"
            return f"_[{label} — view in ChatGPT]_"
        if token_type == "cite":
            return citations.get(match.group(0), "[cite]")
        return ""

    return UI_SENTINEL_TOKEN.sub(replace, text)


def message_parts(message: dict[str, object]) -> list[object]:
    """Validate and return the parts of a displayable conversation message."""
    content = message.get("content")
    if not isinstance(content, dict):
        raise ValueError("A visible message has invalid content data")
    parts = content.get("parts")
    if not isinstance(parts, list):
        raise ValueError("A visible message has invalid content parts")
    content_type = content.get("content_type")
    if content_type not in DISPLAY_CONTENT_TYPES:
        raise ValueError(f"Unsupported visible message content type {content_type!r}")
    if content_type == "text" and not all(isinstance(part, str) for part in parts):
        raise ValueError("A text message contains a non-text part")
    for part in parts:
        if isinstance(part, str):
            continue
        if not isinstance(part, dict):
            raise ValueError("A multimodal message contains an invalid part")
        if part.get("content_type") not in MULTIMODAL_PART_TYPES:
            raise ValueError(
                f"Unsupported multimodal part type {part.get('content_type')!r}"
            )
    return parts


def attachment_lines(message: dict[str, object]) -> list[str]:
    """Render attachment names without attempting to download private file blobs."""
    metadata = message.get("metadata")
    if not isinstance(metadata, dict):
        raise ValueError("A visible message has invalid metadata")
    attachments = metadata.get("attachments", [])
    if not isinstance(attachments, list):
        raise ValueError("A visible message has invalid attachments")

    lines: list[str] = []
    for attachment in attachments:
        if not isinstance(attachment, dict):
            raise ValueError("A visible message has an invalid attachment")
        name = attachment.get("name")
        mime_type = attachment.get("mime_type")
        if not isinstance(name, str) or not isinstance(mime_type, str):
            raise ValueError("A visible message attachment has no name or MIME type")
        description = "An image" if mime_type.startswith("image/") else "A file"
        lines.append(f"> **Attachment:** {description}, `{name}`, was uploaded with this message.")
    return lines


def is_interrupted_empty_assistant_message(message: dict[str, object]) -> bool:
    """Identify ChatGPT's explicit record for a user-interrupted empty response."""
    author = message.get("author")
    metadata = message.get("metadata")
    if not isinstance(author, dict) or not isinstance(metadata, dict):
        return False
    if author.get("role") != "assistant":
        return False
    finish_details = metadata.get("finish_details")
    return (
        isinstance(finish_details, dict)
        and finish_details.get("type") == "interrupted"
        and finish_details.get("reason") == "client_stopped"
    )


def conversation_messages(data: dict[str, object]) -> list[dict[str, object]]:
    """Return the visible user and assistant messages on the active conversation path."""
    mapping = data.get("mapping")
    current_node = data.get("current_node")
    if not isinstance(mapping, dict) or not isinstance(current_node, str):
        raise ValueError("The shared-conversation payload has no active message path")

    path: list[dict[str, object]] = []
    visited_node_ids: set[str] = set()
    node_id: str | None = current_node
    while node_id is not None:
        if node_id in visited_node_ids:
            raise ValueError(f"The active message path contains a cycle at node {node_id!r}")
        visited_node_ids.add(node_id)
        node = mapping.get(node_id)
        if not isinstance(node, dict):
            raise ValueError(f"The active message path references unknown node {node_id!r}")
        path.append(node)
        parent = node.get("parent")
        if parent is not None and not isinstance(parent, str):
            raise ValueError("A conversation node has an invalid parent")
        node_id = parent

    messages: list[dict[str, object]] = []
    for node in reversed(path):
        message = node.get("message")
        if message is None and node.get("parent") is None:
            continue
        if not isinstance(message, dict):
            raise ValueError("A conversation node has no valid message")
        author = message.get("author")
        metadata = message.get("metadata")
        if not isinstance(author, dict) or not isinstance(metadata, dict):
            raise ValueError("A conversation message has invalid author or metadata")
        role = author.get("role")
        if not isinstance(role, str):
            raise ValueError("A conversation message has no author role")
        if metadata.get("is_visually_hidden_from_conversation"):
            continue
        if metadata.get("is_thinking_preamble_message"):
            if role != "assistant":
                raise ValueError("A thinking preamble does not belong to an assistant")
            continue
        if role in INTERNAL_ROLES:
            continue
        if role not in DISPLAY_ROLES:
            raise ValueError(f"Unsupported visible message role {role!r}")

        content = message.get("content")
        if not isinstance(content, dict):
            raise ValueError("A visible message has invalid content data")
        content_type = content.get("content_type")
        if content_type in INTERNAL_ASSISTANT_CONTENT_TYPES and role == "assistant":
            continue
        parts = message_parts(message)
        has_text = any(part_text(part).strip() for part in parts)
        has_attachments = bool(attachment_lines(message))
        if not has_text and not has_attachments:
            if is_interrupted_empty_assistant_message(message):
                continue
            raise ValueError("A visible message has neither text nor an attachment")
        messages.append(message)

    return messages


def render_message(message: dict[str, object]) -> str:
    """Render one visible ChatGPT message as Markdown."""
    author = message["author"]
    if not isinstance(author, dict):
        raise ValueError("A visible message has invalid author data")
    role = author.get("role")
    if role not in DISPLAY_ROLES:
        raise ValueError(f"Cannot render unsupported message role {role!r}")
    parts = message_parts(message)
    text = strip_ui_sentinels(
        "".join(part_text(part) for part in parts), citation_links(message)
    ).strip()
    attachment = "\n".join(attachment_lines(message))
    body = "\n\n".join(part for part in [attachment, text] if part)
    speaker = "You" if role == "user" else "ChatGPT"
    return f"## {speaker}\n\n{body}"


def render_markdown(
    data: dict[str, object], source_url: str, title: str, retrieved_on: str
) -> str:
    """Render a shared conversation as Markdown."""
    messages = conversation_messages(data)
    if not messages:
        raise ValueError("The active conversation path has no visible messages")
    header = (
        f"# {title}\n\n"
        f"> Downloaded from [this shared ChatGPT conversation]({source_url}) on {retrieved_on}."
    )
    return f"{header}\n\n" + "\n\n---\n\n".join(map(render_message, messages)) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("url", help="Public https://chatgpt.com/share/... URL")
    parser.add_argument("--title", help="Markdown heading; defaults to the conversation title")
    parser.add_argument(
        "--retrieved-on",
        default=datetime.date.today().isoformat(),
        help="Retrieval date in YYYY-MM-DD format",
    )
    arguments = parser.parse_args()

    try:
        data = shared_conversation_data(fetch_page(arguments.url))
        conversation_title = data.get("title")
        title = arguments.title or (conversation_title if isinstance(conversation_title, str) else None)
        if not title:
            raise ValueError("The shared conversation has no title; pass --title")
        print(render_markdown(data, arguments.url, title, arguments.retrieved_on), end="")
    except (OSError, ValueError, urllib.error.URLError) as error:
        parser.exit(1, f"error: {error}\n")


if __name__ == "__main__":
    main()
