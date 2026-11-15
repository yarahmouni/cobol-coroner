"""COBOL source and copybook parsing module."""

import re
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path


@dataclass
class BranchInfo:
    """Branch information from COBOL source."""
    paragraph: str
    line_number: int
    branch_type: str  # IF_TRUE, IF_ELSE, EVALUATE_WHEN, EVALUATE_OTHER


def parse_cobol_structure(source_path: str, copybook_dir: str) -> dict:
    """
    Parse COBOL source and copybooks to extract constants, paragraphs, and branches.
    
    Args:
        source_path: Path to the COBOL source file
        copybook_dir: Directory containing copybooks
        
    Returns:
        Dictionary with:
            - constants: List of Decimal constants from VALUE clauses and literals
            - paragraphs: Dict of paragraph_name -> starting_line_number
            - branches: List of BranchInfo objects
    """
    source_path_obj = Path(source_path)
    copybook_dir_obj = Path(copybook_dir)
    
    lines = []
    
    # Read main source
    with open(source_path_obj, 'r') as f:
        lines = f.readlines()
    
    # Read copybooks if directory exists
    if copybook_dir_obj.exists():
        for copybook_file in copybook_dir_obj.glob('*.cpy'):
            with open(copybook_file, 'r') as f:
                lines.extend(f.readlines())
    
    constants = _extract_constants(lines)
    paragraphs = _extract_paragraphs(lines)
    branches = _extract_branches(lines, paragraphs)
    
    return {
        "constants": constants,
        "paragraphs": paragraphs,
        "branches": branches
    }


def _extract_constants(lines: list[str]) -> list[Decimal]:
    """Extract numeric constants from VALUE clauses and IF condition literals."""
    constants = []
    
    # VALUE clause pattern: VALUE 10.00, VALUE 25000.00, etc.
    value_pattern = re.compile(r'\bVALUE\s+([+-]?\d+(?:\.\d+)?)', re.IGNORECASE)
    
    # Numeric literals in conditions and MOVE statements
    literal_pattern = re.compile(r'(?:=|<|>|MOVE)\s+([+-]?\d+(?:\.\d+)?)', re.IGNORECASE)
    
    for line in lines:
        # Extract from VALUE clauses
        for match in value_pattern.finditer(line):
            try:
                constants.append(Decimal(match.group(1)))
            except:
                pass
        
        # Extract from literals in conditions and assignments
        for match in literal_pattern.finditer(line):
            try:
                constants.append(Decimal(match.group(1)))
            except:
                pass
    
    return list(set(constants))  # Remove duplicates


def _extract_paragraphs(lines: list[str]) -> dict[str, int]:
    """
    Extract paragraph names and their starting line numbers.
    
    A paragraph starts at column 8 (after 7 spaces) with a name followed by a period.
    Excludes PROGRAM-ID, FILE-CONTROL, and other non-paragraph identifiers.
    """
    paragraphs = {}
    
    # Paragraph pattern: starts at beginning (after area A), ends with period
    # Must not be a comment line (starting with *)
    para_pattern = re.compile(r'^       ([A-Z][A-Z0-9-]*)\.')
    
    # Keywords that look like paragraphs but aren't
    excluded_keywords = {
        'PROGRAM-ID', 'FILE-CONTROL', 'INPUT-OUTPUT', 'DATA',
        'FILE', 'WORKING-STORAGE', 'LINKAGE', 'PROCEDURE'
    }
    
    for line_num, line in enumerate(lines, start=1):
        # Skip comment lines
        if line.strip().startswith('*>'):
            continue
        
        match = para_pattern.match(line)
        if match:
            para_name = match.group(1)
            # Skip division/section names and excluded keywords
            if ('DIVISION' not in line and 'SECTION' not in line 
                and para_name not in excluded_keywords):
                paragraphs[para_name] = line_num
    
    return paragraphs


