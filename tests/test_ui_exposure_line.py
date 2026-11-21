"""Home page: the exposure line of the Run audit result and the seed sentence.

The slow test runs T1 faulty and T1 correct through the real API and the real engine worker in a
temporary base directory. Expected values are read from the verdict.json of those runs.
"""
import json
import re
import threading
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from coroner.ui.pages import exposure_line
from story_html import visible_text

REPO_ROOT = Path(__file__).resolve().parent.parent
INDEX_TEMPLATE = REPO_ROOT / "coroner" / "ui" / "templates" / "index.html"
SEED_SENTENCE = "Inputs are generated from the seed. The COBOL output is the reference."


# ------------------------------------------------------------------ (a) the pure helper


@pytest.mark.parametrize("verdict, expected", [
    ({"exposure_sum": "3995184.38", "affected_branches": 2}, "Exposure: 3995184.38 across 2 branches"),
    ({"exposure_sum": "10.50", "affected_branches": 1}, "Exposure: 10.50 across 1 branch"),
    ({"exposure_sum": "10.50", "affected_branches": 3}, "Exposure: 10.50 across 3 branches"),
    ({"exposure_sum": "3995184.38"}, None),
    ({"affected_branches": 2}, None),
    ({}, None),
    ({"status": "ALIVE", "cases_total": 2000}, None),
    ({"exposure_sum": "0.00", "affected_branches": 0}, None),
])
def test_exposure_line_from_a_verdict(verdict, expected):
    assert exposure_line(verdict) == expected


@pytest.mark.parametrize("text", ["3995184.38", "10.50", "0.10", "7", "1234567.80"])
def test_exposure_sum_is_kept_verbatim(text):
    line = exposure_line({"exposure_sum": text, "affected_branches": 2})
    assert line == f"Exposure: {text} across 2 branches"


@pytest.mark.parametrize("bad", [None, 2.0, "2", True])
def test_exposure_line_rejects_a_non_integer_branch_count(bad):
    assert exposure_line({"exposure_sum": "10.50", "affected_branches": bad}) is None


def test_exposure_line_rejects_a_sum_that_is_not_a_string():
    assert exposure_line({"exposure_sum": 10.5, "affected_branches": 2}) is None
    assert exposure_line({"exposure_sum": "", "affected_branches": 2}) is None


# ------------------------------------------------------------------ (c) the seed sentence


@pytest.fixture
def home_page(tmp_path, monkeypatch):
    monkeypatch.setenv("CORONER_BASE_DIR", str(tmp_path))
    monkeypatch.setenv("CORONER_EXCHANGE_DIR", str(tmp_path / "exchange"))
    from coroner.ui.app import app

    response = TestClient(app).get("/")
    assert response.status_code == 200
    return response.text


def test_home_page_has_the_seed_sentence_once_outside_any_script(home_page):
    outside_scripts = re.sub(r"<script\b.*?</script>", "", home_page, flags=re.DOTALL | re.IGNORECASE)
    assert outside_scripts.count(SEED_SENTENCE) == 1
    assert home_page.count(SEED_SENTENCE) == 1
    assert visible_text(home_page).count(SEED_SENTENCE) == 1


def test_seed_sentence_is_a_paragraph_between_the_form_and_the_result(home_page):
    match = re.search(r"<p\b[^>]*>\s*" + re.escape(SEED_SENTENCE) + r"\s*</p>", home_page)
    assert match is not None
    assert home_page.index("</form>") < match.start() < home_page.index('id="audit-result"')
    assert "color: var(--secondary-text)" in match.group(0)


# ------------------------------------------------------------------ (d) the template text


def _script_text(template: str) -> str:
    return "\n".join(re.findall(r"<script\b[^>]*>(.*?)</script>", template, flags=re.DOTALL | re.IGNORECASE))


def test_template_shows_exposure_line_with_text_content_only():
    template = INDEX_TEMPLATE.read_text()
    script = _script_text(template)
    assert "data.exposure_line" in script
    assert "line.textContent = exposureLine;" in script
    # the value never goes into innerHTML or a string concatenation
    for number, text in enumerate(script.splitlines(), start=1):
        if "exposureLine" in text or "exposure_line" in text:
            assert "innerHTML" not in text, f"script line {number}: {text.strip()}"
            assert "+" not in text.replace("++", ""), f"script line {number}: {text.strip()}"
    # nothing between the function head and its end touches innerHTML
    function = script[script.index("function showExposure"):]
    function = function[:function.index("\n}\n") + 3]
    assert "innerHTML" not in function


