"""The money figure of a ZOMBIE run without a branch exposure (Cases 2 to 5, credit-fees), kept in a
derived file.

runs/<run_id>/amount_difference.json holds the sum and the largest of |COBOL - Java| over the divergent
decimal output values and how many amounts differ, in exact Decimal arithmetic. The engine writes it for a
new run; `python -m coroner derive --from-runs` writes it for an existing run from the run's own files and
changes no existing file of the run. verdict.json no longer carries the figure. The UI reads it through
one helper (coroner.derive.read_amount_difference).

The real-run tests use the faulty port of T2 to T5 at 200 cases, seed 42, each audited by the real engine
into a temporary base directory (fixture trap_faulty_200). The expected figures are recomputed here from
the run's own comparison_results.json. The repository runs/ folder is never read or written.
"""
import hashlib
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import threading
import time
from decimal import Decimal
from html.parser import HTMLParser
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from coroner.compare import CaseResult, ComparisonResult
from coroner.derive import AMOUNT_FILE, read_amount_difference, write_amount_difference
from coroner.parse.schema import load_schema
from coroner.store import store_verdict
from coroner.ui.pages import amount_view, run_result_summary
from coroner.verdict import Verdict, amount_difference, verdict_from_dict

REPO_ROOT = Path(__file__).resolve().parent.parent
INDEX_TEMPLATE = REPO_ROOT / "coroner" / "ui" / "templates" / "index.html"
TRAP_FOLDERS = {"T2": "T2-rounding", "T3": "T3-comp3-sign", "T4": "T4-zoned-overpunch", "T5": "T5-redefines-invalid"}
OLD_AMOUNT_KEYS = {"amount_difference_sum", "amount_difference_max", "amount_difference_count"}
PLAIN_VERDICT_KEYS = {"status", "sub_label", "cases_total", "cases_divergent", "run_return_codes", "validation_notice"}
DERIVED_KEYS = {"format", "source", "schema_sha256", "sum_of_absolute_differences", "largest_difference",
                "amounts_affected"}
# T2 output: CASE-ID string, FEE1 and FEE2 decimal
SCHEMA = load_schema(str(REPO_ROOT / "samples" / "traps" / TRAP_FOLDERS["T2"] / "schema.json"))


def _mismatch(field_name, cobol_value, java_value):
    return {"field_name": field_name, "kind": "value_mismatch", "cobol_value": cobol_value, "java_value": java_value}


def _comparison(*divergent_fields, exposure_sum=None):
    cases = [CaseResult(case_id=f"C{i}", divergent=True, divergent_fields=[field])
             for i, field in enumerate(divergent_fields)]
    return ComparisonResult(cases=cases, run_return_codes=(0, 0), row_count_match=True,
                            total_divergent=len(cases), exposure_sum=exposure_sum)


def _decimal_columns(trap: str) -> set:
    schema = load_schema(str(REPO_ROOT / "samples" / "traps" / TRAP_FOLDERS[trap] / "schema.json"))
    return {column.name for column in schema.output_columns if column.type == "decimal"}


def _divergent_fields(run_dir: Path) -> list:
    comparison = json.loads((run_dir / "comparison_results.json").read_text())
    return [field for case in comparison["cases"] for field in case["divergent_fields"]]


def _recomputed(run_dir: Path, decimal_columns: set):
    """(sum, largest, count) from the run's comparison_results.json, by a loop separate from the engine's."""
    differences = [
        abs(Decimal(field["cobol_value"].strip()) - Decimal(field["java_value"].strip()))
        for field in _divergent_fields(run_dir) if field["field_name"] in decimal_columns
    ]
    return sum(differences, Decimal(0)), max(differences), len(differences)


def _tree(run_dir: Path) -> dict:
    """Every file of a run folder: relative path -> (SHA-256, size, mtime)."""
    state = {}
    for path in sorted(run_dir.rglob("*")):
        if path.is_file():
            stat = path.stat()
            state[path.relative_to(run_dir).as_posix()] = (
                hashlib.sha256(path.read_bytes()).hexdigest(), stat.st_size, stat.st_mtime_ns)
    return state


def _derived(run_dir: Path) -> dict:
    return json.loads((run_dir / AMOUNT_FILE).read_text())


def _business_lines(run_dir: Path) -> list:
    """The two business lines, written out again from the raw derived file."""
    data = _derived(run_dir)
    assert data["amounts_affected"] > 1
    return [f"{data['amounts_affected']} amounts affected", f"Largest single difference: {data['largest_difference']}"]


