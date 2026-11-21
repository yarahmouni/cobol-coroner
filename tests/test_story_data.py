"""Tests for the story data layer (coroner/ui/story.py).

Fast tests need no run. Slow tests read the real runs of the session fixture `story_runs`
(tests/conftest.py) and compute every expected value independently from the same files.
"""
import csv
import html
import json
import os
import shutil
from collections import Counter
from pathlib import Path

import pytest

from coroner.ui.pages import parse_card
from coroner.ui.story import (
    EXHIBIT_FILES,
    MISSING_RUNS_MESSAGE,
    StoryDataError,
    exhibits,
    first_divergent_case,
    load_catalog,
    load_cases_registry,
    load_run,
    normalize_view,
    t2_column_counts,
    transaction_count,
)


# ---------------------------------------------------------------- fast tests


@pytest.mark.parametrize("value, expected", [
    ("business", "business"),
    ("engineer", "engineer"),
    (None, "business"),
    ("", "business"),
    ("Engineer", "business"),
    ("ENGINEER", "business"),
    ("admin", "business"),
    ("engineer ", "business"),
    (7, "business"),
])
def test_normalize_view_table(value, expected):
    assert normalize_view(value) == expected


def test_missing_catalog_gives_the_typed_error(tmp_path):
    with pytest.raises(StoryDataError) as error:
        load_catalog(tmp_path)
    assert str(error.value) == "Bundled demo runs missing. Run docker compose up to generate them."
    assert str(error.value) == MISSING_RUNS_MESSAGE
    (tmp_path / "runs").mkdir()
    with pytest.raises(StoryDataError):
        load_catalog(tmp_path)


def test_unreadable_catalog_gives_the_typed_error(tmp_path):
    (tmp_path / "runs").mkdir()
    (tmp_path / "runs" / "trap_catalog.json").write_text("{not json")
    with pytest.raises(StoryDataError):
        load_catalog(tmp_path)
    (tmp_path / "runs" / "trap_catalog.json").write_text('{"traps": "none"}')
    with pytest.raises(StoryDataError):
        load_catalog(tmp_path)


def test_missing_run_gives_the_typed_error(tmp_path):
    (tmp_path / "runs").mkdir()
    with pytest.raises(StoryDataError) as error:
        load_run(tmp_path, "0123456789ab")
    assert str(error.value) == MISSING_RUNS_MESSAGE


@pytest.mark.parametrize("run_id", ["", "../etc", "0123456789AB", "0123456789a", "0123456789abc", None])
def test_invalid_run_id_is_refused(tmp_path, run_id):
    with pytest.raises(StoryDataError):
        load_run(tmp_path, run_id)


def test_absent_files_give_none_not_defaults(tmp_path):
    run_dir = tmp_path / "runs" / "0123456789ab"
    run_dir.mkdir(parents=True)
    run = load_run(tmp_path, "0123456789ab")
    assert run.verdict is None
    assert run.inputs is None
    assert run.certificate is None
    assert run.timing is None
    assert run.reconciliation is None
    assert run.failure_report is None
    assert run.card_text is None
    assert first_divergent_case(run) is None
    assert transaction_count(run) is None
    assert t2_column_counts(run) is None
    assert exhibits(run) == []


def test_unreadable_run_file_gives_the_typed_error(tmp_path):
    run_dir = tmp_path / "runs" / "0123456789ab"
    run_dir.mkdir(parents=True)
    (run_dir / "verdict.json").write_text("{broken")
    with pytest.raises(StoryDataError):
        load_run(tmp_path, "0123456789ab")


def test_parse_card_splits_the_sections_and_keeps_file_names():
    """parse_card was moved out of the run page; its output is what the run page template shows."""
    text = (
        "Given the following input rows:\n"
        "  CASE-ID=GEN-000001, BRANCH=001, AMOUNT=10.00\n"
        "  CASE-ID=GEN-000001, BRANCH=9ZZ, AMOUNT=5.00\n"
        "When the COBOL reference and the Java port process this case\n"
        "Then COBOL writes row A, Java does not\n"
        "Then Java writes row B, COBOL does not\n"
        "COBOL lines involved: dir/sub/PROG.cob:201 PARA.; dir/sub/PROG.cob:204 IF X < Y\n"
    )
    assert parse_card(text) == {
        "given": (
            "Given the following input rows:\n"
            "  CASE-ID=GEN-000001, BRANCH=001, AMOUNT=10.00\n"
            "  CASE-ID=GEN-000001, BRANCH=9ZZ, AMOUNT=5.00"
        ),
        "when": "When the COBOL reference and the Java port process this case",
        "then": "Then COBOL writes row A, Java does not\nThen Java writes row B, COBOL does not",
        "cobol_lines": ["PROG.cob:201 PARA.", "PROG.cob:204 IF X < Y"],
    }
    assert parse_card("") is None
    assert parse_card("  \n ") is None


