"""Tests of the static fallback page (D-48): built only from the files of real runs."""

import html
import json
import os
import re
import subprocess
import sys
from html.parser import HTMLParser
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
SCRIPT = REPO / "scripts" / "build_static_page.py"
COMMITTED_PAGE = REPO / "docs" / "static" / "index.html"
LIVE_URL = "https://coroner.iqoba.com"
REPO_URL = "https://github.com/yarahmouni/cobol-coroner"


class TableParser(HTMLParser):
    """Collects every table as caption -> rows of cell text."""

    def __init__(self):
        super().__init__()
        self.tables = {}
        self._caption = None
        self._in_caption = False
        self._row = None
        self._has_td = False
        self._cell = None

    def handle_starttag(self, tag, attrs):
        if tag == "caption":
            self._in_caption = True
            self._caption = ""
        elif tag == "tr":
            self._row = []
            self._has_td = False
        elif tag in ("td", "th") and self._row is not None:
            self._cell = ""
            self._has_td = self._has_td or tag == "td"

    def handle_endtag(self, tag):
        if tag == "caption":
            self._in_caption = False
            self.tables[self._caption] = []
        elif tag in ("td", "th") and self._cell is not None:
            self._row.append(" ".join(self._cell.split()))
            self._cell = None
        elif tag == "tr" and self._row is not None:
            if self._has_td and self._caption in self.tables:
                self.tables[self._caption].append(self._row)
            self._row = None

    def handle_data(self, data):
        if self._in_caption:
            self._caption += data
        elif self._cell is not None:
            self._cell += data


def tables_of(page: str) -> dict:
    parser = TableParser()
    parser.feed(page)
    return parser.tables


def last_word(cell: str) -> str:
    return cell.split()[-1]