def _derive_cli(base: Path) -> subprocess.CompletedProcess:
    """The real CLI: python -m coroner derive --from-runs, with CORONER_BASE_DIR set."""
    env = {**os.environ, "CORONER_BASE_DIR": str(base)}
    return subprocess.run([sys.executable, "-m", "coroner", "derive", "--from-runs"],
                          cwd=REPO_ROOT, env=env, capture_output=True, text=True, timeout=300)


class _Texts(HTMLParser):
    """The text chunks (one per line of the page) inside the element with a given id."""

    def __init__(self, element_id):
        super().__init__(convert_charrefs=True)
        self.element_id, self.chunks, self.found = element_id, [], False
        self._depth = 0

    def handle_starttag(self, tag, attrs):
        if self._depth == 0 and dict(attrs).get("id") == self.element_id:
            self._depth, self.found = 1, True
        elif self._depth:
            self._depth += 1

    def handle_endtag(self, tag):
        if self._depth:
            self._depth -= 1

    def handle_data(self, data):
        if self._depth and data.strip():
            self.chunks.append(data.strip())


def _lines_of(html: str, element_id: str):
    """The lines inside the element with this id, or None when the page has no such element."""
    reader = _Texts(element_id)
    reader.feed(html)
    return reader.chunks if reader.found else None


# ------------------------------------------------------------------ the rules of the figure


def test_figure_is_exact_decimal_arithmetic_over_the_divergent_amounts():
    comparison = _comparison(
        _mismatch("FEE1", "-0000060.02", "-0000060.03"),
        _mismatch("FEE2", "+0000012.35", "+0000012.34"),
        _mismatch("FEE1", "+0000000.10", "+0000000.30"),
    )
    assert amount_difference(comparison, SCHEMA) == (Decimal("0.22"), Decimal("0.20"), 3)


def test_extra_decimals_are_counted_exactly_not_rounded():
    figure = amount_difference(_comparison(_mismatch("FEE1", "+0000012.35", "+0000012.355")), SCHEMA)
    assert figure == (Decimal("0.005"), Decimal("0.005"), 1)


def test_a_string_column_divergence_is_not_an_amount():
    comparison = _comparison(_mismatch("CASE-ID", "A", "B"), _mismatch("FEE1", "+0000000.01", "+0000000.02"))
    assert amount_difference(comparison, SCHEMA) == (Decimal("0.01"), Decimal("0.01"), 1)
    assert amount_difference(_comparison(_mismatch("CASE-ID", "A", "B")), SCHEMA) is None


MISSING_ROW = {"field_name": "<row>", "kind": "missing_in_java", "cobol_value": "present", "java_value": "missing"}


@pytest.mark.parametrize("fields", [
    [MISSING_ROW],
    [_mismatch("FEE1", "+0000000.01", "+0000000.02"), MISSING_ROW],
    [_mismatch("FEE1", "+0000000.01", "not a number")],
    [_mismatch("FEE1", "missing", "+0000000.01")],
    [_mismatch("FEE1", "NaN", "+0000000.01")],
    [_mismatch("FEE1", "+0000000.01", "Infinity")],
    [_mismatch("FEE1", "-0000000.00", "+0000000.00")],  # divergent as text, zero as an amount
])
def test_no_figure_when_it_would_be_partial_or_zero(fields):
    comparison = ComparisonResult(
        cases=[CaseResult(case_id="C0", divergent=True, divergent_fields=fields)],
        run_return_codes=(0, 0), row_count_match=True, total_divergent=1)
    assert amount_difference(comparison, SCHEMA) is None


def test_no_figure_for_a_run_with_a_branch_exposure_or_without_divergence():
    with_exposure = _comparison(_mismatch("FEE1", "+0000000.01", "+0000000.02"), exposure_sum=Decimal("5.00"))
    assert amount_difference(with_exposure, SCHEMA) is None
    alive = ComparisonResult(cases=[CaseResult("C0", False, [])], run_return_codes=(0, 0),
                             row_count_match=True, total_divergent=0)
    assert amount_difference(alive, SCHEMA) is None


# ------------------------------------------------------------------ the derived file and the one reader


