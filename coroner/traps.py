"""Trap catalog runner."""
import hashlib
import io
import json
import os
import re
import shutil
import sys
import tempfile
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any, Callable

from coroner.cases import load_cases_registry
from coroner.cli import run_verify
from coroner.diag.card import generate_card
from coroner.diag.report import FailureReport
from coroner.parse.schema import load_schema
from coroner.store import copybook_file_hashes
from coroner.verdict import Verdict


TRAPS_DIR = Path("samples/traps")
RUNS_DIR = Path("runs")
RUN_ID_PATTERN = re.compile(r"[0-9a-f]{12}")


class CatalogError(Exception):
    """The catalog cannot be built without risking an existing run folder."""


@dataclass
class TrapSetup:
    """Files and metadata of one trap that the catalog needs."""
    trap_id: str
    metadata: dict
    cobol_file: Path
    schema_file: Path
    schema: Any
    copybooks_dir: Path
    faulty_java_file: Path
    correct_java_file: Path


def _fail(message: str) -> None:
    print(f"ERROR: {message}", file=sys.stderr)
    sys.exit(2)


def _trap_setup(trap_id: str, registry: dict) -> TrapSetup:
    """Locate the files of one trap. Exits with status 2 when something is missing."""
    if trap_id not in registry:
        _fail(f"Trap {trap_id} has no entry in the case registry")
    trap_dir = TRAPS_DIR / _trap_folder_name(trap_id)

    if not trap_dir.exists():
        _fail(f"Trap {trap_id} directory not found at {trap_dir}")

    trap_json_path = trap_dir / "trap.json"
    if not trap_json_path.exists():
        _fail(f"Trap {trap_id} metadata not found: {trap_json_path}")
    with open(trap_json_path) as f:
        trap_metadata = json.load(f)

    cobol_files = list(trap_dir.glob("*.cob"))
    if not cobol_files:
        _fail(f"Trap {trap_id} has no COBOL file in {trap_dir}")

    schema_file = trap_dir / "schema.json"
    if not schema_file.exists():
        _fail(f"Trap {trap_id} has no schema.json in {trap_dir}")

    # Copybooks: use copybooks/ if it exists, otherwise the trap folder itself
    copybooks_dir = trap_dir / "copybooks"
    if not copybooks_dir.exists():
        copybooks_dir = trap_dir

    faulty_java_files = list((trap_dir / "java" / "faulty").glob("*.java"))
    if not faulty_java_files:
        _fail(f"Trap {trap_id} has no faulty Java in {trap_dir}")
    correct_java_files = list((trap_dir / "java" / "correct").glob("*.java"))
    if not correct_java_files:
        _fail(f"Trap {trap_id} has no correct Java in {trap_dir}")

    return TrapSetup(
        trap_id=trap_id,
        metadata=trap_metadata,
        cobol_file=cobol_files[0],
        schema_file=schema_file,
        schema=load_schema(str(schema_file)),
        copybooks_dir=copybooks_dir,
        faulty_java_file=faulty_java_files[0],
        correct_java_file=correct_java_files[0],
    )