def build_page(base: Path, out: Path, commit: str = "TEST_COMMIT") -> str:
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "--base", str(base), "--out", str(out), "--commit", commit],
        cwd=REPO, capture_output=True, text=True, timeout=600,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    return (out / "index.html").read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def real_base(tmp_path_factory):
    """A base directory made by the real catalog runner: T1 to T5 at 2000 cases, seed 42."""
    base = tmp_path_factory.mktemp("static_base")
    repo_runs = REPO / "runs"
    before = sorted(p.name for p in repo_runs.iterdir()) if repo_runs.exists() else []
    proc = subprocess.run(
        [sys.executable, "-m", "coroner", "traps"],
        cwd=REPO, capture_output=True, text=True, timeout=1800,
        env={**os.environ, "CORONER_BASE_DIR": str(base)},
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    after = sorted(p.name for p in repo_runs.iterdir()) if repo_runs.exists() else []
    assert before == after, "the catalog run wrote into the repository runs/ folder"
    return base


@pytest.fixture(scope="module")
def built(real_base, tmp_path_factory):
    out = tmp_path_factory.mktemp("static_out")
    return real_base, out, build_page(real_base, out)


def t1_ids(base: Path):
    catalog = json.loads((base / "runs" / "trap_catalog.json").read_text())
    t1 = next(t for t in catalog["traps"] if t["id"] == "T1")
    return catalog, t1["faulty_run_id"], t1["correct_run_id"]


@pytest.mark.slow
def test_page_has_no_script_and_only_two_links(built):
    _, _, page = built
    assert "<script" not in page.lower()
    assert "<link" not in page.lower()
    assert " src=" not in page.lower()
    urls = re.findall(r"https?://[^\s\"'<>)]+", page)
    assert set(urls) == {LIVE_URL, REPO_URL}
    assert page.lower().count("http") == len(urls), "an http string that is not one of the two links"


@pytest.mark.slow
def test_run_ids_are_the_expected_ones(built):
    base, _, page = built
    _, faulty_id, correct_id = t1_ids(base)
    assert (faulty_id, correct_id) == ("f584d5f35228", "29c15f04407b")
    assert faulty_id in page and correct_id in page


@pytest.mark.slow
def test_every_figure_equals_the_run_files(built):
    base, _, page = built
    catalog, faulty_id, correct_id = t1_ids(base)
    runs = base / "runs"
    faulty = json.loads((runs / faulty_id / "verdict.json").read_text())
    correct = json.loads((runs / correct_id / "verdict.json").read_text())
    recon = json.loads((runs / faulty_id / "branch_reconciliation.json").read_text())
    assert faulty["cases_divergent"] == 682 and faulty["cases_total"] == 2000
    tables = tables_of(page)

    verdicts = {row[0]: row[1:] for row in tables["Case 1 verdicts from verdict.json"]}
    for label, key in (
        ("Sub-label", "sub_label"), ("Cases", "cases_total"), ("Divergent cases", "cases_divergent"),
        ("Unreconciled branch exposure, sum", "exposure_sum"), ("Unreconciled branch exposure, max", "exposure_max"),
        ("Branches affected", "affected_branches"), ("Suspense difference", "suspense_difference"),
    ):
        assert verdicts[label] == [str(faulty[key]), str(correct[key])], label
    assert [last_word(c) for c in verdicts["Status"]] == [faulty["status"], correct["status"]]
    assert verdicts["Grand total matches"] == ["yes" if faulty["grand_total_matches"] else "no",
                                               "yes" if correct["grand_total_matches"] else "no"]
    assert verdicts["Run"] == [faulty_id, correct_id]

    rows = tables["Branch reconciliation of the faulty run from branch_reconciliation.json"]
    expected = [[b["branch"], b["cobol_subtotal"], b["java_subtotal"], b["difference"], b["status"]]
                for b in recon["branches"]]
    assert rows[:len(expected)] == expected
    s, g = recon["suspense"], recon["grand_total"]
    assert rows[-2][:4] == ["Suspense", s["cobol"], s["java"], s["difference"]]
    assert rows[-1][:3] == ["Grand total", g["cobol"], g["java"]]

    matrix = tables["Detection Matrix from trap_catalog.json"]
    assert len(matrix) == len(catalog["traps"]) == 6
    for row, trap in zip(matrix, catalog["traps"]):
        assert row[0] == f"Case {trap['case_number']}: {trap['case_name']}"
        assert row[1] == trap["id"]
        if trap["status"] == "measured":
            assert row[3] == f"{trap['cases_detected']} of {trap['cases_generated']}"
            assert row[4] == trap["detection_rate"]
            assert last_word(row[5]) == trap["correct_verdict"]
            assert row[6:] == [trap["faulty_run_id"], trap["correct_run_id"]]
        else:
            assert row[3:5] == ["not measured", "not measured"]
    assert any(r[3] == "682 of 2000" for r in matrix)

    card = (runs / faulty_id / "card.txt").read_text()
    assert html.escape(card, quote=True) in page


@pytest.mark.slow
def test_certificate_shown_and_downloads_equal_the_run_files(built):
    base, out, page = built
    _, faulty_id, correct_id = t1_ids(base)
    shown = re.search(r'<pre id="certificate">(.*?)</pre>', page, re.S).group(1)
    original = (base / "runs" / correct_id / "certificate.json").read_bytes()
    assert json.loads(html.unescape(shown)) == json.loads(original)
    assert (out / f"certificate-{correct_id}.json").read_bytes() == original
    assert (out / f"certificate-{faulty_id}.json").read_bytes() == (base / "runs" / faulty_id / "certificate.json").read_bytes()
    cert = json.loads(original)
    cases = out / f"cases-{cert['cases_file_sha256'][:12]}.csv"
    assert cases.read_bytes() == (base / cert["cases_file"]).read_bytes()


@pytest.mark.slow
def test_replay_line_is_valid_with_the_expected_exit_codes(built):
    _, _, page = built
    blocks = re.findall(r"<pre>(Certificate: VALID.*?)</pre>", page, re.S)
    assert len(blocks) == 2
    assert "exit code: 0" in blocks[0] and "ALIVE: PASS" in blocks[0]
    assert "exit code: 1" in blocks[1] and "ZOMBIE: FAIL" in blocks[1]
    assert "Certificate: INVALID" not in page
    assert str(Path.home()) not in page


@pytest.mark.slow
def test_a_value_with_markup_in_a_run_file_is_escaped(real_base, tmp_path):
    """A copy of the base whose card text holds markup: symlinks to every real file, one edited file."""
    _, faulty_id, correct_id = t1_ids(real_base)
    base = tmp_path / "base"
    (base / "runs").mkdir(parents=True)
    (base / "runs" / "trap_catalog.json").symlink_to(real_base / "runs" / "trap_catalog.json")
    for run_id in (faulty_id, correct_id):
        (base / "runs" / run_id).mkdir()
        for f in (real_base / "runs" / run_id).iterdir():
            (base / "runs" / run_id / f.name).symlink_to(f)
    card_path = base / "runs" / faulty_id / "card.txt"
    card_path.unlink()
    injected = '<script>alert("x")</script> & <b>bold</b>'
    card_path.write_text((real_base / "runs" / faulty_id / "card.txt").read_text() + injected + "\n")

    page = build_page(base, tmp_path / "out")
    assert injected not in page
    assert "<script" not in page.lower()
    assert "<b>bold</b>" not in page
    assert html.escape(injected, quote=True) in page


def test_committed_page_is_static_and_complete():
    page = COMMITTED_PAGE.read_text(encoding="utf-8")
    assert "<script" not in page.lower()
    assert "<caption>Detection Matrix from trap_catalog.json</caption>" in page
    registry = json.loads((REPO / "samples" / "traps" / "cases.json").read_text())
    for trap_id in ("T1", "T2", "T3", "T4", "T5"):
        assert registry[trap_id]["name"] in page
    for tag in ("<header>", "<main>", "<footer>"):
        assert tag in page
    assert page.count("<table") == page.count("<caption>") >= 3
    levels = [int(m) for m in re.findall(r"<h([1-6])[ >]", page)]
    assert levels[0] == 1 and levels.count(1) == 1
    assert all(b - a <= 1 for a, b in zip(levels, levels[1:])), levels
    assert str(Path.home()) not in page
    assert set(re.findall(r"https?://[^\s\"'<>)]+", page)) == {LIVE_URL, REPO_URL}
    assert "Certificate: VALID" in page


def test_committed_downloads_are_the_files_the_page_links_to():
    page = COMMITTED_PAGE.read_text(encoding="utf-8")
    for href in re.findall(r'href="([^"]+)" download', page):
        assert (COMMITTED_PAGE.parent / href).is_file(), href
    certs = sorted(COMMITTED_PAGE.parent.glob("certificate-*.json"))
    assert len(certs) == 2
    for cert in certs:
        data = json.loads(cert.read_text())
        assert data["certificate_sha256"] and data["status"] in ("ALIVE", "ZOMBIE")