def test_verdict_no_longer_carries_the_figure(tmp_path):
    base = dict(status="ZOMBIE", sub_label="FAIL: business behavior diverged on 3 cases", cases_total=10,
                cases_divergent=3, run_return_codes=(0, 0))
    assert not any(hasattr(Verdict(**base), key) for key in OLD_AMOUNT_KEYS)
    store_verdict(str(tmp_path), Verdict(**base))
    written = json.loads((tmp_path / "verdict.json").read_text())
    assert set(written) == PLAIN_VERDICT_KEYS
    assert verdict_from_dict(written) == Verdict(**base)


def test_the_derived_file_has_one_fixed_format_and_the_reader_returns_it(tmp_path):
    path = write_amount_difference(tmp_path, (Decimal("0.90"), Decimal("0.01"), 90), "ab" * 32)
    assert path == tmp_path / AMOUNT_FILE
    assert json.loads(path.read_text()) == {
        "format": 1,
        "source": "comparison_results.json",
        "schema_sha256": "ab" * 32,
        "sum_of_absolute_differences": "0.90",
        "largest_difference": "0.01",
        "amounts_affected": 90,
    }
    assert read_amount_difference(tmp_path) == json.loads(path.read_text())
    # exact text, no exponent
    path = write_amount_difference(tmp_path, (Decimal("546373400.00"), Decimal("1E+2"), 44), "ab" * 32)
    assert json.loads(path.read_text())["sum_of_absolute_differences"] == "546373400.00"
    assert json.loads(path.read_text())["largest_difference"] == "100"
    assert [p.name for p in tmp_path.iterdir()] == [AMOUNT_FILE]  # no temporary file left


GOOD = {"sum_of_absolute_differences": "0.90", "largest_difference": "0.01", "amounts_affected": 90}


@pytest.mark.parametrize("content", [
    "{not json",
    "[]",
    json.dumps({**GOOD, "sum_of_absolute_differences": 0.9}),
    json.dumps({**GOOD, "sum_of_absolute_differences": "abc"}),
    json.dumps({**GOOD, "sum_of_absolute_differences": "NaN"}),
    json.dumps({**GOOD, "largest_difference": None}),
    json.dumps({**GOOD, "amounts_affected": 0}),
    json.dumps({**GOOD, "amounts_affected": True}),
    json.dumps({**GOOD, "amounts_affected": "90"}),
    json.dumps({k: v for k, v in GOOD.items() if k != "amounts_affected"}),
])
def test_the_reader_returns_nothing_for_a_file_that_is_not_a_figure(tmp_path, content):
    (tmp_path / AMOUNT_FILE).write_text(content)
    assert read_amount_difference(tmp_path) is None


def test_the_reader_returns_nothing_without_the_file(tmp_path):
    assert read_amount_difference(tmp_path) is None
    assert amount_view(tmp_path) is None


@pytest.mark.parametrize("count, first", [(90, "90 amounts affected"), (1, "1 amount affected")])
def test_amount_view_texts(tmp_path, count, first):
    write_amount_difference(tmp_path, (Decimal("0.90"), Decimal("0.01"), count), "ab" * 32)
    inputs = {"random_seed": 42, "seed": 42, "case_count": 200}
    view = amount_view(tmp_path, inputs)
    assert view["business"] == [first, "Largest single difference: 0.01"]
    assert view["engineer"] == view["business"] + ["Sum of absolute differences: 0.90 (seed 42, 200 cases)"]
    # nothing is a currency label
    assert not re.search(r"[$\u20ac\u00a3]|USD|EUR|GBP", " ".join(view["engineer"]))


def test_amount_view_says_not_recorded_when_inputs_lack_the_seed_or_the_case_count(tmp_path):
    write_amount_difference(tmp_path, (Decimal("0.90"), Decimal("0.01"), 90), "ab" * 32)
    assert amount_view(tmp_path)["engineer"][-1] == (
        "Sum of absolute differences: 0.90 (seed not recorded, not recorded cases)")


def test_the_box_script_shows_the_exposure_line_and_the_two_amount_lines_with_text_content():
    script = "\n".join(re.findall(r"<script\b[^>]*>(.*?)</script>", INDEX_TEMPLATE.read_text(),
                                  flags=re.DOTALL | re.IGNORECASE))
    assert "showExposure(resultDiv, data.exposure_line);" in script
    assert "showAmountLines(resultDiv, data.amount_lines);" in script
    function = script[script.index("function showAmountLines"):]
    function = function[:function.index("\n}\n") + 3]
    assert "line.textContent = text;" in function
    assert "innerHTML" not in function
    # the page only shows what the server sent: no arithmetic and no formatting on the amounts
    code = re.sub(r"//.*", "", function)
    assert not re.search(r"parseFloat|parseInt|Number\(|toFixed|toLocale|Math\.|Intl\.|\.replace\(|\+", code)


