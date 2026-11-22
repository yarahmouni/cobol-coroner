"""The money figure of a ZOMBIE run for the cases without a branch exposure (T2 to T5, credit-fees).

The engine writes amount_difference_sum, amount_difference_max and amount_difference_count into
verdict.json: the sum, the largest and the number of |COBOL - Java| over the divergent decimal output
values, in exact Decimal arithmetic. The home page box reads them through run_result_summary.

The real-run tests use the faulty port of T2 to T5 at 200 cases, seed 42, each audited by the real engine
into a temporary base directory (fixture trap_faulty_200). The expected figures are recomputed here from
the run's own comparison_results.json; the repository runs/ folder is never read or written.
"""
import json
import re
import shutil
from decimal import Decimal
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from coroner.compare import CaseResult, ComparisonResult
from coroner.parse.schema import load_schema
from coroner.store import store_verdict
from coroner.ui.pages import amount_line, run_result_summary
from coroner.verdict import Verdict, amount_difference, verdict_from_dict

REPO_ROOT = Path(__file__).resolve().parent.parent
INDEX_TEMPLATE = REPO_ROOT / "coroner" / "ui" / "templates" / "index.html"
AMOUNT_KEYS = {"amount_difference_sum", "amount_difference_max", "amount_difference_count"}
TRAP_FOLDERS = {"T2": "T2-rounding", "T3": "T3-comp3-sign", "T4": "T4-zoned-overpunch", "T5": "T5-redefines-invalid"}
# T2 output: CASE-ID string, FEE1 and FEE2 decimal
SCHEMA = load_schema(str(REPO_ROOT / "samples" / "traps" / TRAP_FOLDERS["T2"] / "schema.json"))


def _mismatch(field_name, cobol_value, java_value):
    return {"field_name": field_name, "kind": "value_mismatch", "cobol_value": cobol_value, "java_value": java_value}


def _comparison(*divergent_fields, exposure_sum=None):
    cases = [CaseResult(case_id=f"C{i}", divergent=True, divergent_fields=[field])
             for i, field in enumerate(divergent_fields)]
    return ComparisonResult(cases=cases, run_return_codes=(0, 0), row_count_match=True,
                            total_divergent=len(cases), exposure_sum=exposure_sum)


def _decimal_columns(schema_path: Path) -> set:
    return {column.name for column in load_schema(str(schema_path)).output_columns if column.type == "decimal"}


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


# ------------------------------------------------------------------ storage and the UI helper


def test_store_verdict_writes_the_keys_only_when_the_run_has_the_figure(tmp_path):
    base = dict(status="ZOMBIE", sub_label="FAIL: business behavior diverged on 3 cases", cases_total=10,
                cases_divergent=3, run_return_codes=(0, 0))
    with_figure = Verdict(**base, amount_difference_sum=Decimal("0.90"), amount_difference_max=Decimal("0.01"),
                          amount_difference_count=90)
    store_verdict(str(tmp_path / "a"), with_figure)
    store_verdict(str(tmp_path / "b"), Verdict(**base))
    written = json.loads((tmp_path / "a" / "verdict.json").read_text())
    assert (written["amount_difference_sum"], written["amount_difference_max"],
            written["amount_difference_count"]) == ("0.90", "0.01", 90)
    assert AMOUNT_KEYS.isdisjoint(json.loads((tmp_path / "b" / "verdict.json").read_text()))
    assert verdict_from_dict(written) == with_figure