def test_registry_function_is_the_story_one():
    assert set(load_cases_registry()) == {"T1", "T2", "T3", "T4", "T5", "T6"}


# ---------------------------------------------------------------- slow tests


def _json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _catalog_entry(story_runs, trap_id):
    traps = _json(story_runs.base / "runs" / "trap_catalog.json")["traps"]
    return next(t for t in traps if t["id"] == trap_id)


@pytest.mark.slow
def test_load_catalog_matches_the_file(story_runs):
    catalog = load_catalog(story_runs.base)
    raw = _json(story_runs.base / "runs" / "trap_catalog.json")["traps"]
    assert list(catalog) == [t["id"] for t in raw]
    for trap in raw:
        entry = catalog[trap["id"]]
        assert entry.faulty_run_id == trap.get("faulty_run_id")
        assert entry.correct_run_id == trap.get("correct_run_id")
        assert entry.entry == trap
    assert catalog["T6"].faulty_run_id is None
    assert catalog["T6"].correct_run_id is None
    assert catalog["T1"].faulty_run_id != catalog["T1"].correct_run_id


@pytest.mark.slow
def test_load_run_reads_every_file(story_runs):
    catalog = load_catalog(story_runs.base)
    run_id = catalog["T1"].faulty_run_id
    run_dir = story_runs.base / "runs" / run_id
    run = load_run(story_runs.base, run_id)
    assert run.run_id == run_id
    assert run.run_dir == run_dir
    assert run.verdict == _json(run_dir / "verdict.json")
    assert run.inputs == _json(run_dir / "inputs.json")
    assert run.certificate == _json(run_dir / "certificate.json")
    assert run.timing == (_json(run_dir / "timing.json") if (run_dir / "timing.json").exists() else None)
    assert run.reconciliation == _json(run_dir / "branch_reconciliation.json")
    assert run.failure_report == _json(run_dir / "failure_report.json")
    assert run.card_text == (run_dir / "card.txt").read_text(encoding="utf-8")
    assert run.verdict["status"] == "ZOMBIE"
    assert run.verdict["cases_total"] == story_runs.cases
    # a T2 run has no branch reconciliation and no timing file: None, not a default
    t2 = load_run(story_runs.base, catalog["T2"].faulty_run_id)
    assert t2.reconciliation is None
    assert t2.timing is None


@pytest.mark.slow
def test_first_divergent_case_equals_an_independent_scan(story_runs):
    catalog = load_catalog(story_runs.base)
    run_id = catalog["T1"].faulty_run_id
    run_dir = story_runs.base / "runs" / run_id
    cases = _json(run_dir / "comparison_results.json")["cases"]
    expected_index = next(i for i, c in enumerate(cases) if c["divergent"])
    run = load_run(story_runs.base, run_id)
    found = first_divergent_case(run)
    assert found.case_id == cases[expected_index]["case_id"]
    assert found.position == expected_index + 1
    assert found.cases_total == _json(run_dir / "verdict.json")["cases_total"] == len(cases)
    # cases before it are all clean, so it really is the first
    assert not any(c["divergent"] for c in cases[:expected_index])


@pytest.mark.slow
def test_first_divergent_case_is_none_for_an_alive_run(story_runs):
    catalog = load_catalog(story_runs.base)
    run = load_run(story_runs.base, catalog["T1"].correct_run_id)
    assert run.verdict["status"] == "ALIVE"
    assert first_divergent_case(run) is None


@pytest.mark.slow
def test_exhibits_equal_the_files_in_the_run_folder(story_runs):
    catalog = load_catalog(story_runs.base)
    for trap_id in ("T1", "T2"):
        for run_id in (catalog[trap_id].faulty_run_id, catalog[trap_id].correct_run_id):
            run_dir = story_runs.base / "runs" / run_id
            on_disk = set(os.listdir(run_dir))
            expected = [name for _, name in EXHIBIT_FILES if name in on_disk]
            assert [e.file_name for e in exhibits(load_run(story_runs.base, run_id))] == expected
    faulty = load_run(story_runs.base, catalog["T1"].faulty_run_id)
    names = [e.file_name for e in exhibits(faulty)]
    assert names == ["certificate.json", "failure_report.json", "minimal_case_input.csv", "ZombieRegressionTest.java"]
    correct = load_run(story_runs.base, catalog["T1"].correct_run_id)
    assert [e.file_name for e in exhibits(correct)] == ["certificate.json"]


