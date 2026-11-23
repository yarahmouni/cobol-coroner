"""Tests of the Kiro IDE hook files in .kiro/hooks/ and of the two scripts they call.

Only the files and the commands are tested. The hooks were not run inside the Kiro IDE.
"""
import importlib.util
import json
import re
import shlex
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
HOOKS_DIR = REPO_ROOT / ".kiro" / "hooks"
HOOK_FILES = sorted(HOOKS_DIR.glob("*.json"))
TRIGGERS = {
    "PostFileSave", "PostFileCreate", "PostFileDelete", "PreToolUse", "PostToolUse",
    "Stop", "SessionStart", "UserPromptSubmit", "PreTaskExec", "PostTaskExec",
}
EXPECTED_FILES = {
    "coroner-commit-gate.json",
    "coroner-stop-check.json",
    "fast-tests-on-save.json",
    "public-repo-check.json",
    "trap-catalog-refresh.json",
}
EM_DASH = chr(0x2014)
EN_DASH = chr(0x2013)
HOME_PREFIX = "/" + "Users" + "/"


def load_hook(name):
    data = json.loads((HOOKS_DIR / name).read_text(encoding="utf-8"))
    assert len(data["hooks"]) == 1, f"{name} should hold one hook"
    return data["hooks"][0]


# --- the files ---------------------------------------------------------------

def test_the_five_hook_files_exist():
    assert {path.name for path in HOOK_FILES} == EXPECTED_FILES


@pytest.mark.parametrize("path", HOOK_FILES, ids=lambda path: path.name)
def test_hook_file_has_the_v1_shape(path):
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["version"] == "v1"
    assert isinstance(data["hooks"], list) and data["hooks"]
    for hook in data["hooks"]:
        assert hook["name"].strip()
        assert hook["description"].strip()
        assert hook["trigger"] in TRIGGERS
        if "matcher" in hook:
            re.compile(hook["matcher"])
        if "timeout" in hook:
            assert isinstance(hook["timeout"], int) and hook["timeout"] > 0
        assert isinstance(hook.get("enabled"), bool)
        action = hook["action"]
        if action["type"] == "command":
            assert action["command"].strip()
        else:
            assert action["type"] == "agent"
            assert action["prompt"].strip()


@pytest.mark.parametrize("path", HOOK_FILES, ids=lambda path: path.name)
def test_hook_file_has_no_dash_characters(path):
    text = path.read_text(encoding="utf-8")
    assert EM_DASH not in text and EN_DASH not in text


def test_no_legacy_hook_file_under_kiro():
    assert list((REPO_ROOT / ".kiro").rglob("*.kiro.hook")) == []


def test_command_programs_exist():
    seen = 0
    for path in HOOK_FILES:
        for hook in json.loads(path.read_text(encoding="utf-8"))["hooks"]:
            if hook["action"]["type"] != "command":
                continue
            seen += 1
            words = shlex.split(hook["action"]["command"].replace("{{filePath}}", "x.py"))
            assert words[0] == ".venv/bin/python", f"{path.name}: unexpected program {words[0]}"
            if words[1] == "-m":
                module_path = REPO_ROOT / Path(*words[2].split("."))
                assert module_path.with_suffix(".py").is_file() or (module_path / "__init__.py").is_file(), (
                    f"{path.name}: module {words[2]} not found"
                )
            else:
                assert (REPO_ROOT / words[1]).is_file(), f"{path.name}: script {words[1]} not found"
    assert seen == 4


def test_the_gate_and_stop_files_use_the_commands_of_the_agent_config():
    agent = json.loads((REPO_ROOT / ".kiro" / "agents" / "coroner-auditor.json").read_text(encoding="utf-8"))
    assert load_hook("coroner-commit-gate.json")["action"]["command"] == agent["hooks"]["preToolUse"][0]["command"]
    assert load_hook("coroner-stop-check.json")["action"]["command"] == agent["hooks"]["stop"][0]["command"]
    assert load_hook("coroner-commit-gate.json")["matcher"] == "shell"


