"""The card in the trap catalog is the card the engine wrote for the same run (real runs, no mocks)."""
import json
from pathlib import Path

import pytest

from coroner.parse.schema import load_schema

pytestmark = pytest.mark.slow

TRAPS_DIR = Path(__file__).resolve().parent.parent / "samples" / "traps"


def given_lines(card_text):
    """The lines of a card from its first "Given" line up to, not including, the "When" line."""
    lines = card_text.splitlines()
    start = next(i for i, line in enumerate(lines) if line.startswith("Given"))
    end = next(i for i, line in enumerate(lines) if line.startswith("When"))
    assert start < end
    return lines[start:end]


def trap_by_id(story_runs, trap_id):
    return next(t for t in story_runs.catalog["traps"] if t["id"] == trap_id)


def run_files(story_runs, trap):
    run_dir = story_runs.base / "runs" / trap["faulty_run_id"]
    report = json.loads((run_dir / "failure_report.json").read_text())
    card = (run_dir / "card.txt").read_text()
    return report, card


def schema_of(trap_id):
    folder = next(p for p in TRAPS_DIR.iterdir() if p.name.startswith(trap_id + "-"))
    return load_schema(str(folder / "schema.json"))


def test_t1_catalog_given_equals_run_card_given(story_runs):
    trap = trap_by_id(story_runs, "T1")
    _, run_card = run_files(story_runs, trap)
    text_file = (story_runs.base / "runs" / "trap_catalog.txt").read_text()

    expected = given_lines(run_card)
    assert given_lines(trap["card"]) == expected
    assert given_lines(text_file[text_file.index("== Case 1 "):]) == expected


def test_t1_catalog_given_lists_minimal_rows_not_input_row(story_runs):
    trap = trap_by_id(story_runs, "T1")
    report, _ = run_files(story_runs, trap)
    schema = schema_of("T1")

    assert report.get("minimal_case_rows"), "failure_report.json has no minimal_case_rows"
    assert report.get("original_case_rows"), "failure_report.json has no original_case_rows"

    given = given_lines(trap["card"])
    assert given[0] == "Given the following input rows:"
    expected_rows = [
        "  " + ", ".join(f"{col.name}={row.get(col.name, '')}" for col in schema.input_columns)
        for row in report["minimal_case_rows"]
    ]
    assert given[1:] == expected_rows

    # In this seeded run the first original row is not part of the minimal case, so the
    # input_row fallback and the minimal rows give different Given blocks.
    assert report["input_row"] not in report["minimal_case_rows"]
    input_row_line = "  " + ", ".join(
        f"{col.name}={report['input_row'].get(col.name, '')}" for col in schema.input_columns
    )
    assert input_row_line not in given
    assert not any(line.startswith("Given CASE-ID=") for line in given)

    assert trap["minimal_case"] == report


def test_single_row_traps_keep_the_single_row_card(story_runs):
    checked = []
    for trap in story_runs.catalog["traps"]:
        if trap["id"] == "T1" or trap["status"] != "measured" or not trap.get("card"):
            continue
        report, run_card = run_files(story_runs, trap)
        assert not report.get("minimal_case_rows"), f"{trap['id']} unexpectedly has minimal_case_rows"
        schema = schema_of(trap["id"])

        expected_given = "Given " + ", ".join(
            f"{col.name}={report['input_row'].get(col.name, '')}" for col in schema.input_columns
        )
        assert given_lines(trap["card"]) == [expected_given]
        assert given_lines(trap["card"]) == given_lines(run_card)
        checked.append(trap["id"])

    assert {"T2", "T4"} <= set(checked)
