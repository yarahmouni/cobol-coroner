"""Pytest configuration for Coroner tests."""
import json
import os
import shutil
import subprocess
import sys
from collections import namedtuple
from pathlib import Path

import pytest
from hypothesis import settings, Phase

# Register a deterministic profile for reproducible tests
settings.register_profile(
    "coroner",
    derandomize=True,
    database=None,
    phases=[Phase.explicit, Phase.reuse, Phase.generate, Phase.target, Phase.shrink]
)

# Load the profile
settings.load_profile("coroner")

# Import the hook from the plugin module
from noskip_plugin import pytest_runtest_makereport  # noqa: F401


@pytest.fixture(autouse=True, scope="session")
def isolated_variants_dir(tmp_path_factory):
    """Point the engine worker's HALF_EVEN variant folder at a session temp directory.

    <repo>/build/variants/CreditFees.java is shared with scripts/init_demo_runs.sh and make zombie.
    No test may write it: the worker, when a test asks for the credit-fees faulty port, generates
    the variant here instead. The folder ends in build/variants like the real one.
    """
    import os

    folder = tmp_path_factory.mktemp("variants_root") / "build" / "variants"
    shared = Path(__file__).resolve().parent.parent / "build" / "variants" / "CreditFees.java"

    def state():
        return (shared.stat().st_mtime_ns, shared.stat().st_size) if shared.exists() else None

    shared_before = state()
    previous = os.environ.get("CORONER_VARIANTS_DIR")
    os.environ["CORONER_VARIANTS_DIR"] = str(folder)
    yield folder
    if previous is None:
        os.environ.pop("CORONER_VARIANTS_DIR", None)
    else:
        os.environ["CORONER_VARIANTS_DIR"] = previous
    assert state() == shared_before, (
        "a test wrote <repo>/build/variants/CreditFees.java, which is shared with "
        "scripts/init_demo_runs.sh and make zombie (or one of them ran during the tests)"
    )


@pytest.fixture(autouse=True, scope="function")
def restore_environment():
    """Give every test the environment the previous one started with.

    Several tests set CORONER_BASE_DIR, CORONER_EXCHANGE_DIR and other variables on os.environ for
    the process. Without this fixture such a value stays set for every later test of the same
    process, so the result of a test would depend on which tests ran before it in its worker
    (pytest-xdist runs files in another order than a serial run).
    """
    before = dict(os.environ)
    yield
    for name in set(os.environ) - set(before):
        del os.environ[name]
    for name, value in before.items():
        if os.environ.get(name) != value:
            os.environ[name] = value


@pytest.fixture(autouse=True, scope="function")
def reset_ui_rate_limiter():
    """Reset UI rate limiter before each test."""
    import sys
    
    # Reset only if the module is already imported
    mod = sys.modules.get("coroner.ui.app")
    if mod:
        mod.reset_rate_limiter()
    
    yield
    
    # Reset again after test
    mod = sys.modules.get("coroner.ui.app")
    if mod:
        mod.reset_rate_limiter()


REPO_ROOT = Path(__file__).resolve().parent.parent
T1_SAMPLE = "samples/traps/T1-ebcdic-match-merge"
CREDIT_FEES_SAMPLE = "samples/credit-fees"

# Run ids asserted by the tests (same inputs, seed 42, 2000 cases).
T1_FAULTY_2000_ID = "f584d5f35228"
T1_CORRECT_2000_ID = "29c15f04407b"
CREDIT_FEES_2000_ID = "df4d7929ce44"

# One real engine audit: run id, its base directory, the run folder, the CLI exit status and stdout.
EngineRun = namedtuple("EngineRun", "run_id base run_dir returncode stdout")


def _folder_listing(folder: Path) -> list:
    """Names and modification times of the entries of a folder (empty if it does not exist)."""
    if not folder.exists():
        return []
    return sorted((p.name, p.stat().st_mtime_ns) for p in folder.iterdir())


def file_state(path: Path):
    """Modification time and SHA-256 of a file, or None when it does not exist."""
    import hashlib

    if not path.exists():
        return None
    return (path.stat().st_mtime_ns, hashlib.sha256(path.read_bytes()).hexdigest())


def _tree_state(folder: Path) -> list:
    """Relative path, size and modification time of every file under a folder."""
    return sorted(
        (str(p.relative_to(folder)), p.stat().st_size, p.stat().st_mtime_ns)
        for p in folder.rglob("*") if p.is_file()
    )


