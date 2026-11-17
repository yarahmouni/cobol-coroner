"""Pytest configuration for Coroner tests."""
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
