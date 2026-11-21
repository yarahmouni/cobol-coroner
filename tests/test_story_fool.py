"""Tests for the "Can you fool Coroner?" page (GET /fool).

Fast tests need no run: they use an empty base directory, where the page shows the typed "Bundled
demo runs missing" alert and still lists the three disabled toggles. Slow tests read the real runs of
the session fixture `fool_runs` (tests/conftest.py: the trap catalog plus the credit-fees correct run
and the credit-fees HALF_EVEN variant run) and compute every expected value from the run files
themselves, never from a literal.
"""
import csv
import itertools
import json
import re
import shutil
from collections import Counter
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from coroner.ui.app import app
from coroner.ui.sentences import generate_zombie_sentence

from story_html import (
    anchors,
    into_container,
    live_regions,
    live_regions_within,
    tags,
    visible_text,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
UI_DIR = REPO_ROOT / "coroner" / "ui"
MISSING = "Bundled demo runs missing. Run docker compose up to generate them."
POSITIONING = (
    "Coroner does not translate COBOL. AWS Transform, Kiro, an LLM or a human migrates COBOL "
    "to Java. Coroner independently verifies the result."
)
PARAMS = ("case1", "case2", "case4")
TRAP_OF = {"case1": "T1", "case4": "T4"}
# The credit-fees toggle is named by its run (owner decision, Q7): typed here on purpose, not read from the code.
HALF_EVEN_LABEL = "HALF_EVEN rounding, credit-fees sample (HALF_EVEN variant run)"
FORBIDDEN_FOR_HALF_EVEN = (re.compile(r"Case\s*2"), re.compile(r"Vanishing Cent"), re.compile(r"\bT2\b"))


@pytest.fixture
def empty_client(tmp_path, monkeypatch):
    monkeypatch.setenv("CORONER_BASE_DIR", str(tmp_path))
    return TestClient(app)


def _registry():
    return json.loads((REPO_ROOT / "samples" / "traps" / "cases.json").read_text())


def _label(param):
    if param == "case2":
        return HALF_EVEN_LABEL
    entry = _registry()[TRAP_OF[param]]
    return f"Case {entry['case']} {entry['name']}"


def _toggle_label_text(page: str, param: str) -> str:
    """Visible text of the <label> of one checkbox."""
    match = re.search(rf'<label for="toggle-{param}">(.*?)</label>', page, re.S)
    assert match, param
    return visible_text(match.group(1))


def _assert_not_named_by_a_case(text: str, where: str):
    for pattern in FORBIDDEN_FOR_HALF_EVEN:
        assert not pattern.search(text), f"{where}: {pattern.pattern!r} in {text!r}"


# ------------------------------------------------------------------ fast tests (no run)


def test_exactly_three_checkboxes_named_case1_case2_case4_with_labels(empty_client):
    page = empty_client.get("/fool").text
    boxes = [a for t, a in tags(page, "input") if a.get("type") == "checkbox"]
    assert [a["name"] for a in boxes] == list(PARAMS)
    labelled = {a.get("for") for t, a in tags(page, "label")}
    assert {a["id"] for a in boxes} <= labelled
    assert all(a["value"] == "on" for a in boxes)


def test_page_lists_the_case_names_from_the_registry_and_the_run_label_for_half_even(empty_client):
    text = visible_text(empty_client.get("/fool").text)
    for param in PARAMS:
        assert _label(param) in text
    assert _label("case1") == "Case 1 The Missing Branch"
    assert _label("case2") == HALF_EVEN_LABEL


@pytest.mark.parametrize("view", ["business", "engineer"])
def test_half_even_toggle_is_named_by_its_run_and_never_by_a_case(empty_client, view):
    url = f"/fool?case1=on&case2=on&case4=on&view={view}"
    page = empty_client.get(url).text
    fragment = empty_client.get(url, headers={"HX-Request": "true"}).text
    # Every place where the toggle is rendered without runs: the label of the checkbox and the page text.
    assert _toggle_label_text(page, "case2").startswith(HALF_EVEN_LABEL)
    assert _label("case1") in _toggle_label_text(page, "case1")
    assert _label("case4") in _toggle_label_text(page, "case4")
    # The result rows (page and htmx fragment, real runs) are checked by the slow test below.
    _assert_not_named_by_a_case(_toggle_label_text(page, "case2"), "toggle label")
    # Nothing on the page names this toggle by a case, also in attributes (aria labels, ids shown to a reader).
    _assert_not_named_by_a_case(visible_text(page), "page text")
    _assert_not_named_by_a_case(visible_text(fragment), "fragment text")
    _assert_not_named_by_a_case(re.sub(r"toggle-case2", "", page), "page html")
    _assert_not_named_by_a_case(re.sub(r"toggle-case2", "", fragment), "fragment html")


def test_missing_runs_disable_every_toggle_and_show_no_number(empty_client):
    page = empty_client.get("/fool?case1=on&case2=on&case4=on").text
    boxes = [a for t, a in tags(page, "input") if a.get("type") == "checkbox"]
    assert all("disabled" in a and "checked" not in a for a in boxes)
    text = visible_text(page)
    assert MISSING in text
    assert text.count("Bundled run missing") == 3
    assert "Coroner detected" not in text and "Coroner certified" not in text
    assert "test cases diverge" not in text


def test_page_has_the_positioning_sentence_the_no_upload_sentence_and_the_site_links(empty_client):
    page = empty_client.get("/fool").text
    text = visible_text(page)
    assert POSITIONING in text
    assert "No code is uploaded and no audit starts" in text
    hrefs = [a["href"] for a in anchors(page)]
    assert "/" in hrefs and "/matrix" in hrefs and "/story/step/1?view=business" in hrefs


def test_view_links_carry_the_switched_on_toggles_and_unknown_views_give_business(empty_client):
    page = empty_client.get("/fool", params={"case1": "on", "case4": "on", "view": "<script>"}).text
    views = [a for a in anchors(page) if a["href"].startswith("/fool?")]
    assert [a["href"] for a in views] == [
        "/fool?case1=on&case4=on&view=business", "/fool?case1=on&case4=on&view=engineer",
    ]
    assert views[0].get("aria-current") == "true" and "aria-current" not in views[1]
    assert "view=%3Cscript" not in page and "&lt;script&gt;" not in page and "view=<script>" not in page


def test_htmx_request_gets_only_the_result_region_and_the_out_of_band_view_links(empty_client):
    response = empty_client.get("/fool?case2=on", headers={"HX-Request": "true"})
    assert "<html" not in response.text.lower()
    assert POSITIONING not in visible_text(response.text)
    oob = [a for t, a in tags(response.text, "nav") if a.get("hx-swap-oob") == "true"]
    assert [a["id"] for a in oob] == ["fool-views"]
    assert "HX-Request" in response.headers["vary"]
    assert response.headers["cache-control"] == "no-store"
    full = empty_client.get(
        "/fool", headers={"HX-Request": "true", "HX-History-Restore-Request": "true"},
    )
    assert "<html" in full.text.lower() and POSITIONING in visible_text(full.text)


def test_exactly_one_live_region_for_the_toggle_result_the_page_container(empty_client):
    page = empty_client.get("/fool?case1=on").text
    fragment = empty_client.get("/fool?case1=on", headers={"HX-Request": "true"}).text
    assert live_regions_within(page, "fool-result") == 1
    assert live_regions(fragment) == 0
    container = [a for t, a in tags(page, "div") if a.get("id") == "fool-result"][0]
    assert container["role"] == "status" and container["aria-live"] == "polite"
    # The page has no other live region, and the swapped result adds none inside the container.
    assert live_regions(page) == 1


def test_form_is_a_get_form_with_htmx_on_change_and_an_update_button_without_javascript(empty_client):
    page = empty_client.get("/fool").text
    form = [a for t, a in tags(page, "form")][0]
    assert form["method"] == "get" and form["action"] == "/fool"
    assert form["hx-get"] == "/fool" and form["hx-trigger"] == "change"
    assert form["hx-target"] == "#fool-result" and form["hx-push-url"] == "true"
    assert len(tags(page, "noscript")) == 1
    assert "<noscript><button type=\"submit\">Update</button></noscript>" in page


def test_fool_templates_have_no_em_dash():
    files = sorted((UI_DIR / "templates").glob("fool*.html")) + [UI_DIR / "templates" / "story_styles.html"]
    assert len(files) == 4
    for path in files:
        assert "\u2014" not in path.read_text(), path.name
    assert "\u2014" not in (UI_DIR / "story.py").read_text()


# ------------------------------------------------------------------ slow tests (real runs)


def _read(path: Path):
    return json.loads(path.read_text())


def _toggle_ids(fool_runs):
    """param -> (faulty run id, correct run id). The T1 and T4 ids come from the catalog file."""
    catalog = {t["id"]: t for t in _read(fool_runs.base / "runs" / "trap_catalog.json")["traps"]}
    return {
        "case1": (catalog["T1"]["faulty_run_id"], catalog["T1"]["correct_run_id"]),
        "case2": (fool_runs.half_even_run, fool_runs.correct_run),
        "case4": (catalog["T4"]["faulty_run_id"], catalog["T4"]["correct_run_id"]),
    }


def _verdict(base: Path, run_id: str) -> dict:
    return _read(base / "runs" / run_id / "verdict.json")


def _counter(page: str) -> str:
    import re
    return " ".join(re.search(r'<p class="fool-counter">(.*?)</p>', page, re.S).group(1).split())


def _rows(page: str) -> list:
    """The visible text of each of the three toggle rows, in page order."""
    chunks = page.split('<section class="fool-row"')[1:]
    assert len(chunks) == 3
    return [visible_text('<section class="fool-row"' + chunk.split("</section>")[0]) for chunk in chunks]


def _expected(base: Path, ids: dict, selected: set):
    """(N, D, M, C, shown run ids) computed from the verdict.json files of the runs."""
    shown = {p: (ids[p][0] if p in selected else ids[p][1]) for p in PARAMS}
    n = len(selected)
    d = sum(1 for p in selected if _verdict(base, ids[p][0])["status"] == "ZOMBIE")
    m = len(PARAMS)
    c = sum(1 for p in PARAMS if _verdict(base, ids[p][1])["status"] == "ALIVE")
    return n, d, m, c, shown


@pytest.mark.slow
def test_runs_of_the_page_are_found_from_run_files_not_typed(fool_runs):
    """The independent scan of the inputs.json files finds the two credit-fees runs the fixture made."""
    found = {}
    for inputs_file in (fool_runs.base / "runs").glob("*/inputs.json"):
        inputs = _read(inputs_file)
        if "credit-fees" in inputs["cobol_file"]:
            kind = "variant" if "variants" in inputs["java_file"] else "correct"
            found[kind] = inputs_file.parent.name
    assert found == {"variant": fool_runs.half_even_run, "correct": fool_runs.correct_run}
    assert _verdict(fool_runs.base, fool_runs.half_even_run)["status"] == "ZOMBIE"
    assert _verdict(fool_runs.base, fool_runs.correct_run)["status"] == "ALIVE"


@pytest.mark.slow
@pytest.mark.parametrize(
    "selected",
    [set(c) for r in range(4) for c in itertools.combinations(PARAMS, r)],
    ids=lambda s: "+".join(sorted(s)) or "none",
)
def test_counter_and_rows_for_each_of_the_eight_toggle_combinations(fool_runs, fool_client, selected):
    base, ids = fool_runs.base, _toggle_ids(fool_runs)
    n, d, m, c, shown = _expected(base, ids, selected)
    page = fool_client.get("/fool", params={p: "on" for p in selected}).text
    if selected:
        assert _counter(page) == f"Coroner detected {d} of {n} injected defects"
        assert "Coroner certified" not in visible_text(page)
        assert "No defect injected" not in visible_text(page)
    else:
        assert _counter(page) == "No defect injected"
        assert f"Coroner certified {c} of {m} clean ports" in visible_text(page)
    boxes = {a["name"]: a for t, a in tags(page, "input") if a.get("type") == "checkbox"}
    for param in PARAMS:
        assert ("checked" in boxes[param]) == (param in selected)
        assert "disabled" not in boxes[param]
    for param, row in zip(PARAMS, _rows(page)):
        verdict = _verdict(base, shown[param])
        assert _label(param) in row
        assert verdict["status"] in row
        assert f"{verdict['cases_divergent']} of {verdict['cases_total']} test cases diverge" in row
        assert ("This defect is on" in row) == (param in selected)
        assert ("This defect is off" in row) == (param not in selected)
        assert f'href="/run/{shown[param]}"' in page
@pytest.mark.slow
@pytest.mark.parametrize("view", ["business", "engineer"])
@pytest.mark.parametrize("kind", ["page", "fragment"])
def test_real_half_even_row_shows_the_credit_fees_label_and_no_case_name(fool_runs, fool_client, view, kind):
    """All three toggles on, real runs: the HALF_EVEN row is named by its run, Cases 1 and 4 keep their case names."""
    headers = {"HX-Request": "true"} if kind == "fragment" else {}
    html = fool_client.get(f"/fool?case1=on&case2=on&case4=on&view={view}", headers=headers).text
    rows = _rows(html)
    assert rows[1].startswith(HALF_EVEN_LABEL)
    assert "This defect is on" in rows[1] and "ZOMBIE" in rows[1]
    if view == "engineer":
        assert f"Run id {fool_runs.half_even_run}" in rows[1]
    _assert_not_named_by_a_case(rows[1], f"{kind} {view} HALF_EVEN row")
    _assert_not_named_by_a_case(visible_text(html), f"{kind} {view} text")
    assert rows[0].startswith("Case 1 The Missing Branch")
    assert rows[2].startswith(_label("case4"))
    assert _label("case4").startswith("Case 4 ")
    if kind == "page":
        _assert_not_named_by_a_case(_toggle_label_text(html, "case2"), "toggle label")
        assert _toggle_label_text(html, "case1").startswith(_label("case1"))
        assert _toggle_label_text(html, "case4").startswith(_label("case4"))




@pytest.mark.slow
def test_a_shown_zombie_sentence_equals_the_sentence_of_the_run_page(fool_runs, fool_client):
    base, ids = fool_runs.base, _toggle_ids(fool_runs)
    page = fool_client.get("/fool?case1=on&case2=on&case4=on").text
    text = visible_text(page)
    for param in PARAMS:
        run_id = ids[param][0]
        run_page = visible_text(fool_client.get(f"/run/{run_id}").text)
        verdict = _verdict(base, run_id)
        if param == "case2":
            sentence = verdict["sub_label"]
        else:
            sentence = generate_zombie_sentence(TRAP_OF[param], base / "runs" / run_id)
        assert sentence in text, param
        assert sentence in run_page, param
    t1 = _verdict(base, ids["case1"][0])
    assert (
        f"This Java migration is not safe to promote: {t1['affected_branches']} branch subtotals "
        f"do not reconcile with COBOL."
    ) in text


@pytest.mark.slow
def test_engineer_details_come_from_the_run_files(fool_runs, fool_client):
    base, ids = fool_runs.base, _toggle_ids(fool_runs)
    page = fool_client.get("/fool?case1=on&case2=on&case4=on&view=engineer").text
    rows = dict(zip(PARAMS, _rows(page)))
    catalog = {t["id"]: t for t in _read(base / "runs" / "trap_catalog.json")["traps"]}
    for param in PARAMS:
        run_id = ids[param][0]
        inputs, verdict = _read(base / "runs" / run_id / "inputs.json"), _verdict(base, run_id)
        row = rows[param]
        assert f"Run id {run_id}" in row
        assert f"Seed {inputs['random_seed']}" in row
        assert f"Divergent cases {verdict['cases_divergent']}" in row
        assert "COBOL lines involved" in row

    # Case 1 and Case 4: the cobol_lines of the catalog entry, written without the folder.
    for param in ("case1", "case4"):
        for reference in catalog[TRAP_OF[param]]["cobol_lines"]:
            path_part, line = reference.rsplit(":", 1)
            assert f"{Path(path_part).name}:{line}" in rows[param]

    # Case 2: the lines of the run's card.txt and the divergent values per output column.
    card = (base / "runs" / ids["case2"][0] / "card.txt").read_text()
    lines_part = [l for l in card.splitlines() if l.startswith("COBOL lines involved:")][0].split(":", 1)[1]
    for part in lines_part.split("; "):
        path_part, rest = part.strip().split(":", 1)
        assert f"{Path(path_part).name}:{rest}" in rows["case2"]
    comparison = _read(base / "runs" / ids["case2"][0] / "comparison_results.json")
    columns = Counter(
        field["field_name"] for case in comparison["cases"] for field in case["divergent_fields"]
    )
    assert columns
    for name, count in columns.items():
        assert f"{name} {count}" in rows["case2"]

    # Case 4: divergent cases by the last character of the input, from the generated cases.
    run_dir = base / "runs" / ids["case4"][0]
    values = {r["CASE-ID"]: r["ZONED-VALUE"] for r in csv.DictReader((run_dir / "generated_cases.csv").open())}
    divergent = [c["case_id"] for c in _read(run_dir / "comparison_results.json")["cases"] if c["divergent"]]
    closing = sum(values[i].endswith("}") for i in divergent)
    opening = sum(values[i].endswith("{") for i in divergent)
    assert divergent
    assert f"{len(divergent)} divergent; {closing} end in }}; {opening} end in {{" in rows["case4"]


@pytest.mark.slow
def test_business_view_has_none_of_the_engineer_labels(fool_runs, fool_client):
    text = visible_text(fool_client.get("/fool?case1=on&case2=on&case4=on&view=business").text)
    for label in ("Run id", "Seed", "COBOL lines involved", "Divergent values per output column", "Divergent cases by"):
        assert label not in text


@pytest.mark.slow
def test_only_the_value_on_switches_a_toggle_on(fool_runs, fool_client):
    page = fool_client.get("/fool?case1=true&case2=1&case4=ON").text
    boxes = [a for t, a in tags(page, "input") if a.get("type") == "checkbox"]
    assert not any("checked" in a for a in boxes)
    assert _counter(page) == "No defect injected"


@pytest.mark.slow
def test_page_starts_no_audit_and_writes_nothing(fool_runs, fool_client):
    runs = fool_runs.base / "runs"
    before = sorted((p.name, p.stat().st_mtime_ns) for p in runs.iterdir())
    for query in ("", "?case1=on&case2=on&case4=on", "?case4=on&view=engineer"):
        assert fool_client.get(f"/fool{query}").status_code == 200
    assert sorted((p.name, p.stat().st_mtime_ns) for p in runs.iterdir()) == before


@pytest.mark.slow
def test_htmx_fragment_for_real_runs_has_the_counter_and_no_live_region(fool_runs, fool_client):
    base, ids = fool_runs.base, _toggle_ids(fool_runs)
    n, d, *_ = _expected(base, ids, {"case1", "case4"})
    page = fool_client.get("/fool?case1=on&case4=on").text
    fragment = fool_client.get("/fool?case1=on&case4=on", headers={"HX-Request": "true"}).text
    assert _counter(fragment) == f"Coroner detected {d} of {n} injected defects"
    assert live_regions(fragment) == 0
    assert live_regions_within(page, "fool-result") == 1
    assert POSITIONING not in visible_text(fragment)


# ---- the counter is computed from the files: edited and deleted runs in a temporary copy


@pytest.fixture
def runs_copy(fool_runs, tmp_path, monkeypatch):
    """A copy of the runs folder that a test may edit; the session runs stay untouched."""
    shutil.copytree(fool_runs.base / "runs", tmp_path / "runs")
    monkeypatch.setenv("CORONER_BASE_DIR", str(tmp_path))
    return TestClient(app), tmp_path


@pytest.mark.slow
def test_a_faulty_verdict_edited_to_alive_lowers_d_and_keeps_n(fool_runs, runs_copy):
    client, base = runs_copy
    ids = _toggle_ids(fool_runs)
    all_on = {"case1": "on", "case2": "on", "case4": "on"}
    n, d, *_ = _expected(base, ids, set(PARAMS))
    assert _counter(client.get("/fool", params=all_on).text) == f"Coroner detected {d} of {n} injected defects"
    path = base / "runs" / ids["case4"][0] / "verdict.json"
    verdict = _read(path)
    verdict["status"] = "ALIVE"
    path.write_text(json.dumps(verdict))
    n2, d2, *_ = _expected(base, ids, set(PARAMS))
    assert (n2, d2) == (n, d - 1)
    assert _counter(client.get("/fool", params=all_on).text) == f"Coroner detected {d - 1} of {n} injected defects"


@pytest.mark.slow
def test_a_deleted_faulty_run_disables_its_toggle_and_lowers_n(fool_runs, runs_copy):
    client, base = runs_copy
    ids = _toggle_ids(fool_runs)
    shutil.rmtree(base / "runs" / ids["case2"][0])
    page = client.get("/fool?case1=on&case2=on&case4=on").text
    boxes = {a["name"]: a for t, a in tags(page, "input") if a.get("type") == "checkbox"}
    assert "disabled" in boxes["case2"] and "checked" not in boxes["case2"]
    assert "disabled" not in boxes["case1"] and "checked" in boxes["case1"]
    n, d, *_ = _expected(base, ids, {"case1", "case4"})
    assert _counter(page) == f"Coroner detected {d} of {n} injected defects"
    assert n == 2
    rows = _rows(page)
    assert "Bundled run missing" in rows[1]
    assert "Bundled run missing" in visible_text(page)
    # Only the HALF_EVEN run is gone: the correct credit-fees run is still shown for that toggle.
    assert f'href="/run/{ids["case2"][1]}"' in page


@pytest.mark.slow
def test_a_deleted_correct_run_lowers_m_when_no_defect_is_on(fool_runs, runs_copy):
    client, base = runs_copy
    ids = _toggle_ids(fool_runs)
    shutil.rmtree(base / "runs" / ids["case1"][1])
    page = client.get("/fool").text
    c = sum(1 for p in ("case2", "case4") if _verdict(base, ids[p][1])["status"] == "ALIVE")
    assert "Coroner certified {} of 2 clean ports".format(c) in visible_text(page)
    assert "Bundled run missing" in _rows(page)[0]


@pytest.mark.slow
def test_an_edited_clean_verdict_lowers_c_and_keeps_m(fool_runs, runs_copy):
    client, base = runs_copy
    ids = _toggle_ids(fool_runs)
    path = base / "runs" / ids["case1"][1] / "verdict.json"
    verdict = _read(path)
    verdict["status"] = "ZOMBIE"
    path.write_text(json.dumps(verdict))
    _, _, m, c, _ = _expected(base, ids, set())
    assert f"Coroner certified {c} of {m} clean ports" in visible_text(client.get("/fool").text)
    assert c == m - 1
