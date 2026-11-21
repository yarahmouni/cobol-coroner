"""Tests for steps 1 to 3 of the guided story.

Step 1 needs no run (fast). Steps 2 and 3 read the real catalog of the session fixture
`story_runs` (slow): every expected value is read from the run files by the test itself.
"""
import csv
import json
import shutil
from decimal import Decimal
from pathlib import Path

import pytest

from coroner.ui.story import same_amount

from story_html import anchors, listing_lines, table_rows, tags, visible_text

REPO_ROOT = Path(__file__).resolve().parent.parent
T1_DIR = REPO_ROOT / "samples" / "traps" / "T1-ebcdic-match-merge"
COBOL_FILE = T1_DIR / "MATCH-MERGE.cob"

ENGINEER_LABELS = ("Technical details", "Schema file", "Input columns", "COBOL file", "Run id", "Seed", "Java file")


def _t1_faulty_run_dir(base: Path) -> Path:
    catalog = json.loads((base / "runs" / "trap_catalog.json").read_text())
    entry = next(trap for trap in catalog["traps"] if trap["id"] == "T1")
    return base / "runs" / entry["faulty_run_id"]


def _read(run_dir: Path, name: str):
    return json.loads((run_dir / name).read_text())


@pytest.fixture
def empty_client(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    from coroner.ui.app import app

    monkeypatch.setenv("CORONER_BASE_DIR", str(tmp_path))
    return TestClient(app)


@pytest.fixture
def edited_copy(story_runs, tmp_path, monkeypatch):
    """A copy of the story base directory that a test may edit; the session runs stay untouched."""
    from fastapi.testclient import TestClient

    from coroner.ui.app import app

    copy = tmp_path / "base_copy"
    shutil.copytree(story_runs.base, copy)
    monkeypatch.setenv("CORONER_BASE_DIR", str(copy))
    return copy, TestClient(app)


# ------------------------------------------------------------------ step 1 (fast)


def test_step1_text_and_listing_lines_equal_the_file(empty_client):
    page = empty_client.get("/story/step/1").text
    assert "Every night, the bank reconciles branch subtotals to catch posting errors before opening." in visible_text(page)
    source = COBOL_FILE.read_text().split("\n")
    rendered = listing_lines(page)
    assert len(rendered) >= 2
    for number, text in rendered:
        assert text == source[number - 1].rstrip("\r")
    numbers = [n for n, _ in rendered]
    assert numbers == list(range(numbers[0], numbers[-1] + 1))
    assert "TABLE-CODE(1)" in rendered[0][1]
    assert "TABLE-CODE(9)" in rendered[-1][1]


def test_step1_listing_is_closed_in_business_and_open_in_engineer(empty_client):
    business = [a for t, a in tags(empty_client.get("/story/step/1?view=business").text, "details")]
    engineer = [a for t, a in tags(empty_client.get("/story/step/1?view=engineer").text, "details")]
    assert len(business) == 1 and "open" not in business[0]
    assert len(engineer) == 1 and "open" in engineer[0]


def test_step1_engineer_details_come_from_the_schema_and_the_file(empty_client):
    schema = json.loads((T1_DIR / "schema.json").read_text())
    columns = [c["name"] for c in schema["input"]["columns"]]
    page = empty_client.get("/story/step/1?view=engineer").text
    text = visible_text(page)
    assert "Technical details" in text
    assert "schema.json" in text
    assert ", ".join(columns) in text
    assert "MATCH-MERGE.cob" in text
    numbers = [n for n, _ in listing_lines(page)]
    assert f"lines {numbers[0]} to {numbers[-1]}" in text


def test_step1_business_view_has_no_engineer_label(empty_client):
    text = visible_text(empty_client.get("/story/step/1?view=business").text)
    for label in ENGINEER_LABELS:
        assert label not in text


def test_step1_listing_moves_with_the_file(empty_client, monkeypatch, tmp_path):
    """The numbers are found in the file at request time: a copy with lines inserted shifts them."""
    from coroner.ui import story

    original = [n for n, _ in listing_lines(empty_client.get("/story/step/1").text)]
    folder = tmp_path / "traps"
    copy = folder / T1_DIR.name
    shutil.copytree(T1_DIR, copy, ignore=shutil.ignore_patterns("java", "fixtures"))
    cobol = copy / "MATCH-MERGE.cob"
    cobol.write_text("      * inserted 1\n      * inserted 2\n" + cobol.read_text())
    monkeypatch.setattr(story, "TRAPS_ROOT", folder)
    shifted = [n for n, _ in listing_lines(empty_client.get("/story/step/1").text)]
    assert shifted == [n + 2 for n in original]


@pytest.mark.parametrize("first, second, expected", [
    ("12.50", "12.5", True),
    ("0.00", "0", True),
    ("12.50", "12.51", False),
    ("1", "-1", False),
    ("abc", "abc", True),
    ("abc", "abd", False),
])
def test_step3_same_amount_compares_values_not_text(first, second, expected):
    assert same_amount(first, second) is expected


# ------------------------------------------------------------------ step 2 (slow)


@pytest.mark.slow
def test_step2_every_number_equals_the_run_files(story_runs, story_client):
    run_dir = _t1_faulty_run_dir(story_runs.base)
    reconciliation = _read(run_dir, "branch_reconciliation.json")
    verdict = _read(run_dir, "verdict.json")
    with (run_dir / "generated_cases.csv").open(newline="") as f:
        transactions = sum(1 for _ in csv.reader(f)) - 1

    page = story_client.get("/story/step/2").text
    text = visible_text(page)
    assert f"The COBOL program posted {transactions} transactions in {verdict['cases_total']} test batches." in text

    rows = table_rows(page)
    body = {row[0]: row[1] for row in rows if len(row) == 2}
    for branch in reconciliation["branches"]:
        assert body[branch["branch"]] == branch["cobol_subtotal"]
    suspense_rows = [row for row in rows if row[0].startswith("Suspense")]
    assert suspense_rows == [[suspense_rows[0][0], reconciliation["suspense"]["cobol"]]]
    assert "(SUSP)" in suspense_rows[0][0]
    assert body["Grand total"] == reconciliation["grand_total"]["cobol"]
    assert len(rows) == 1 + len(reconciliation["branches"]) + 1 + 1

    # No verdict on the COBOL result, no Java figure, no "mainframe".
    for forbidden in ("ZOMBIE", "ALIVE", 'class="verdict-badge', "mainframe"):
        assert forbidden not in page
    assert [n for n, _ in listing_lines(page)]


@pytest.mark.slow
def test_step2_listing_shows_the_collation_and_sort_blocks(story_client):
    page = story_client.get("/story/step/2").text
    text = visible_text(page)
    assert "Collating sequence" in text and "Sort of the transactions" in text
    source = COBOL_FILE.read_text().split("\n")
    rendered = listing_lines(page)
    assert any("ALPHABET" in text for _, text in rendered)
    assert any("SORT" in text for _, text in rendered)
    for number, text in rendered:
        assert text == source[number - 1].rstrip("\r")


@pytest.mark.slow
def test_step2_engineer_view_has_run_id_and_seed_business_view_has_neither(story_runs, story_client):
    run_dir = _t1_faulty_run_dir(story_runs.base)
    inputs = _read(run_dir, "inputs.json")
    engineer = visible_text(story_client.get("/story/step/2?view=engineer").text)
    assert run_dir.name in engineer
    assert f"Seed {inputs['random_seed']}" in engineer
    business = visible_text(story_client.get("/story/step/2?view=business").text)
    assert run_dir.name not in business
    for label in ENGINEER_LABELS:
        assert label not in business


@pytest.mark.slow
def test_step2_displayed_subtotal_is_read_from_the_file_not_typed(edited_copy):
    base, client = edited_copy
    run_dir = _t1_faulty_run_dir(base)
    path = run_dir / "branch_reconciliation.json"
    reconciliation = json.loads(path.read_text())
    original = reconciliation["branches"][0]["cobol_subtotal"]
    reconciliation["branches"][0]["cobol_subtotal"] = "123456.78"
    reconciliation["suspense"]["cobol"] = "7.77"
    reconciliation["grand_total"]["cobol"] = "888.88"
    path.write_text(json.dumps(reconciliation))

    page = client.get("/story/step/2").text
    cells = [cell for row in table_rows(page) for cell in row]
    assert "123456.78" in cells and "7.77" in cells and "888.88" in cells
    assert original not in cells


@pytest.mark.slow
def test_step2_without_the_reconciliation_file_shows_the_alert_not_a_number(edited_copy):
    base, client = edited_copy
    (_t1_faulty_run_dir(base) / "branch_reconciliation.json").unlink()
    page = client.get("/story/step/2").text
    assert "Bundled demo runs missing. Run docker compose up to generate them." in visible_text(page)
    assert "<table" not in page


# ------------------------------------------------------------------ step 3 (slow)


@pytest.mark.slow
def test_step3_shows_both_grand_totals_and_matches_from_the_values(story_runs, story_client):
    run_dir = _t1_faulty_run_dir(story_runs.base)
    totals = _read(run_dir, "branch_reconciliation.json")["grand_total"]
    page = story_client.get("/story/step/3").text
    text = visible_text(page)
    assert f"COBOL grand total: {totals['cobol']}" in text
    assert f"Java grand total: {totals['java']}" in text
    assert "A Java version was written to replace it." in text
    if Decimal(totals["cobol"]) == Decimal(totals["java"]):
        assert "They match." in text and "They differ." not in text
    else:
        assert "They differ." in text and "They match." not in text
    # No verdict and no branch table yet: step 4 shows the finding.
    for forbidden in ("ZOMBIE", "ALIVE", 'class="verdict-badge', "<table", "mainframe"):
        assert forbidden not in page


@pytest.mark.slow
def test_step3_they_match_is_decided_by_comparing_the_values(edited_copy):
    base, client = edited_copy
    path = _t1_faulty_run_dir(base) / "branch_reconciliation.json"
    reconciliation = json.loads(path.read_text())

    reconciliation["grand_total"] = {"cobol": "100.50", "java": "100.5"}
    path.write_text(json.dumps(reconciliation))
    text = visible_text(client.get("/story/step/3").text)
    assert "Java grand total: 100.5" in text
    assert "They match." in text and "They differ." not in text

    reconciliation["grand_total"] = {"cobol": "100.50", "java": "100.51"}
    path.write_text(json.dumps(reconciliation))
    text = visible_text(client.get("/story/step/3").text)
    assert "Java grand total: 100.51" in text
    assert "They differ." in text and "They match." not in text


@pytest.mark.slow
def test_step3_engineer_view_shows_the_java_file_of_the_certificate(story_runs, story_client):
    run_dir = _t1_faulty_run_dir(story_runs.base)
    certificate = _read(run_dir, "certificate.json")
    java_name = Path(certificate["java_file"]).name
    engineer = visible_text(story_client.get("/story/step/3?view=engineer").text)
    assert f"Java file {java_name}" in engineer
    assert f"Run id {run_dir.name}" in engineer
    business = visible_text(story_client.get("/story/step/3?view=business").text)
    assert java_name not in business
    for label in ENGINEER_LABELS:
        assert label not in business


@pytest.mark.slow
@pytest.mark.parametrize("step", [1, 2, 3])
@pytest.mark.parametrize("view", ["business", "engineer"])
def test_step1_step2_step3_never_say_mainframe(story_client, step, view):
    page = story_client.get(f"/story/step/{step}?view={view}").text
    assert "mainframe" not in page.lower()
