"""Tests for the case registry (samples/traps/cases.json) and the places that show case names."""
import html
import json
import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from coroner.cases import (
    CasesRegistryError,
    auditable_trap_ids,
    case_card,
    case_label,
    load_cases_registry,
)
from coroner.ui.app import app
from coroner.ui.story import load_catalog, load_run

REPO_ROOT = Path(__file__).resolve().parent.parent
TRAPS_DIR = REPO_ROOT / "samples" / "traps"
TEMPLATES_DIR = REPO_ROOT / "coroner" / "ui" / "templates"

# The table of Req 11, typed once here because the registry file is what it is checked against.
EXPECTED_REGISTRY = {
    "T1": (1, "The Missing Branch"),
    "T2": (2, "The Vanishing Cent"),
    "T3": (3, "The Phantom Minus"),
    "T4": (4, "The Sign of Zero"),
    "T5": (5, "The Silent Zero"),
    "T6": (6, "reserved"),
}


def test_registry_has_exactly_the_six_entries():
    registry = load_cases_registry()
    assert {k: (v["case"], v["name"]) for k, v in registry.items()} == EXPECTED_REGISTRY


def test_every_trap_folder_has_a_registry_entry():
    registry = load_cases_registry()
    folder_ids = {p.name.split("-")[0] for p in TRAPS_DIR.iterdir() if p.is_dir()}
    assert folder_ids == set(registry), "trap folders and registry entries differ"
    for trap_id in ("T1", "T2", "T3", "T4", "T5"):
        assert any(TRAPS_DIR.glob(f"{trap_id}-*/trap.json"))


def test_case_label_display_form():
    registry = load_cases_registry()
    assert case_label("T1", registry) == "Case 1 The Missing Branch"
    assert case_label("T6", registry) == "Case 6 reserved"
    assert case_label("T9", registry) is None
    assert case_label(None, registry) is None


def test_auditable_trap_ids_exclude_the_placeholder():
    assert auditable_trap_ids() == ["T1", "T2", "T3", "T4", "T5"]


@pytest.mark.parametrize("key", ["subtitle", "detail"])
@pytest.mark.parametrize("bad", ["", "   ", 3, None, ["a"]])
def test_optional_text_fields_must_be_non_empty_strings(tmp_path, key, bad):
    path = tmp_path / "cases.json"
    path.write_text(json.dumps({"T1": {"case": 1, "name": "First", key: bad}}))
    with pytest.raises(CasesRegistryError, match=key):
        load_cases_registry(path)


def test_optional_text_fields_are_optional(tmp_path):
    path = tmp_path / "cases.json"
    path.write_text(json.dumps({
        "T1": {"case": 1, "name": "First"},
        "T2": {"case": 2, "name": "Second", "subtitle": "Only a subtitle"},
    }))
    registry = load_cases_registry(path)
    assert case_card("T1", registry) == ["Case 1: First"]
    assert case_card("T2", registry) == ["Case 2: Second", "Only a subtitle"]


def test_only_t3_has_subtitle_and_detail():
    registry = load_cases_registry()
    for trap_id, entry in registry.items():
        assert ("subtitle" in entry) == (trap_id == "T3")
        assert ("detail" in entry) == (trap_id == "T3")


def test_case_card_lines():
    registry = load_cases_registry()
    assert case_card("T3", registry) == [
        "Case 3: The Phantom Minus",
        "A positive amount read as negative",
        "Packed-decimal sign nibble F interpreted as a minus sign by the Java port",
    ]
    assert case_card("T1", registry) == ["Case 1: The Missing Branch"]
    assert case_card("T9", registry) is None
    assert case_card(None, registry) is None
    # the short title used by lists is unchanged by the card
    assert case_label("T3", registry) == "Case 3 The Phantom Minus"


def test_malformed_registry_is_refused(tmp_path):
    bad = tmp_path / "cases.json"
    bad.write_text('{"T1": {"case": "one", "name": "x"}}')
    with pytest.raises(CasesRegistryError):
        load_cases_registry(bad)
    bad.write_text("not json")
    with pytest.raises(CasesRegistryError):
        load_cases_registry(bad)
    with pytest.raises(CasesRegistryError):
        load_cases_registry(tmp_path / "missing.json")


def test_registry_is_read_at_call_time(tmp_path):
    path = tmp_path / "cases.json"
    path.write_text(json.dumps({"T1": {"case": 1, "name": "First"}}))
    assert case_label("T1", load_cases_registry(path)) == "Case 1 First"
    path.write_text(json.dumps({"T1": {"case": 1, "name": "Second"}}))
    assert case_label("T1", load_cases_registry(path)) == "Case 1 Second"


def test_home_selector_reads_the_registry(tmp_path, monkeypatch):
    monkeypatch.setenv("CORONER_BASE_DIR", str(tmp_path))
    page = html.unescape(TestClient(app).get("/").text)
    registry = load_cases_registry()
    for trap_id in auditable_trap_ids(registry):
        label = case_label(trap_id, registry)
        assert f'<option value="{trap_id}">{label} ({trap_id})</option>' in page
    assert '<option value="T6"' not in page
    assert '<option value="credit-fees">' in page


def test_templates_have_no_typed_sample_labels():
    for template in TEMPLATES_DIR.glob("*.html"):
        text = template.read_text()
        for typed in ("EBCDIC collation)", "(rounding)", "(COMP-3 sign)", "(zoned overpunch)", "(REDEFINES)"):
            assert typed not in text, f"{template.name} still has the typed label {typed}"