def _engine_audit(base: Path, cobol: str, copybooks: str, java: str, schema: str,
                  cases: int, expected_exit: int) -> EngineRun:
    """Run `python -m coroner verify` from the repository root into `base`, with relative sample paths.

    Relative paths make the certificate record the same paths as the bundled ones, so the gate
    can match it against the repository files.
    """
    env = {**os.environ, "CORONER_BASE_DIR": str(base)}
    env.pop("CORONER_REPLAY_TIMEOUT", None)
    proc = subprocess.run(
        [sys.executable, "-m", "coroner", "verify", "--cobol", cobol, "--copybooks", copybooks,
         "--java", java, "--schema", schema, "--cases", str(cases), "--seed", "42"],
        cwd=REPO_ROOT, env=env, capture_output=True, text=True, timeout=600,
    )
    assert proc.returncode == expected_exit, (
        f"audit of {java} at {cases} cases exited {proc.returncode}, expected {expected_exit}\n"
        f"{proc.stdout}\n{proc.stderr}"
    )
    run_id = None
    for line in proc.stdout.splitlines():
        if line.startswith("Run: "):
            run_id = Path(line.split("Run: ", 1)[1].strip()).name
            break
    assert run_id is not None, f"no run id in the output:\n{proc.stdout}"
    run_dir = base / "runs" / run_id
    assert (run_dir / "certificate.json").is_file(), f"audit did not produce run {run_id}\n{proc.stdout}"
    return EngineRun(run_id, base, run_dir, proc.returncode, proc.stdout)


def _shared_engine_run(base: Path, expected_id, *audit_args) -> EngineRun:
    """One shared audit: the repository runs/ folder is checked before and after, the run id when given."""
    repo_runs = REPO_ROOT / "runs"
    before = _folder_listing(repo_runs)
    run = _engine_audit(base, *audit_args)
    if expected_id is not None:
        assert run.run_id == expected_id, f"run id {run.run_id}, expected {expected_id}"
    assert _folder_listing(repo_runs) == before, "the engine run touched the repository runs/ folder"
    return run


def _t1_args(kind: str) -> tuple:
    return (f"{T1_SAMPLE}/MATCH-MERGE.cob", f"{T1_SAMPLE}/copybooks",
            f"{T1_SAMPLE}/java/{kind}/MatchMerge.java", f"{T1_SAMPLE}/schema.json")


@pytest.fixture
def copy_runs():
    """Return a function that copies run folders into another base directory.

    A test that edits a run (tamper, an edited certificate, a forged copy) must work on its own
    copy of a shared run, never on the shared one: `copy_runs(source_base, target_base, *run_ids)`.
    """
    def copy(source_base: Path, target_base: Path, *run_ids: str) -> None:
        (target_base / "runs").mkdir(parents=True, exist_ok=True)
        for run_id in run_ids:
            shutil.copytree(source_base / "runs" / run_id, target_base / "runs" / run_id)
    return copy


def _assert_shared_run_unchanged(run: EngineRun, state: list) -> None:
    assert _tree_state(run.run_dir) == state, (
        f"a test changed the shared run {run.run_id}; a test that edits a run must copy it first"
    )


@pytest.fixture(scope="session")
def engine_2000_base(tmp_path_factory):
    """One temporary base directory for the 2000-case runs shared by the whole session."""
    return tmp_path_factory.mktemp("engine_2000")


@pytest.fixture(scope="session")
def t1_faulty_2000(engine_2000_base):
    """T1 faulty, 2000 cases, seed 42: ZOMBIE, exit 1, run f584d5f35228. Shared, read only.

    Built once per session by the real engine (CLI, relative sample paths) into `engine_2000_base`.
    Tests that edit the run copy it with `copy_runs`; the fixture checks at the end of the session
    that the shared run folder did not change.
    """
    run = _shared_engine_run(engine_2000_base, T1_FAULTY_2000_ID, *_t1_args("faulty"), 2000, 1)
    state = _tree_state(run.run_dir)
    yield run
    _assert_shared_run_unchanged(run, state)


