"""CardDemo CBACT04C audit: generator_script, its security rule and a full pipeline run.

Real runs only: the engine, the COBOL harness and the Java compiler are the
real ones. The Java side is a stand-in written by the test that does not port
anything (it writes only the CSV header), so the verdict must be ZOMBIE.
"""
import csv
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from coroner.gate import certificate_matches_files
from coroner.gen import generate_cases
from coroner.parse.schema import GeneratorScriptError, load_schema

REPO = Path(__file__).resolve().parents[1]
SAMPLE = REPO / "samples" / "carddemo-cbact04c"
SCHEMA = SAMPLE / "schema.json"
HARNESS = "samples/carddemo-cbact04c/adapted/HARNESS-CBACT04C.cob"
COPYBOOKS = "samples/carddemo-cbact04c/upstream/cpy"
T1 = REPO / "samples" / "traps" / "T1-ebcdic-match-merge"
GENERATOR_SOURCE = SAMPLE / "generator.py"


def write_stand_in(directory: Path) -> Path:
    """A Java program that ports nothing: it writes only the output header."""
    columns = [c["name"] for c in json.loads(SCHEMA.read_text())["output"]["columns"]]
    java = directory / "StandIn.java"
    java.write_text(
        "import java.io.FileWriter;\n"
        "import java.io.IOException;\n"
        "\n"
        "public class StandIn {\n"
        "    public static void main(String[] args) throws IOException {\n"
        "        try (FileWriter out = new FileWriter(System.getenv(\"OUTPUT_FILE\"))) {\n"
        f"            out.write(\"{','.join(columns)}\\n\");\n"
        "        }\n"
        "    }\n"
        "}\n"
    )
    return java


def run_coroner(args: list[str], base_dir: Path, timeout: int = 300) -> subprocess.CompletedProcess:
    env = dict(os.environ, CORONER_BASE_DIR=str(base_dir))
    return subprocess.run(
        [sys.executable, "-m", "coroner", *args],
        cwd=REPO, env=env, capture_output=True, text=True, timeout=timeout,
    )


def verify_args(java: Path, schema: Path, cases: int, seed: int = 42) -> list[str]:
    return [
        "verify", "--cobol", HARNESS, "--copybooks", COPYBOOKS,
        "--java", str(java), "--schema", str(schema),
        "--cases", str(cases), "--seed", str(seed),
    ]


def schema_copy(directory: Path, generator_script: str) -> Path:
    """A copy of the CardDemo schema (and nothing else) with another generator_script."""
    directory.mkdir(parents=True, exist_ok=True)
    data = json.loads(SCHEMA.read_text())
    data["generator_script"] = generator_script
    path = directory / "schema.json"
    path.write_text(json.dumps(data))
    return path


def run_id_of(stdout: str) -> str:
    match = re.search(r"^Run: runs/([0-9a-f]{12})$", stdout, re.MULTILINE)
    assert match, f"no run id in output:\n{stdout}"
    return match.group(1)


# (a) the script must be inside the schema folder; refused before any import

@pytest.fixture
def outside_script(tmp_path):
    """A script outside the schema folder that leaves a marker file if it is ever executed."""
    marker = tmp_path / "marker-script-was-imported"
    script = tmp_path / "outside" / "evil.py"
    script.parent.mkdir()
    script.write_text(
        f"open({str(marker)!r}, 'w').write('executed')\n"
        "def generate_cases(schema, rng, num_cases):\n"
        "    return []\n"
    )
    return script, marker


def make_declared(kind: str, tmp_path: Path, script: Path) -> str:
    schema_dir = tmp_path / "schema"
    schema_dir.mkdir(exist_ok=True)
    if kind == "absolute":
        return str(script)
    if kind == "dotdot":
        return "../outside/evil.py"
    (schema_dir / "link.py").symlink_to(script)
    return "link.py"


@pytest.mark.parametrize("kind", ["absolute", "dotdot", "symlink"])
def test_generator_script_outside_schema_folder_is_an_error(tmp_path, outside_script, kind):
    script, marker = outside_script
    declared = make_declared(kind, tmp_path, script)
    schema = schema_copy(tmp_path / "schema", declared)
    java = write_stand_in(tmp_path)
    base = tmp_path / "base"

    result = run_coroner(verify_args(java, schema, cases=5), base)

    assert result.returncode == 2, result.stdout + result.stderr
    assert f"ERROR: generator script outside schema directory: {declared}" in result.stderr
    assert not marker.exists(), "the script was imported before the check"
    assert not (base / "runs").exists(), "a run was started"
    with pytest.raises(GeneratorScriptError, match="outside schema directory"):
        load_schema(str(schema))