@pytest.mark.parametrize("data, expected", [
    ({"amount_difference_sum": "0.90", "amount_difference_count": 90}, "Amount difference: 0.90 across 90 amounts"),
    ({"amount_difference_sum": "0.01", "amount_difference_count": 1}, "Amount difference: 0.01 across 1 amount"),
    ({"amount_difference_sum": "546373400.00", "amount_difference_count": 44},
     "Amount difference: 546373400.00 across 44 amounts"),
    ({"amount_difference_sum": "0.90"}, None),
    ({"amount_difference_count": 90}, None),
    ({"amount_difference_sum": "0.90", "amount_difference_count": 0}, None),
    ({"amount_difference_sum": "0.90", "amount_difference_count": True}, None),
    ({"amount_difference_sum": 0.9, "amount_difference_count": 90}, None),
    ({"amount_difference_sum": "", "amount_difference_count": 90}, None),
    ({}, None),
])
def test_amount_line_from_a_verdict(data, expected):
    assert amount_line(data) == expected


def test_the_box_script_shows_the_exposure_line_first_then_the_amount_line():
    script = "\n".join(re.findall(r"<script\b[^>]*>(.*?)</script>", INDEX_TEMPLATE.read_text(),
                                  flags=re.DOTALL | re.IGNORECASE))
    assert "showExposure(resultDiv, data.exposure_line || data.amount_line);" in script


# ------------------------------------------------------------------ real runs of T2 to T5


def test_verdict_json_holds_the_figure_recomputed_from_the_comparison_files(trap_faulty_200):
    trap, run = trap_faulty_200
    columns = _decimal_columns(REPO_ROOT / "samples" / "traps" / TRAP_FOLDERS[trap] / "schema.json")
    expected_sum, expected_max, expected_count = _recomputed(run.run_dir, columns)
    verdict = json.loads((run.run_dir / "verdict.json").read_text())

    assert verdict["status"] == "ZOMBIE"
    assert Decimal(verdict["amount_difference_sum"]) == expected_sum > 0
    assert Decimal(verdict["amount_difference_max"]) == expected_max
    assert verdict["amount_difference_count"] == expected_count > 0
    # exact text: no exponent, no rounding
    assert verdict["amount_difference_sum"] == format(expected_sum, "f")
    # a run without a branch exposure carries no exposure fields
    assert "exposure_sum" not in verdict and "affected_branches" not in verdict


def test_the_figure_means_what_each_trap_does(trap_faulty_200):
    trap, run = trap_faulty_200
    verdict = json.loads((run.run_dir / "verdict.json").read_text())
    total, largest = Decimal(verdict["amount_difference_sum"]), Decimal(verdict["amount_difference_max"])
    fields = _divergent_fields(run.run_dir)
    if trap == "T2":  # a rounding difference of exactly one cent per divergent fee
        assert largest == Decimal("0.01") and total == Decimal("0.01") * verdict["amount_difference_count"]
    elif trap in ("T3", "T4"):  # same magnitude, opposite sign: the difference is twice the COBOL value
        assert all(abs(Decimal(f["cobol_value"])) == abs(Decimal(f["java_value"])) for f in fields)
        assert total == 2 * sum(abs(Decimal(f["cobol_value"])) for f in fields)
    else:  # T5: Java writes the fee alone where COBOL adds it to the amount
        assert all(Decimal(f["java_value"]) == Decimal("1.00") for f in fields)
        assert total == sum(abs(Decimal(f["cobol_value"]) - Decimal("1.00")) for f in fields)


def test_other_verdict_fields_are_the_ones_written_before(trap_faulty_200):
    trap, run = trap_faulty_200
    verdict = json.loads((run.run_dir / "verdict.json").read_text())
    assert set(verdict) == {"status", "sub_label", "cases_total", "cases_divergent", "run_return_codes",
                            "validation_notice"} | AMOUNT_KEYS
    assert verdict["cases_total"] == 200 and verdict["cases_divergent"] > 0


def test_summary_line_is_built_from_the_recorded_figure(trap_faulty_200):
    trap, run = trap_faulty_200
    verdict = json.loads((run.run_dir / "verdict.json").read_text())
    summary = run_result_summary(run.run_dir)
    noun = "amount" if verdict["amount_difference_count"] == 1 else "amounts"
    assert summary["amount_line"] == (
        f"Amount difference: {verdict['amount_difference_sum']} across {verdict['amount_difference_count']} {noun}")
    assert summary["exposure_line"] is None


