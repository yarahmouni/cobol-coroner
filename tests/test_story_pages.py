"""Tests for the steps of the guided story.

Steps 1 and 6 need no run (fast). The others read the real catalog of the session fixture
`story_runs` (slow): every expected value is read from the run files by the test itself.
"""
import csv
import hashlib
import json
import re
import shutil
from decimal import Decimal
from pathlib import Path

import pytest

from coroner.ui.story import same_amount

from story_html import (
    anchors,
    example_block,
    executed_listing_numbers,
    form_fields,
    has_live_region_root,
    headings,
    listing_lines,
    table_rows,
    tags,
    visible_text,
)

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


# ================================================================== steps 4 to 8
#
# Expected values are read from the run files (or computed from the COBOL file) by the tests
# themselves. Tests that need runs use the session fixture `story_runs` and carry the slow marker.

STEP_LABELS_FOR_ENGINEER = ENGINEER_LABELS + (
    "Duration", "Exposure maximum", "Suspense difference", "Return codes",
    "Divergent output", "Technical cause", "COBOL rule", "Certificate hash",
)
MISSING_RUNS = "Bundled demo runs missing. Run docker compose up to generate them."
AUTOPSY_HEADINGS = ("Cause of death", "Time of death")
EXHIBIT_NAMES = ("certificate.json", "failure_report.json", "minimal_case_input.csv", "ZombieRegressionTest.java")


def _t1_entry(base: Path) -> dict:
    catalog = json.loads((base / "runs" / "trap_catalog.json").read_text())
    return next(trap for trap in catalog["traps"] if trap["id"] == "T1")


def _t1_correct_run_dir(base: Path) -> Path:
    return base / "runs" / _t1_entry(base)["correct_run_id"]


def _money(value) -> str:
    return f"{Decimal(str(value)):.2f}"


def _line_range(lines, start_prefix: str, until_prefix: str):
    """First and last line number (1-based) from the line starting with start_prefix to the line before until_prefix."""
    start = next(i for i, line in enumerate(lines) if line.strip().startswith(start_prefix))
    until = next(i for i in range(start + 1, len(lines)) if lines[i].strip().startswith(until_prefix))
    last = until
    while not lines[last - 1].strip():
        last -= 1
    return start + 1, last


def _card_example_lines(run_dir: Path):
    """The Given and Then lines of card.txt, read by the test with its own small loop."""
    kept, section = [], None
    for line in (run_dir / "card.txt").read_text().split("\n"):
        if line.startswith("Given"):
            section = "given"
            kept.append(line)
        elif line.startswith("Then"):
            section = "then"
            kept.append(line)
        elif line.startswith("When") or line.startswith("COBOL lines involved:"):
            section = None
        elif section and line.strip():
            kept.append(line)
    return kept


def _t1_sentence(verdict: dict) -> str:
    sentence = (
        f"This Java migration is not safe to promote: {verdict['affected_branches']} "
        "branch subtotals do not reconcile with COBOL."
    )
    if verdict["grand_total_matches"]:
        sentence += " The grand total still balances, so the error is hidden in branch-level reporting."
    return sentence


def _download_links(page: str):
    return [a["href"] for a in anchors(page) if "/download/" in a["href"]]


# ------------------------------------------------------------------ fast: no run needed


def test_t1_trap_json_never_says_mainframe():
    """The story never says mainframe for a GnuCOBOL run (Req 3): the T1 fix sentences name the COBOL program."""
    trap = json.loads((T1_DIR / "trap.json").read_text())
    for key, value in trap.items():
        assert "mainframe" not in json.dumps(value).lower(), key
    assert "COBOL program" in trap["business_fix"]


@pytest.mark.parametrize("step", [4, 5, 7, 8])
def test_steps_4_5_7_8_without_runs_show_the_alert_and_no_number_or_action(empty_client, step):
    page = empty_client.get(f"/story/step/{step}").text
    text = visible_text(page)
    assert MISSING_RUNS in text
    assert [a for t, a in tags(page) if a.get("role") == "alert"]
    for form in ("/story/gate-check", "/story/run", "/story/tamper"):
        assert form_fields(page, form) == {}
    assert "<table" not in page and "<dl" not in page
    assert not any(h in headings(page) for h in AUTOPSY_HEADINGS)


