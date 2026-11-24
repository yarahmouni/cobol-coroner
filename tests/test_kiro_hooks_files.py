"""Tests of the Kiro IDE hook files in .kiro/hooks/ and of the two scripts they call.

The files, the commands and the regular expressions are tested here. The owner ran the hooks in the
Kiro IDE on Windows on 2026-11-24 (with scripts\\kiro-hook.cmd); the quoted command form of the
files was measured with /bin/sh on macOS only, as the tests below do.
"""
import importlib.util
import json
import os
import re
import shlex
import stat
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
LAUNCHER_COMMAND = "scripts/kiro-hook.cmd"
QUOTED_LAUNCHER = '"' + LAUNCHER_COMMAND + '"'
POLYGLOT_FIRST_LINE = ':; exec "$(dirname "$0")/kiro-hook" "$@" #'
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
            assert words[0] == LAUNCHER_COMMAND, f"{path.name}: unexpected program {words[0]}"
            if words[1] == "-m":
                module_path = REPO_ROOT / Path(*words[2].split("."))
                assert module_path.with_suffix(".py").is_file() or (module_path / "__init__.py").is_file(), (
                    f"{path.name}: module {words[2]} not found"
                )
            else:
                assert (REPO_ROOT / words[1]).is_file(), f"{path.name}: script {words[1]} not found"
    assert seen == 4


def test_no_hook_command_names_an_interpreter_path_or_bare_python():
    seen = 0
    for path in HOOK_FILES:
        for hook in json.loads(path.read_text(encoding="utf-8"))["hooks"]:
            if hook["action"]["type"] != "command":
                continue
            seen += 1
            command = hook["action"]["command"]
            assert "bin/python" not in command, f"{path.name}: {command}"
            assert "Scripts" not in command and ".venv" not in command, f"{path.name}: {command}"
            assert not command.lstrip().lower().startswith("python"), f"{path.name}: {command}"
            assert command.startswith(QUOTED_LAUNCHER + " "), f"{path.name}: {command}"
    assert seen == 4


def test_the_gate_and_stop_files_use_the_commands_of_the_agent_config():
    """The IDE hooks run the same module and subcommand as the kiro-cli agent, through the launcher.

    The agent configuration (kiro-cli on macOS, measured in docs/evidence/) keeps its direct
    interpreter path on purpose, so only the part after the interpreter or launcher is compared.
    """
    agent = json.loads((REPO_ROOT / ".kiro" / "agents" / "coroner-auditor.json").read_text(encoding="utf-8"))

    def arguments(command, program):
        assert command.startswith(program + " "), command
        return command[len(program) + 1:]

    gate = load_hook("coroner-commit-gate.json")["action"]["command"]
    stop = load_hook("coroner-stop-check.json")["action"]["command"]
    agent_gate = agent["hooks"]["preToolUse"][0]["command"]
    agent_stop = agent["hooks"]["stop"][0]["command"]
    assert arguments(gate, QUOTED_LAUNCHER) == arguments(agent_gate, ".venv/bin/python") == "-m coroner.hooks gate"
    assert arguments(stop, QUOTED_LAUNCHER) == arguments(agent_stop, ".venv/bin/python") == "-m coroner.hooks stop"
    assert load_hook("coroner-commit-gate.json")["matcher"] == "shell"


def test_command_hook_descriptions_say_what_was_measured_on_windows_and_on_macos():
    windows = (
        "Windows: the owner ran the hooks in the Kiro IDE on Windows on 2026-11-24 with scripts\\kiro-hook.cmd; "
        "this quoted command form, which also runs in a POSIX shell, was measured on macOS only."
    )
    runs_through = (
        "The command runs through scripts/kiro-hook.cmd, which hands over to scripts/kiro-hook in a POSIX shell, "
        "and picks the repository virtual environment."
    )
    for name in ("coroner-commit-gate.json", "coroner-stop-check.json", "fast-tests-on-save.json", "public-repo-check.json"):
        description = load_hook(name)["description"]
        assert windows in description, name
        assert runs_through in description, name
        assert "untested" not in description, name


# --- the launchers ----------------------------------------------------------------

LAUNCHER = REPO_ROOT / "scripts" / "kiro-hook"
LAUNCHER_CMD = REPO_ROOT / "scripts" / "kiro-hook.cmd"


