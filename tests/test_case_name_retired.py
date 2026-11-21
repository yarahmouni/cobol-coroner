"""The former name of Case 3 (renamed by the owner decision Q8) must not appear in any file."""
import os
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SKIPPED_DIRS = {
    ".git", ".venv", ".worktrees", "build", "runs", "prompts",
    "node_modules", "target", "__pycache__", ".pytest_cache",
}
MAX_BYTES = 5 * 1024 * 1024

# Built from parts so that this file does not contain the name it looks for.
# The last part allows any apostrophe character.
RETIRED_NAME = re.compile(
    re.escape("The Negative ") + re.escape("That Wasn") + r".t",
    re.IGNORECASE,
)


def find_files_with_retired_name(root: Path) -> list[str]:
    offenders = []
    for folder, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d not in SKIPPED_DIRS]
        for name in files:
            path = Path(folder) / name
            try:
                if path.is_symlink() or path.stat().st_size > MAX_BYTES:
                    continue
                text = path.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            if RETIRED_NAME.search(text):
                offenders.append(str(path.relative_to(root)))
    return sorted(offenders)


def test_retired_name_appears_in_no_file():
    offenders = find_files_with_retired_name(REPO_ROOT)
    assert not offenders, "the retired Case 3 name is still in: " + ", ".join(offenders)


def test_scan_finds_the_name_in_a_temporary_tree(tmp_path):
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "a.md").write_text("Case 3 " + "The Negative " + "That Wasn't", encoding="utf-8")
    (tmp_path / "docs" / "curly.md").write_text("the negative " + "that wasn\u2019t", encoding="utf-8")
    (tmp_path / "docs" / "clean.md").write_text("The Phantom Minus", encoding="utf-8")
    (tmp_path / "runs").mkdir()
    (tmp_path / "runs" / "skipped.md").write_text("The Negative " + "That Wasn't", encoding="utf-8")
    assert find_files_with_retired_name(tmp_path) == ["docs/a.md", "docs/curly.md"]