def test_step6_text_and_listing_are_read_from_trap_json_and_the_file_without_a_run(empty_client):
    trap = json.loads((T1_DIR / "trap.json").read_text())
    business = empty_client.get("/story/step/6?view=business").text
    engineer = empty_client.get("/story/step/6?view=engineer").text
    business_text, engineer_text = visible_text(business), visible_text(engineer)

    assert "The corrected Java version orders branch codes the way the COBOL program does." in business_text
    assert trap["business_fix"] in business_text and trap["fix_sentence"] not in business_text
    assert trap["fix_sentence"] in engineer_text and trap["business_fix"] not in engineer_text

    source = COBOL_FILE.read_text().split("\n")
    first, last = _line_range(source, "BALANCE-LINE.", "WRITE-CASE-RESULTS.")
    for page in (business, engineer):
        rendered = listing_lines(page)
        assert [n for n, _ in rendered] == list(range(first, last + 1))
        for number, text in rendered:
            assert text == source[number - 1].rstrip("\r")
        assert executed_listing_numbers(page) == []
    details_business = [a for t, a in tags(business, "details")]
    details_engineer = [a for t, a in tags(engineer, "details")]
    assert len(details_business) == 1 and "open" not in details_business[0]
    assert len(details_engineer) == 1 and "open" in details_engineer[0]
    for page in (business_text, engineer_text):
        assert "mainframe" not in page.lower()
        assert not any(h in page for h in AUTOPSY_HEADINGS)


# ------------------------------------------------------------------ step 4 (slow)


@pytest.mark.slow
def test_step4_every_figure_equals_the_run_files(story_runs, story_client):
    run_dir = _t1_faulty_run_dir(story_runs.base)
    verdict = _read(run_dir, "verdict.json")
    page = story_client.get("/story/step/4").text
    text = visible_text(page)

    assert f"Coroner ran both programs on the same {verdict['cases_total']} test batches." in text
    assert f"{verdict['cases_divergent']} of {verdict['cases_total']} batches diverge" in text
    balances = "yes" if verdict["grand_total_matches"] else "no"
    assert (
        f"Exposure {_money(verdict['exposure_sum'])} Branches affected {verdict['affected_branches']} "
        f"Grand total balances {balances}"
    ) in text
    assert verdict["status"] == "ZOMBIE" and "ZOMBIE MIGRATION REJECTED" in text
    assert any("zombie" in a.get("class", "").split() for t, a in tags(page, "div"))
    assert "<rect" in page


@pytest.mark.slow
def test_step4_zombie_sentence_equals_the_one_on_the_run_page(story_runs, story_client):
    run_dir = _t1_faulty_run_dir(story_runs.base)
    sentence = _t1_sentence(_read(run_dir, "verdict.json"))
    assert sentence in visible_text(story_client.get("/story/step/4").text)
    assert sentence in visible_text(story_client.get(f"/run/{run_dir.name}").text)


@pytest.mark.slow
def test_step4_forms_target_the_real_routes_with_the_faulty_run(story_runs, story_client):
    from coroner.ui.app import RunAuditRequest

    run_dir = _t1_faulty_run_dir(story_runs.base)
    inputs = _read(run_dir, "inputs.json")
    page = story_client.get("/story/step/4?view=engineer").text

    gate = form_fields(page, "/story/gate-check")
    assert gate == {"run_id": _t1_entry(story_runs.base)["faulty_run_id"], "view": "engineer"}
    assert "Check the gate" in visible_text(page)

    run = form_fields(page, "/story/run")
    assert run["port"] == "faulty" and run["view"] == "engineer"
    assert run["seed"] == str(inputs["random_seed"])
    # The defaults are accepted by the model of POST /api/run (bounds and port).
    request = RunAuditRequest(sample="T1", port=run["port"], seed=run["seed"], cases=run["cases"])
    inputs_by_id = {a["id"]: a for t, a in tags(page, "input") if "id" in a}
    for field, name in (("seed", "run-seed"), ("cases", "run-cases")):
        metadata = RunAuditRequest.model_fields[field].metadata
        assert inputs_by_id[name]["min"] == str(next(m.ge for m in metadata if hasattr(m, "ge")))
        assert inputs_by_id[name]["max"] == str(next(m.le for m in metadata if hasattr(m, "le")))
    assert request.cases == int(run["cases"])
    labelled = {a.get("for") for t, a in tags(page, "label")}
    assert {"run-seed", "run-cases"} <= labelled

    regions = {a["id"]: a for t, a in tags(page, "div") if a.get("id") in ("gate-result", "run-result")}
    assert set(regions) == {"gate-result", "run-result"}
    for region in regions.values():
        assert region["role"] == "status" and region["aria-live"] == "polite"
    notes = visible_text(page)
    assert len(tags(page, "noscript")) == 2
    assert notes.count("python3 -m coroner verify <certificate.json>") == 2