def make_fake_repository(tmp_path, python_relative):
    """A copy of the POSIX launcher in <root>/scripts, with a fake interpreter at the given path.

    The root name holds a space, to check quoting. The fake interpreter prints its own name, its
    arguments, the working directory and the standard input, which shows what the launcher passed.
    """
    root = tmp_path / "my repo"
    (root / "scripts").mkdir(parents=True)
    launcher = root / "scripts" / "kiro-hook"
    launcher.write_text(LAUNCHER.read_text(encoding="utf-8"), encoding="utf-8")
    launcher.chmod(0o755)
    if python_relative:
        python = root / python_relative
        python.parent.mkdir(parents=True)
        python.write_text(
            '#!/bin/sh\necho "fake-python"\nfor argument in "$@"; do echo "arg:$argument"; done\n'
            'echo "cwd:$(pwd)"\necho "stdin:$(cat)"\nexit 7\n',
            encoding="utf-8",
        )
        python.chmod(0o755)
    return root, launcher


def run_launcher(launcher, cwd, *arguments, stdin=""):
    return subprocess.run(
        [str(launcher), *arguments], input=stdin, capture_output=True, text=True, cwd=cwd, timeout=60,
    )


def test_both_launchers_exist():
    assert LAUNCHER.is_file()
    assert LAUNCHER_CMD.is_file()


def test_the_posix_launcher_is_a_shell_script_with_the_executable_bit():
    assert LAUNCHER.read_text(encoding="utf-8").startswith("#!/bin/sh\n")
    if os.name != "nt":
        assert LAUNCHER.stat().st_mode & stat.S_IXUSR, "scripts/kiro-hook must be executable (git update-index --chmod=+x)"


def test_the_launcher_runs_the_repository_interpreter_and_passes_arguments_and_stdin(tmp_path):
    root, launcher = make_fake_repository(tmp_path, ".venv/bin/python")
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    result = run_launcher(launcher, elsewhere, "-m", "coroner.hooks", "gate", "a b", stdin='{"x": 1}')
    assert result.returncode == 7, "the exit status of the interpreter is the exit status of the launcher"
    assert result.stdout.splitlines() == [
        "fake-python", "arg:-m", "arg:coroner.hooks", "arg:gate", "arg:a b",
        f"cwd:{elsewhere.resolve()}", 'stdin:{"x": 1}',
    ]
    assert result.stderr == ""


def test_the_launcher_finds_the_interpreter_from_its_own_location_not_the_working_directory(tmp_path):
    _, launcher = make_fake_repository(tmp_path, ".venv/bin/python")
    for cwd in (tmp_path, launcher.parent, launcher.parent.parent):
        assert run_launcher(launcher, cwd).stdout.splitlines()[0] == "fake-python"


def test_the_launcher_falls_back_to_the_windows_layout_of_the_environment(tmp_path):
    """Git Bash on Windows runs this script, and the interpreter is .venv/Scripts/python.exe there."""
    _, launcher = make_fake_repository(tmp_path, ".venv/Scripts/python.exe")
    result = run_launcher(launcher, tmp_path, "-c", "x")
    assert result.stdout.splitlines()[:3] == ["fake-python", "arg:-c", "arg:x"]


def test_without_an_environment_the_launcher_says_so_and_exits_1_without_a_block(tmp_path):
    """Exit 1 is no block: the gate blocks with a JSON decision and exit 2. coroner.hooks fails open too."""
    _, launcher = make_fake_repository(tmp_path, None)
    result = run_launcher(launcher, tmp_path, "-m", "coroner.hooks", "gate", stdin="{}")
    assert result.returncode == 1
    assert result.stdout == ""
    assert "no virtual environment" in result.stderr and ".venv" in result.stderr
    assert "block" not in result.stderr


def test_the_launcher_runs_the_python_of_the_repository_venv():
    """With the repository virtual environment (a developer machine), the interpreter is that environment's.

    Where there is none (the CI image and the CI checkout have no .venv), the launcher must say so.
    """
    result = run_launcher(LAUNCHER, REPO_ROOT, "-c", "import sys; print(sys.prefix)")
    if (REPO_ROOT / ".venv").is_dir():
        assert result.returncode == 0, result.stderr
        assert Path(result.stdout.strip()).resolve() == (REPO_ROOT / ".venv").resolve()
    else:
        assert result.returncode == 1
        assert "no virtual environment" in result.stderr