def test_generator_script_inside_schema_folder_is_accepted(tmp_path):
    shutil.copy(GENERATOR_SOURCE, tmp_path / "generator.py")
    schema_path = schema_copy(tmp_path, "generator.py")
    schema = load_schema(str(schema_path))
    assert schema.generator_script == "generator.py"
    assert Path(schema.generator_script_path) == (tmp_path / "generator.py").resolve()


def test_generator_script_missing_is_an_error(tmp_path):
    schema_path = schema_copy(tmp_path, "nothing-here.py")
    with pytest.raises(GeneratorScriptError, match="not found"):
        load_schema(str(schema_path))


# (b) determinism and what the generator covers

@pytest.fixture(scope="module")
def schema_obj():
    return load_schema(str(SCHEMA))


def test_same_seed_gives_byte_identical_cases_file(schema_obj, tmp_path):
    first = Path(generate_cases(schema_obj, {}, 42, 200, 0.06, str(tmp_path / "a"))).read_bytes()
    second = Path(generate_cases(schema_obj, {}, 42, 200, 0.06, str(tmp_path / "b"))).read_bytes()
    other = Path(generate_cases(schema_obj, {}, 43, 200, 0.06, str(tmp_path / "c"))).read_bytes()
    assert first == second
    assert first != other
    assert b"\r" not in first and b'"' not in first
    header = first.split(b"\n")[0].decode().split(",")
    assert header == [c.name for c in schema_obj.input_columns]
    assert len(first.splitlines()) == 201


def test_generator_draws_only_from_the_given_rng():
    source = GENERATOR_SOURCE.read_text()
    imports = re.findall(r"^\s*(?:import|from)\s+(\S+)", source, re.MULTILINE)
    assert imports == ["coroner.gen"]
    assert re.search(r"\.(randint|randrange|choice|shuffle|uniform|sample|getrandbits)\(", source) is None


