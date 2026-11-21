"""The image carries the trap catalog files so get_detection_matrix works with no volume.

The final stage of the Dockerfile runs `python3 -m coroner traps` and scripts/keep_catalog_only.sh in
one RUN step, so the image keeps runs/trap_catalog.json and runs/trap_catalog.txt and no run folder.
The fast test reads the Dockerfile. The slow test makes the same step on this machine in a temporary
base directory and calls the real MCP server over stdio.
"""
import asyncio
import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

from test_mcp_server import run_mcp_session

REPO_ROOT = Path(__file__).resolve().parent.parent
DOCKERFILE = REPO_ROOT / "Dockerfile"
SCRIPT = REPO_ROOT / "scripts" / "keep_catalog_only.sh"
CATALOG_FILES = ("trap_catalog.json", "trap_catalog.txt")


def final_stage_instructions():
    """Return the (keyword, arguments) instructions of the last stage, continuation lines joined."""
    text = DOCKERFILE.read_text()
    text = re.sub(r"\\\n", " ", text)
    instructions = []
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        keyword, _, rest = line.partition(" ")
        instructions.append((keyword.upper(), rest.strip()))
    last_from = max(i for i, (kw, _) in enumerate(instructions) if kw == "FROM")
    return instructions[last_from + 1:]


def test_dockerfile_final_stage_builds_catalog_and_removes_run_folders():
    stage = final_stage_instructions()

    pip_indexes = [i for i, (kw, rest) in enumerate(stage) if kw == "RUN" and "pip install" in rest]
    assert pip_indexes, "final stage has no pip install"

    traps_indexes = [i for i, (kw, rest) in enumerate(stage) if kw == "RUN" and "coroner traps" in rest]
    assert len(traps_indexes) == 1, "final stage must run `coroner traps` in exactly one RUN instruction"
    traps_index = traps_indexes[0]
    traps_run = stage[traps_index][1]

    assert traps_index > max(pip_indexes), "`coroner traps` must run after the pip install"

    users = [(i, rest) for i, (kw, rest) in enumerate(stage) if kw == "USER" and i < traps_index]
    assert users and users[-1][1] == "coroner", "`coroner traps` must run as the coroner user (USER coroner)"

    # The removal is in the same RUN instruction, so no layer keeps the run folders
    assert "scripts/keep_catalog_only.sh" in traps_run
    # The build fails when either step fails
    assert "&&" in traps_run and "||" not in traps_run and ";" not in traps_run

    # No base directory: the catalog is written under /app/runs
    assert "CORONER_BASE_DIR" not in traps_run
    for keyword, rest in stage:
        if keyword in ("ENV", "ARG"):
            assert "CORONER_BASE_DIR" not in rest, "final stage must not set CORONER_BASE_DIR"

    # Nothing later brings run folders back
    for keyword, rest in stage[traps_index + 1:]:
        assert keyword not in ("COPY", "ADD"), f"{keyword} after the catalog step: {rest}"


def test_keep_catalog_script_keeps_the_two_catalog_files_and_deletes_the_rest():
    text = SCRIPT.read_text()
    for name in CATALOG_FILES:
        assert f"! -name {name}" in text, f"script must keep {name}"
    assert "-mindepth 1 -maxdepth 1" in text
    assert "rm -rf" in text


def test_dockerignore_excludes_runs():
    lines = [line.strip() for line in (REPO_ROOT / ".dockerignore").read_text().splitlines()]
    assert "runs" in lines, "the catalog is built inside the image, never copied from the context"


@pytest.mark.slow
def test_catalog_only_base_directory_serves_detection_matrix(tmp_path):
    """Same step as the Dockerfile in a temporary base directory, then the real MCP server."""
    env = os.environ.copy()
    env["CORONER_BASE_DIR"] = str(tmp_path)
    runs = tmp_path / "runs"

    built = subprocess.run(
        [sys.executable, "-m", "coroner", "traps"],
        cwd=REPO_ROOT, env=env, capture_output=True, text=True, timeout=900,
    )
    assert built.returncode == 0, f"coroner traps failed: {built.stdout[-500:]} {built.stderr[-500:]}"
    run_folders = [p for p in runs.iterdir() if p.is_dir()]
    assert len(run_folders) >= 10, f"the catalog build made only {len(run_folders)} run folders"

    kept = subprocess.run(
        ["bash", str(SCRIPT), str(tmp_path)],
        cwd=REPO_ROOT, env=env, capture_output=True, text=True, timeout=120,
    )
    assert kept.returncode == 0, kept.stderr

    left = sorted(p.name for p in runs.iterdir())
    assert not [p for p in runs.iterdir() if p.is_dir()], f"no run folder is left, found {left}"
    assert left == sorted(CATALOG_FILES), f"only the two catalog files remain, found {left}"

    async def check(session):
        everything = await session.call_tool("get_detection_matrix", arguments={})
        assert everything.is_error is False, everything.content[0].text
        catalog = json.loads(everything.content[0].text)
        assert [t["id"] for t in catalog["traps"]] == ["T1", "T2", "T3", "T4", "T5", "T6"]

        one = await session.call_tool("get_detection_matrix", arguments={"trap_id": "T1"})
        assert one.is_error is False, one.content[0].text
        t1 = json.loads(one.content[0].text)
        assert t1["case_name"] == "The Missing Branch"
        assert t1["cases_detected"] == 682
        assert t1["cases_generated"] == 2000
        assert t1["faulty_run_id"] == "f584d5f35228"
        assert t1 == next(t for t in catalog["traps"] if t["id"] == "T1")

        # The run folder named by the catalog is not in the base directory until the audit is rerun
        verdict = await session.call_tool("get_verdict", arguments={"run_id": t1["faulty_run_id"]})
        assert verdict.is_error is True

    asyncio.run(run_mcp_session(check, base_dir=tmp_path))
