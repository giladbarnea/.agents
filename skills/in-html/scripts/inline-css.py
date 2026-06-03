#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""Inline a CSS file into an HTML file's <head> as a <style> block, making it self-contained.

Any <link rel="stylesheet"> pointing at the given CSS file (by basename) is removed,
so the output has no dangling external reference.

Usage:
    ./inline-css.py page.html style.css -o page.self-contained.html
"""
import argparse
import re
import sys
from pathlib import Path


def inline_css(html: str, css: str, css_basename: str) -> str:
    """Return html with css injected as a <style> block in <head>, dropping links to css_basename.

    >>> inline_css("<head><link rel='stylesheet' href='s.css'></head><body>x</body>", "a{}", "s.css")
    '<head><style>\\na{}\\n</style></head><body>x</body>'
    """
    link_pattern = re.compile(
        r"""<link\b[^>]*?href\s*=\s*['"][^'"]*""" + re.escape(css_basename) + r"""['"][^>]*?>\s*""",
        re.IGNORECASE,
    )
    html = link_pattern.sub("", html)
    style_block = "<style>\n" + css + "\n</style>"
    if re.search(r"</head>", html, re.IGNORECASE):
        return re.sub(r"</head>", style_block + "</head>", html, count=1, flags=re.IGNORECASE)
    # No <head>: fail loudly rather than guess.
    sys.exit("error: no </head> found in HTML; cannot inject <style>")


def main() -> None:
    parser = argparse.ArgumentParser(description="Inline a CSS file into an HTML <head> as <style>.")
    parser.add_argument("html", type=Path, help="path to the HTML file")
    parser.add_argument("css", type=Path, help="path to the CSS file")
    parser.add_argument("-o", "--output", type=Path, required=True, help="output HTML path")
    args = parser.parse_args()

    html_text = args.html.read_text()
    css_text = args.css.read_text()
    result = inline_css(html_text, css_text, args.css.name)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(result)
    print(f"wrote self-contained HTML → {args.output}")


if __name__ == "__main__":
    main()
