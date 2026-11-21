"""Integration and constraints of the guided story (guided-story Task 15, Req 9 and 10).

The slow tests use the real runs of the fixtures story_runs and fool_runs (tests/conftest.py) in
temporary base directories. Expected values are read from the files of those runs.
"""
import json
import re
from decimal import Decimal
from pathlib import Path

import pytest

from story_html import anchors, listing_lines, visible_text

REPO_ROOT = Path(__file__).resolve().parent.parent
EM_DASH = chr(0x2014)


def _entry(catalog, trap_id):
    return next(trap for trap in catalog["traps"] if trap["id"] == trap_id)


def _read(run_dir, name):
    return json.loads((run_dir / name).read_text())


# ------------------------------------------------------------------ no em dash in the files of this work


def test_the_story_files_have_no_em_dash():
    ui = REPO_ROOT / "coroner" / "ui"
    files = [
        *sorted((ui / "templates").glob("story*.html")),
        *sorted((ui / "templates").glob("fool*.html")),
        ui / "templates" / "index.html",
        ui / "static" / "story.js",
        ui / "story.py",
        ui / "story_routes.py",
        REPO_ROOT / "coroner" / "cases.py",
        REPO_ROOT / "samples" / "traps" / "cases.json",
        *sorted((REPO_ROOT / "samples" / "traps").glob("*/trap.json")),
        *sorted((REPO_ROOT / ".kiro" / "specs" / "guided-story").glob("*.md")),
        REPO_ROOT / "scripts" / "deploy_check.py",
        *sorted(Path(__file__).parent.glob("test_story_*.py")),
        Path(__file__).parent / "story_html.py",
    ]
    assert len(files) >= 30
    spec_files = {p.name for p in files if p.parent.name == "guided-story"}
    assert spec_files == {"requirements.md", "design.md", "tasks.md"}
    for path in files:
        assert EM_DASH not in path.read_text(encoding="utf-8"), str(path.relative_to(REPO_ROOT))


# ------------------------------------------------------------------ the eight steps in one walk


def _step_markers(story_runs, step):
    """Strings the page of a step must contain, built from the files of the T1 runs."""
    entry = _entry(story_runs.catalog, "T1")
    faulty = story_runs.base / "runs" / entry["faulty_run_id"]
    correct = story_runs.base / "runs" / entry["correct_run_id"]
    verdict = _read(faulty, "verdict.json")
    reconciliation = _read(faulty, "branch_reconciliation.json")
    if step == 1:
        return ["Every night, the bank reconciles branch subtotals"]
    if step == 2:
        return [reconciliation["grand_total"]["cobol"]] + [b["cobol_subtotal"] for b in reconciliation["branches"]]
    if step == 3:
        totals = reconciliation["grand_total"]
        return [f"COBOL grand total: {totals['cobol']}", f"Java grand total: {totals['java']}"]
    if step == 4:
        return [f"{verdict['cases_divergent']} of {verdict['cases_total']} batches diverge", "ZOMBIE"]
    if step == 5:
        position, case_id = next(
            (n, c["case_id"]) for n, c in enumerate(_read(faulty, "comparison_results.json")["cases"], 1) if c["divergent"]
        )
        return ["Cause of death", f"The first divergent case is {case_id} (case {position} of {verdict['cases_total']})."]
    if step == 6:
        return [json.loads((REPO_ROOT / "samples/traps/T1-ebcdic-match-merge/trap.json").read_text())["business_fix"]]
    if step == 7:
        alive = _read(correct, "verdict.json")
        return [f"{alive['cases_divergent']} of {alive['cases_total']} batches diverge", "ALIVE"]
    return ["Editing a certificate makes it INVALID. The audit result cannot be faked."]


@pytest.mark.slow
def test_walk_through_the_eight_steps_with_the_real_routes(story_runs, story_client):
    """Follow Next from /story to the home page: each response holds its measured values."""
    path = "/story"
    for step in range(1, 9):
        response = story_client.get(path)
        assert response.status_code == 200, path
        text = visible_text(response.text)
        assert f"Step {step} of 8" in text, path
        for marker in _step_markers(story_runs, step):
            assert marker in text, (step, marker)
        next_links = [a["href"] for a in anchors(response.text) if a.get("class") == "story-next"]
        assert len(next_links) == 1
        path = next_links[0]
    assert path == "/"
    assert story_client.get(path).status_code == 200