def _build_trap_entry(
    setup: TrapSetup,
    registry: dict,
    cases: int,
    faulty_verdict: Verdict,
    faulty_run_dir: Path,
    correct_verdict: Verdict,
    correct_run_dir: Path,
) -> dict[str, Any]:
    """The catalog entry of one trap, built from the verdicts and the files of its two runs."""
    trap_id = setup.trap_id
    trap_metadata = setup.metadata
    trap_result: dict[str, Any] = {
        "id": trap_id,
        "title": trap_metadata["title"],
        "status": "measured",
        "case_number": registry[trap_id]["case"],
        "case_name": registry[trap_id]["name"],
    }

    trap_result["cases_generated"] = cases
    trap_result["cases_detected"] = faulty_verdict.cases_divergent

    # Detection rate as a 4-decimal string
    if cases > 0:
        rate = trap_result["cases_detected"] / cases
        trap_result["detection_rate"] = f"{rate:.4f}"
    else:
        trap_result["detection_rate"] = "0.0000"

    trap_result["faulty_run_id"] = faulty_run_dir.name

    # Load failure report for minimal case and COBOL lines
    failure_report_path = faulty_run_dir / "failure_report.json"
    if failure_report_path.exists():
        with open(failure_report_path) as f:
            failure_report_json = json.load(f)

        # Reconstruct FailureReport object for the reviewed card generator
        failure_report_obj = FailureReport(
            case_id=failure_report_json["case_id"],
            input_row=failure_report_json["input_row"],
            cobol_output=failure_report_json["cobol_output"],
            java_output=failure_report_json["java_output"],
            divergent_fields=failure_report_json["divergent_fields"],
            cobol_return_code=failure_report_json.get("cobol_return_code", 0),
            java_return_code=failure_report_json.get("java_return_code", 0),
            executed_lines=failure_report_json.get("executed_lines", []),
            original_case_rows=failure_report_json.get("original_case_rows"),
            minimal_case_rows=failure_report_json.get("minimal_case_rows")
        )

        trap_result["minimal_case"] = failure_report_json

        # COBOL lines: use the reviewed "COBOL lines involved" rule from card.py
        # which filters to relevant statements only
        card_text = generate_card(
            failure_report=failure_report_obj,
            schema=setup.schema,
            cobol_source_path=str(setup.cobol_file),
            copybook_dir=str(setup.copybooks_dir),
            trap_title=trap_metadata["title"],
            probable_cause=trap_metadata["probable_cause"],
            suggested_fix=trap_metadata["fix_sentence"]
        )

        trap_result["card"] = card_text

        # Extract COBOL lines from the card (they are formatted as "file:line STATEMENT")
        # For the JSON, store as a list of "file:line" strings
        if "COBOL lines involved:" in card_text:
            lines_section = card_text.split("COBOL lines involved:")[1].split("\n")[0]
            cobol_lines_raw = [line.strip() for line in lines_section.split(";") if line.strip()]
            # Extract just "file:line" part
            trap_result["cobol_lines"] = [line.split(" ")[0] for line in cobol_lines_raw]
        else:
            trap_result["cobol_lines"] = []
    else:
        trap_result["minimal_case"] = {}
        trap_result["cobol_lines"] = []
        trap_result["card"] = ""

    # Add metadata
    trap_result["probable_cause"] = trap_metadata["probable_cause"]
    trap_result["fix_sentence"] = trap_metadata["fix_sentence"]

    # For T1, add exposure fields from verdict
    if trap_id == "T1":
        if faulty_verdict.exposure_sum is not None:
            trap_result["exposure_sum"] = f"{faulty_verdict.exposure_sum:.2f}"
        else:
            trap_result["exposure_sum"] = "0.00"

        if faulty_verdict.exposure_max is not None:
            trap_result["max_exposure"] = f"{faulty_verdict.exposure_max:.2f}"
        else:
            trap_result["max_exposure"] = "0.00"

        trap_result["affected_branches"] = faulty_verdict.affected_branches or 0
        trap_result["grand_total_matches"] = faulty_verdict.grand_total_matches or False

    trap_result["correct_run_id"] = correct_run_dir.name
    trap_result["correct_verdict"] = correct_verdict.status

    return trap_result


def _t6_placeholder(registry: dict) -> dict[str, Any]:
    if "T6" not in registry:
        _fail("Trap T6 has no entry in the case registry")
    return {
        "id": "T6",
        "title": "Reserved for owner field trap",
        "status": "placeholder: owner field trap pending",
        "case_number": registry["T6"]["case"],
        "case_name": registry["T6"]["name"],
    }


# A run getter returns (verdict, run directory) for the "faulty" or "correct" port of a trap.
RunGetter = Callable[[str, TrapSetup], tuple[Verdict, Path]]


