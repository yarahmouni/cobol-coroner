"""Trap catalog runner."""
import json
import sys
from pathlib import Path
from typing import Any

from coroner.cli import run_verify
from coroner.diag.card import generate_card
from coroner.diag.report import FailureReport
from coroner.parse.schema import load_schema


TRAPS_DIR = Path("samples/traps")
RUNS_DIR = Path("runs")


def run_catalog(seed: int = 42, cases: int = 2000) -> dict[str, Any]:
    """
    Run the catalog on all built traps.
    
    Args:
        seed: Random seed
        cases: Number of cases to generate
        
    Returns:
        Catalog dict with results for all traps
    """
    results = []
    
    # T1 to T5
    for trap_id in ["T1", "T2", "T3", "T4", "T5"]:
        trap_dir = TRAPS_DIR / _trap_folder_name(trap_id)
        
        if not trap_dir.exists():
            print(f"ERROR: Trap {trap_id} directory not found at {trap_dir}", file=sys.stderr)
            sys.exit(2)
            
        # Load trap metadata
        trap_json_path = trap_dir / "trap.json"
        if not trap_json_path.exists():
            print(f"ERROR: Trap {trap_id} metadata not found: {trap_json_path}", file=sys.stderr)
            sys.exit(2)
            
        with open(trap_json_path) as f:
            trap_metadata = json.load(f)
        
        trap_result = {
            "id": trap_id,
            "title": trap_metadata["title"],
            "status": "measured"
        }
        
        # Find COBOL program
        cobol_files = list(trap_dir.glob("*.cob"))
        if not cobol_files:
            print(f"ERROR: Trap {trap_id} has no COBOL file in {trap_dir}", file=sys.stderr)
            sys.exit(2)
        cobol_file = cobol_files[0]
        
        # Schema
        schema_file = trap_dir / "schema.json"
        if not schema_file.exists():
            print(f"ERROR: Trap {trap_id} has no schema.json in {trap_dir}", file=sys.stderr)
            sys.exit(2)
        
        schema = load_schema(str(schema_file))
            
        # Copybooks: use copybooks/ if it exists, otherwise the trap folder itself
        copybooks_dir = trap_dir / "copybooks"
        if not copybooks_dir.exists():
            copybooks_dir = trap_dir
        
        # Run faulty Java
        faulty_java = trap_dir / "java" / "faulty"
        faulty_java_files = list(faulty_java.glob("*.java"))
        if not faulty_java_files:
            print(f"ERROR: Trap {trap_id} has no faulty Java in {trap_dir}", file=sys.stderr)
            sys.exit(2)
        faulty_java_file = faulty_java_files[0]
        
        print(f"\nRunning {trap_id} faulty Java...")
        try:
            faulty_verdict, faulty_run_dir = run_verify(
                cobol_path=str(cobol_file),
                java_path=str(faulty_java_file),
                schema_path=str(schema_file),
                copybooks_dir=str(copybooks_dir),
                num_cases=cases,
                seed=seed,
                timings=False
            )
            faulty_run_id = faulty_run_dir.name
        except Exception as e:
            print(f"ERROR: Faulty run failed for {trap_id}: {e}", file=sys.stderr)
            sys.exit(2)
            
        trap_result["cases_generated"] = cases
        trap_result["cases_detected"] = faulty_verdict.cases_divergent
        
        # Detection rate as a 4-decimal string
        if cases > 0:
            rate = trap_result["cases_detected"] / cases
            trap_result["detection_rate"] = f"{rate:.4f}"
        else:
            trap_result["detection_rate"] = "0.0000"
            
        trap_result["faulty_run_id"] = faulty_run_id
        
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
                executed_lines=failure_report_json.get("executed_lines", [])
            )
            
            trap_result["minimal_case"] = failure_report_json
            
            # COBOL lines: use the reviewed "COBOL lines involved" rule from card.py
            # which filters to relevant statements only
            card_text = generate_card(
                failure_report=failure_report_obj,
                schema=schema,
                cobol_source_path=str(cobol_file),
                copybook_dir=str(copybooks_dir),
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
        
        # Run correct Java
        correct_java = trap_dir / "java" / "correct"
        correct_java_files = list(correct_java.glob("*.java"))
        if not correct_java_files:
            print(f"ERROR: Trap {trap_id} has no correct Java in {trap_dir}", file=sys.stderr)
            sys.exit(2)
        correct_java_file = correct_java_files[0]
        
        print(f"Running {trap_id} correct Java...")
        try:
            correct_verdict, correct_run_dir = run_verify(
                cobol_path=str(cobol_file),
                java_path=str(correct_java_file),
                schema_path=str(schema_file),
                copybooks_dir=str(copybooks_dir),
                num_cases=cases,
                seed=seed,
                timings=False
            )
            correct_run_id = correct_run_dir.name
        except Exception as e:
            print(f"ERROR: Correct run failed for {trap_id}: {e}", file=sys.stderr)
            sys.exit(2)
            
        trap_result["correct_run_id"] = correct_run_id
        trap_result["correct_verdict"] = correct_verdict.status
        
        results.append(trap_result)
    
    # T6 placeholder
    results.append({
        "id": "T6",
        "title": "Reserved for owner field trap",
        "status": "placeholder: owner field trap pending"
    })
    
    return {"traps": results}


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


def write_catalog_files(catalog: dict[str, Any]) -> None:
    """
    Write catalog JSON and text files.
    
    Args:
        catalog: Catalog dict with trap results
    """
    RUNS_DIR.mkdir(exist_ok=True)
    
    # Write JSON with sorted keys
    json_path = RUNS_DIR / "trap_catalog.json"
    with open(json_path, "w") as f:
        json.dump(catalog, f, indent=2, sort_keys=True)
    print(f"\nWrote {json_path}")
    
    # Write text rendering
    txt_path = RUNS_DIR / "trap_catalog.txt"
    with open(txt_path, "w") as f:
        f.write("Six banking migration traps that silently corrupt amounts, signs, ordering or control totals.\n")
        f.write("targeted regression traps within its supported COBOL subset.\n\n")
        
        for trap in catalog["traps"]:
            f.write(f"== {trap['id']}: {trap['title']} ==\n")
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
                    f.write(f"\nCOBOL lines executed in minimal case:\n")
                    for line in trap["cobol_lines"][:10]:  # Show first 10
                        f.write(f"  {line}\n")
            
            f.write("\n")
    
    print(f"Wrote {txt_path}")


def main() -> None:
    """CLI entry point for trap catalog."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Run trap catalog")
    parser.add_argument("--cases", type=int, default=2000, help="Number of cases")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    
    args = parser.parse_args()
    
    catalog = run_catalog(seed=args.seed, cases=args.cases)
    write_catalog_files(catalog)


if __name__ == "__main__":
    main()