# ------------------------------------------------------------------ real runs of T2 to T5


def test_a_new_run_writes_the_figure_recomputed_from_its_comparison_file(trap_faulty_200):
    trap, run = trap_faulty_200
    expected_sum, expected_max, expected_count = _recomputed(run.run_dir, _decimal_columns(trap))
    derived = _derived(run.run_dir)
    inputs = json.loads((run.run_dir / "inputs.json").read_text())

    assert set(derived) == DERIVED_KEYS
    assert derived["format"] == 1 and derived["source"] == "comparison_results.json"
    assert derived["schema_sha256"] == inputs["schema_sha256"]
    assert Decimal(derived["sum_of_absolute_differences"]) == expected_sum > 0
    assert Decimal(derived["largest_difference"]) == expected_max
    assert derived["amounts_affected"] == expected_count > 0
    # exact text: no exponent, no rounding
    assert derived["sum_of_absolute_differences"] == format(expected_sum, "f")
    assert read_amount_difference(run.run_dir) == derived


def test_verdict_json_of_a_new_run_holds_no_figure_and_no_exposure(trap_faulty_200):
    trap, run = trap_faulty_200
    verdict = json.loads((run.run_dir / "verdict.json").read_text())
    assert set(verdict) == PLAIN_VERDICT_KEYS
    assert verdict["status"] == "ZOMBIE" and verdict["cases_total"] == 200 and verdict["cases_divergent"] > 0


def test_the_figure_means_what_each_trap_does(trap_faulty_200):
    trap, run = trap_faulty_200
    derived = _derived(run.run_dir)
    total, largest = Decimal(derived["sum_of_absolute_differences"]), Decimal(derived["largest_difference"])
    fields = _divergent_fields(run.run_dir)
    if trap == "T2":  # a rounding difference of exactly one cent per divergent fee
        assert largest == Decimal("0.01") and total == Decimal("0.01") * derived["amounts_affected"]
    elif trap in ("T3", "T4"):  # same magnitude, opposite sign: the difference is twice the COBOL value
        assert all(abs(Decimal(f["cobol_value"])) == abs(Decimal(f["java_value"])) for f in fields)
        assert total == 2 * sum(abs(Decimal(f["cobol_value"])) for f in fields)
    else:  # T5: Java writes the fee alone where COBOL adds it to the amount
        assert all(Decimal(f["java_value"]) == Decimal("1.00") for f in fields)
        assert total == sum(abs(Decimal(f["cobol_value"]) - Decimal("1.00")) for f in fields)


def test_summary_lines_are_built_from_the_derived_file(trap_faulty_200):
    trap, run = trap_faulty_200
    summary = run_result_summary(run.run_dir)
    assert summary["amount_lines"] == _business_lines(run.run_dir)
    assert summary["exposure_line"] is None
    assert "amount_line" not in summary


# ------------------------------------------------------------------ derivation on a run made before


def test_derivation_adds_one_file_and_changes_nothing_else(trap_faulty_200, tmp_path, copy_runs):
    """A real run whose derived file is absent: derive writes it, every other file keeps its bytes."""
    trap, run = trap_faulty_200
    base = tmp_path / "base"
    copy_runs(run.base, base, run.run_id)
    run_dir = base / "runs" / run.run_id
    engine_file = (run_dir / AMOUNT_FILE).read_bytes()
    (run_dir / AMOUNT_FILE).unlink()
    certificate_before = json.loads((run_dir / "certificate.json").read_text())
    before = _tree(run_dir)
    assert AMOUNT_FILE not in before

    first = _derive_cli(base)
    assert first.returncode == 0, first.stdout + first.stderr
    assert f"Wrote runs/{run.run_id}/{AMOUNT_FILE}" in first.stdout
    assert "written 1, already present 0, not applicable 0, no figure 0, errors 0" in first.stdout

    after = _tree(run_dir)
    assert set(after) - set(before) == {AMOUNT_FILE}
    assert {name: after[name] for name in before} == before  # hash, size and mtime of every pre-existing file
    # computed from the run's own files, equal to what the engine writes for a new run
    assert (run_dir / AMOUNT_FILE).read_bytes() == engine_file
    expected = _recomputed(run_dir, _decimal_columns(trap))
    derived = _derived(run_dir)
    assert (Decimal(derived["sum_of_absolute_differences"]), Decimal(derived["largest_difference"]),
            derived["amounts_affected"]) == expected
    # the run id and the certificate are the ones the run had
    assert [p.name for p in (base / "runs").iterdir()] == [run.run_id]
    assert json.loads((run_dir / "certificate.json").read_text()) == certificate_before
    assert not [p for p in run_dir.iterdir() if p.name.startswith(".")]  # no temporary file left

    # a second run changes nothing: the file is skipped, no file is written again
    state = _tree(run_dir)
    second = _derive_cli(base)
    assert second.returncode == 0, second.stdout + second.stderr
    assert "Wrote runs/" not in second.stdout
    assert "written 0, already present 1" in second.stdout
    assert _tree(run_dir) == state