@pytest.mark.slow
def test_exhibit_disappears_with_its_file(story_runs, tmp_path):
    catalog = load_catalog(story_runs.base)
    run_id = catalog["T1"].faulty_run_id
    shutil.copytree(story_runs.base / "runs" / run_id, tmp_path / "runs" / run_id)
    (tmp_path / "runs" / run_id / "ZombieRegressionTest.java").unlink()
    names = [e.file_name for e in exhibits(load_run(tmp_path, run_id))]
    assert "ZombieRegressionTest.java" not in names
    assert "certificate.json" in names


@pytest.mark.slow
def test_transaction_count_equals_the_rows_of_the_cases_file(story_runs):
    catalog = load_catalog(story_runs.base)
    run_id = catalog["T1"].faulty_run_id
    cases_file = story_runs.base / "runs" / run_id / "generated_cases.csv"
    lines = cases_file.read_text(encoding="utf-8").splitlines()
    run = load_run(story_runs.base, run_id)
    assert transaction_count(run) == len(lines) - 1
    # a case is a batch: there are more transactions than cases
    with cases_file.open(newline="", encoding="utf-8") as f:
        case_ids = {row["CASE-ID"] for row in csv.DictReader(f)}
    assert len(case_ids) == run.verdict["cases_total"]
    assert transaction_count(run) > run.verdict["cases_total"]


@pytest.mark.slow
def test_t2_column_counts_equal_an_independent_scan(story_runs):
    catalog = load_catalog(story_runs.base)
    run_id = catalog["T2"].faulty_run_id
    raw = _json(story_runs.base / "runs" / run_id / "comparison_results.json")
    expected = Counter(
        field["field_name"]
        for case in raw["cases"]
        for field in case["divergent_fields"]
    )
    counts = t2_column_counts(load_run(story_runs.base, run_id))
    assert counts == dict(expected)
    assert set(counts) <= {"FEE1", "FEE2"}
    assert sum(counts.values()) >= 1
    assert t2_column_counts(load_run(story_runs.base, catalog["T2"].correct_run_id)) == {}


@pytest.mark.slow
def test_missing_optional_file_in_a_copy_gives_none(story_runs, tmp_path):
    catalog = load_catalog(story_runs.base)
    run_id = catalog["T1"].faulty_run_id
    shutil.copytree(story_runs.base / "runs" / run_id, tmp_path / "runs" / run_id)
    (tmp_path / "runs" / run_id / "failure_report.json").unlink()
    (tmp_path / "runs" / run_id / "comparison_results.json").unlink()
    run = load_run(tmp_path, run_id)
    assert run.failure_report is None
    assert run.verdict is not None
    assert first_divergent_case(run) is None
    assert t2_column_counts(run) is None


@pytest.mark.slow
def test_a_catalog_run_missing_on_disk_is_the_typed_error(story_runs, tmp_path):
    shutil.copytree(story_runs.base / "runs", tmp_path / "runs")
    catalog = load_catalog(tmp_path)
    shutil.rmtree(tmp_path / "runs" / catalog["T4"].faulty_run_id)
    with pytest.raises(StoryDataError) as error:
        load_run(tmp_path, catalog["T4"].faulty_run_id)
    assert str(error.value) == MISSING_RUNS_MESSAGE
    # the other runs still load
    assert load_run(tmp_path, catalog["T1"].faulty_run_id).verdict is not None


@pytest.mark.slow
def test_run_page_still_shows_the_card_it_parses(story_runs, monkeypatch):
    """The run page parses card.txt with the shared parse_card: its text is on the page."""
    from fastapi.testclient import TestClient

    from coroner.ui.app import app

    monkeypatch.setenv("CORONER_BASE_DIR", str(story_runs.base))
    catalog = load_catalog(story_runs.base)
    run = load_run(story_runs.base, catalog["T1"].faulty_run_id)
    card = parse_card(run.card_text)
    page = html.unescape(TestClient(app).get(f"/run/{run.run_id}").text)
    assert card["given"] in page
    assert card["when"] in page
    assert card["then"] in page
    assert card["cobol_lines"], "the T1 faulty card lists COBOL lines"
    for line in card["cobol_lines"]:
        assert line in page


@pytest.mark.slow
def test_fixture_catalog_has_the_three_zombie_ports(story_runs):
    catalog = load_catalog(story_runs.base)
    for trap_id in ("T1", "T2", "T4"):
        assert load_run(story_runs.base, catalog[trap_id].faulty_run_id).verdict["status"] == "ZOMBIE"
        assert load_run(story_runs.base, catalog[trap_id].correct_run_id).verdict["status"] == "ALIVE"
    assert _catalog_entry(story_runs, "T4")["cases_detected"] >= 1
