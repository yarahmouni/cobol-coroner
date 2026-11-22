"""The amount difference of a run, kept in a derived file next to the run's own files.

runs/<run_id>/amount_difference.json holds the money figure of a ZOMBIE run that has no branch
exposure (Cases 2 to 5 and credit-fees): the sum and the largest of |COBOL - Java| over the
divergent decimal output values and how many amounts differ, in exact Decimal arithmetic.

It is a derived file, not part of the run's record: no other file of the run (verdict.json,
certificate.json, inputs.json, ...) mentions it, so the run id and the certificate do not depend on
it. The engine writes it for a new run; `python -m coroner derive --from-runs` writes it for an
existing run from the run's own files (comparison_results.json, verdict.json, and the schema the
run recorded in inputs.json, checked by its SHA-256) and never changes any file of the run.
"""

import hashlib
import json
import os
import re
import tempfile
from decimal import Decimal, InvalidOperation
from pathlib import Path

from coroner.verdict import amount_difference_from_fields, decimal_output_columns

AMOUNT_FILE = "amount_difference.json"
FORMAT_VERSION = 1
SOURCE = "comparison_results.json"
RUN_ID_PATTERN = re.compile(r"^[0-9a-f]{12}$")
REPO_ROOT = Path(__file__).resolve().parent.parent

# Outcomes of derive_run
WRITTEN = "written"
EXISTS = "exists"
NOT_APPLICABLE = "not applicable"
NO_FIGURE = "no figure"
ERROR = "error"


def amount_record(figure: tuple[Decimal, Decimal, int], schema_sha256: str) -> dict:
    """The content of amount_difference.json for a figure (sum, largest, count)."""
    total, largest, count = figure
    return {
        "format": FORMAT_VERSION,
        "source": SOURCE,
        "schema_sha256": schema_sha256,
        "sum_of_absolute_differences": format(total, "f"),
        "largest_difference": format(largest, "f"),
        "amounts_affected": count,
    }


def write_amount_difference(run_dir, figure: tuple[Decimal, Decimal, int], schema_sha256: str) -> Path:
    """Write amount_difference.json atomically (temporary file in the run folder, then rename)."""
    run_dir = Path(run_dir)
    run_dir.mkdir(parents=True, exist_ok=True)
    final = run_dir / AMOUNT_FILE
    fd, temp_path = tempfile.mkstemp(dir=run_dir, prefix=".amount_", suffix=".json.tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(amount_record(figure, schema_sha256), handle, indent=2, sort_keys=True)
            handle.write("\n")
        os.replace(temp_path, final)
    except BaseException:
        try:
            os.unlink(temp_path)
        except OSError:
            pass
        raise
    return final


def read_amount_difference(run_dir) -> dict | None:
    """
    The one reader of the figure: the content of <run_dir>/amount_difference.json, or None when the
    file is absent, unreadable or not a figure (amounts and count are checked, nothing is guessed).
    The amounts are returned as the decimal strings the engine wrote.
    """
    try:
        data = json.loads((Path(run_dir) / AMOUNT_FILE).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(data, dict):
        return None
    for key in ("sum_of_absolute_differences", "largest_difference"):
        value = data.get(key)
        if not isinstance(value, str):
            return None
        try:
            if not Decimal(value).is_finite():
                return None
        except InvalidOperation:
            return None
    count = data.get("amounts_affected")
    if isinstance(count, bool) or not isinstance(count, int) or count <= 0:
        return None
    return data


def _recorded_schema(inputs: dict):
    """The schema file a run recorded, found by its SHA-256 (it may be a relative path), or None."""
    recorded = inputs.get("schema_file")
    expected = inputs.get("schema_sha256")
    if not isinstance(recorded, str) or not recorded or not isinstance(expected, str):
        return None
    candidate_paths = [Path(recorded)] if Path(recorded).is_absolute() else [REPO_ROOT / recorded, Path.cwd() / recorded]
    for path in candidate_paths:
        if path.is_file() and hashlib.sha256(path.read_bytes()).hexdigest() == expected:
            return path
    return None


def derive_run(run_dir) -> tuple[str, str]:
    """
    Write amount_difference.json for one existing run when it should have one and has none.
    Returns (outcome, detail). No existing file of the run is opened for writing.

    EXISTS: the file is already there. NOT_APPLICABLE: not a ZOMBIE run, a run with a branch
    exposure, or an ERROR run. NO_FIGURE: a ZOMBIE run for which no honest figure exists. ERROR: the
    run's files cannot be read or its schema is not the one the run recorded.
    """
    run_dir = Path(run_dir)
    if (run_dir / AMOUNT_FILE).exists():
        return EXISTS, ""
    try:
        verdict = json.loads((run_dir / "verdict.json").read_text(encoding="utf-8"))
    except FileNotFoundError:
        return NOT_APPLICABLE, "no verdict.json"
    except (OSError, ValueError) as error:
        return ERROR, f"verdict.json unreadable: {error}"
    if not isinstance(verdict, dict) or verdict.get("status") != "ZOMBIE":
        return NOT_APPLICABLE, "not a ZOMBIE run"
    if "exposure_sum" in verdict:
        return NOT_APPLICABLE, "branch exposure run"

    try:
        inputs = json.loads((run_dir / "inputs.json").read_text(encoding="utf-8"))
        comparison = json.loads((run_dir / "comparison_results.json").read_text(encoding="utf-8"))
        cases = comparison["cases"]
    except (OSError, ValueError, KeyError, TypeError) as error:
        return ERROR, f"run files unreadable: {error}"
    schema_path = _recorded_schema(inputs if isinstance(inputs, dict) else {})
    if schema_path is None:
        return ERROR, "the schema recorded by the run was not found or has changed (SHA-256 differs)"
    try:
        from coroner.parse.schema import load_schema

        columns = decimal_output_columns(load_schema(str(schema_path)))
        figure = amount_difference_from_fields(
            (field for case in cases for field in case["divergent_fields"]), columns
        )
    except Exception as error:  # an unreadable schema or file shape: reported, never fatal
        return ERROR, f"cannot compute the figure: {error}"
    if figure is None:
        return NO_FIGURE, "no honest figure for this run"
    write_amount_difference(run_dir, figure, inputs["schema_sha256"])
    return WRITTEN, ""


def derive_all(base_dir) -> dict:
    """
    derive_run for every run folder (12 lowercase hex characters, not a symlink) under
    <base_dir>/runs. Returns {"counts": {outcome: n}, "errors": [(run_id, detail)], "written": [run_id]}.
    """
    runs_dir = Path(base_dir) / "runs"
    counts = {WRITTEN: 0, EXISTS: 0, NOT_APPLICABLE: 0, NO_FIGURE: 0, ERROR: 0}
    errors, written = [], []
    if runs_dir.is_dir():
        for entry in sorted(runs_dir.iterdir()):
            if not RUN_ID_PATTERN.match(entry.name) or entry.is_symlink() or not entry.is_dir():
                continue
            outcome, detail = derive_run(entry)
            counts[outcome] += 1
            if outcome == ERROR:
                errors.append((entry.name, detail))
            elif outcome == WRITTEN:
                written.append(entry.name)
    return {"counts": counts, "errors": errors, "written": written}