@pytest.mark.slow
def test_the_certificate_of_a_derived_run_replays_valid(trap_faulty_200, tmp_path, copy_runs):
    from coroner.certificate import replay_certificate

    trap, run = trap_faulty_200
    base = tmp_path / "base"
    copy_runs(run.base, base, run.run_id)
    (base / "runs" / run.run_id / AMOUNT_FILE).unlink()
    assert _derive_cli(base).returncode == 0
    assert (base / "runs" / run.run_id / AMOUNT_FILE).is_file()

    result = replay_certificate(str(base / "runs" / run.run_id / "certificate.json"), base_dir=str(base))
    assert result.valid, result.reason
    assert result.cases_divergent == json.loads((run.run_dir / "verdict.json").read_text())["cases_divergent"]
    assert not any("comparison engine differs" in warning for warning in result.warnings)


def test_the_certificate_of_the_new_run_replays_valid_with_the_file_present(trap_faulty_200):
    """The derived file is not an input of the certificate: no certificate field mentions it."""
    trap, run = trap_faulty_200
    certificate_text = (run.run_dir / "certificate.json").read_text()
    assert "amount_difference" not in certificate_text and AMOUNT_FILE not in certificate_text


def test_derivation_leaves_runs_that_have_no_figure_alone(t1_faulty_30, t1_correct_200, credit_fees_alive_30,
                                                          tmp_path, copy_runs):
    base = tmp_path / "base"
    copy_runs(t1_faulty_30.base, base, t1_faulty_30.run_id)  # Case 1: a branch exposure
    copy_runs(credit_fees_alive_30.base, base, credit_fees_alive_30.run_id)  # ALIVE
    copy_runs(t1_correct_200.base, base, t1_correct_200.run_id)  # ALIVE
    before = {p.name: _tree(p) for p in (base / "runs").iterdir()}

    result = _derive_cli(base)

    assert result.returncode == 0, result.stdout + result.stderr
    assert "written 0, already present 0, not applicable 3, no figure 0, errors 0" in result.stdout
    assert {p.name: _tree(p) for p in (base / "runs").iterdir()} == before
    assert not list((base / "runs").glob(f"*/{AMOUNT_FILE}"))


def test_derivation_refuses_when_the_schema_is_not_the_one_the_run_recorded(trap_faulty_200, tmp_path, copy_runs):
    trap, run = trap_faulty_200
    base = tmp_path / "base"
    copy_runs(run.base, base, run.run_id)
    run_dir = base / "runs" / run.run_id
    (run_dir / AMOUNT_FILE).unlink()
    inputs = json.loads((run_dir / "inputs.json").read_text())
    inputs["schema_sha256"] = "0" * 64  # test set-up: the recorded schema hash no longer matches the file
    (run_dir / "inputs.json").write_text(json.dumps(inputs))
    before = _tree(run_dir)

    result = _derive_cli(base)

    assert result.returncode == 2
    assert f"ERROR: run {run.run_id}" in result.stderr and "SHA-256 differs" in result.stderr
    assert "errors 1" in result.stdout
    assert _tree(run_dir) == before


def test_derive_help_describes_the_command():
    result = subprocess.run([sys.executable, "-m", "coroner", "derive", "--help"], cwd=REPO_ROOT,
                            capture_output=True, text=True, timeout=60)
    assert result.returncode == 0
    assert "--from-runs" in result.stdout and "amount_difference.json" in result.stdout
    assert "No existing file of a run is changed" in " ".join(result.stdout.split())


