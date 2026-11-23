"""Tests for Trap 6 (T6-cursed-modulo): FUNCTION MOD of a negative day offset.

Every expected value comes from running the COBOL program, never from a hand-written file.
"""
import csv
import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

from coroner.cases import auditable_trap_ids, case_card, case_label, load_cases_registry

TRAP_DIR = Path("samples/traps/T6-cursed-modulo")
COBOL_FILE = TRAP_DIR / "ROTATION-SLOT.cob"
FAULTY_JAVA = TRAP_DIR / "java/faulty/RotationSlot.java"
CORRECT_JAVA = TRAP_DIR / "java/correct/RotationSlot.java"
SCHEMA_FILE = TRAP_DIR / "schema.json"
FIXTURE = TRAP_DIR / "fixtures/offsets.csv"
BUILD_DIR = Path("build/traps/T6")


@pytest.fixture(scope="module", autouse=True)
def build_programs(tmp_path_factory):
    """Build the COBOL program and both Java ports into a temporary folder of this module."""
    global BUILD_DIR
    BUILD_DIR = tmp_path_factory.mktemp("t6_build")

    cobol_bin = BUILD_DIR / "ref" / "ROTATION-SLOT"
    cobol_bin.parent.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(
        ["cobc", "-x", "-Wall", str(COBOL_FILE), "-o", str(cobol_bin)],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        pytest.fail(f"COBOL compilation failed: {result.stderr}")
    assert result.stderr == "", f"cobc -Wall printed warnings: {result.stderr}"

    for variant, java_file in (("correct", CORRECT_JAVA), ("faulty", FAULTY_JAVA)):
        result = subprocess.run(
            ["javac", "-Xlint:all", "-d", str(BUILD_DIR / variant), str(java_file)],
            capture_output=True, text=True,
        )
        if result.returncode != 0:
            pytest.fail(f"{variant} Java compilation failed: {result.stderr}")


def run_cobol(input_file: Path, output_file: Path) -> int:
    env = os.environ.copy()
    env["INPUT_FILE"] = str(input_file)
    env["OUTPUT_FILE"] = str(output_file)
    result = subprocess.run(
        [str(BUILD_DIR / "ref" / "ROTATION-SLOT")], env=env, capture_output=True, text=True, timeout=10
    )
    return result.returncode


def run_java(variant: str, input_file: Path, output_file: Path) -> int:
    env = os.environ.copy()
    env["INPUT_FILE"] = str(input_file)
    env["OUTPUT_FILE"] = str(output_file)
    result = subprocess.run(
        ["java", "-cp", str(BUILD_DIR / variant), "RotationSlot"],
        env=env, capture_output=True, text=True, timeout=10,
    )
    return result.returncode


def read_rows(path: Path) -> dict[str, dict[str, str]]:
    with open(path, newline="", encoding="utf-8") as f:
        return {row["CASE-ID"].strip(): row for row in csv.DictReader(f)}


def test_t6_cobol_runs_fixture():
    """The COBOL program runs on the fixture with rc 0 and writes the header and one row per input."""
    output_file = BUILD_DIR / "cobol-fixture-out.csv"
    assert run_cobol(FIXTURE, output_file) == 0
    lines = output_file.read_text().strip().split("\n")
    assert lines[0] == "CASE-ID,DAY-OFFSET,SLOT"
    assert len(lines) - 1 == len(FIXTURE.read_text().strip().split("\n")) - 1


def test_t6_fixture_expected_equals_cobol():
    """The committed expected output is byte-identical to a fresh COBOL run."""
    output_file = BUILD_DIR / "cobol-fresh.csv"
    assert run_cobol(FIXTURE, output_file) == 0
    assert output_file.read_text() == (TRAP_DIR / "fixtures/expected-output.csv").read_text()


def test_t6_correct_java_equals_cobol_fixture():
    """The correct port writes the same bytes as COBOL on the fixture."""
    cobol_out = BUILD_DIR / "cobol-out.csv"
    java_out = BUILD_DIR / "java-correct-out.csv"
    assert run_cobol(FIXTURE, cobol_out) == 0
    assert run_java("correct", FIXTURE, java_out) == 0
    assert java_out.read_text() == cobol_out.read_text()


def test_t6_fixture_minus_11_cobol_slot_3_faulty_slot_minus_4():
    """Offset -11: COBOL writes slot +3 (from the COBOL run), the faulty port writes -4."""
    cobol_out = BUILD_DIR / "cobol-minus11.csv"
    faulty_out = BUILD_DIR / "java-faulty-minus11.csv"
    assert run_cobol(FIXTURE, cobol_out) == 0
    assert run_java("faulty", FIXTURE, faulty_out) == 0

    cobol_row = read_rows(cobol_out)["FIX-000001"]
    faulty_row = read_rows(faulty_out)["FIX-000001"]
    assert cobol_row["DAY-OFFSET"] == "-011"
    assert cobol_row["SLOT"] == "+3"
    assert faulty_row["SLOT"] == "-4"


def test_t6_faulty_differs_only_for_negative_offsets_not_multiple_of_7():
    """On the fixture the faulty port differs from COBOL exactly for negative offsets that are not multiples of 7."""
    cobol_out = BUILD_DIR / "cobol-diff.csv"
    faulty_out = BUILD_DIR / "java-faulty-diff.csv"
    assert run_cobol(FIXTURE, cobol_out) == 0
    assert run_java("faulty", FIXTURE, faulty_out) == 0

    cobol_rows = read_rows(cobol_out)
    faulty_rows = read_rows(faulty_out)
    assert cobol_rows.keys() == faulty_rows.keys()
    for case_id, cobol_row in cobol_rows.items():
        offset = int(cobol_row["DAY-OFFSET"])
        differs = cobol_row["SLOT"] != faulty_rows[case_id]["SLOT"]
        assert differs == (offset < 0 and offset % 7 != 0), f"{case_id} offset {offset}"


def test_t6_registry_and_metadata():
    """T6 is a normal case: registry entry, card, trap folder, metadata with the public sources."""
    registry = load_cases_registry()
    assert registry["T6"]["case"] == 6
    assert registry["T6"]["name"] == "The Cursed Modulo"
    assert case_label("T6", registry) == "Case 6 The Cursed Modulo"
    card = case_card("T6", registry)
    assert card[0] == "Case 6: The Cursed Modulo" and len(card) == 3
    assert auditable_trap_ids() == ["T1", "T2", "T3", "T4", "T5", "T6"]
    assert not Path("samples/traps/T6-reserved").exists()

    trap = json.loads((TRAP_DIR / "trap.json").read_text())
    assert trap["id"] == "T6"
    for key in ("title", "business_name", "business_cause", "probable_cause", "technical_cause",
                "business_fix", "fix_sentence"):
        assert isinstance(trap[key], str) and trap[key].strip(), key
    urls = {source["url"] for source in trap["sources"]}
    assert "https://www.ibm.com/docs/en/SS6SG3_6.5/lr/ref/rlinfmod.html" in urls
    assert "https://wiki.sei.cmu.edu/confluence/x/IxRMBQ" in urls
    assert "FUNCTION REM" in trap["technical_cause"] and "DIVIDE" in trap["technical_cause"]
    assert "Case 3" in trap["differs_from_case_3"]

    readme = (TRAP_DIR / "README.md").read_text()
    for url in urls:
        assert url in readme
    assert "15.17.3" in readme and "NUM51-J" in readme


def test_t6_is_an_allowed_sample_of_run_audit(tmp_path):
    """The Run audit request accepts T6, and the engine worker resolves its files from trap.json."""
    from coroner.engine_worker import resolve_sample_paths
    from coroner.ui.app import RunAuditRequest

    request = RunAuditRequest(sample="T6", port="faulty", seed=42, cases=200)
    assert request.sample == "T6"
    for port, java_file in (("correct", CORRECT_JAVA), ("faulty", FAULTY_JAVA)):
        cobol, java, schema, copybooks = resolve_sample_paths("T6", port, tmp_path)
        assert Path(cobol).name == "ROTATION-SLOT.cob"
        assert Path(java).resolve() == java_file.resolve()
        assert Path(schema).resolve() == SCHEMA_FILE.resolve()
        assert Path(copybooks).exists()


@pytest.fixture(scope="module")
def engine_runs(tmp_path_factory):
    """The real engine on T6 at 200 cases, seed 42, in a temporary base: {port: (exit code, run dir)}."""
    base = tmp_path_factory.mktemp("t6_engine_base")
    runs = {}
    for port, java_file in (("faulty", FAULTY_JAVA), ("correct", CORRECT_JAVA)):
        result = subprocess.run(
            [sys.executable, "-m", "coroner", "verify",
             "--cobol", str(COBOL_FILE), "--copybooks", str(TRAP_DIR),
             "--java", str(java_file), "--schema", str(SCHEMA_FILE),
             "--cases", "200", "--seed", "42"],
            capture_output=True, text=True, timeout=120,
            env={**os.environ, "CORONER_BASE_DIR": str(base)},
        )
        match = re.search(r"Run: runs/([0-9a-f]{12})", result.stdout)
        assert match, f"no run id in output: {result.stdout}\n{result.stderr}"
        runs[port] = (result.returncode, base / "runs" / match.group(1), result.stdout)
    return runs


@pytest.mark.slow
def test_t6_faulty_java_zombie_200_cases(engine_runs):
    code, run_dir, stdout = engine_runs["faulty"]
    assert code == 1, stdout
    assert "ZOMBIE" in stdout
    verdict = json.loads((run_dir / "verdict.json").read_text())
    assert verdict["status"] == "ZOMBIE"
    assert verdict["cases_divergent"] > 0


@pytest.mark.slow
def test_t6_correct_java_alive_200_cases(engine_runs):
    code, run_dir, stdout = engine_runs["correct"]
    assert code == 0, stdout
    assert "ALIVE" in stdout
    verdict = json.loads((run_dir / "verdict.json").read_text())
    assert verdict["status"] == "ALIVE"
    assert verdict["cases_divergent"] == 0


@pytest.mark.slow
def test_t6_divergent_cases_are_exactly_negative_offsets_not_multiple_of_7(engine_runs):
    """The divergent cases of the engine run are the negative offsets that are not multiples of 7, and only those."""
    _, run_dir, _ = engine_runs["faulty"]
    generated = read_rows(run_dir / "generated_cases.csv")
    comparison = json.loads((run_dir / "comparison_results.json").read_text())

    expected = {
        case_id for case_id, row in generated.items()
        if int(row["DAY-OFFSET"]) < 0 and int(row["DAY-OFFSET"]) % 7 != 0
    }
    divergent = {case["case_id"].strip() for case in comparison["cases"] if case["divergent"]}
    assert expected, "the generator produced no negative offset that is not a multiple of 7"
    assert divergent == expected

    for case in comparison["cases"]:
        for field in case["divergent_fields"]:
            assert field["field_name"] == "SLOT"
            offset = int(generated[case["case_id"].strip()]["DAY-OFFSET"])
            cobol_slot, java_slot = int(field["cobol_value"]), int(field["java_value"])
            assert 0 <= cobol_slot <= 6
            assert cobol_slot == offset - 7 * (offset // 7)
            assert java_slot == cobol_slot - 7


@pytest.mark.slow
def test_t6_generator_makes_a_sizable_share_of_negative_offsets(engine_runs):
    _, run_dir, _ = engine_runs["faulty"]
    offsets = [int(row["DAY-OFFSET"]) for row in read_rows(run_dir / "generated_cases.csv").values()]
    negative = sum(1 for offset in offsets if offset < 0)
    assert negative >= len(offsets) // 4


@pytest.mark.slow
def test_t6_slot_is_not_reported_as_an_amount(engine_runs):
    """A slot is a code: the run has no amount difference file and no money figure."""
    _, run_dir, _ = engine_runs["faulty"]
    assert not (run_dir / "amount_difference.json").exists()


@pytest.mark.slow
def test_t6_run_page_and_sentence_read_the_run(engine_runs, monkeypatch):
    """The run page of the faulty run shows the Case 6 card and a sentence whose count is read from the run."""
    from fastapi.testclient import TestClient

    from coroner.ui.app import app
    from coroner.ui.sentences import generate_zombie_sentence

    _, run_dir, _ = engine_runs["faulty"]
    comparison = json.loads((run_dir / "comparison_results.json").read_text())
    count = sum(len(case["divergent_fields"]) for case in comparison["cases"] if case["divergent"])

    sentence = generate_zombie_sentence("T6", run_dir)
    assert sentence.startswith(f"This Java migration is not safe to promote: {count} rotation slots differ from COBOL")
    assert "negative slot" in sentence

    monkeypatch.setenv("CORONER_BASE_DIR", str(run_dir.parent.parent))
    page = TestClient(app).get(f"/run/{run_dir.name}")
    assert page.status_code == 200
    assert "Case 6: The Cursed Modulo" in page.text
    assert sentence in page.text