@pytest.mark.slow
def test_step4_the_gate_form_blocks_the_faulty_run_through_the_real_route(story_client):
    fields = form_fields(story_client.get("/story/step/4").text, "/story/gate-check")
    fragment = story_client.post("/story/gate-check", data=fields)
    assert "This ZOMBIE migration cannot be committed" in visible_text(fragment.text)
    assert has_live_region_root(fragment.text)


@pytest.mark.slow
def test_step4_business_view_has_no_run_id_or_engineer_label(story_runs, story_client):
    run_dir = _t1_faulty_run_dir(story_runs.base)
    text = visible_text(story_client.get("/story/step/4?view=business").text)
    assert run_dir.name not in text
    for label in STEP_LABELS_FOR_ENGINEER:
        assert label not in text


@pytest.mark.slow
def test_step4_engineer_details_come_from_the_files(story_runs, story_client):
    run_dir = _t1_faulty_run_dir(story_runs.base)
    verdict = _read(run_dir, "verdict.json")
    inputs = _read(run_dir, "inputs.json")
    timing = run_dir / "timing.json"
    duration = f"{_read(run_dir, 'timing.json')['duration_seconds']} s" if timing.exists() else "not recorded"
    text = visible_text(story_client.get("/story/step/4?view=engineer").text)
    cobol_rc, java_rc = verdict["run_return_codes"]
    assert (
        f"Run id {run_dir.name} Seed {inputs['random_seed']} Duration {duration} "
        f"Exposure maximum {_money(verdict['exposure_max'])} "
        f"Suspense difference {_money(verdict['suspense_difference'])} "
        f"Return codes COBOL {cobol_rc}, Java {java_rc}"
    ) in text


@pytest.mark.slow
def test_step4_values_are_read_from_the_files_not_typed(edited_copy):
    base, client = edited_copy
    run_dir = _t1_faulty_run_dir(base)
    verdict = _read(run_dir, "verdict.json")
    verdict.update(exposure_sum="1234.5", affected_branches=7, grand_total_matches=False,
                   cases_divergent=3, cases_total=11)
    (run_dir / "verdict.json").write_text(json.dumps(verdict))
    (run_dir / "timing.json").write_text(json.dumps({"duration_seconds": "4.2"}))
    text = visible_text(client.get("/story/step/4?view=engineer").text)
    assert "Exposure 1234.50 Branches affected 7 Grand total balances no" in text
    assert "3 of 11 batches diverge" in text
    assert "on the same 11 test batches" in text
    assert "Duration 4.2 s" in text

    del verdict["exposure_sum"]
    (run_dir / "verdict.json").write_text(json.dumps(verdict))
    assert "Exposure not recorded" in visible_text(client.get("/story/step/4").text)


# ------------------------------------------------------------------ step 5 (slow)


@pytest.mark.slow
def test_step5_branch_table_and_suspense_line_equal_the_reconciliation_file(story_runs, story_client):
    run_dir = _t1_faulty_run_dir(story_runs.base)
    reconciliation = _read(run_dir, "branch_reconciliation.json")
    branches = reconciliation["branches"]
    mismatching = [b for b in branches if Decimal(b["cobol_subtotal"]) != Decimal(b["java_subtotal"])]
    assert mismatching, "the T1 faulty run must have branches that do not reconcile"
    mismatching.sort(key=lambda b: abs(Decimal(b["cobol_subtotal"]) - Decimal(b["java_subtotal"])), reverse=True)
    page = story_client.get("/story/step/5").text
    text = visible_text(page)

    rows = table_rows(page)
    assert rows[0] == ["Branch", "COBOL subtotal", "Java subtotal", "Difference"]
    assert rows[1:] == [[b["branch"], b["cobol_subtotal"], b["java_subtotal"], b["difference"]] for b in mismatching]
    others = len(branches) - len(mismatching)
    assert f"{others} other {'branch matches' if others == 1 else 'branches match'}" in text
    suspense = abs(Decimal(reconciliation["suspense"]["difference"]))
    assert f"Posted to suspense instead of a branch: {suspense:.2f}" in text