# ------------------------------------------------------------------ home page data


def _app_client(base: Path, exchange: Path, monkeypatch) -> TestClient:
    monkeypatch.setenv("CORONER_BASE_DIR", str(base))
    monkeypatch.setenv("CORONER_EXCHANGE_DIR", str(exchange))
    from coroner.ui.app import app

    return TestClient(app)


def test_home_cache_hit_carries_the_two_lines_and_a_run_without_the_file_carries_none(
        trap_faulty_200, tmp_path, copy_runs, monkeypatch):
    trap, run = trap_faulty_200
    base, exchange = tmp_path / "base", tmp_path / "exchange"
    exchange.mkdir()
    copy_runs(run.base, base, run.run_id)
    older = "abcdef012345"  # a run made before the figure existed: same files, no derived file
    shutil.copytree(base / "runs" / run.run_id, base / "runs" / older)
    (base / "runs" / older / AMOUNT_FILE).unlink()
    before = _tree(base / "runs" / older)

    client = _app_client(base, exchange, monkeypatch)
    from coroner.ui.app import update_run_index

    update_run_index(trap, "faulty", 42, 200, run.run_id)
    update_run_index(trap, "faulty", 43, 200, older)
    new = client.post("/api/run", json={"sample": trap, "port": "faulty", "seed": 42, "cases": 200}).json()
    old = client.post("/api/run", json={"sample": trap, "port": "faulty", "seed": 43, "cases": 200}).json()

    assert new["amount_lines"] == _business_lines(base / "runs" / run.run_id)
    assert new["exposure_line"] is None and "amount_line" not in new
    assert new["verdict"] == old["verdict"] == "ZOMBIE"
    assert old["amount_lines"] is None and old["exposure_line"] is None
    assert _tree(base / "runs" / older) == before  # reading never writes


def test_done_job_status_carries_the_two_lines(trap_faulty_200, tmp_path, copy_runs, monkeypatch):
    """The status endpoint of a finished job reads the run through the same helper as the cache hit."""
    trap, run = trap_faulty_200
    base, exchange = tmp_path / "base", tmp_path / "exchange"
    copy_runs(run.base, base, run.run_id)
    job_id = "0123456789ab"
    job_dir = exchange / "jobs" / job_id
    job_dir.mkdir(parents=True)
    (job_dir / "status.json").write_text(json.dumps({"status": "done", "run_id": run.run_id}))

    data = _app_client(base, exchange, monkeypatch).get(f"/api/job/{job_id}/status").json()

    assert data["status"] == "done" and data["run_id"] == run.run_id and data["verdict"] == "ZOMBIE"
    assert data["amount_lines"] == _business_lines(base / "runs" / run.run_id)
    assert data["exposure_line"] is None


@pytest.mark.slow
def test_real_worker_job_for_case_3_carries_the_lines_and_the_derived_file(tmp_path, monkeypatch, capsys):
    """T3 faulty, seed 42, 200 cases through the real API and the real engine worker."""
    from coroner.engine_worker import execute_job, find_oldest_queued_job
    from coroner.ui.app import reset_rate_limiter

    base, exchange = tmp_path / "base", tmp_path / "exchange"
    base.mkdir()
    exchange.mkdir()
    monkeypatch.setenv("CORONER_JOB_TIMEOUT", "180")
    client = _app_client(base, exchange, monkeypatch)

    reset_rate_limiter()
    response = client.post("/api/run", json={"sample": "T3", "port": "faulty", "seed": 42, "cases": 200})
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
        except Exception as error:
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

    run_dir = base / "runs" / data["run_id"]
    assert data["run_id"] == "38ae1c058b27"  # the run id measured before the change
    assert (run_dir / AMOUNT_FILE).is_file()  # copied from the engine's job folder with the run
    assert set(json.loads((run_dir / "verdict.json").read_text())) == PLAIN_VERDICT_KEYS
    assert data["amount_lines"] == _business_lines(run_dir)
    again = client.post("/api/run", json={"sample": "T3", "port": "faulty", "seed": 42, "cases": 200})
    assert again.status_code == 200 and again.json()["amount_lines"] == data["amount_lines"]
    with capsys.disabled():
        print(f"\nMEASURED T3 faulty seed 42, 200 cases, done job amount_lines: {data['amount_lines']!r}")


