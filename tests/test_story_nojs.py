"""The story and the fool page without JavaScript (guided-story Task 14, Req 17).

Every request here is a plain GET without the HX-Request header, the way a browser with JavaScript
off (or a crawler) asks. The expected values are read by the test from the files of the real runs
(fixtures story_runs and fool_runs, tests/conftest.py), never typed.
"""
import csv
import json
import re
from decimal import Decimal
from pathlib import Path

import pytest

from story_html import anchors, listing_lines, tags, visible_text

pytestmark = pytest.mark.slow

REPO_ROOT = Path(__file__).resolve().parent.parent
COBOL_FILE = REPO_ROOT / "samples" / "traps" / "T1-ebcdic-match-merge" / "MATCH-MERGE.cob"
POSITIONING = (
    "Coroner does not translate COBOL. AWS Transform, Kiro, an LLM or a human migrates COBOL "
    "to Java. Coroner independently verifies the result."
)
VIEWS = ("business", "engineer")


def _case_label(trap_id):
    entry = json.loads((REPO_ROOT / "samples" / "traps" / "cases.json").read_text())[trap_id]
    return f"Case {entry['case']} {entry['name']}"


def _entry(catalog, trap_id):
    return next(trap for trap in catalog["traps"] if trap["id"] == trap_id)


def _run_dir(base, run_id):
    return Path(base) / "runs" / run_id


def _read(run_dir, name):
    return json.loads((run_dir / name).read_text())


def _money(value):
    return f"{Decimal(str(value)):.2f}"


@pytest.fixture
def faulty_dir(story_runs):
    return _run_dir(story_runs.base, _entry(story_runs.catalog, "T1")["faulty_run_id"])


@pytest.fixture
def correct_dir(story_runs):
    return _run_dir(story_runs.base, _entry(story_runs.catalog, "T1")["correct_run_id"])


# ------------------------------------------------------------------ the shell of every step page


@pytest.mark.parametrize("view", VIEWS)
@pytest.mark.parametrize("step", range(1, 9))
def test_every_step_page_is_complete_without_htmx(story_client, step, view):
    """Full page, case name, positioning sentence, both view links and Next and Back as links."""
    response = story_client.get(f"/story/step/{step}?view={view}")
    assert response.status_code == 200
    page = response.text
    assert "<html" in page.lower() and 'id="story-content"' in page
    text = visible_text(page)
    assert f"Step {step} of 8" in text
    assert POSITIONING in text
    assert _case_label("T1") in text
    view_links = {a["href"] for a in anchors(page) if a.get("hx-get") and "view=" in a["href"]}
    assert {f"/story/step/{step}?view=business", f"/story/step/{step}?view=engineer"} <= view_links
    next_links = [a for a in anchors(page) if a.get("class") == "story-next"]
    assert len(next_links) == 1 and next_links[0]["href"]
    # Every number the page shows comes from a file: no step is the missing-runs alert.
    assert "Bundled demo runs missing" not in text


# ------------------------------------------------------------------ measured values and listings per step


def test_step1_shows_the_listing_and_the_process_text(story_client):
    page = story_client.get("/story/step/1").text
    assert "Every night, the bank reconciles branch subtotals" in visible_text(page)
    source = COBOL_FILE.read_text().split("\n")
    rendered = listing_lines(page)
    assert rendered
    for number, text in rendered:
        assert text == source[number - 1].rstrip("\r")


def test_step2_shows_the_cobol_figures_and_the_listing(story_client, faulty_dir):
    reconciliation = _read(faulty_dir, "branch_reconciliation.json")
    verdict = _read(faulty_dir, "verdict.json")
    with (faulty_dir / "generated_cases.csv").open(newline="") as f:
        transactions = sum(1 for _ in csv.reader(f)) - 1
    page = story_client.get("/story/step/2").text
    text = visible_text(page)
    assert f"The COBOL program posted {transactions} transactions in {verdict['cases_total']} test batches." in text
    assert reconciliation["grand_total"]["cobol"] in text
    for branch in reconciliation["branches"]:
        assert branch["cobol_subtotal"] in text
    source = COBOL_FILE.read_text().split("\n")
    rendered = listing_lines(page)
    assert rendered
    assert all(text == source[number - 1].rstrip("\r") for number, text in rendered)


def test_step3_shows_both_grand_totals(story_client, faulty_dir):
    totals = _read(faulty_dir, "branch_reconciliation.json")["grand_total"]
    text = visible_text(story_client.get("/story/step/3").text)
    assert f"COBOL grand total: {totals['cobol']}" in text
    assert f"Java grand total: {totals['java']}" in text


def test_step4_shows_the_verdict_and_the_batch_count(story_client, faulty_dir):
    verdict = _read(faulty_dir, "verdict.json")
    text = visible_text(story_client.get("/story/step/4").text)
    assert verdict["status"] == "ZOMBIE"
    assert f"{verdict['cases_divergent']} of {verdict['cases_total']} batches diverge" in text
    assert f"Exposure {_money(verdict['exposure_sum'])}" in text
    assert "ZOMBIE" in text