def test_triggers_and_matchers():
    assert load_hook("coroner-commit-gate.json")["trigger"] == "PreToolUse"
    assert load_hook("coroner-stop-check.json")["trigger"] == "Stop"
    assert load_hook("fast-tests-on-save.json")["trigger"] == "PostFileSave"
    assert load_hook("public-repo-check.json")["trigger"] == "PreToolUse"
    assert load_hook("public-repo-check.json")["matcher"] == "shell"
    assert load_hook("trap-catalog-refresh.json")["trigger"] == "PostFileSave"
    assert load_hook("trap-catalog-refresh.json")["action"]["type"] == "agent"


# --- the regular expressions ---------------------------------------------------

def test_fast_tests_regex():
    pattern = re.compile(load_hook("fast-tests-on-save.json")["matcher"])
    for subject in (
        "coroner/verdict.py", "tests/test_hooks.py", "coroner/ui/app.py",
        "/work/project/coroner/verdict.py", "C:/work/project/tests/test_hooks.py",
    ):
        assert pattern.search(subject), subject
        assert pattern.match(subject), subject
    for subject in (
        "README.md", "docs/reviews.md", "scripts/kiro_hook_fast_tests.py", "tests/fixtures/sample_trace.txt",
        "coroner/ui/static/htmx.min.js", "samples/credit-fees/java/CreditFees.java",
    ):
        assert not pattern.search(subject), subject
        assert not pattern.match(subject), subject


def test_trap_refresh_regex():
    pattern = re.compile(load_hook("trap-catalog-refresh.json")["matcher"])
    for subject in (
        "samples/traps/T1-ebcdic-match-merge/MATCH-MERGE.cob",
        "/work/project/samples/traps/T1-ebcdic-match-merge/MATCH-MERGE.cob",
        "samples/traps/T1-ebcdic-match-merge/schema.json",
        "samples/traps/T1-ebcdic-match-merge/java/faulty/MatchMerge.java",
    ):
        assert pattern.search(subject), subject
        assert pattern.match(subject), subject
    for subject in (
        "samples/credit-fees/CREDIT-FEES.cob",
        "samples/credit-fees/schema.json",
        "samples/traps/cases.json",
        "samples/traps/T1-ebcdic-match-merge/trap.json",
        "coroner/traps.py",
    ):
        assert not pattern.search(subject), subject
        assert not pattern.match(subject), subject


def test_trap_refresh_regex_matches_every_trap_cobol_program():
    pattern = re.compile(load_hook("trap-catalog-refresh.json")["matcher"])
    programs = sorted((REPO_ROOT / "samples" / "traps").rglob("*.cob"))
    assert programs
    for program in programs:
        assert pattern.search(program.relative_to(REPO_ROOT).as_posix()), program


# --- the commit gate ------------------------------------------------------------

@pytest.mark.parametrize("tool_name", ["shell", "execute_bash", "bash", "executeBash"])
@pytest.mark.parametrize("command", ["ls", "git status"])
def test_commit_gate_allows_other_shell_commands_silently(tool_name, command):
    event = {
        "hook_event_name": "PreToolUse", "cwd": str(REPO_ROOT), "session_id": "s1",
        "tool_name": tool_name, "tool_input": {"command": command},
    }
    result = subprocess.run(
        [sys.executable, "-m", "coroner.hooks", "gate"], input=json.dumps(event),
        capture_output=True, text=True, cwd=REPO_ROOT, timeout=60,
    )
    assert result.returncode == 0
    assert result.stdout == "" and result.stderr == ""


# --- the public repository check --------------------------------------------------

SCRIPT = REPO_ROOT / "scripts" / "kiro_hook_public_repo.py"


def load_script():
    spec = importlib.util.spec_from_file_location("kiro_hook_public_repo", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def git(repo, *args):
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)


def stage(repo, relative, text):
    path = repo / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    git(repo, "add", relative)


def run_check(repo, command):
    event = {
        "hook_event_name": "PreToolUse", "cwd": str(repo), "session_id": "s1",
        "tool_name": "shell", "tool_input": {"command": command},
    }
    return subprocess.run(
        [sys.executable, str(SCRIPT)], input=json.dumps(event),
        capture_output=True, text=True, cwd=repo, timeout=60,
    )


@pytest.fixture
def repo(tmp_path):
    git(tmp_path, "init", "-q")
    stage(tmp_path, "docs/architecture.md", "### Root files\n- `README.md`\n\n### Scripts\n- `scripts/known.py`\n")
    return tmp_path