# ------------------------------------------------------------------ the run page, Business and Engineer


@pytest.fixture
def run_page(trap_faulty_200, tmp_path, copy_runs, monkeypatch):
    trap, run = trap_faulty_200
    base = tmp_path / "base"
    copy_runs(run.base, base, run.run_id)
    client = _app_client(base, tmp_path / "exchange", monkeypatch)
    response = client.get(f"/run/{run.run_id}")
    assert response.status_code == 200
    return trap, run, response.text, base


def test_run_page_business_view_shows_the_two_lines_in_the_verdict_section(run_page):
    trap, run, html, base = run_page
    lines = _lines_of(html, "amount-difference")
    assert lines == _business_lines(run.run_dir)
    # the lines sit in the first screen (the story section), before the closed technical details
    assert html.index('id="story"') < html.index('id="amount-difference"') < html.index('id="technical"')
    assert not re.search(r"[$\u20ac\u00a3]|USD|EUR|GBP", " ".join(lines))


def test_run_page_engineer_view_adds_the_sum_with_the_seed_and_the_case_count(run_page):
    trap, run, html, base = run_page
    derived = _derived(run.run_dir)
    inputs = json.loads((run.run_dir / "inputs.json").read_text())
    lines = _lines_of(html, "amount-difference-engineer")
    assert lines[:2] == _business_lines(run.run_dir)
    assert lines[2] == (f"Sum of absolute differences: {derived['sum_of_absolute_differences']} "
                        f"(seed {inputs['random_seed']}, {inputs['case_count']} cases)")
    assert len(lines) == 3 and inputs["random_seed"] == 42 and inputs["case_count"] == 200
    assert html.index('id="technical"') < html.index('id="amount-difference-engineer"')
    assert "amount_difference.json, derived from comparison_results.json" in html


def test_run_page_without_the_derived_file_shows_no_amount_lines(trap_faulty_200, tmp_path, copy_runs, monkeypatch):
    trap, run = trap_faulty_200
    base = tmp_path / "base"
    copy_runs(run.base, base, run.run_id)
    (base / "runs" / run.run_id / AMOUNT_FILE).unlink()
    html = _app_client(base, tmp_path / "exchange", monkeypatch).get(f"/run/{run.run_id}").text
    assert _lines_of(html, "amount-difference") is None
    assert _lines_of(html, "amount-difference-engineer") is None
    assert "Largest single difference" not in html and "Sum of absolute differences" not in html


def test_case_1_run_page_shows_only_its_exposure_and_alive_shows_no_amount_lines(
        t1_faulty_30, t1_correct_200, tmp_path, copy_runs, monkeypatch):
    base = tmp_path / "base"
    copy_runs(t1_faulty_30.base, base, t1_faulty_30.run_id)
    copy_runs(t1_correct_200.base, base, t1_correct_200.run_id)
    client = _app_client(base, tmp_path / "exchange", monkeypatch)

    faulty = client.get(f"/run/{t1_faulty_30.run_id}").text
    assert "Branches affected" in faulty and "Exposure" in faulty
    for html in (faulty, client.get(f"/run/{t1_correct_200.run_id}").text):
        assert _lines_of(html, "amount-difference") is None
        assert _lines_of(html, "amount-difference-engineer") is None
        assert "Largest single difference" not in html and "amounts affected" not in html
    assert not (t1_faulty_30.run_dir / AMOUNT_FILE).exists()
    assert not (t1_correct_200.run_dir / AMOUNT_FILE).exists()


def test_case_1_summary_has_the_exposure_line_and_no_amount_lines(t1_faulty_30, credit_fees_alive_30):
    summary = run_result_summary(t1_faulty_30.run_dir)
    assert summary["exposure_line"].startswith("Exposure: ") and summary["amount_lines"] is None
    alive = run_result_summary(credit_fees_alive_30.run_dir)
    assert alive["verdict"] == "ALIVE" and alive["amount_lines"] is None and alive["exposure_line"] is None