def _build_catalog(cases: int, get_run: RunGetter) -> dict[str, Any]:
    registry = load_cases_registry()
    results = []
    for trap_id in ["T1", "T2", "T3", "T4", "T5"]:
        setup = _trap_setup(trap_id, registry)
        faulty_verdict, faulty_run_dir = get_run("faulty", setup)
        correct_verdict, correct_run_dir = get_run("correct", setup)
        results.append(_build_trap_entry(
            setup, registry, cases, faulty_verdict, faulty_run_dir, correct_verdict, correct_run_dir
        ))
    results.append(_t6_placeholder(registry))
    return {"traps": results}


def run_catalog(seed: int = 42, cases: int = 2000, base_dir: str = ".") -> dict[str, Any]:
    """
    Run the catalog on all built traps: the engine runs the faulty and the correct port of
    every trap, whether or not a run with the same content already exists.

    Args:
        seed: Random seed
        cases: Number of cases to generate
        base_dir: Base directory for runs/ and build/ (default current directory)

    Returns:
        Catalog dict with results for all traps
    """
    def get_run(kind: str, setup: TrapSetup) -> tuple[Verdict, Path]:
        if kind == "faulty":
            print(f"\nRunning {setup.trap_id} faulty Java...")
            java_file = setup.faulty_java_file
        else:
            print(f"Running {setup.trap_id} correct Java...")
            java_file = setup.correct_java_file
        try:
            return run_verify(
                cobol_path=str(setup.cobol_file),
                java_path=str(java_file),
                schema_path=str(setup.schema_file),
                copybooks_dir=str(setup.copybooks_dir),
                num_cases=cases,
                seed=seed,
                timings=False,
                base_dir=base_dir
            )
        except Exception as e:
            _fail(f"{kind.capitalize()} run failed for {setup.trap_id}: {e}")

    return _build_catalog(cases, get_run)