@pytest.fixture(scope="session")
def t1_correct_2000(engine_2000_base):
    """T1 correct, 2000 cases, seed 42: ALIVE, exit 0, run 29c15f04407b. Shared, read only."""
    run = _shared_engine_run(engine_2000_base, T1_CORRECT_2000_ID, *_t1_args("correct"), 2000, 0)
    state = _tree_state(run.run_dir)
    yield run
    _assert_shared_run_unchanged(run, state)


@pytest.fixture(scope="session")
def credit_fees_2000(engine_2000_base):
    """credit-fees correct port, 2000 cases, seed 42: ALIVE, exit 0, run df4d7929ce44. Shared, read only."""
    run = _shared_engine_run(
        engine_2000_base, CREDIT_FEES_2000_ID,
        f"{CREDIT_FEES_SAMPLE}/CREDIT-FEES.cob", f"{CREDIT_FEES_SAMPLE}/copybooks",
        f"{CREDIT_FEES_SAMPLE}/java/CreditFees.java", f"{CREDIT_FEES_SAMPLE}/schema.json", 2000, 0,
    )
    state = _tree_state(run.run_dir)
    yield run
    _assert_shared_run_unchanged(run, state)


@pytest.fixture(scope="session")
def t1_faulty_200(tmp_path_factory):
    """T1 faulty, 200 cases, seed 42: ZOMBIE, exit 1. Shared by the tests that only read the run."""
    run = _shared_engine_run(tmp_path_factory.mktemp("t1_faulty_200"), None, *_t1_args("faulty"), 200, 1)
    state = _tree_state(run.run_dir)
    yield run
    _assert_shared_run_unchanged(run, state)


@pytest.fixture(scope="session")
def t1_correct_200(tmp_path_factory):
    """T1 correct, 200 cases, seed 42: ALIVE, exit 0. Shared by the tests that only read the run."""
    run = _shared_engine_run(tmp_path_factory.mktemp("t1_correct_200"), None, *_t1_args("correct"), 200, 0)
    state = _tree_state(run.run_dir)
    yield run
    _assert_shared_run_unchanged(run, state)


@pytest.fixture(scope="session")
def t1_faulty_30(tmp_path_factory):
    """T1 faulty, 30 cases, seed 42: ZOMBIE, exit 1. Shared; a test that edits it copies it first."""
    run = _shared_engine_run(tmp_path_factory.mktemp("t1_faulty_30"), None, *_t1_args("faulty"), 30, 1)
    assert json.loads((run.run_dir / "verdict.json").read_text())["status"] == "ZOMBIE"
    state = _tree_state(run.run_dir)
    yield run
    _assert_shared_run_unchanged(run, state)


# Faulty port of each trap T2 to T5 at 200 cases, seed 42: (sample folder, COBOL file, Java class, run id).
# The run ids were measured before the amount difference file was added and must not change.
TRAP_FAULTY_200 = {
    "T2": ("T2-rounding", "ROUNDING-CALC", "RoundingCalc", "20d699eb804a"),
    "T3": ("T3-comp3-sign", "COMP3-SIGN", "Comp3Sign", "38ae1c058b27"),
    "T4": ("T4-zoned-overpunch", "ZONED-OVERPUNCH", "ZonedOverpunch", "0eeb10e0d21b"),
    "T5": ("T5-redefines-invalid", "REDEFINES-INVALID", "RedefinesInvalid", "92c502344514"),
}


@pytest.fixture(scope="session", params=list(TRAP_FAULTY_200))
def trap_faulty_200(request, tmp_path_factory):
    """The faulty port of T2, T3, T4 and T5 at 200 cases, seed 42: ZOMBIE, exit 1. Shared, read only.

    Each run is its own real engine audit in its own temporary base directory; the run id is asserted.
    """
    folder, cobol, java_class, run_id = TRAP_FAULTY_200[request.param]
    sample = f"samples/traps/{folder}"
    copybooks = f"{sample}/copybooks" if (REPO_ROOT / sample / "copybooks").is_dir() else sample
    run = _shared_engine_run(
        tmp_path_factory.mktemp(f"{request.param.lower()}_faulty_200"), run_id,
        f"{sample}/{cobol}.cob", copybooks, f"{sample}/java/faulty/{java_class}.java", f"{sample}/schema.json", 200, 1,
    )
    state = _tree_state(run.run_dir)
    yield request.param, run
    _assert_shared_run_unchanged(run, state)