def test_public_check_blocks_a_commit_with_an_em_dash(repo):
    stage(repo, "docs/note.md", "first line\nsecond " + EM_DASH + " line\n")
    result = run_check(repo, "git commit -m x")
    assert result.returncode == 2
    assert result.stderr.strip().splitlines() == ["docs/note.md:2: added line contains an em dash"]
    block = json.loads(result.stdout)
    assert block == {"decision": "block", "reason": "docs/note.md:2: added line contains an em dash"}


def test_public_check_blocks_an_en_dash(repo):
    stage(repo, "docs/note.md", "range 1" + EN_DASH + "2\n")
    result = run_check(repo, "git commit -m x")
    assert result.returncode == 2
    assert "docs/note.md:1: added line contains an en dash" in result.stderr


def test_public_check_reports_one_line_per_finding(repo):
    stage(repo, "docs/a.md", EM_DASH + "\nok\n" + EN_DASH + "\n")
    stage(repo, "docs/b.md", "x " + EM_DASH + "\n")
    result = run_check(repo, "git commit -m x")
    assert result.returncode == 2
    assert sorted(result.stderr.strip().splitlines()) == [
        "docs/a.md:1: added line contains an em dash",
        "docs/a.md:3: added line contains an en dash",
        "docs/b.md:1: added line contains an em dash",
    ]


def test_public_check_allows_a_clean_commit_silently(repo):
    stage(repo, "docs/note.md", "plain words, a hyphen-ated word and a minus - sign\n")
    result = run_check(repo, "git commit -m x")
    assert result.returncode == 0
    assert result.stdout == "" and result.stderr == ""


@pytest.mark.parametrize("command", ["git status", "git push origin main", "echo git commit", "ls"])
def test_public_check_ignores_other_commands_even_with_a_dash_staged(repo, command):
    stage(repo, "docs/note.md", "bad " + EM_DASH + " line\n")
    result = run_check(repo, command)
    assert result.returncode == 0
    assert result.stdout == "" and result.stderr == ""


def test_public_check_reuses_the_precommit_guard_for_home_paths_and_unlisted_files(repo):
    stage(repo, "docs/paths.md", "see " + HOME_PREFIX + "someone/project\n")
    stage(repo, "stray.txt", "x\n")
    stage(repo, "scripts/known.py", "x = 1\n")
    stage(repo, "scripts/unknown.py", "x = 1\n")
    result = run_check(repo, "git commit -m x")
    assert result.returncode == 2
    lines = sorted(result.stderr.strip().splitlines())
    assert lines == [
        "docs/paths.md: contains forbidden home path prefix",
        "scripts/unknown.py: added scripts file not listed in docs/architecture.md",
        "stray.txt: added root file not listed in docs/architecture.md",
    ]


def test_public_check_ignores_input_that_is_not_json_or_has_no_command(repo):
    for text in ("not json", "{}", '{"tool_input": {}}', '{"tool_input": {"command": 5}}'):
        result = subprocess.run(
            [sys.executable, str(SCRIPT)], input=text, capture_output=True, text=True, cwd=repo, timeout=60,
        )
        assert result.returncode == 0
        assert result.stdout == "" and result.stderr == ""


def test_public_check_does_not_count_removed_lines():
    script = load_script()
    diff = (
        "diff --git a/f.md b/f.md\n--- a/f.md\n+++ b/f.md\n@@ -1,2 +1,2 @@\n"
        "-old " + EM_DASH + " line\n+new line\n-old " + EN_DASH + "\n+other line\n"
    )
    assert script.dash_findings(diff) == []


def test_public_check_line_numbers_follow_the_hunk_header():
    script = load_script()
    diff = "diff --git a/f.md b/f.md\n--- a/f.md\n+++ b/f.md\n@@ -4,0 +5,2 @@\n+fine\n+bad " + EM_DASH + "\n"
    assert script.dash_findings(diff) == ["f.md:6: added line contains an em dash"]


def test_the_guard_code_is_imported_and_not_copied():
    source = SCRIPT.read_text(encoding="utf-8")
    assert "import precommit_guard" in source
    assert "from coroner.hooks import is_git_commit_push_merge" in source
    assert "forbidden home path" not in source
    assert HOME_PREFIX not in source