@pytest.mark.slow
@pytest.mark.parametrize("step", [1, 2, 5, 6])
def test_the_listing_of_a_step_is_the_cobol_file(story_client, step):
    source = (REPO_ROOT / "samples/traps/T1-ebcdic-match-merge/MATCH-MERGE.cob").read_text().split("\n")
    rendered = listing_lines(story_client.get(f"/story/step/{step}").text)
    assert rendered
    assert all(text == source[number - 1].rstrip("\r") for number, text in rendered)


# ------------------------------------------------------------------ nothing written outside the temporary folders


def _listing(folder: Path):
    return sorted((p.name, p.stat().st_mtime_ns) for p in folder.iterdir()) if folder.exists() else []


# The only folder another test creates in the repository build/ folder while tests run in parallel:
# tests/test_mcp_server.py makes one with a unique name (this prefix) because the MCP server refuses
# a Java path outside the repository, and removes it at the end. Nothing else may appear there.
OTHER_TESTS_BUILD_PREFIX = "mcp-test-variant-"


def _build_listing():
    build = REPO_ROOT / "build"
    if not build.exists():
        return []
    return sorted(p.name for p in build.iterdir() if not p.name.startswith(OTHER_TESTS_BUILD_PREFIX))


@pytest.mark.slow
def test_story_and_fool_requests_leave_the_repository_root_and_runs_untouched(
    story_runs, story_client, fool_runs, tmp_path, monkeypatch
):
    """Pages, fragments, a real gate check and a real Tamper: no new file at the root, runs/ unchanged."""
    root_before = sorted(p.name for p in REPO_ROOT.iterdir())
    runs_before = _listing(REPO_ROOT / "runs")
    build_before = _build_listing()

    exchange = tmp_path / "exchange"
    exchange.mkdir()
    monkeypatch.setenv("CORONER_EXCHANGE_DIR", str(exchange))

    for step in range(1, 9):
        for view in ("business", "engineer"):
            assert story_client.get(f"/story/step/{step}?view={view}").status_code == 200
            assert story_client.get(f"/story/step/{step}?view={view}", headers={"HX-Request": "true"}).status_code == 200

    from coroner.ui.app import reset_rate_limiter

    entry = _entry(story_runs.catalog, "T1")
    reset_rate_limiter()
    gate = story_client.post("/story/gate-check", data={"run_id": entry["faulty_run_id"]})
    assert "This ZOMBIE migration cannot be committed" in gate.text
    reset_rate_limiter()
    certificate = _read(story_runs.base / "runs" / entry["faulty_run_id"], "certificate.json")
    tamper = story_client.post("/story/tamper", data={
        "run_id": entry["faulty_run_id"], "status": "ALIVE", "cases_total": str(certificate["cases_total"]),
        "cases_divergent": "0", "random_seed": str(certificate["random_seed"]),
    })
    assert "Certificate: INVALID" in tamper.text

    from fastapi.testclient import TestClient

    from coroner.ui.app import app

    monkeypatch.setenv("CORONER_BASE_DIR", str(fool_runs.base))
    fool = TestClient(app)
    for query in ("", "?case1=on", "?case1=on&case2=on&case4=on&view=engineer"):
        assert fool.get(f"/fool{query}").status_code == 200

    assert sorted(p.name for p in REPO_ROOT.iterdir()) == root_before, "a file was added to or removed from the root"
    assert _listing(REPO_ROOT / "runs") == runs_before, "the repository runs/ folder changed"
    assert _build_listing() == build_before, "build/ changed"


def test_no_new_root_file_is_missing_from_the_layout_document():
    """Every file at the root is listed in docs/architecture.md, the rule the pre-commit guard enforces."""
    layout = (REPO_ROOT / "docs" / "architecture.md").read_text()
    ignored = {".git", ".venv", "build", "runs", "prompts", ".pytest_cache", ".hypothesis", "__pycache__", ".DS_Store"}
    for path in sorted(REPO_ROOT.iterdir()):
        if path.is_file() and path.name not in ignored and not path.name.startswith(".env"):
            assert path.name in layout, f"{path.name} is at the root and not in docs/architecture.md"
