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
import sys
from pathlib import Path
from jinja2 import Environment, FileSystemLoader


def render_j2(j2_path: Path) -> str:
    """Render a Jinja2 template file to string."""
    template_dir = str(j2_path.parent)
    env = Environment(loader=FileSystemLoader([template_dir, "/"]))
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

    if args.dry_run:
        if not output_path.exists():
            print(f"✗ {output_path} would have been changed.", file=sys.stderr)
            sys.exit(1)
        existing = output_path.read_text().strip()
        if rendered.strip() == existing:
            print("✓ No changes would have been made.", file=sys.stderr)
            sys.exit(0)
        else:
            print(f"✗ {output_path} would have been changed.", file=sys.stderr)
            sys.exit(1)

    output_path.write_text(rendered)
    print(f"Rendered → {output_path}")


if __name__ == "__main__":
    main()
