#!/usr/bin/env python3
"""Small shared helpers for structured transcript file tools."""

import re
import xml.etree.ElementTree
import xml.sax.saxutils


FILE_TOOLS = {"Read", "Write", "Edit", "Patch", "Delete"}
FILE_OUTPUT_TOOLS = FILE_TOOLS | {"read_many_files"}


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


def render_reference(operation: str, path: str, identifier: str | None) -> str:
    attributes = f"path={xml.sax.saxutils.quoteattr(path)}"
    if identifier is not None:
        attributes += f" id={xml.sax.saxutils.quoteattr(identifier)}"
    return f"<{operation} {attributes}/>"


def reference_path(block: str) -> str | None:
    try:
        element = xml.etree.ElementTree.fromstring(block.strip())
    except xml.etree.ElementTree.ParseError:
        return None
    if element.tag not in FILE_TOOLS or list(element) or (element.text or "").strip():
        return None
    return element.attrib.get("path") or None
