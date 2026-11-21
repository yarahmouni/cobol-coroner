"""Pytest configuration for Coroner tests."""
import json
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


@pytest.fixture(scope="module")
def t1_faulty_run(tmp_path_factory):
    """Create a real T1 faulty run at 200 cases for UI tests."""
    from coroner.cli import run_verify
    
    tmp_path = tmp_path_factory.mktemp("t1_faulty")
    
    cobol_file = Path("samples/traps/T1-ebcdic-match-merge/MATCH-MERGE.cob").resolve()
    copybooks = Path("samples/traps/T1-ebcdic-match-merge/copybooks").resolve()
    java_file = Path("samples/traps/T1-ebcdic-match-merge/java/faulty/MatchMerge.java").resolve()
    schema_file = Path("samples/traps/T1-ebcdic-match-merge/schema.json").resolve()
    
    verdict, run_dir = run_verify(
        cobol_path=str(cobol_file),
        copybooks_dir=str(copybooks),
        java_path=str(java_file),
        schema_path=str(schema_file),
        num_cases=200,
        seed=42,
        timings=False,
        base_dir=str(tmp_path),
    )
    
    return run_dir.name, tmp_path


@pytest.fixture(scope="module")
def t1_correct_run(tmp_path_factory):
    """Create a real T1 correct run at 200 cases for UI tests."""
    from coroner.cli import run_verify
    
    tmp_path = tmp_path_factory.mktemp("t1_correct")
    
    cobol_file = Path("samples/traps/T1-ebcdic-match-merge/MATCH-MERGE.cob").resolve()
    copybooks = Path("samples/traps/T1-ebcdic-match-merge/copybooks").resolve()
    java_file = Path("samples/traps/T1-ebcdic-match-merge/java/correct/MatchMerge.java").resolve()
    schema_file = Path("samples/traps/T1-ebcdic-match-merge/schema.json").resolve()
    
    verdict, run_dir = run_verify(
        cobol_path=str(cobol_file),
        copybooks_dir=str(copybooks),
        java_path=str(java_file),
        schema_path=str(schema_file),
        num_cases=200,
        seed=42,
        timings=False,
        base_dir=str(tmp_path),
    )
    
    return run_dir.name, tmp_path


STORY_CASES = 9


def _folder_listing(folder: Path) -> list:
    """Names and modification times of the entries of a folder (empty if it does not exist)."""
    if not folder.exists():
        return []
    return sorted((p.name, p.stat().st_mtime_ns) for p in folder.iterdir())


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

    Returns a namedtuple (base, cases, catalog): the base directory to give to the story data
    layer, the case count, and the dict returned by run_catalog.
    """
    from collections import namedtuple

    from coroner.traps import run_catalog, write_catalog_files

    repo_runs = Path(__file__).resolve().parent.parent / "runs"
    before = _folder_listing(repo_runs)

    base = tmp_path_factory.mktemp("story_runs")
    catalog = run_catalog(seed=42, cases=STORY_CASES, base_dir=str(base))
    write_catalog_files(catalog, base_dir=str(base))

    by_id = {trap["id"]: trap for trap in catalog["traps"]}
    for trap_id in ("T1", "T2", "T4"):
        assert by_id[trap_id]["cases_detected"] >= 1, (
            f"{trap_id} faulty port is not ZOMBIE at {STORY_CASES} cases"
        )
    assert _folder_listing(repo_runs) == before, "the story catalog touched the repository runs/ folder"

    return namedtuple("StoryRuns", "base cases catalog")(base, STORY_CASES, catalog)


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