@pytest.mark.slow
@pytest.mark.parametrize("view", ["business", "engineer"])
def test_step5_has_the_three_autopsy_headings_and_other_steps_do_not(story_client, view):
    page5 = story_client.get(f"/story/step/5?view={view}").text
    assert [h for h in headings(page5) if h in AUTOPSY_HEADINGS + ("Exhibits",)] == [
        "Cause of death", "Time of death", "Exhibits",
    ]
    for step in (1, 2, 3, 4, 6, 7, 8):
        page = story_client.get(f"/story/step/{step}?view={view}").text
        assert not any(h in headings(page) for h in AUTOPSY_HEADINGS), step


@pytest.mark.slow
def test_step5_cause_of_death_business_text_is_trap_json_and_has_no_engineer_label(story_runs, story_client):
    trap = json.loads((T1_DIR / "trap.json").read_text())
    text = visible_text(story_client.get("/story/step/5?view=business").text)
    assert trap["business_cause"] in text
    for label in STEP_LABELS_FOR_ENGINEER:
        assert label not in text
    assert trap["technical_cause"] not in text and trap["cobol_rule"] not in text
    assert _t1_faulty_run_dir(story_runs.base).name not in text


@pytest.mark.slow
def test_step5_engineer_cause_of_death_lists_the_failure_report_the_rule_and_the_anchor_lines(story_runs, story_client):
    run_dir = _t1_faulty_run_dir(story_runs.base)
    failure = _read(run_dir, "failure_report.json")
    trap = json.loads((T1_DIR / "trap.json").read_text())
    text = visible_text(story_client.get("/story/step/5?view=engineer").text)

    assert len(failure["divergent_fields"]) >= 2
    for position, entry in enumerate(failure["divergent_fields"][:2], start=1):
        key = ", ".join(f"{name}={str(value).strip()}" for name, value in entry["output_key"].items())
        fields = ", ".join(dict.fromkeys([*entry["cobol_values"], *entry["java_values"]]))
        assert f"Divergent output {position} {entry['kind']}; key {key}; fields {fields}" in text
    assert f"Technical cause {trap['technical_cause']}" in text
    assert f"COBOL rule {trap['cobol_rule']}" in text
    source = COBOL_FILE.read_text().split("\n")
    collation = _line_range(source, "SPECIAL-NAMES.", "INPUT-OUTPUT SECTION")
    match = _line_range(source, "BALANCE-LINE.", "WRITE-CASE-RESULTS.")
    assert f"MATCH-MERGE.cob lines {collation[0]} to {collation[1]}" in text
    assert f"MATCH-MERGE.cob lines {match[0]} to {match[1]}" in text


@pytest.mark.slow
def test_step5_time_of_death_is_the_first_divergent_case_and_not_the_minimal_case(story_runs, story_client):
    run_dir = _t1_faulty_run_dir(story_runs.base)
    verdict = _read(run_dir, "verdict.json")
    comparison = _read(run_dir, "comparison_results.json")
    first_position, first_id = next(
        (position, case["case_id"])
        for position, case in enumerate(comparison["cases"], start=1) if case["divergent"]
    )
    minimal_id = _read(run_dir, "failure_report.json")["case_id"]
    # The two are computed from two different files and differ in this run: the page must not mix them.
    assert first_id != minimal_id
    text = visible_text(story_client.get("/story/step/5").text)
    assert f"The first divergent case is {first_id} (case {first_position} of {verdict['cases_total']})." in text
    time_of_death = text.split("Time of death")[1].split("Exhibits")[0]
    assert minimal_id not in time_of_death