def _file_sha256(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _index_runs(runs_dir: Path) -> list[tuple[Path, dict]]:
    """
    (run folder, inputs.json content) of every complete run in runs/.

    A run is complete when it has a readable inputs.json and a verdict.json. Anything else in
    runs/ (catalog files, folders without a verdict) is left alone and never matched.
    """
    index = []
    if not runs_dir.is_dir():
        return index
    for run_dir in sorted(runs_dir.iterdir()):
        if not run_dir.is_dir() or not RUN_ID_PATTERN.fullmatch(run_dir.name):
            continue
        inputs_path = run_dir / "inputs.json"
        if not inputs_path.is_file() or not (run_dir / "verdict.json").is_file():
            continue
        try:
            inputs = json.loads(inputs_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if isinstance(inputs, dict):
            index.append((run_dir, inputs))
    return index


def _inputs_match(inputs: dict, cobol_sha: str, java_sha: str, schema_sha: str,
                  copybooks: dict[str, str], seed: int, cases: int) -> bool:
    """True when inputs.json records exactly these sources, seed and case count."""
    try:
        recorded_copybooks = {cb["name"]: cb["sha256"] for cb in inputs["copybook_hashes"]}
    except (KeyError, TypeError):
        return False
    return (
        inputs.get("cobol_source_sha256") == cobol_sha
        and inputs.get("java_source_sha256") == java_sha
        and inputs.get("schema_sha256") == schema_sha
        and recorded_copybooks == copybooks
        and inputs.get("seed") == seed
        and inputs.get("case_count") == cases
    )


def _verdict_from_run(run_dir: Path) -> Verdict:
    """The Verdict stored in a run's verdict.json."""
    data = json.loads((run_dir / "verdict.json").read_text(encoding="utf-8"))

    def decimal(key: str) -> Decimal | None:
        value = data.get(key)
        return Decimal(value) if value is not None else None

    return Verdict(
        status=data["status"],
        sub_label=data["sub_label"],
        cases_total=data["cases_total"],
        cases_divergent=data["cases_divergent"],
        run_return_codes=tuple(data["run_return_codes"]),
        validation_notice=data.get("validation_notice", "Validated under GnuCOBOL 3.x"),
        exposure_sum=decimal("exposure_sum"),
        exposure_max=decimal("exposure_max"),
        affected_branches=data.get("affected_branches"),
        suspense_difference=decimal("suspense_difference"),
        grand_total_matches=data.get("grand_total_matches"),
    )


def _generate_missing_run(kind: str, setup: TrapSetup, java_file: Path, seed: int,
                          cases: int, base_dir: str) -> tuple[Verdict, Path]:
    """
    Run the engine for a port that has no run yet, then move the finished run into runs/.

    The engine writes into a scratch base directory, so nothing in runs/ is touched while it
    works. The run id is the one the engine computed. If runs/<run id> already exists the
    run is thrown away and CatalogError is raised: an existing folder is never overwritten.
    """
    base = Path(base_dir)
    (base / "build").mkdir(parents=True, exist_ok=True)
    scratch = Path(tempfile.mkdtemp(prefix=".catalog-scratch-", dir=base / "build"))
    try:
        try:
            verdict, scratch_run_dir = run_verify(
                cobol_path=str(setup.cobol_file),
                java_path=str(java_file),
                schema_path=str(setup.schema_file),
                copybooks_dir=str(setup.copybooks_dir),
                num_cases=cases,
                seed=seed,
                timings=False,
                base_dir=str(scratch)
            )
        except Exception as e:
            _fail(f"{kind.capitalize()} run failed for {setup.trap_id}: {e}")
        target = base / "runs" / scratch_run_dir.name
        if target.exists():
            raise CatalogError(
                f"run folder {target} already exists but no complete run with the inputs of "
                f"{setup.trap_id} {kind} was found in it. It is left untouched and the "
                f"catalog is not written."
            )
        target.parent.mkdir(parents=True, exist_ok=True)
        os.rename(scratch_run_dir, target)
        return verdict, target
    finally:
        shutil.rmtree(scratch, ignore_errors=True)


def catalog_from_runs(seed: int = 42, cases: int = 2000, base_dir: str = ".") -> dict[str, Any]:
    """
    Build the catalog from the runs already in <base_dir>/runs.

    For each trap and port, the run is found by reading runs/*/inputs.json: the COBOL source,
    Java source, schema and copybook hashes, the seed and the case count must equal those of the
    trap's files. No engine call is made for a port whose run exists, and no run folder is
    modified. When several runs match, the newest by inputs.json timestamp is used.

    A port with no matching run is run once into a scratch folder and moved into runs/; if its
    run folder already exists, CatalogError is raised before anything is written.
    """
    index = _index_runs(Path(base_dir) / "runs")

    def get_run(kind: str, setup: TrapSetup) -> tuple[Verdict, Path]:
        java_file = setup.faulty_java_file if kind == "faulty" else setup.correct_java_file
        cobol_sha = _file_sha256(setup.cobol_file)
        java_sha = _file_sha256(java_file)
        schema_sha = _file_sha256(setup.schema_file)
        copybooks = copybook_file_hashes(str(setup.copybooks_dir))
        found = [
            (inputs.get("timestamp", ""), run_dir.name, run_dir)
            for run_dir, inputs in index
            if _inputs_match(inputs, cobol_sha, java_sha, schema_sha, copybooks, seed, cases)
        ]
        if found:
            run_dir = max(found)[2]
            print(f"Kept existing run {run_dir.name} for {setup.trap_id} {kind}")
            return _verdict_from_run(run_dir), run_dir
        print(f"No run found for {setup.trap_id} {kind}, generating it")
        verdict, run_dir = _generate_missing_run(kind, setup, java_file, seed, cases, base_dir)
        index.append((run_dir, json.loads((run_dir / "inputs.json").read_text(encoding="utf-8"))))
        print(f"Generated run {run_dir.name} for {setup.trap_id} {kind}")
        return verdict, run_dir

    return _build_catalog(cases, get_run)


def _trap_folder_name(trap_id: str) -> str:
    """Get the full folder name for a trap ID."""
    names = {
        "T1": "T1-ebcdic-match-merge",
        "T2": "T2-rounding",
        "T3": "T3-comp3-sign",
        "T4": "T4-zoned-overpunch",
        "T5": "T5-redefines-invalid",
        "T6": "T6-reserved"
    }
    return names.get(trap_id, "")


def _write_atomically(path: Path, text: str) -> None:
    """Write text to a temporary file in the same folder, then os.replace it onto path."""
    fd, temp_name = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
        os.chmod(temp_name, 0o644)
        os.replace(temp_name, path)
    except BaseException:
        try:
            os.unlink(temp_name)
        except OSError:
            pass
        raise


def render_catalog_text(catalog: dict[str, Any]) -> str:
    """Text rendering of the catalog."""
    f = io.StringIO()
    f.write("Six banking migration traps that silently corrupt amounts, signs, ordering or control totals.\n")
    f.write("targeted regression traps within its supported COBOL subset.\n\n")

    for trap in catalog["traps"]:
        f.write(f"== Case {trap['case_number']} {trap['case_name']} ({trap['id']}): {trap['title']} ==\n")
        f.write(f"Status: {trap['status']}\n")

        if trap["status"] == "measured":
            f.write(f"Cases generated: {trap['cases_generated']}\n")
            f.write(f"Cases detected: {trap['cases_detected']}\n")
            f.write(f"Detection rate: {trap['detection_rate']}\n")
            f.write(f"Correct Java verdict: {trap['correct_verdict']}\n")
            f.write(f"Faulty run: {trap['faulty_run_id']}\n")
            f.write(f"Correct run: {trap['correct_run_id']}\n")

            # T1 exposure
            if trap["id"] == "T1":
                f.write(f"Unreconciled branch exposure: sum {trap['exposure_sum']}, max {trap['max_exposure']}\n")
                f.write(f"Affected branches: {trap['affected_branches']}\n")
                f.write(f"Grand total matches: {trap['grand_total_matches']}\n")

            if trap.get("card"):
                f.write(f"\n{trap['card']}\n")

            if trap.get("cobol_lines"):
                f.write("\nCOBOL lines executed in minimal case:\n")
                for line in trap["cobol_lines"][:10]:  # Show first 10
                    f.write(f"  {line}\n")

        f.write("\n")
    return f.getvalue()


def write_catalog_files(catalog: dict[str, Any], base_dir: str = ".") -> None:
    """
    Write catalog JSON and text files, each atomically (temporary file, then os.replace).

    These two files are the only files in runs/ that are not inside a run folder.

    Args:
        catalog: Catalog dict with trap results
        base_dir: Base directory for runs/ (default current directory)
    """
    runs_dir = Path(base_dir) / "runs"
    runs_dir.mkdir(exist_ok=True)

    # Write JSON with sorted keys
    json_path = runs_dir / "trap_catalog.json"
    _write_atomically(json_path, json.dumps(catalog, indent=2, sort_keys=True))
    print(f"\nWrote {json_path}")

    # Write text rendering
    txt_path = runs_dir / "trap_catalog.txt"
    _write_atomically(txt_path, render_catalog_text(catalog))
    print(f"Wrote {txt_path}")


def main() -> None:
    """CLI entry point for trap catalog."""
    import argparse

    parser = argparse.ArgumentParser(description="Run trap catalog")
    parser.add_argument("--cases", type=int, default=2000, help="Number of cases")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    parser.add_argument("--from-runs", action="store_true",
                        help="Build the catalog from existing runs, without running the engine for them")

    args = parser.parse_args()

    if args.from_runs:
        catalog = catalog_from_runs(seed=args.seed, cases=args.cases)
    else:
        catalog = run_catalog(seed=args.seed, cases=args.cases)
    write_catalog_files(catalog)


if __name__ == "__main__":
    main()
