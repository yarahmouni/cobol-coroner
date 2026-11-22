"""UI page rendering logic."""

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Optional

# run_id validation: exactly 12 lowercase hexadecimal characters
RUN_ID_PATTERN = re.compile(r"^[0-9a-f]{12}$")


def exposure_line(verdict_data: dict) -> Optional[str]:
    """
    The one-line exposure for the Run audit result, built from the fields of a run's verdict.json.

    Returns "Exposure: <exposure_sum> across <affected_branches> branch(es)" when verdict.json
    records both fields and affected_branches is above 0, otherwise None. exposure_sum is used
    exactly as recorded (a decimal string); nothing is added, rounded or recomputed.
    """
    exposure_sum = verdict_data.get("exposure_sum")
    affected = verdict_data.get("affected_branches")
    if not isinstance(exposure_sum, str) or not exposure_sum:
        return None
    if isinstance(affected, bool) or not isinstance(affected, int) or affected <= 0:
        return None
    noun = "branch" if affected == 1 else "branches"
    return f"Exposure: {exposure_sum} across {affected} {noun}"


def amount_view(run_dir: Path, inputs_data: Optional[dict] = None) -> Optional[dict]:
    """
    The texts of the amount difference of a run, read only from <run_dir>/amount_difference.json
    (through the one reader, coroner.derive.read_amount_difference), exactly as the engine wrote it.

    Returns None when the run has no such file. Otherwise:
      business: ["<N> amounts affected", "Largest single difference: <amount>"]
      engineer: the two lines above, then "Sum of absolute differences: <amount> (seed <S>, <C> cases)"
    The seed and the case count come from the run's inputs.json (inputs_data); "not recorded" when
    absent. No currency label. Nothing is computed here: amounts are the recorded decimal strings.
    """
    from coroner.derive import read_amount_difference

    data = read_amount_difference(run_dir)
    if data is None:
        return None
    count = data["amounts_affected"]
    business = [
        f"{count} {'amount' if count == 1 else 'amounts'} affected",
        f"Largest single difference: {data['largest_difference']}",
    ]
    inputs_data = inputs_data or {}
    seed = inputs_data.get("random_seed", inputs_data.get("seed"))
    cases = inputs_data.get("case_count")
    seed_text = "not recorded" if seed is None else str(seed)
    cases_text = "not recorded" if cases is None else str(cases)
    sum_line = f"Sum of absolute differences: {data['sum_of_absolute_differences']} (seed {seed_text}, {cases_text} cases)"
    return {"business": business, "engineer": business + [sum_line]}


def run_result_summary(run_dir: Path) -> dict:
    """
    The result fields of the Run audit box, read from <run_dir>/verdict.json and, for the amount
    lines, <run_dir>/amount_difference.json.

    Returns verdict (the recorded status), cases_divergent and cases_total (each only when the file
    records it), exposure_line (None when the run has no exposure) and amount_lines (the two
    business lines of amount_view, or None when the run has no amount difference file or has an
    exposure line). Used by the job status when a job is done and by the cache-hit answer of
    POST /api/run, so both paths give the same fields. Returns an empty dict when verdict.json is
    missing or unreadable.
    """
    try:
        verdict_data = json.loads((Path(run_dir) / "verdict.json").read_text())
    except (OSError, ValueError):
        return {}
    if not isinstance(verdict_data, dict):
        return {}
    exposure = exposure_line(verdict_data)
    amounts = amount_view(run_dir) if exposure is None and verdict_data.get("status") == "ZOMBIE" else None
    summary = {
        "verdict": verdict_data.get("status"),
        "exposure_line": exposure,
        "amount_lines": amounts["business"] if amounts else None,
    }
    for key in ("cases_divergent", "cases_total"):
        if key in verdict_data:
            summary[key] = verdict_data[key]
    return summary


