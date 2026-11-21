"""Replay regenerates the cases from the recorded seed (R-138 integrity defect).

Every run here is a real engine run in a temporary base directory.
The repository runs/ folder is never read or written.
"""
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from coroner.certificate import compute_certificate_sha256, replay_certificate
from coroner.cli import run_verify
from coroner.gen import DEFAULT_TIE_SHARE, GENERATOR_VERSION

T1 = Path("samples/traps/T1-ebcdic-match-merge")
CREDIT_FEES = Path("samples/credit-fees")
CARDDEMO = Path("samples/carddemo-cbact04c")

SEED_REASON = "replay mismatch (generated cases do not match random_seed)"


def _t1_run(base, java, cases, seed=42):
    verdict, run_dir = run_verify(
        cobol_path=str((T1 / "MATCH-MERGE.cob").resolve()),
        copybooks_dir=str((T1 / "copybooks").resolve()),
        java_path=str((T1 / "java" / java / "MatchMerge.java").resolve()),
        schema_path=str((T1 / "schema.json").resolve()),
        num_cases=cases,
        seed=seed,
        base_dir=str(base),
    )
    return run_dir


def _forge(cert_path: Path, target: Path, **edits) -> Path:
    """Copy a certificate with edits (None removes a key) and a recomputed hash."""
    cert = json.loads(cert_path.read_text())
    cert.pop("certificate_sha256")
    for key, value in edits.items():
        if value is None:
            del cert[key]
        else:
            cert[key] = value
    cert["certificate_sha256"] = compute_certificate_sha256(cert)
    target.write_text(json.dumps(cert, indent=2, sort_keys=True) + "\n")
    return target


@pytest.fixture(scope="module")
def t1_faulty(tmp_path_factory):
    base = tmp_path_factory.mktemp("seed_check_t1")
    run_dir = _t1_run(base, "faulty", 50)
    return base, run_dir / "certificate.json"


@pytest.fixture(scope="module")
def credit_fees_run(tmp_path_factory):
    base = tmp_path_factory.mktemp("seed_check_cf")
    _, run_dir = run_verify(
        cobol_path=str((CREDIT_FEES / "CREDIT-FEES.cob").resolve()),
        copybooks_dir=str((CREDIT_FEES / "copybooks").resolve()),
        java_path=str((CREDIT_FEES / "java" / "CreditFees.java").resolve()),
        schema_path=str((CREDIT_FEES / "schema.json").resolve()),
        num_cases=50,
        seed=42,
        base_dir=str(base),
    )
    return base, run_dir / "certificate.json"


def test_new_certificate_records_what_regeneration_needs(t1_faulty):
    _, cert_path = t1_faulty
    cert = json.loads(cert_path.read_text())
    assert cert["generator_version"] == GENERATOR_VERSION
    assert cert["tie_share"] == DEFAULT_TIE_SHARE == 0.06
    assert cert["random_seed"] == 42 and cert["case_count"] == 50


@pytest.mark.slow
def test_a_fresh_certificate_replays_valid(t1_faulty):
    base, cert_path = t1_faulty
    result = replay_certificate(str(cert_path), base_dir=str(base))
    assert result.valid, result.reason
    assert not any("not regenerated" in w for w in result.warnings)
    assert result.cases_total == 50


def test_seed_edit_with_recomputed_hash_is_invalid(t1_faulty, tmp_path):
    base, cert_path = t1_faulty
    forged = _forge(cert_path, tmp_path / "forged.json", random_seed=43)
    result = replay_certificate(str(forged), base_dir=str(base))
    assert not result.valid
    assert result.reason == SEED_REASON


def test_tie_share_edit_with_recomputed_hash_is_invalid(credit_fees_run, tmp_path):
    """credit-fees uses the tie share (a batch schema such as T1 does not read it)."""
    base, cert_path = credit_fees_run
    forged = _forge(cert_path, tmp_path / "forged.json", tie_share=0.5)
    result = replay_certificate(str(forged), base_dir=str(base))
    assert not result.valid
    assert result.reason == SEED_REASON


@pytest.mark.slow
@pytest.mark.parametrize("recorded, shown", [(None, "none"), (0, "0")])
def test_old_style_certificate_replays_valid_with_a_warning(t1_faulty, tmp_path, recorded, shown):
    base, cert_path = t1_faulty
    forged = _forge(cert_path, tmp_path / "old.json", generator_version=recorded)
    result = replay_certificate(str(forged), base_dir=str(base))
    assert result.valid, result.reason
    expected = f"cases not regenerated from the seed (generator version recorded: {shown}, current: {GENERATOR_VERSION})"
    assert expected in result.warnings


@pytest.mark.slow
def test_tamper_route_with_only_the_seed_edited_is_invalid(t1_faulty, tmp_path, monkeypatch):
    base, cert_path = t1_faulty
    run_id = cert_path.parent.name
    exchange = tmp_path / "exchange"
    exchange.mkdir()
    monkeypatch.setenv("CORONER_BASE_DIR", str(base))
    monkeypatch.setenv("CORONER_EXCHANGE_DIR", str(exchange))

    from coroner.ui.app import app, reset_rate_limiter

    reset_rate_limiter()
    cert = json.loads(cert_path.read_text())
    response = TestClient(app).post("/api/tamper", data={
        "run_id": run_id,
        "status": cert["status"],
        "cases_total": cert["cases_total"],
        "cases_divergent": cert["cases_divergent"],
        "random_seed": cert["random_seed"] + 1,
    })
    assert response.status_code == 200
    assert "Certificate: INVALID" in response.text
    assert "generated cases do not match random_seed" in response.text
    reset_rate_limiter()


@pytest.mark.slow
def test_run_ids_are_unchanged(tmp_path):
    faulty = _t1_run(tmp_path, "faulty", 2000)
    correct = _t1_run(tmp_path, "correct", 2000)
    assert faulty.name == "f584d5f35228"
    assert correct.name == "29c15f04407b"
    cert = json.loads((correct / "certificate.json").read_text())
    assert cert["generator_version"] == GENERATOR_VERSION and cert["tie_share"] == 0.06


@pytest.mark.slow
def test_generator_script_schema_is_regenerated_from_the_seed(tmp_path):
    """CardDemo uses a generator script: replay must regenerate through that script."""
    _, run_dir = run_verify(
        cobol_path=str((CARDDEMO / "adapted" / "HARNESS-CBACT04C.cob").resolve()),
        copybooks_dir=str((CARDDEMO / "upstream" / "cpy").resolve()),
        java_path=str((CARDDEMO / "java" / "Cbact04c.java").resolve()),
        schema_path=str((CARDDEMO / "schema.json").resolve()),
        num_cases=5,
        seed=42,
        base_dir=str(tmp_path),
    )
    cert_path = run_dir / "certificate.json"
    cert = json.loads(cert_path.read_text())
    assert cert["generator_version"] == GENERATOR_VERSION and "generator_script_sha256" in cert

    forged = _forge(cert_path, tmp_path / "forged.json", random_seed=43)
    result = replay_certificate(str(forged), base_dir=str(tmp_path))
    assert not result.valid and result.reason == SEED_REASON

    result = replay_certificate(str(cert_path), base_dir=str(tmp_path))
    assert result.valid, result.reason