def test_cache_hit_of_a_new_run_shows_the_line_and_of_an_older_run_does_not(trap_faulty_200, tmp_path, monkeypatch):
    """The page reads the run as it is: a run made before the change has no figure, and is never rewritten."""
    trap, run = trap_faulty_200
    base, exchange = tmp_path / "base", tmp_path / "exchange"
    exchange.mkdir()
    (base / "runs").mkdir(parents=True)
    new_id, old_id = run.run_id, "abcdef012345"
    shutil.copytree(run.run_dir, base / "runs" / new_id)
    shutil.copytree(run.run_dir, base / "runs" / old_id)
    old_verdict = base / "runs" / old_id / "verdict.json"
    data = json.loads(old_verdict.read_text())
    for key in AMOUNT_KEYS:
        del data[key]
    old_verdict.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")
    before = (old_verdict.read_bytes(), old_verdict.stat().st_mtime_ns)

    monkeypatch.setenv("CORONER_BASE_DIR", str(base))
    monkeypatch.setenv("CORONER_EXCHANGE_DIR", str(exchange))
    from coroner.ui.app import app, update_run_index

    update_run_index(trap, "faulty", 42, 200, new_id)
    update_run_index(trap, "faulty", 43, 200, old_id)
    client = TestClient(app)
    new = client.post("/api/run", json={"sample": trap, "port": "faulty", "seed": 42, "cases": 200}).json()
    old = client.post("/api/run", json={"sample": trap, "port": "faulty", "seed": 43, "cases": 200}).json()

    recorded = json.loads((run.run_dir / "verdict.json").read_text())
    assert new["amount_line"] == (f"Amount difference: {recorded['amount_difference_sum']} across "
                                  f"{recorded['amount_difference_count']} amounts")
    assert new["verdict"] == old["verdict"] == "ZOMBIE"
    assert old["amount_line"] is None and old["exposure_line"] is None
    assert (old_verdict.read_bytes(), old_verdict.stat().st_mtime_ns) == before


@pytest.mark.slow
def test_certificate_of_the_new_run_replays_valid(trap_faulty_200):
    trap, run = trap_faulty_200
    from coroner.certificate import replay_certificate

    result = replay_certificate(str(run.run_dir / "certificate.json"), base_dir=str(run.base))
    assert result.valid, result.reason
    assert result.cases_divergent == json.loads((run.run_dir / "verdict.json").read_text())["cases_divergent"]
    assert not any("comparison engine differs" in warning for warning in result.warnings)


# ------------------------------------------------------------------ other runs


def test_credit_fees_half_even_run_gets_the_figure_and_the_alive_run_does_not(
        credit_fees_half_even_30, credit_fees_alive_30):
    zombie = json.loads((credit_fees_half_even_30.run_dir / "verdict.json").read_text())
    columns = _decimal_columns(REPO_ROOT / "samples" / "credit-fees" / "schema.json")
    total, largest, count = _recomputed(credit_fees_half_even_30.run_dir, columns)
    assert (Decimal(zombie["amount_difference_sum"]), Decimal(zombie["amount_difference_max"]),
            zombie["amount_difference_count"]) == (total, largest, count)
    assert AMOUNT_KEYS.isdisjoint(json.loads((credit_fees_alive_30.run_dir / "verdict.json").read_text()))


def test_case_1_keeps_its_exposure_and_gets_no_amount_figure(t1_faulty_30):
    verdict = json.loads((t1_faulty_30.run_dir / "verdict.json").read_text())
    assert "exposure_sum" in verdict and AMOUNT_KEYS.isdisjoint(verdict)
    summary = run_result_summary(t1_faulty_30.run_dir)
    assert summary["exposure_line"].startswith("Exposure: ") and summary["amount_line"] is None