def parse_card(card_text: str) -> Optional[dict]:
    """
    Split the text of card.txt into its Given, When and Then parts and its COBOL lines.

    Returns None for an empty card. Each COBOL line is "<file name>:<line number> <statement>".
    """
    card_text = card_text.strip()
    if not card_text:
        return None
    # Card format:
    # Given the following input rows:
    #   ...
    # When the COBOL reference and the Java port process this case
    # Then ...
    # COBOL lines involved: path:line statement; path:line statement; ...
    given_lines = []
    when_lines = []
    then_lines = []
    cobol_lines = []

    section = None
    for line in card_text.split("\n"):
        if line.startswith("Given"):
            section = "given"
            given_lines.append(line)
        elif line.startswith("When"):
            section = "when"
            when_lines.append(line)
        elif line.startswith("Then"):
            section = "then"
            then_lines.append(line)
        elif line.startswith("COBOL lines involved:"):
            section = "cobol"
            rest = line[len("COBOL lines involved:"):].strip()
            if rest:
                for part in rest.split("; "):
                    if part:
                        # part is "full/path/file.cob:123 STATEMENT TEXT": keep "file.cob:123 STATEMENT TEXT"
                        if ":" in part:
                            path_part, rest_part = part.split(":", 1)
                            cobol_lines.append(f"{Path(path_part).name}:{rest_part}")
                        else:
                            cobol_lines.append(part)
        elif section == "given" and line.strip():
            given_lines.append(line)
        elif section == "when" and line.strip():
            when_lines.append(line)
        elif section == "then" and line.strip():
            then_lines.append(line)

    return {
        "given": "\n".join(given_lines),
        "when": "\n".join(when_lines),
        "then": "\n".join(then_lines),
        "cobol_lines": cobol_lines,
    }


def format_timestamp(timestamp_str: str) -> str:
    """Format ISO timestamp to human-readable date and time."""
    try:
        dt = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
        return dt.strftime("%Y-%m-%d %H:%M:%S UTC")
    except (ValueError, AttributeError):
        return timestamp_str


def get_value_column_from_schema(schema_path: Path) -> Optional[str]:
    """Extract the non-key output column name from schema."""
    try:
        schema = json.loads(schema_path.read_text())
        output_cols = schema["output"]["columns"]
        if len(output_cols) >= 2:
            return output_cols[1]["name"]
    except (KeyError, IndexError, json.JSONDecodeError, OSError):
        pass
    return None


def has_group_key(schema_path: Path) -> bool:
    """Check if schema declares a group key (for branch exposure)."""
    try:
        schema = json.loads(schema_path.read_text())
        return "group_key" in schema
    except (json.JSONDecodeError, OSError):
        return False


def count_divergent_rows(comparison_results: dict) -> int:
    """
    Count the number of divergent output rows.
    
    Divergent rows means divergent output rows: count every output row key
    present in only one side or with a different value, from comparison_results.json.
    """
    count = 0
    for case in comparison_results.get("cases", []):
        divergent_fields = case.get("divergent_fields", [])
        # Each entry in divergent_fields is one divergent row
        count += len(divergent_fields)
    return count


def count_divergent_cases(comparison_results: dict) -> int:
    """Count the number of divergent cases (cases with at least one divergent row)."""
    count = 0
    for case in comparison_results.get("cases", []):
        if case.get("divergent", False):
            count += 1
    return count


def compute_exhibit_data(run_dir: Path, verdict_data: dict, inputs_data: dict) -> Optional[dict]:
    """
    Compute Exhibit 1 (Unreconciled branch exposure) data.
    
    Returns dict with exhibit data if applicable, None otherwise.
    """
    # Extract exposure data from verdict - only if present
    exposure_sum = verdict_data.get("exposure_sum")
    exposure_max = verdict_data.get("exposure_max")
    affected_branches = verdict_data.get("affected_branches")
    grand_total_matches = verdict_data.get("grand_total_matches")
    suspense_difference = verdict_data.get("suspense_difference")
    
    # If these keys exist, the schema has a group key
    if exposure_sum is None or affected_branches is None:
        return None
    
    # exposure_sum and exposure_max might be strings, convert to Decimal
    from decimal import Decimal
    if isinstance(exposure_sum, str):
        exposure_sum = Decimal(exposure_sum)
    if isinstance(exposure_max, str):
        exposure_max = Decimal(exposure_max)
    if isinstance(suspense_difference, str):
        suspense_difference = Decimal(suspense_difference)
    
    # Count divergent cases and rows from comparison_results.json
    comparison_file = run_dir / "comparison_results.json"
    divergent_cases = 0
    divergent_rows = 0
    if comparison_file.exists():
        try:
            comparison_data = json.loads(comparison_file.read_text())
            divergent_cases = count_divergent_cases(comparison_data)
            divergent_rows = count_divergent_rows(comparison_data)
        except (json.JSONDecodeError, OSError):
            pass
    
    return {
        "number": 1,
        "title": "Unreconciled branch exposure",
        "exposure_sum": f"{exposure_sum:.2f}",
        "exposure_max": f"{exposure_max:.2f}" if exposure_max is not None else None,
        "affected_branches": affected_branches,
        "grand_total_matches": grand_total_matches,
        "suspense_difference": f"{abs(suspense_difference):.2f}" if suspense_difference is not None else None,
        "divergent_cases": divergent_cases,
        "divergent_rows": divergent_rows,
        "run_id": run_dir.name
    }
