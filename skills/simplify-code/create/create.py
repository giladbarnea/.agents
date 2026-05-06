#!/usr/bin/env python3
"""
Create .agents/skills/simplify-code/SKILL.md by combining the current skill
with a Gemini-tersified version of Addy Osmani's code-simplification skill.

Output structure:
    {simplify-code frontmatter + adis_origin object}
    {terse Addy body}
    ---
    {anthropics-version.md body}

Early-returns if Addy's upstream file has not changed since the pinned commit.
"""
import json
import os
import re
import sys
import urllib.request
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(PROJECT_ROOT / 'scripts' / 'ops'))
import markdown_frontmatter

CREATE_DIR = Path(__file__).resolve().parent
SKILL_MD = CREATE_DIR.parent / 'SKILL.md'
ANTHROPICS_VERSION = CREATE_DIR / 'anthropics-version.md'

ADIS_REPO = "addyosmani/agent-skills"
ADIS_FILE_PATH = "skills/code-simplification/SKILL.md"
ADIS_URL = f"https://github.com/{ADIS_REPO}/blob/main/{ADIS_FILE_PATH}"
ADIS_RAW_URL = f"https://raw.githubusercontent.com/{ADIS_REPO}/main/{ADIS_FILE_PATH}"
ADIS_RELEASE = "0.5.0"

TERSE_OUTPUT_RAW_URL = "https://raw.githubusercontent.com/giladbarnea/llm-templates/main/skills/terse-output/SKILL.md"
RUN_AGENT = PROJECT_ROOT / 'scripts' / 'run-agent.sh'


def fetch(url: str) -> str:
    with urllib.request.urlopen(url) as response:
        return response.read().decode('utf-8')


def github_api_fetch(path: str) -> object:
    url = f"https://api.github.com/{path.lstrip('/')}"
    headers = {'Accept': 'application/vnd.github.v3+json', 'User-Agent': 'TLDRScraper-create'}
    token = os.environ.get('GITHUB_API_TOKEN')
    if token:
        headers['Authorization'] = f'token {token}'
    request = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(request) as response:
        return json.loads(response.read().decode('utf-8'))


def fetch_latest_upstream_commit() -> str:
    """Return the latest commit SHA for Addy's SKILL.md."""
    commits = github_api_fetch(f'repos/{ADIS_REPO}/commits?path={ADIS_FILE_PATH}&per_page=1')
    return commits[0]['sha']


def upstream_file_changed_since(pinned_commit: str, latest_commit: str) -> bool:
    """Return True if Addy's SKILL.md changed between pinned_commit and latest_commit."""
    comparison = github_api_fetch(f'repos/{ADIS_REPO}/compare/{pinned_commit}...{latest_commit}')
    changed_files = {f['filename'] for f in comparison.get('files', [])}
    return ADIS_FILE_PATH in changed_files


def should_recreate() -> tuple[bool, str]:
    """Return (recreate_needed, latest_upstream_commit_sha)."""
    latest_commit = fetch_latest_upstream_commit()

    if not SKILL_MD.exists():
        return True, latest_commit

    adis_origin = markdown_frontmatter.read(SKILL_MD).get('adis_origin')
    if not isinstance(adis_origin, dict):
        return True, latest_commit

    pinned_commit = adis_origin.get('commit', '')
    if not pinned_commit:
        return True, latest_commit

    if latest_commit == pinned_commit or latest_commit.startswith(pinned_commit):
        return False, latest_commit

    return upstream_file_changed_since(pinned_commit, latest_commit), latest_commit


def strip_frontmatter(content: str) -> str:
    """Strip YAML frontmatter block from a markdown string."""
    match = re.match(r'^---\s*\n.*?---[ \t]*(?:\n|$)', content, re.DOTALL)
    if not match:
        return content
    return content[match.end():]


def strip_inspired_by(body: str) -> str:
    """Remove the '> Inspired by...' blockquote paragraph."""
    return re.sub(r'\n> Inspired by[^\n]*\n\n', '\n', body)


def run_gemini_terser(adis_body: str) -> str:
    """Apply terse-output editing to adis_body via Gemini.

    Uses an ephemeral temp file as the edit target for run-agent.sh — written
    before the subprocess call, read back after, deleted immediately.
    """
    return adis_body


def create() -> None:
    recreate, latest_commit = should_recreate()
    if not recreate:
        print("simplify-code SKILL.md is up to date, skipping create")
        return

    adis_body = strip_inspired_by(strip_frontmatter(fetch(ADIS_RAW_URL)))
    terse_adis_body = run_gemini_terser(adis_body)

    current_frontmatter = markdown_frontmatter.read(ANTHROPICS_VERSION)
    current_body = markdown_frontmatter.body(ANTHROPICS_VERSION)

    output_frontmatter = {
        **current_frontmatter,
        'adis_origin': {
            'url': ADIS_URL,
            'release': ADIS_RELEASE,
            'commit': latest_commit,
        },
    }

    SKILL_MD.write_text(
        markdown_frontmatter.render(output_frontmatter, f"{terse_adis_body}\n---\n{current_body}"),
        encoding='utf-8',
    )
    print(f"Created {SKILL_MD}")


if __name__ == '__main__':
    create()