def _credit_fees_args(java: str) -> tuple:
    return (f"{CREDIT_FEES_SAMPLE}/CREDIT-FEES.cob", f"{CREDIT_FEES_SAMPLE}/copybooks",
            java, f"{CREDIT_FEES_SAMPLE}/schema.json")


@pytest.fixture(scope="session")
def credit_fees_alive_30(tmp_path_factory):
    """credit-fees correct port, 30 cases, seed 42: ALIVE, exit 0. Shared; a test that edits it copies it first."""
    run = _shared_engine_run(
        tmp_path_factory.mktemp("credit_fees_alive_30"), None,
        *_credit_fees_args(f"{CREDIT_FEES_SAMPLE}/java/CreditFees.java"), 30, 0,
    )
    assert json.loads((run.run_dir / "verdict.json").read_text())["status"] == "ALIVE"
    state = _tree_state(run.run_dir)
    yield run
    _assert_shared_run_unchanged(run, state)


@pytest.fixture(scope="session")
def credit_fees_half_even_30(tmp_path_factory):
    """credit-fees HALF_EVEN variant, 30 cases, seed 42: ZOMBIE, exit 1. Shared; copy it before editing.

    The variant is generated from the correct port into the fixture's own base directory, which stays
    in place for the whole session because the certificate records the path of the Java file.
    """
    from coroner.catalog.legacy_variant import generate_half_even_variant

    base = tmp_path_factory.mktemp("credit_fees_half_even_30")
    variant = base / "variant" / "CreditFees.java"
    variant.parent.mkdir()
    generate_half_even_variant(str(REPO_ROOT / CREDIT_FEES_SAMPLE / "java" / "CreditFees.java"), str(variant))
    run = _shared_engine_run(base, None, *_credit_fees_args(str(variant)), 30, 1)
    assert json.loads((run.run_dir / "verdict.json").read_text())["status"] == "ZOMBIE"
    state = _tree_state(run.run_dir)
    yield run
    _assert_shared_run_unchanged(run, state)


@pytest.fixture
def t1_faulty_run(t1_faulty_200):
    """A real T1 faulty run at 200 cases for UI tests: (run id, base directory). Read only."""
    return t1_faulty_200.run_id, t1_faulty_200.base


@pytest.fixture
def t1_correct_run(t1_correct_200):
    """A real T1 correct run at 200 cases for UI tests: (run id, base directory). Read only."""
    return t1_correct_200.run_id, t1_correct_200.base


STORY_CASES = 9


@pytest.fixture(scope="session")
def story_runs(tmp_path_factory):
    """
    The real trap catalog of the guided story tests, produced once per session.

    run_catalog runs the faulty and the correct port of T1 to T5 with the real engine into a
    temporary base directory and write_catalog_files writes runs/trap_catalog.json there. The
    repository runs/ folder is never read or written: its listing is checked before and after.

    Case count: 9, seed 42. It is the smallest count at which the faulty ports of T1, T2 and T4
    are all ZOMBIE (measured with `run_verify`, seed 42, counts 1 to 9 and 10 to 28 on the
    operator machine, GnuCOBOL 3.2.0): at 9 cases T1 diverges on 4, T2 on 7 and T4 on 1; at 8
    cases T4 is ALIVE (0 divergent cases). The fixture asserts the three verdicts, so a
    generator change that lowers one of them fails here and not in a later test.

    Returns a namedtuple (base, cases, catalog, repo_catalog_before): the base directory to give to the
    story data layer, the case count, the dict returned by run_catalog, and the state (mtime and SHA-256,
    or None when absent) of the repository's runs/trap_catalog.json taken before the catalog was built.
    This is the one shared catalog of the session: the story, fool-independent UI and Detection Matrix
    tests read it, and a test that writes to it copies it first.
    """
    from collections import namedtuple

    from coroner.traps import run_catalog, write_catalog_files

    repo_runs = Path(__file__).resolve().parent.parent / "runs"
    before = _folder_listing(repo_runs)
    catalog_before = file_state(repo_runs / "trap_catalog.json")

    base = tmp_path_factory.mktemp("story_runs")
    catalog = run_catalog(seed=42, cases=STORY_CASES, base_dir=str(base))
    write_catalog_files(catalog, base_dir=str(base))

    by_id = {trap["id"]: trap for trap in catalog["traps"]}
    for trap_id in ("T1", "T2", "T4"):
        assert by_id[trap_id]["cases_detected"] >= 1, (
            f"{trap_id} faulty port is not ZOMBIE at {STORY_CASES} cases"
        )
    assert _folder_listing(repo_runs) == before, "the story catalog touched the repository runs/ folder"

    return namedtuple("StoryRuns", "base cases catalog repo_catalog_before")(
        base, STORY_CASES, catalog, catalog_before,
    )


