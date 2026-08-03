#!/usr/bin/env -S uv run
# /// script
# requires-python = "==3.12.*"
# dependencies = ["jinja2"]
# ///
"""Render a Jinja2 template file to its output.

Given a `.j2` file, renders it with Jinja2 and writes the result
next to the template with the `.j2` extension stripped.

    render.py path/to/file.md.j2   # writes path/to/file.md
"""

import argparse
import re
import sys
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, pass_environment


FRONTMATTER_PATTERN = re.compile(
    r"\A---[ \t]*\r?\n.*?\r?\n---[ \t]*(?:\r?\n|\Z)", re.DOTALL
)


def strip_frontmatter(content: str) -> str:
    r"""Remove leading YAML frontmatter when present.

    >>> strip_frontmatter("Plain Markdown")
    'Plain Markdown'
    >>> strip_frontmatter("---\nname: example\n---\nBody")
    'Body'
    """
    return FRONTMATTER_PATTERN.sub("", content, count=1)


@pass_environment
def skill_body(environment: Environment, template_name: str) -> str:
    """Load a skill through the active Jinja loader without its frontmatter."""
    if environment.loader is None:
        raise RuntimeError("The Jinja environment has no template loader.")
    source, _, _ = environment.loader.get_source(environment, template_name)
    return strip_frontmatter(source)


def render_j2(j2_path: Path) -> str:
    """Render a Jinja2 template file to string."""
    template_directory = str(j2_path.parent)
    hub_directory = str(Path(__file__).resolve().parent)
    env = Environment(
        loader=FileSystemLoader([template_directory, hub_directory, "/"])
    )
    env.globals["skill_body"] = skill_body
    template = env.get_template(j2_path.name)
    return template.render()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Render a Jinja2 template and write the output next to it."  # noqa: E501
    )
    parser.add_argument(
        "template",
        nargs="?",
        type=Path,
        help="Path to the .j2 template file.",
    )
    parser.add_argument(
        "-n",
        "--dry-run",
        action="store_true",
        help="Check if output would change without writing.",
    )
    parser.add_argument(
        "--stdout",
        action="store_true",
        help="Print the rendered output to stdout without writing.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    if args.template is None:
        # argparse already printed usage; exit cleanly.
        sys.exit(0)

    j2_path = args.template.resolve()
    if not j2_path.exists():
        print(f"Error: {j2_path} not found", file=sys.stderr)
        sys.exit(1)

    output_path = j2_path.parent / j2_path.name.replace(".j2", "")
    rendered = render_j2(j2_path)

    if args.stdout:
        sys.stdout.write(rendered)
        sys.exit(0)

    if args.dry_run:
        if not output_path.exists():
            print(f"✗ {output_path} would have been changed.", file=sys.stderr)
            sys.exit(1)
        existing = output_path.read_text().strip()
        if rendered.strip() == existing:
            print(f"✓ No changes would have been made to {output_path}.", file=sys.stderr)
            sys.exit(0)
        else:
            print(f"✗ {output_path} would have been changed.", file=sys.stderr)
            sys.exit(1)

    output_path.write_text(rendered)
    print(f"✓ Rendered → {output_path}")


if __name__ == "__main__":
    main()