@pytest.mark.slow
def test_step5_exhibits_are_the_files_of_the_run_folder_and_each_link_downloads_the_file(story_runs, story_client):
    run_dir = _t1_faulty_run_dir(story_runs.base)
    present = [name for name in EXHIBIT_NAMES if (run_dir / name).is_file()]
    assert present == list(EXHIBIT_NAMES), "the faulty run must have all four evidence files"
    page = story_client.get("/story/step/5").text
    assert _download_links(page) == [f"/run/{run_dir.name}/download/{name}" for name in present]
    for name in present:
        response = story_client.get(f"/run/{run_dir.name}/download/{name}")
        assert response.status_code == 200 and response.content == (run_dir / name).read_bytes()


@pytest.mark.slow
def test_step5_deleting_a_file_removes_its_exhibit(edited_copy):
    base, client = edited_copy
    run_dir = _t1_faulty_run_dir(base)
    (run_dir / "ZombieRegressionTest.java").unlink()
    page = client.get("/story/step/5").text
    assert _download_links(page) == [
        f"/run/{run_dir.name}/download/{name}" for name in EXHIBIT_NAMES if name != "ZombieRegressionTest.java"
    ]
    assert "ZombieRegressionTest.java" not in visible_text(page)
    (run_dir / "failure_report.json").unlink()
    (run_dir / "minimal_case_input.csv").unlink()
    assert _download_links(client.get("/story/step/5").text) == [f"/run/{run_dir.name}/download/certificate.json"]


@pytest.mark.slow
def test_step5_example_is_the_card_text_and_not_the_observed_input_row(story_runs, story_client):
    run_dir = _t1_faulty_run_dir(story_runs.base)
    failure = _read(run_dir, "failure_report.json")
    # The failure report's input_row is the first row of the original multi-row case, not the minimal case.
    assert failure["input_row"] != failure["minimal_case_rows"][0]
    page = story_client.get("/story/step/5").text
    example = example_block(page)
    expected = _card_example_lines(run_dir)
    assert len(expected) >= 3
    assert " ".join(example.split()) == " ".join(" ".join(expected).split())
    row = failure["input_row"]
    assert f"CASE-ID={row['CASE-ID']}, BRANCH={row['BRANCH']}, AMOUNT={row['AMOUNT']}" not in example


@pytest.mark.slow
def test_step5_listing_marks_the_lines_of_the_card_as_executed(story_runs, story_client):
    run_dir = _t1_faulty_run_dir(story_runs.base)
    card = (run_dir / "card.txt").read_text()
    card_lines = {int(n) for n in re.findall(r"MATCH-MERGE\.cob:(\d+)", card)}
    source = COBOL_FILE.read_text().split("\n")
    first, last = _line_range(source, "BALANCE-LINE.", "WRITE-CASE-RESULTS.")
    page = story_client.get("/story/step/5").text
    assert [n for n, _ in listing_lines(page)] == list(range(first, last + 1))
    assert set(executed_listing_numbers(page)) == card_lines
    assert "executed" in visible_text(page)


@pytest.mark.slow
@pytest.mark.parametrize("view", ["business", "engineer"])
def test_step5_never_says_mainframe(story_client, view):
    assert "mainframe" not in story_client.get(f"/story/step/5?view={view}").text.lower()


# ------------------------------------------------------------------ steps 6 and 7 (slow)


@pytest.mark.slow
def test_step7_figures_equal_the_correct_run_files(story_runs, story_client):
    run_dir = _t1_correct_run_dir(story_runs.base)
    verdict = _read(run_dir, "verdict.json")
    page = story_client.get("/story/step/7").text
    text = visible_text(page)
    assert verdict["status"] == "ALIVE" and "ALIVE MIGRATION CERTIFIED" in text
    assert f"{verdict['cases_divergent']} of {verdict['cases_total']} batches diverge" in text
    assert f"Exposure {_money(verdict['exposure_sum'])}" in text
    assert any("alive" in a.get("class", "").split() for t, a in tags(page, "div"))
    assert "<circle" in page
    assert "Coroner audited the corrected version on the same test batches." in text
    assert not any(h in text for h in AUTOPSY_HEADINGS)
    assert not any(h in headings(page) for h in AUTOPSY_HEADINGS)


@pytest.mark.slow
def test_step7_certificate_is_described_as_valid_only_through_the_gate(story_runs, story_client):
    for view in ("business", "engineer"):
        text = visible_text(story_client.get(f"/story/step/7?view={view}").text)
        assert "valid" not in text.lower()
        assert "Certificate: VALID" not in text