def test_the_windows_launcher_text():
    text = LAUNCHER_CMD.read_text(encoding="utf-8")
    assert ".venv\\Scripts\\python.exe" in text
    assert '"%PYTHON%" %*' in text, "all arguments go to Python"
    assert "%~dp0" in text, "the environment is found from the location of the launcher"
    assert "exit /b %ERRORLEVEL%" in text, "the exit status of Python is the exit status of the launcher"
    assert "exit /b 1" in text and ">&2 echo" in text, "no environment: a message on stderr and exit 1"
    assert "bin/python" not in text


def test_the_windows_launcher_starts_with_the_polyglot_line_and_has_the_executable_bit():
    lines = LAUNCHER_CMD.read_text(encoding="utf-8").splitlines()
    assert lines[0] == POLYGLOT_FIRST_LINE
    assert lines[1] == "@echo off", "cmd.exe skips the first line as a label, then echo is switched off"
    assert lines[2].startswith("rem "), "one rem line explains the first line"
    if os.name != "nt":
        assert LAUNCHER_CMD.stat().st_mode & stat.S_IXUSR, "scripts/kiro-hook.cmd must be executable"


@pytest.mark.skipif(os.name == "nt", reason="runs the quoted command form with /bin/sh")
@pytest.mark.parametrize("hook_file", [
    "coroner-commit-gate.json", "coroner-stop-check.json", "fast-tests-on-save.json", "public-repo-check.json",
])
def test_the_quoted_command_form_runs_in_a_posix_shell_and_passes_arguments_and_stdin(tmp_path, hook_file):
    """The command string of each hook file, run with /bin/sh from a copy of both launchers.

    The first line of scripts/kiro-hook.cmd makes sh hand over to scripts/kiro-hook, which finds the
    fake interpreter in the temporary layout (the root name holds a space).
    """
    root, _ = make_fake_repository(tmp_path, ".venv/bin/python")
    launcher_cmd = root / "scripts" / "kiro-hook.cmd"
    launcher_cmd.write_text(LAUNCHER_CMD.read_text(encoding="utf-8"), encoding="utf-8")
    launcher_cmd.chmod(0o755)
    command = load_hook(hook_file)["action"]["command"].replace("{{filePath}}", "tests/test_x.py")
    words = shlex.split(command)
    result = subprocess.run(
        ["/bin/sh", "-c", command], input='{"event": 1}', capture_output=True, text=True, cwd=root, timeout=60,
    )
    assert result.returncode == 7, "the exit status of the interpreter is the exit status of the command"
    assert result.stdout.splitlines() == [
        "fake-python", *[f"arg:{word}" for word in words[1:]], f"cwd:{root.resolve()}", 'stdin:{"event": 1}',
    ]
    assert result.stderr == ""


def test_both_launchers_and_the_hook_files_are_listed_in_the_architecture_file():
    layout = (REPO_ROOT / "docs" / "architecture.md").read_text(encoding="utf-8")
    assert "`scripts/kiro-hook`" in layout
    assert "`scripts/kiro-hook.cmd`" in layout


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


def test_fast_tests_regex_accepts_windows_paths_with_backslashes():
    """Kiro passes Windows paths with backslashes (measured by the owner, 2026-11-24)."""
    pattern = re.compile(load_hook("fast-tests-on-save.json")["matcher"])
    for subject in (
        "coroner\\verdict.py", "tests\\test_verdict.py", "C:\\x\\cobol-coroner\\tests\\test_verdict.py",
        "coroner\\ui\\app.py",
    ):
        assert pattern.search(subject), subject
        assert pattern.match(subject), subject
    for subject in ("coroner\\verdict.txt", "docs\\x.py", "scripts\\kiro_hook_fast_tests.py", "tests\\fixtures\\x.txt"):
        assert not pattern.search(subject), subject
        assert not pattern.match(subject), subject


def test_trap_refresh_regex_accepts_windows_paths_with_backslashes():
    pattern = re.compile(load_hook("trap-catalog-refresh.json")["matcher"])
    for subject in (
        "samples\\traps\\T6-cursed-modulo\\ROTATION-SLOT.cob",
        "samples\\traps\\T1-ebcdic-match-merge\\schema.json",
        "C:\\x\\cobol-coroner\\samples\\traps\\T1-ebcdic-match-merge\\java\\faulty\\MatchMerge.java",
    ):
        assert pattern.search(subject), subject
        assert pattern.match(subject), subject
    for subject in (
        "samples\\credit-fees\\schema.json", "samples\\traps\\cases.json",
        "samples\\traps\\T1-ebcdic-match-merge\\trap.json", "coroner\\traps.py",
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