def _extract_branches(lines: list[str], paragraphs: dict[str, int]) -> list[BranchInfo]:
    """
    Extract branch first-statement line numbers.
    
    Branch markers are the first STATEMENT after:
    - IF condition: first statement after the condition ends (true arm)
    - ELSE: first statement after ELSE
    - WHEN clause: first statement inside WHEN
    - WHEN OTHER: first statement inside WHEN OTHER
    
    A nested IF or EVALUATE is a statement and can be the first statement of an arm.
    """
    branches = []
    
    # Track current paragraph
    current_para = None
    
    # Track pending branches
    pending_if_true = []  # List of IF line numbers waiting for their true branch
    pending_else = []  # List of ELSE line numbers waiting for their branch
    
    in_evaluate = False
    pending_when = None
    
    for line_num, line in enumerate(lines, start=1):
        # Skip comments and blank lines
        if not line.strip() or line.strip().startswith('*>'):
            continue
        
        # Update current paragraph
        for para_name, para_line in paragraphs.items():
            if line_num == para_line:
                current_para = para_name
        
        # Normalize line for pattern matching
        stripped = line.strip()
        upper = stripped.upper()
        
        # END-IF: clean up
        if upper.startswith('END-IF'):
            if pending_if_true:
                pending_if_true.pop()
            if pending_else:
                pending_else.pop()
            continue
        
        # END-EVALUATE
        if upper.startswith('END-EVALUATE'):
            in_evaluate = False
            pending_when = None
            continue
        
        # ELSE detection (not a statement, just changes pending state)
        if upper.startswith('ELSE') and not upper.startswith('END-'):
            if pending_if_true:
                pending_if_true.pop()
            pending_else.append(line_num)
            continue
        
        # WHEN detection inside EVALUATE (not a statement, just changes pending state)
        if in_evaluate and upper.startswith('WHEN '):
            pending_when = line_num
            continue
        
        # Now check if this is a statement (including IF, EVALUATE)
        if _is_statement(stripped):
            # Mark branches BEFORE processing control flow keywords
            # First statement after WHEN
            if pending_when is not None:
                when_line_content = lines[pending_when - 1].strip().upper()
                branch_type = "EVALUATE_OTHER" if "OTHER" in when_line_content else "EVALUATE_WHEN"
                branches.append(BranchInfo(
                    paragraph=current_para or "UNKNOWN",
                    line_number=line_num,
                    branch_type=branch_type
                ))
                pending_when = None
            
            # First statement after ELSE (all pending ELSEs)
            for else_line in pending_else:
                branches.append(BranchInfo(
                    paragraph=current_para or "UNKNOWN",
                    line_number=line_num,
                    branch_type="IF_ELSE"
                ))
            pending_else = []
            
            # First statement after IF (all pending IFs)
            for if_line in pending_if_true:
                branches.append(BranchInfo(
                    paragraph=current_para or "UNKNOWN",
                    line_number=line_num,
                    branch_type="IF_TRUE"
                ))
            pending_if_true = []
            
            # Now process control flow that starts new pending branches
            # EVALUATE detection (starts evaluate, is a statement for marking)
            if upper.startswith('EVALUATE '):
                in_evaluate = True
                continue
            
            # IF detection (starts new pending branches, is a statement for marking)
            if upper.startswith('IF ') and not upper.startswith('END-IF'):
                pending_if_true.append(line_num)
                continue
    
    return branches


def _is_statement(line: str) -> bool:
    """
    Check if a line contains a statement.
    
    Statements include:
    - Imperative verbs: MOVE, PERFORM, COMPUTE, etc.
    - Conditional statements: IF, EVALUATE
    - Special keywords: CONTINUE
    
    NOT statements:
    - END-* terminators
    - Exception phrases: ON SIZE ERROR, AT END
    - Bare WHEN, ELSE keywords
    """
    line = line.strip()
    
    # NOT statements
    if not line:
        return False
    if line.startswith('END-'):
        return False
    if line.startswith('ON SIZE ERROR') or line.startswith('NOT ON SIZE ERROR'):
        return False
    if line.startswith('AT END') or line.startswith('NOT AT END'):
        return False
    if line.startswith('WHEN '):
        return False
    if line.startswith('ELSE') and line != 'ELSE':
        return False
    
    # Common COBOL verbs that indicate statements
    statement_verbs = [
        'MOVE', 'PERFORM', 'COMPUTE', 'DISPLAY', 'ADD', 'SUBTRACT',
        'MULTIPLY', 'DIVIDE', 'STRING', 'UNSTRING', 'ACCEPT', 'OPEN',
        'CLOSE', 'READ', 'WRITE', 'INITIALIZE', 'SET', 'STOP', 'CALL',
        'CONTINUE', 'GO TO', 'EXIT', 'IF ', 'EVALUATE '
    ]
    
    for verb in statement_verbs:
        if line.startswith(verb):
            return True
    
    return False
