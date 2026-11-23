#!/usr/bin/env python3
"""Kiro IDE hook (PreToolUse, shell): check the staged diff before a real git commit.

Reads the event JSON on stdin. Does nothing (exit 0, no output) unless the command is a
git commit. Then it blocks (exit 2) when the staged diff breaks a repository rule:
  - an added line contains an em dash or an en dash;
  - a staged file contains a home path, or a file is added at the repository root or in
    scripts/ without being listed in docs/architecture.md (the checks of
    scripts/precommit_guard.py, reused by import).
One finding per line on stderr; the same text goes into the JSON block form on stdout.
It does not check for private names (see .kiro/steering/public-repo.md): no script can.
"""
import json
import re
import subprocess
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS_DIR.parent))
sys.path.insert(0, str(SCRIPTS_DIR))

import precommit_guard  # noqa: E402
from coroner.hooks import is_git_commit_push_merge  # noqa: E402

EM_DASH = chr(0x2014)
EN_DASH = chr(0x2013)
HUNK = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,\d+)? @@")


def is_git_commit(command):
    """True for a command whose first two words are git commit (the gate's word parsing)."""
    return is_git_commit_push_merge(command) and command.split()[1] == "commit"


def git(repo, *args):
    return subprocess.run(
        ["git", "-C", str(repo), "-c", "core.quotepath=off", *args],
        capture_output=True, check=False,
    )


def added_lines(diff_text):
    """Yield (path, line number, text) for every added line of a git diff made with -U0."""
    path = None
    line_no = 0
    in_hunk = False
    for line in diff_text.split("\n"):
        if line.startswith("diff --git "):
            in_hunk = False
            path = None
        elif not in_hunk and line.startswith("+++ "):
            path = line[6:].split("\t")[0] if line.startswith("+++ b/") else None
        elif line.startswith("@@"):
            match = HUNK.match(line)
            if match:
                line_no = int(match.group(1))
                in_hunk = True
        elif in_hunk and line.startswith("+"):
            yield path, line_no, line[1:]
            line_no += 1


def dash_findings(diff_text):
    findings = []
    for path, line_no, text in added_lines(diff_text):
        where = f"{path or '(unknown file)'}:{line_no}"
        if EM_DASH in text:
            findings.append(f"{where}: added line contains an em dash")
        if EN_DASH in text:
            findings.append(f"{where}: added line contains an en dash")
    return findings


def guard_findings(repo):
    """The findings of scripts/precommit_guard.py check() on the staged files."""
    listing = git(repo, "diff", "--cached", "--name-status", "--diff-filter=AM")
    staged = []
    for line in listing.stdout.decode("utf-8", "replace").splitlines():
        parts = line.split(None, 1)
        if len(parts) == 2:
            staged.append((parts[0], parts[1]))

    def read_text(path):
        shown = git(repo, "show", f":{path}")
        if shown.returncode != 0:
            return None
        try:
            return shown.stdout.decode("utf-8")
        except UnicodeDecodeError:
            return None

    architecture = Path(repo) / "docs" / "architecture.md"
    if architecture.is_file():
        allowed = precommit_guard.parse_allowed_paths(architecture.read_text(encoding="utf-8"))
    else:
        # No list to check against: the unlisted-file rule does not apply.
        allowed = {path for _, path in staged}
    return precommit_guard.check(staged, read_text, allowed)


def main():
    try:
        event = json.loads(sys.stdin.read())
    except json.JSONDecodeError:
        return 0
    tool_input = event.get("tool_input") if isinstance(event, dict) else None
    command = tool_input.get("command", "") if isinstance(tool_input, dict) else ""
    if not isinstance(command, str) or not is_git_commit(command):
        return 0

    top = git(event.get("cwd") or ".", "rev-parse", "--show-toplevel")
    if top.returncode != 0:
        return 0
    repo = Path(top.stdout.decode("utf-8", "replace").strip())

    diff = git(repo, "diff", "--cached", "-U0", "--no-color", "--no-ext-diff")
    findings = dash_findings(diff.stdout.decode("utf-8", "replace")) + guard_findings(repo)
    if not findings:
        return 0
    message = "\n".join(findings)
    print(json.dumps({"decision": "block", "reason": message}))
    print(message, file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
