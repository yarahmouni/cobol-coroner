#!/usr/bin/env python3
"""Check COBOL coding rules for CREDIT-FEES.cob.

Verifies:
1. No GO TO statements
2. Every EVALUATE has WHEN OTHER
3. Every IF has a corresponding ELSE
"""
import re
import sys
from pathlib import Path


def main():
    cobol_file = Path("samples/credit-fees/CREDIT-FEES.cob")
    
    if not cobol_file.exists():
        print(f"ERROR: {cobol_file} not found", file=sys.stderr)
        return 1
    
    with open(cobol_file, "r") as f:
        content = f.read()
    
    # Remove comments (lines starting with *> or * in column 7)
    lines = content.split("\n")
    code_lines = []
    for line in lines:
        if line.strip().startswith("*>"):
            continue
        if len(line) >= 7 and line[6] == "*":
            continue
        code_lines.append(line)
    
    code = "\n".join(code_lines)
    
    violations = []
    
    # Check 1: No GO TO
    go_to_pattern = r'\bGO\s+TO\b'
    go_to_matches = re.findall(go_to_pattern, code, re.IGNORECASE)
    if go_to_matches:
        violations.append(f"Found {len(go_to_matches)} GO TO statement(s)")
    
    print(f"GO TO count: {len(go_to_matches)}")
    
    # Check 2: EVALUATE and WHEN OTHER counts match
    evaluate_pattern = r'\bEVALUATE\b(?!\s*\.)'  # Exclude END-EVALUATE
    when_other_pattern = r'\bWHEN\s+OTHER\b'
    
    # Filter out lines that start with END-EVALUATE
    evaluate_matches = []
    for match in re.finditer(evaluate_pattern, code, re.IGNORECASE):
        # Get the context around the match
        start = max(0, match.start() - 10)
        context = code[start:match.end()].upper()
        if 'END-EVALUATE' not in context and 'END EVALUATE' not in context:
            evaluate_matches.append(match)
    
    evaluate_count = len(evaluate_matches)
    when_other_count = len(re.findall(when_other_pattern, code, re.IGNORECASE))
    
    print(f"EVALUATE count: {evaluate_count}")
    print(f"WHEN OTHER count: {when_other_count}")
    
    if evaluate_count != when_other_count:
        violations.append(
            f"EVALUATE count ({evaluate_count}) does not match WHEN OTHER count ({when_other_count})"
        )
    
    # Check 3: IF and ELSE counts match
    # Count only IFs that start a new statement (line-starting after whitespace)
    if_count = 0
    else_count = 0
    
    for line in code_lines:
        stripped = line.lstrip()
        # Skip empty lines
        if not stripped:
            continue
        # Match IF at start of statement
        if re.match(r'\bIF\b', stripped, re.IGNORECASE):
            if_count += 1
        # Match ELSE at start of statement  
        if re.match(r'\bELSE\b', stripped, re.IGNORECASE):
            else_count += 1
    
    print(f"IF count: {if_count}")
    print(f"ELSE count: {else_count}")
    
    if if_count != else_count:
        violations.append(
            f"IF count ({if_count}) does not match ELSE count ({else_count})"
        )
    
    # Summary
    if violations:
        print("\nVIOLATIONS FOUND:")
        for v in violations:
            print(f"  - {v}")
        return 1
    else:
        print("\nAll COBOL coding rules verified: PASS")
        return 0


if __name__ == "__main__":
    sys.exit(main())