def test_step5_shows_the_autopsy_the_exhibits_and_the_listing(story_client, faulty_dir):
    verdict = _read(faulty_dir, "verdict.json")
    comparison = _read(faulty_dir, "comparison_results.json")
    position, case_id = next(
        (position, case["case_id"]) for position, case in enumerate(comparison["cases"], start=1) if case["divergent"]
    )
    page = story_client.get("/story/step/5").text
    text = visible_text(page)
    for heading in ("Cause of death", "Time of death", "Exhibits"):
        assert heading in text
    assert f"The first divergent case is {case_id} (case {position} of {verdict['cases_total']})." in text
    links = [a["href"] for a in anchors(page) if "/download/" in a["href"]]
    assert links and all(re.fullmatch(r"/run/[0-9a-f]{12}/download/[A-Za-z_.]+", link) for link in links)
    suspense = abs(Decimal(_read(faulty_dir, "branch_reconciliation.json")["suspense"]["difference"]))
    assert f"Posted to suspense instead of a branch: {suspense:.2f}" in text
    assert listing_lines(page)


def test_step6_shows_the_fix_and_the_listing(story_client):
    trap = json.loads((COBOL_FILE.parent / "trap.json").read_text())
    page = story_client.get("/story/step/6").text
    assert trap["business_fix"] in visible_text(page)
    assert listing_lines(page)


def test_step7_shows_the_alive_figures(story_client, correct_dir):
    verdict = _read(correct_dir, "verdict.json")
    text = visible_text(story_client.get("/story/step/7").text)
    assert verdict["status"] == "ALIVE"
    assert f"{verdict['cases_divergent']} of {verdict['cases_total']} batches diverge" in text
    assert "ALIVE" in text


def test_step8_form_is_prefilled_from_the_certificate(story_client, faulty_dir):
    certificate = _read(faulty_dir, "certificate.json")
    page = story_client.get("/story/step/8").text
    values = {a.get("name"): a.get("value") for _, a in tags(page, "input") if a.get("name")}
    assert values["random_seed"] == str(certificate["random_seed"])
    assert values["cases_total"] == str(certificate["cases_total"])
    assert "Editing a certificate makes it INVALID" in visible_text(page)


# ------------------------------------------------------------------ the noscript notes (Req 17)


ACTION_CONTAINERS = {4: ("gate-result", "run-result"), 7: ("gate-result", "run-result"), 8: ("tamper-result",)}


@pytest.mark.parametrize("step", sorted(ACTION_CONTAINERS))
def test_every_action_form_has_a_noscript_note_right_after_its_result_container(story_client, step):
    page = story_client.get(f"/story/step/{step}").text
    notes = re.findall(r"<noscript>(.*?)</noscript>", page, re.S)
    assert len(notes) == len(ACTION_CONTAINERS[step])
    for note in notes:
        assert "needs JavaScript" in note
        assert "python3 -m coroner verify" in note
    for container in ACTION_CONTAINERS[step]:
        assert re.search(rf'<div id="{container}"></div>\s*<noscript>', page), container


def test_the_fool_form_is_a_plain_get_form_with_an_update_button_for_noscript(fool_client):
    page = fool_client.get("/fool").text
    forms = [a for _, a in tags(page, "form") if a.get("action") == "/fool"]
    assert len(forms) == 1 and forms[0]["method"] == "get"
    assert re.search(r"<noscript><button type=\"submit\">Update</button></noscript>", page)


# ------------------------------------------------------------------ the fool page with parameters


def _verdict_status(base, run_id):
    return _read(_run_dir(base, run_id), "verdict.json")["status"]


def _expected_counter(fool_runs, selected):
    """"Coroner detected D of N injected defects" computed from the verdict.json files of the runs."""
    runs = {
        "case1": _entry(fool_runs.catalog, "T1")["faulty_run_id"],
        "case2": fool_runs.half_even_run,
        "case4": _entry(fool_runs.catalog, "T4")["faulty_run_id"],
    }
    statuses = [_verdict_status(fool_runs.base, runs[name]) for name in selected]
    return f"Coroner detected {sum(1 for s in statuses if s == 'ZOMBIE')} of {len(statuses)} injected defects"


@pytest.mark.parametrize("selected", [
    ("case1",), ("case2",), ("case4",), ("case1", "case4"), ("case1", "case2", "case4"),
])
def test_the_get_form_with_parameters_shows_the_right_counter(fool_client, fool_runs, selected):
    query = "&".join(f"{name}=on" for name in selected)
    response = fool_client.get(f"/fool?{query}")
    assert response.status_code == 200
    page = response.text
    assert "<html" in page.lower()
    assert _expected_counter(fool_runs, selected) in visible_text(page)
    checked = sorted(a["name"] for _, a in tags(page, "input") if a.get("type") == "checkbox" and "checked" in a)
    assert checked == sorted(selected)


def test_the_fool_page_with_no_toggle_counts_the_clean_ports(fool_client, fool_runs):
    runs = [
        _entry(fool_runs.catalog, "T1")["correct_run_id"],
        fool_runs.correct_run,
        _entry(fool_runs.catalog, "T4")["correct_run_id"],
    ]
    alive = sum(1 for run_id in runs if _verdict_status(fool_runs.base, run_id) == "ALIVE")
    text = visible_text(fool_client.get("/fool").text)
    assert "No defect injected" in text
    assert f"Coroner certified {alive} of {len(runs)} clean ports" in text
    assert POSITIONING in text