@pytest.mark.slow
def test_step7_exhibits_list_the_certificate_only(edited_copy):
    base, client = edited_copy
    run_dir = _t1_correct_run_dir(base)
    assert _download_links(client.get("/story/step/7").text) == [f"/run/{run_dir.name}/download/certificate.json"]
    # Even when the folder holds other evidence files, the ALIVE step lists the certificate only.
    (run_dir / "failure_report.json").write_text("{}")
    (run_dir / "ZombieRegressionTest.java").write_text("class X {}")
    assert _download_links(client.get("/story/step/7").text) == [f"/run/{run_dir.name}/download/certificate.json"]


@pytest.mark.slow
def test_step7_forms_target_the_correct_run_and_the_gate_allows_it(story_runs, story_client):
    page = story_client.get("/story/step/7?view=engineer").text
    correct_id = _t1_entry(story_runs.base)["correct_run_id"]
    gate = form_fields(page, "/story/gate-check")
    assert gate == {"run_id": correct_id, "view": "engineer"}
    run = form_fields(page, "/story/run")
    assert run["port"] == "correct"
    assert len(tags(page, "noscript")) == 2
    fragment = story_client.post("/story/gate-check", data=gate)
    assert "Commit allowed" in visible_text(fragment.text)
    assert has_live_region_root(fragment.text)


@pytest.mark.slow
def test_step7_engineer_and_business_views(story_runs, story_client):
    run_dir = _t1_correct_run_dir(story_runs.base)
    inputs = _read(run_dir, "inputs.json")
    digest = _read(run_dir, "certificate.json")["certificate_sha256"][:12]
    engineer = visible_text(story_client.get("/story/step/7?view=engineer").text)
    assert f"Run id {run_dir.name} Seed {inputs['random_seed']} Certificate hash (first 12 characters) {digest}" in engineer
    business = visible_text(story_client.get("/story/step/7?view=business").text)
    assert run_dir.name not in business and digest not in business
    for label in STEP_LABELS_FOR_ENGINEER:
        assert label not in business


# ------------------------------------------------------------------ step 8 (slow)


@pytest.fixture
def tamper_client(story_runs, story_client, tmp_path, monkeypatch):
    """The story client with its own exchange directory (the Tamper endpoint writes a copy there)."""
    exchange = tmp_path / "exchange"
    exchange.mkdir()
    monkeypatch.setenv("CORONER_EXCHANGE_DIR", str(exchange))
    return story_client, exchange


def _post_tamper(client, fields, **edits):
    from coroner.ui.app import reset_rate_limiter

    reset_rate_limiter()
    data = dict(fields)
    data.update({name: str(value) for name, value in edits.items()})
    return client.post("/story/tamper", data=data)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


@pytest.mark.slow
def test_step8_form_values_equal_the_certificate_of_the_faulty_run(story_runs, story_client):
    run_dir = _t1_faulty_run_dir(story_runs.base)
    certificate = _read(run_dir, "certificate.json")
    page = story_client.get("/story/step/8").text
    fields = form_fields(page, "/story/tamper")
    assert fields["run_id"] == run_dir.name
    for name in ("status", "cases_total", "cases_divergent", "random_seed"):
        assert fields[name] == str(certificate[name]), name
    labelled = {a.get("for") for t, a in tags(page, "label")}
    assert {"tamper-status", "tamper-cases-total", "tamper-cases-divergent", "tamper-random-seed"} <= labelled
    text = visible_text(page)
    assert "Try to make the rejected migration look clean by editing its certificate." in text
    assert "Change the status to ALIVE and the divergent count to 0" in text
    assert "Editing a certificate makes it INVALID. The audit result cannot be faked." in text
    result = {a["id"]: a for t, a in tags(page, "div") if a.get("id") == "tamper-result"}["tamper-result"]
    assert result["role"] == "status" and result["aria-live"] == "polite"
    assert len(tags(page, "noscript")) == 1
    finish = [a for a in anchors(page) if a.get("class") == "story-next"]
    assert [a["href"] for a in finish] == ["/"] and "Finish" in text