def test_credit_fees_half_even_run_gets_the_figure_and_the_alive_run_does_not(
        credit_fees_half_even_30, credit_fees_alive_30):
    columns = {c.name for c in load_schema(str(REPO_ROOT / "samples" / "credit-fees" / "schema.json")).output_columns
               if c.type == "decimal"}
    total, largest, count = _recomputed(credit_fees_half_even_30.run_dir, columns)
    derived = _derived(credit_fees_half_even_30.run_dir)
    assert (Decimal(derived["sum_of_absolute_differences"]), Decimal(derived["largest_difference"]),
            derived["amounts_affected"]) == (total, largest, count)
    assert set(json.loads((credit_fees_half_even_30.run_dir / "verdict.json").read_text())) == PLAIN_VERDICT_KEYS
    assert not (credit_fees_alive_30.run_dir / AMOUNT_FILE).exists()


# ------------------------------------------------------------------ MCP


def test_mcp_get_verdict_returns_the_verdict_file_without_the_figure(trap_faulty_200, tmp_path, copy_runs):
    """get_verdict (real stdio server) returns verdict.json as it is: the figure is in amount_difference.json."""
    import asyncio

    from test_mcp_server import run_mcp_session

    trap, run = trap_faulty_200
    base = tmp_path / "base"
    copy_runs(run.base, base, run.run_id)

    async def check(session):
        result = await session.call_tool("get_verdict", arguments={"run_id": run.run_id})
        assert result.is_error is False
        return json.loads(result.content[0].text)

    verdict = asyncio.run(run_mcp_session(check, base_dir=base))
    assert set(verdict) == PLAIN_VERDICT_KEYS
    assert OLD_AMOUNT_KEYS.isdisjoint(verdict)


# ------------------------------------------------------------------ the browser


@pytest.fixture
def home_server(trap_faulty_200, tmp_path, copy_runs):
    from coroner.ui.app import update_run_index

    trap, run = trap_faulty_200
    base, exchange = tmp_path / "base", tmp_path / "exchange"
    exchange.mkdir()
    copy_runs(run.base, base, run.run_id)
    os.environ["CORONER_BASE_DIR"] = str(base)  # restored after the test by the autouse fixture
    update_run_index(trap, "faulty", 42, 200, run.run_id)
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    process = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "coroner.ui.app:app", "--host", "127.0.0.1", "--port", str(port),
         "--log-level", "warning"],
        env={**os.environ, "CORONER_BASE_DIR": str(base), "CORONER_EXCHANGE_DIR": str(exchange)},
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    try:
        for _ in range(100):
            with socket.socket() as probe:
                probe.settimeout(0.2)
                if probe.connect_ex(("127.0.0.1", port)) == 0:
                    break
            time.sleep(0.1)
        else:
            raise RuntimeError("UI server did not start")
        yield trap, run, f"http://127.0.0.1:{port}"
    finally:
        process.terminate()
        process.wait(timeout=10)


@pytest.mark.slow
def test_browser_shows_the_two_lines_in_the_home_box_and_on_the_run_page(home_server, capsys):
    from playwright.sync_api import sync_playwright

    trap, run, url = home_server
    expected = _business_lines(run.run_dir)
    with sync_playwright() as playwright:
        options = {"headless": True}
        if os.environ.get("SCREENSHOT_CHANNEL"):
            options["channel"] = os.environ["SCREENSHOT_CHANNEL"]
        browser = playwright.chromium.launch(**options)
        try:
            page = browser.new_page()
            page.goto(url + "/")
            page.select_option("#sample", trap)
            page.select_option("#port", "faulty")
            page.click("#run-audit-form button[type=submit]")
            page.wait_for_selector("#audit-result .verdict-badge.zombie")
            assert page.inner_text("#amount-count-text") == expected[0]
            assert page.inner_text("#amount-largest-text") == expected[1]
            assert page.locator("#exposure-text").count() == 0
            home_lines = [page.inner_text("#amount-count-text"), page.inner_text("#amount-largest-text")]

            def lines(selector):
                return [line for line in page.inner_text(selector).split("\n") if line.strip()]

            page.goto(f"{url}/run/{run.run_id}")
            business = lines("#amount-difference")
            assert business == expected
            page.click("#technical summary")
            engineer = lines("#amount-difference-engineer")
            assert engineer[:2] == expected
            assert engineer[2].startswith("Sum of absolute differences: ")
            assert engineer[2].endswith("(seed 42, 200 cases)")
            if trap == "T3":
                with capsys.disabled():
                    print(f"\nRENDERED T3 home lines: {home_lines!r}")
                    print(f"RENDERED T3 Business lines: {business!r}")
                    print(f"RENDERED T3 Engineer lines: {engineer!r}")
        finally:
            browser.close()