@pytest.mark.slow
def test_catalog_entries_carry_case_number_and_name(story_runs):
    registry = load_cases_registry()
    written = json.loads((story_runs.base / "runs" / "trap_catalog.json").read_text())
    assert [t["id"] for t in written["traps"]] == list(EXPECTED_REGISTRY)
    for trap in written["traps"]:
        assert trap["case_number"] == registry[trap["id"]]["case"]
        assert trap["case_name"] == registry[trap["id"]]["name"]
    assert written["traps"] == json.loads(json.dumps(story_runs.catalog["traps"]))


@pytest.mark.slow
def test_catalog_text_prints_case_names(story_runs):
    text = (story_runs.base / "runs" / "trap_catalog.txt").read_text()
    registry = load_cases_registry()
    for trap_id, entry in registry.items():
        assert f"== Case {entry['case']} {entry['name']} ({trap_id}):" in text
    assert "Case 1 The Missing Branch" in text


@pytest.mark.slow
def test_matrix_and_run_page_show_case_names(story_runs, monkeypatch):
    monkeypatch.setenv("CORONER_BASE_DIR", str(story_runs.base))
    client = TestClient(app)

    matrix = html.unescape(client.get("/matrix").text)
    registry = load_cases_registry()
    for trap_id in registry:
        assert f"<td style=\"padding: 1rem;\">{case_label(trap_id, registry)}</td>" in matrix
    t6_at = matrix.index(">T6<")
    t6_row = matrix[matrix.rfind("<tr", 0, t6_at):matrix.index("</tr>", t6_at)]
    cells = re.findall(r"<td[^>]*>([^<]*)</td>", t6_row)
    assert cells[0] == "T6"
    assert cells[1] == "Case 6 reserved"
    assert cells[3:] == ["not measured"] * 3

    catalog = load_catalog(story_runs.base)
    for trap_id in ("T1", "T2", "T3", "T4", "T5"):
        for run_id in (catalog[trap_id].faulty_run_id, catalog[trap_id].correct_run_id):
            page = client.get(f"/run/{run_id}")
            assert page.status_code == 200
            text = html.unescape(page.text)
            if trap_id == "T3":
                assert "<strong>Case 3: The Phantom Minus</strong>" in text
            else:
                assert f"<strong>{case_label(trap_id, registry)}</strong>" in text
    # the run page reads the same run the data layer reads
    assert load_run(story_runs.base, catalog["T1"].faulty_run_id).verdict["status"] == "ZOMBIE"


T3_CARD_LINES = [
    "Case 3: The Phantom Minus",
    "A positive amount read as negative",
    "Packed-decimal sign nibble F interpreted as a minus sign by the Java port",
]


def _text_lines(page_html: str) -> list[str]:
    """Visible text of a page, one stripped non-empty string per tag-delimited chunk."""
    text = html.unescape(re.sub(r"<[^>]+>", "\n", page_html))
    return [line.strip() for line in text.splitlines() if line.strip()]


@pytest.mark.slow
def test_t3_run_page_shows_the_three_line_case_card(story_runs, monkeypatch):
    monkeypatch.setenv("CORONER_BASE_DIR", str(story_runs.base))
    client = TestClient(app)
    catalog = load_catalog(story_runs.base)
    for run_id in (catalog["T3"].faulty_run_id, catalog["T3"].correct_run_id):
        page = client.get(f"/run/{run_id}")
        assert page.status_code == 200
        lines = _text_lines(page.text)
        at = lines.index(T3_CARD_LINES[0])
        assert lines[at:at + 3] == T3_CARD_LINES
        # the title line is strong, each line has its own element
        assert f"<strong>{T3_CARD_LINES[0]}</strong>" in page.text
        for line in T3_CARD_LINES[1:]:
            assert re.search(rf"<p[^>]*>\s*{re.escape(line)}\s*</p>", page.text)
        # the audit date, version and run id line comes after the card, and no longer carries the label
        audit_at = next(i for i, line in enumerate(lines) if line.startswith("Audit ") and run_id in line)
        assert audit_at == at + 3
        assert "Case 3 The Phantom Minus" not in page.text


@pytest.mark.slow
def test_t1_run_page_header_is_unchanged(story_runs, monkeypatch):
    monkeypatch.setenv("CORONER_BASE_DIR", str(story_runs.base))
    client = TestClient(app)
    catalog = load_catalog(story_runs.base)
    for run_id in (catalog["T1"].faulty_run_id, catalog["T1"].correct_run_id):
        page = client.get(f"/run/{run_id}")
        assert page.status_code == 200
        assert 'class="case-card"' not in page.text
        text = html.unescape(page.text)
        assert "<strong>Case 1 The Missing Branch</strong> · Audit " in text
        assert "Case 1: The Missing Branch" not in text
        assert "A positive amount read as negative" not in text


def test_home_selector_shows_the_short_title_only(tmp_path, monkeypatch):
    monkeypatch.setenv("CORONER_BASE_DIR", str(tmp_path))
    page = html.unescape(TestClient(app).get("/").text)
    assert '<option value="T3">Case 3 The Phantom Minus (T3)</option>' in page
    assert "A positive amount read as negative" not in page
    assert "Packed-decimal sign nibble F" not in page
