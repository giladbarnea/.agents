#!/usr/bin/env python3
"""Small shared helpers for structured transcript file tools."""

import os.path
import re
import xml.etree.ElementTree
import xml.sax.saxutils


FILE_TOOLS = {"Read", "Write", "Edit", "Patch", "Delete"}
FILE_OUTPUT_TOOLS = FILE_TOOLS | {"read_many_files"}
SKILL_INVOCATION_PATTERN = re.compile(
    r"\A(?P<body><skill\b.*?</skill>)(?P<tail>.*)\Z", re.DOTALL
)


def split_skill_invocation(block: str) -> tuple[str, str] | None:
    r"""Split one leading skill body from its invocation-specific user instruction.

    >>> split_skill_invocation('<skill name="demo">rules</skill>\n\ndo work')
    ('<skill name="demo">rules</skill>', '\n\ndo work')
    >>> split_skill_invocation('ordinary prose') is None
    True
    """
    match = SKILL_INVOCATION_PATTERN.match(block)
    if match is None:
        return None
    return match.group("body"), match.group("tail")


def path_identity(path: str) -> str:
    """Return a stable comparison key without changing the displayed path.

    Absolute paths resolve filesystem aliases; relative paths remain relative.

    >>> path_identity("notes/../board.json")
    'board.json'
    """
    expanded_path = os.path.expanduser(path)
    if os.path.isabs(expanded_path):
        return os.path.realpath(expanded_path)
    return os.path.normpath(path)


def file_references(block: dict[str, object]) -> list[tuple[str, str, str | None]]:
    """Return `(operation, path, tool_id)` references for a tool-input block.

    >>> file_references({'type': 'tool-input', 'name': 'read_many_files', 'paths': ['a', 'b']})
    [('Read', 'a', None), ('Read', 'b', None)]
    """
    if block.get("type") != "tool-input":
        return []
    name = block.get("name")
    identifier = block.get("id") if isinstance(block.get("id"), str) else None
    if name == "read_many_files":
        paths = block.get("paths")
        if not isinstance(paths, list) or not paths or not all(
            isinstance(path, str) and path for path in paths
        ):
            raise ValueError(f"read_many_files {identifier!r} requires non-empty string paths")
        return [("Read", path, identifier) for path in paths if isinstance(path, str)]
    if name not in FILE_TOOLS:
        return []

    path = block.get("path") or block.get("file_path")
    if not isinstance(path, str) or not path:
        patch = block.get("input")
        match = (
            re.search(r"\*\*\* (?:Update|Add|Delete) File: (.+)", patch)
            if isinstance(patch, str)
            else None
        )
        path = match.group(1) if match else None
    if not isinstance(path, str) or not path:
        raise ValueError(f"{name} {identifier!r} has no file path")
    return [(str(name), path, identifier)]


def render_reference(
    operation: str,
    path: str,
    identifier: str | None,
    native_tool_call_id: str | None = None,
    native_content_index: int | None = None,
) -> str:
    attributes = f"path={xml.sax.saxutils.quoteattr(path)}"
    if identifier is not None:
        attributes += f" id={xml.sax.saxutils.quoteattr(identifier)}"
    if native_tool_call_id is not None:
        attributes += (
            f" native_tool_call_id={xml.sax.saxutils.quoteattr(native_tool_call_id)}"
        )
    if native_content_index is not None:
        attributes += f' native_content_index="{native_content_index}"'
    return f"<{operation} {attributes}/>"


def file_reference(block: str) -> tuple[str, str] | None:
    """Return the operation and path from a rendered file reference.

    >>> file_reference('<Read path="notes.md" id="read"/>')
    ('Read', 'notes.md')
    """
    try:
        element = xml.etree.ElementTree.fromstring(block.strip())
    except xml.etree.ElementTree.ParseError:
        return None
    if element.tag not in FILE_TOOLS or list(element) or (element.text or "").strip():
        return None
    path = element.attrib.get("path")
    return (element.tag, path) if path else None


def reference_path(block: str) -> str | None:
    reference = file_reference(block)
    return reference[1] if reference is not None else None