@pytest.fixture
def story_client(story_runs, monkeypatch):
    """A test client whose base directory is the real catalog of `story_runs`, with a clean gate cache."""
    from fastapi.testclient import TestClient

    from coroner.ui.app import app, clear_gate_check_cache

    monkeypatch.setenv("CORONER_BASE_DIR", str(story_runs.base))
    clear_gate_check_cache()
    yield TestClient(app)
    clear_gate_check_cache()


FOOL_CASES = 20


@pytest.fixture(scope="session")
def fool_runs(tmp_path_factory):
    """
    The real runs of the fool page tests, produced once per session in a temporary base directory.

    The trap catalog (faulty and correct port of T1 to T5), the credit-fees correct run and the
    credit-fees HALF_EVEN variant run are all made with the real engine at the same case count and
    seed 42, because the page finds the credit-fees runs by the case count and seed of the catalog.

    Case count: 20. Measured with `run_verify` on the credit-fees HALF_EVEN variant, seed 42: 9, 10,
    12 and 15 cases are ALIVE (no divergent case), 20 cases and more are ZOMBIE. T1, T2 and T4
    faulty ports are already ZOMBIE at 9 cases (see `story_runs`). The fixture asserts the verdicts.
    The repository runs/ folder is never read or written: its listing is checked before and after.

    Returns a namedtuple (base, cases, catalog, half_even_run, correct_run): the base directory, the
    case count, the dict returned by run_catalog and the two credit-fees run ids returned by run_verify.
    """
    from collections import namedtuple

    from coroner.catalog.legacy_variant import generate_half_even_variant
    from coroner.cli import run_verify
    from coroner.traps import run_catalog, write_catalog_files

    repo = Path(__file__).resolve().parent.parent
    before = _folder_listing(repo / "runs")

    base = tmp_path_factory.mktemp("fool_runs")
    catalog = run_catalog(seed=42, cases=FOOL_CASES, base_dir=str(base))
    write_catalog_files(catalog, base_dir=str(base))

    variant = base / "build" / "variants" / "CreditFees.java"
    variant.parent.mkdir(parents=True)
    generate_half_even_variant(str(repo / "samples/credit-fees/java/CreditFees.java"), str(variant))

    def credit_fees_run(java_file):
        _, run_dir = run_verify(
            cobol_path=str(repo / "samples/credit-fees/CREDIT-FEES.cob"),
            copybooks_dir=str(repo / "samples/credit-fees/copybooks"),
            java_path=str(java_file),
            schema_path=str(repo / "samples/credit-fees/schema.json"),
            num_cases=FOOL_CASES,
            seed=42,
            timings=False,
            base_dir=str(base),
        )
        return run_dir.name, json.loads((run_dir / "verdict.json").read_text())["status"]

    half_even_id, half_even_status = credit_fees_run(variant)
    correct_id, correct_status = credit_fees_run(repo / "samples/credit-fees/java/CreditFees.java")
    assert half_even_status == "ZOMBIE", f"HALF_EVEN variant is not ZOMBIE at {FOOL_CASES} cases"
    assert correct_status == "ALIVE"
    by_id = {trap["id"]: trap for trap in catalog["traps"]}
    for trap_id in ("T1", "T4"):
        assert by_id[trap_id]["cases_detected"] >= 1, f"{trap_id} faulty port is not ZOMBIE at {FOOL_CASES} cases"
    assert _folder_listing(repo / "runs") == before, "the fool runs touched the repository runs/ folder"

    return namedtuple("FoolRuns", "base cases catalog half_even_run correct_run")(
        base, FOOL_CASES, catalog, half_even_id, correct_id,
    )


@pytest.fixture
def fool_client(fool_runs, monkeypatch):
    """A test client whose base directory is the real runs of `fool_runs`."""
    from fastapi.testclient import TestClient

    from coroner.ui.app import app

    monkeypatch.setenv("CORONER_BASE_DIR", str(fool_runs.base))
    return TestClient(app)