def test_template_does_no_arithmetic_or_formatting_on_exposure():
    template = INDEX_TEMPLATE.read_text()
    exposure_lines = [text for text in template.splitlines() if "xposure" in text]
    assert exposure_lines, "the template no longer mentions the exposure line"
    forbidden = re.compile(
        r"parseFloat|parseInt|Number\(|toFixed|toLocale|Math\.|Intl\.|\.replace\(|\.split\(|\.slice\(|\.substring\(|"
        r"\bexposure\w*\s*[-*/%]|[-*/%]\s*\w*xposure|\|\s*(round|float|int|format)"
    )
    for text in exposure_lines:
        # arithmetic is looked for in code, not in string literals or comments
        code = re.sub(r"'[^']*'|\"[^\"]*\"", "''", text)
        code = re.sub(r"//.*", "", code)
        assert not forbidden.search(code), text.strip()
    # no Jinja expression of the page reads an exposure value
    assert not re.search(r"\{\{[^}]*xposure", template)
    assert not re.search(r"\{%[^%]*xposure", template)


def test_template_keeps_the_exposure_line_out_of_the_branch_noun_logic():
    """The singular or plural of branch is decided on the server, never in the page."""
    template = INDEX_TEMPLATE.read_text()
    assert "branches" not in _script_text(template)


# ------------------------------------------------------------------ (b) the measured runs


def _run_audit(client, sample, port, seed, cases):
    """POST the audit, run the real worker on the job, poll the status until done."""
    from coroner.engine_worker import execute_job, find_oldest_queued_job
    from coroner.ui.app import reset_rate_limiter

    reset_rate_limiter()
    response = client.post("/api/run", json={"sample": sample, "port": port, "seed": seed, "cases": cases})
    assert response.status_code == 202, response.text
    job_id = response.json()["job_id"]

    failure = []

    def work():
        try:
            deadline = time.monotonic() + 30
            while time.monotonic() < deadline:
                job_dir = find_oldest_queued_job()
                if job_dir:
                    execute_job(job_dir)
                    return
                time.sleep(0.1)
            failure.append(RuntimeError("worker never saw the job"))
        except Exception as error:  # reported by the test below
            failure.append(error)

    worker = threading.Thread(target=work, daemon=True)
    worker.start()

    data = None
    for _ in range(300):
        data = client.get(f"/api/job/{job_id}/status").json()
        if data["status"] in ("done", "error"):
            break
        time.sleep(1)
    worker.join(timeout=10)
    assert not failure, failure[0]
    assert data is not None and data["status"] == "done", data
    return data


def _expected_line(verdict):
    """The rule of the task, written out again from the values read in the run's verdict.json."""
    if "exposure_sum" in verdict and "affected_branches" in verdict and verdict["affected_branches"] > 0:
        noun = "branch" if verdict["affected_branches"] == 1 else "branches"
        return "Exposure: " + verdict["exposure_sum"] + " across " + str(verdict["affected_branches"]) + " " + noun
    return None


@pytest.mark.slow
def test_run_audit_status_carries_the_measured_exposure_line(tmp_path, monkeypatch, capsys):
    base = tmp_path / "base"
    base.mkdir()
    exchange = tmp_path / "exchange"
    exchange.mkdir()
    monkeypatch.setenv("CORONER_BASE_DIR", str(base))
    monkeypatch.setenv("CORONER_EXCHANGE_DIR", str(exchange))
    monkeypatch.setenv("CORONER_JOB_TIMEOUT", "180")

    repo_runs = REPO_ROOT / "runs"
    before = sorted(path.name for path in repo_runs.iterdir()) if repo_runs.exists() else None

    from coroner.ui.app import app

    client = TestClient(app)

    faulty = _run_audit(client, "T1", "faulty", seed=42, cases=2000)
    faulty_verdict = json.loads((base / "runs" / faulty["run_id"] / "verdict.json").read_text())
    assert faulty["verdict"] == "ZOMBIE" == faulty_verdict["status"]
    assert faulty_verdict["affected_branches"] > 1
    assert faulty["exposure_line"] == (
        "Exposure: " + faulty_verdict["exposure_sum"] + " across " + str(faulty_verdict["affected_branches"]) + " branches"
    )
    assert faulty["exposure_line"] == _expected_line(faulty_verdict)
    assert faulty["cases_divergent"] == faulty_verdict["cases_divergent"]
    assert faulty["cases_total"] == faulty_verdict["cases_total"] == 2000

    correct = _run_audit(client, "T1", "correct", seed=42, cases=2000)
    correct_verdict = json.loads((base / "runs" / correct["run_id"] / "verdict.json").read_text())
    assert correct["verdict"] == "ALIVE" == correct_verdict["status"]
    assert "exposure_line" in correct
    assert correct["exposure_line"] == _expected_line(correct_verdict)

    after = sorted(path.name for path in repo_runs.iterdir()) if repo_runs.exists() else None
    assert after == before, "the repository runs/ folder was touched"

    with capsys.disabled():
        print(f"\nMEASURED T1 faulty exposure_line: {faulty['exposure_line']!r} (run {faulty['run_id']})")
        print(f"MEASURED T1 correct exposure_line: {correct['exposure_line']!r} (run {correct['run_id']})")