@pytest.mark.slow
def test_step8_every_form_field_is_a_real_certificate_key_that_the_replay_checks(story_runs, tamper_client):
    """cases_total is a real key (the certificate holds it next to case_count) and an edit of it is seen by the replay."""
    client, _ = tamper_client
    run_dir = _t1_faulty_run_dir(story_runs.base)
    certificate = _read(run_dir, "certificate.json")
    assert {"status", "cases_total", "cases_divergent", "random_seed", "case_count"} <= set(certificate)
    fields = form_fields(client.get("/story/step/8").text, "/story/tamper")

    more = certificate["cases_total"] + 1
    text = visible_text(_post_tamper(client, fields, cases_total=more).text)
    assert "Certificate: INVALID" in text
    assert f"replay mismatch (cases_total: expected {more}, got {certificate['cases_total']})" in text

    text = visible_text(_post_tamper(client, fields, cases_divergent=0).text)
    assert f"replay mismatch (cases_divergent: expected 0, got {certificate['cases_divergent']})" in text


@pytest.mark.slow
def test_step8_cheating_gives_invalid_with_the_replay_reason_and_leaves_the_original_untouched(story_runs, tamper_client):
    from coroner.ui.app import reset_rate_limiter

    client, exchange = tamper_client
    run_dir = _t1_faulty_run_dir(story_runs.base)
    certificate = _read(run_dir, "certificate.json")
    before = _sha256(run_dir / "certificate.json")
    fields = form_fields(client.get("/story/step/8").text, "/story/tamper")

    response = _post_tamper(client, fields, status="ALIVE", cases_divergent=0)
    assert response.status_code == 200 and has_live_region_root(response.text)
    text = visible_text(response.text)
    assert "Certificate: INVALID" in text
    assert f"replay mismatch (status: expected ALIVE, got {certificate['status']})" in text
    assert "<polygon" in response.text
    assert any("invalid" in a.get("class", "").split() for t, a in tags(response.text, "div"))
    # The reason is the one the API endpoint gives for the same edit.
    reset_rate_limiter()
    api = client.post("/api/tamper", data={**fields, "status": "ALIVE", "cases_divergent": "0"})
    assert visible_text(api.text) in text

    assert _sha256(run_dir / "certificate.json") == before
    assert list((exchange / "tamper").glob("*")) == []


@pytest.mark.slow
def test_step8_unmodified_values_give_valid(story_runs, tamper_client):
    client, _ = tamper_client
    run_dir = _t1_faulty_run_dir(story_runs.base)
    certificate = _read(run_dir, "certificate.json")
    fields = form_fields(client.get("/story/step/8").text, "/story/tamper")
    response = _post_tamper(client, fields)
    text = visible_text(response.text)
    assert "Certificate: VALID" in text
    assert f"Status: {certificate['status']} Cases: {certificate['cases_total']} Divergences: {certificate['cases_divergent']}" in text
    assert "<circle" in response.text and has_live_region_root(response.text)


@pytest.mark.slow
def test_step8_429_422_and_other_failures_become_alerts(story_runs, tamper_client, monkeypatch):
    client, _ = tamper_client
    fields = form_fields(client.get("/story/step/8").text, "/story/tamper")
    monkeypatch.setenv("CORONER_TAMPER_RATE_WINDOW", "3600")
    from coroner.ui.app import reset_rate_limiter

    reset_rate_limiter()
    # The first request uses the one allowed request of the window; its status is not accepted (422).
    first = client.post("/story/tamper", data={**fields, "status": "BOGUS"})
    assert first.status_code == 200
    assert "status must be ALIVE, ZOMBIE, or ERROR" in visible_text(first.text)
    assert [a for t, a in tags(first.text) if a.get("role") == "alert"]

    second = client.post("/story/tamper", data=fields)
    text = visible_text(second.text)
    assert [a for t, a in tags(second.text) if a.get("role") == "alert"]
    assert "Rate limit exceeded for tamper" in text
    seconds = int(re.search(r"Try again in (\d+) seconds?\.", text).group(1))
    assert 1 <= seconds <= 3600
    retry = form_fields(second.text, "/story/tamper")
    assert retry == {**fields, "view": "business"}

    reset_rate_limiter()
    assert "whole numbers" in visible_text(client.post("/story/tamper", data={**fields, "cases_total": "abc"}).text)
    reset_rate_limiter()
    unknown = client.post("/story/tamper", data={**fields, "run_id": "0" * 12})
    assert "Run not found" in visible_text(unknown.text)
    assert [a for t, a in tags(unknown.text) if a.get("role") == "alert"]