def test_generator_covers_the_cases_that_matter(schema_obj, tmp_path):
    path = generate_cases(schema_obj, {}, 42, 2000, 0.06, str(tmp_path))
    with open(path, newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == 2000

    seen = set()
    for row in rows:
        accounts = {i: row[f"ACCT-GROUP-ID-{i}"] for i in range(1, 6) if int(row[f"ACCT-ID-{i}"]) > 0}
        own = {(row[f"RATE-GROUP-{i}"], row[f"RATE-TYPE-{i}"], int(row[f"RATE-CAT-{i}"])) for i in range(1, 21) if row[f"RATE-GROUP-{i}"]}
        per_account = {}
        for i in range(1, 11):
            index = int(row[f"CATBAL-ACCT-INDEX-{i}"])
            if index == 0:
                continue
            balance = row[f"CATBAL-BAL-{i}"]
            seen.add("negative balance" if balance.startswith("-") else "zero balance" if float(balance) == 0 else "positive balance")
            per_account[index] = per_account.get(index, 0) + 1
            if index not in accounts:
                seen.add("balance on an unused account slot")
                continue
            key = (accounts[index], row[f"CATBAL-TYPE-{i}"], int(row[f"CATBAL-CAT-{i}"]))
            default = ("DEFAULT", key[1], key[2])
            if key in own:
                seen.add("group with its own rate")
            elif default in own:
                seen.add("group falling back to DEFAULT")
            else:
                seen.add("no rate and no DEFAULT")
        if any(count >= 2 for count in per_account.values()):
            seen.add("several balances on one account")
        for i in range(1, 21):
            if row[f"RATE-GROUP-{i}"]:
                seen.add("zero rate" if float(row[f"RATE-VALUE-{i}"]) == 0 else "non-zero rate")
        if any(row[f"XREF-EXISTS-{i}"] == "N" for i in range(1, 6)):
            seen.add("account without cross-reference")
        ids = [int(row[f"ACCT-ID-{i}"]) for i in range(1, 6) if int(row[f"ACCT-ID-{i}"]) > 0]
        if ids != sorted(ids):
            seen.add("slot order differs from key order")
        if len(ids) == 1:
            seen.add("single account")

    assert seen == {
        "negative balance", "zero balance", "positive balance",
        "zero rate", "non-zero rate",
        "group with its own rate", "group falling back to DEFAULT", "no rate and no DEFAULT",
        "account without cross-reference", "balance on an unused account slot",
        "several balances on one account", "slot order differs from key order", "single account",
    }


# (c) the existing T1 audit is untouched by the extension

@pytest.mark.slow
def test_t1_correct_run_id_is_unchanged(tmp_path):
    result = run_coroner([
        "verify", "--cobol", str(T1 / "MATCH-MERGE.cob"), "--copybooks", str(T1 / "copybooks"),
        "--java", str(T1 / "java" / "correct" / "MatchMerge.java"), "--schema", str(T1 / "schema.json"),
        "--cases", "2000", "--seed", "42",
    ], tmp_path)
    assert result.returncode == 0, result.stdout + result.stderr
    assert run_id_of(result.stdout) == "29c15f04407b"


# (d) a stand-in that ports nothing: the whole pipeline runs and compares

@pytest.fixture(scope="module")
def stand_in_run(tmp_path_factory):
    """One real 20-case audit of the CardDemo harness against the stand-in."""
    root = tmp_path_factory.mktemp("carddemo_audit")
    schema_dir = root / "schema"
    schema_dir.mkdir()
    shutil.copy(GENERATOR_SOURCE, schema_dir / "generator.py")
    schema = schema_copy(schema_dir, "generator.py")
    java = write_stand_in(root)
    base = root / "base"
    result = run_coroner(verify_args(java, schema, cases=20), base)
    return {"result": result, "base": base, "schema_dir": schema_dir, "schema": schema, "java": java}


@pytest.mark.slow
def test_stand_in_gives_zombie_end_to_end(stand_in_run):
    result = stand_in_run["result"]
    assert result.returncode == 1, result.stdout + result.stderr
    assert "ZOMBIE: FAIL: business behavior diverged on 20 cases" in result.stdout
    run_dir = stand_in_run["base"] / "runs" / run_id_of(result.stdout)
    verdict = json.loads((run_dir / "verdict.json").read_text())
    assert verdict["status"] == "ZOMBIE"
    assert verdict["cases_total"] == 20 and verdict["cases_divergent"] == 20
    assert (run_dir / "failure_report.json").is_file()
    cases = (run_dir / "generated_cases.csv").read_text().splitlines()
    assert len(cases) == 21


@pytest.mark.slow
def test_certificate_records_the_generator_script_hash(stand_in_run):
    run_dir = stand_in_run["base"] / "runs" / run_id_of(stand_in_run["result"].stdout)
    expected = hashlib.sha256((stand_in_run["schema_dir"] / "generator.py").read_bytes()).hexdigest()
    certificate = json.loads((run_dir / "certificate.json").read_text())
    inputs = json.loads((run_dir / "inputs.json").read_text())
    assert certificate["generator_script"] == "generator.py"
    assert certificate["generator_script_sha256"] == expected
    assert inputs["generator_script_sha256"] == expected


@pytest.mark.slow
def test_replay_refuses_a_changed_generator_script(stand_in_run):
    run_dir = stand_in_run["base"] / "runs" / run_id_of(stand_in_run["result"].stdout)
    certificate = run_dir / "certificate.json"
    script = stand_in_run["schema_dir"] / "generator.py"
    original = script.read_bytes()

    replay = run_coroner(["verify", str(certificate)], stand_in_run["base"])
    assert replay.returncode == 1, replay.stdout + replay.stderr  # valid ZOMBIE
    assert "Certificate: VALID" in replay.stdout

    try:
        script.write_bytes(original + b"\n# changed after the audit\n")
        # the schema file itself is unchanged, so only the script hash can catch this
        replay = run_coroner(["verify", str(certificate)], stand_in_run["base"])
    finally:
        script.write_bytes(original)
    assert replay.returncode == 3, replay.stdout + replay.stderr
    assert "Certificate: INVALID: generator script hash mismatch" in replay.stdout


@pytest.mark.slow
def test_gate_match_includes_the_generator_script(stand_in_run):
    run_dir = stand_in_run["base"] / "runs" / run_id_of(stand_in_run["result"].stdout)
    certificate = json.loads((run_dir / "certificate.json").read_text())
    scope = {
        "cobol": HARNESS,
        "java": str(stand_in_run["java"]),
        "schema": str(stand_in_run["schema"]),
        "copybooks": COPYBOOKS,
    }
    script = stand_in_run["schema_dir"] / "generator.py"
    original = script.read_bytes()

    assert certificate_matches_files(certificate, scope, REPO) is True
    try:
        script.write_bytes(original + b"\n# changed after the audit\n")
        assert certificate_matches_files(certificate, scope, REPO) is False
    finally:
        script.write_bytes(original)
