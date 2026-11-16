"""Schema parsing for COBOL Coroner engine."""

import json
import re
from dataclasses import dataclass
from decimal import Decimal


@dataclass
class SchemaColumn:
    """Schema column definition."""
    name: str
    type: str  # "string", "decimal", "integer"
    pic: str
    description: str
    scale: int | None = None
    signed: bool = False
    comp3: bool = False
    domain: list[str] | None = None  # Optional domain list for string columns
    domain_weights: list[int] | None = None  # Optional weights for domain values
    packed_hex: dict | None = None  # Optional packed hex domain spec for COMP-3 decoding
    zoned_overpunch: dict | None = None  # Optional zoned overpunch spec {"digits": 9, "convention": "EBCDIC", "sign_share": 0.5}


@dataclass
class Schema:
    """Complete schema definition."""
    program_name: str
    description: str
    input_file: str
    input_columns: list[SchemaColumn]
    output_file: str
    output_columns: list[SchemaColumn]
    internal_precision: dict[str, dict] | None = None
    case_rows: dict[str, int] | None = None  # {"min": 2, "max": 12}
    output_key: list[str] | None = None  # ["CASE-ID", "BRANCH"]
    group_key: str | None = None  # "BRANCH"
    subtotal: str | None = None  # "SUBTOTAL"
    grand_total_key: str | None = None  # "TOTAL"
    cobc_flags: list[str] | None = None  # ["-fsign=EBCDIC"]
    tie_strategy: str | None = None  # "product_pairs" for T2 trap


def parse_pic(pic: str) -> tuple[bool, int, int]:
    """
    Parse a COBOL PIC clause to extract sign, digit count, and scale.
    
    Returns: (signed, total_digits, scale)
    
    Examples:
        S9(9)V99 -> (True, 11, 2)
        X(10) -> (False, 10, 0)
        9(3) -> (False, 3, 0)
        V9(5) -> (False, 5, 5)
        +9(7).99 -> (True, 9, 2)
    """
    signed = pic.startswith('S') or pic.startswith('+')
    
    # For string types (X)
    if 'X' in pic:
        match = re.search(r'X\((\d+)\)', pic)
        if match:
            return (False, int(match.group(1)), 0)
        elif pic == 'X':
            return (False, 1, 0)
        raise ValueError(f"Cannot parse PIC clause: {pic}")
    
    # For numeric types, must contain 9 or V
    if '9' not in pic and 'V' not in pic:
        raise ValueError(f"Cannot parse PIC clause: {pic}")
    
    # For numeric types (9 and V)
    total_digits = 0
    scale = 0
    
    # Find all digit specifications before V or decimal point
    integer_part = pic.split('V')[0].split('.')[0]
    # Remove leading S or + and spaces
    integer_part = integer_part.lstrip('S+').strip()
    
    # Count integer digits
    for match in re.finditer(r'9\((\d+)\)|9', integer_part):
        if match.group(1):
            total_digits += int(match.group(1))
        else:
            total_digits += 1
    
    # Handle decimal part after V
    if 'V' in pic:
        decimal_part = pic.split('V')[1]
        for match in re.finditer(r'9\((\d+)\)|9', decimal_part):
            if match.group(1):
                scale += int(match.group(1))
            else:
                scale += 1
        total_digits += scale
    # Handle decimal part after .
    elif '.' in pic:
        decimal_part = pic.split('.')[1]
        for match in re.finditer(r'9\((\d+)\)|9', decimal_part):
            if match.group(1):
                scale += int(match.group(1))
            else:
                scale += 1
        total_digits += scale
    
    # If no digits found at all, it's unparseable
    if total_digits == 0 and scale == 0:
        raise ValueError(f"Cannot parse PIC clause: {pic}")
    
    return (signed, total_digits, scale)


def load_schema(path: str) -> Schema:
    """
    Load and validate schema.json.
    
    Raises ValueError on invalid schema or missing required fields.
    """
    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON in schema file: {e}")
    except FileNotFoundError:
        raise ValueError(f"Schema file not found: {path}")
    
    # Validate required top-level fields
    required_fields = ['program', 'description', 'input', 'output']
    for field in required_fields:
        if field not in data:
            raise ValueError(f"Missing required field: {field}")
    
    # Validate input section
    if 'file' not in data['input']:
        raise ValueError("Missing required field: input.file")
    if 'columns' not in data['input']:
        raise ValueError("Missing required field: input.columns")
    
    # Validate output section
    if 'file' not in data['output']:
        raise ValueError("Missing required field: output.file")
    if 'columns' not in data['output']:
        raise ValueError("Missing required field: output.columns")
    
    # Parse input columns
    input_columns = []
    for col_data in data['input']['columns']:
        if 'name' not in col_data:
            raise ValueError("Input column missing required field: name")
        if 'type' not in col_data:
            raise ValueError(f"Input column {col_data.get('name', '?')} missing required field: type")
        if 'pic' not in col_data:
            raise ValueError(f"Input column {col_data.get('name', '?')} missing required field: pic")
        if 'description' not in col_data:
            raise ValueError(f"Input column {col_data.get('name', '?')} missing required field: description")
        
        signed, total_digits, scale_from_pic = parse_pic(col_data['pic'])
        
        # For decimal and integer types, use scale from column data or from PIC
        scale = col_data.get('scale', scale_from_pic if col_data['type'] in ('decimal', 'integer') else None)
        
        input_columns.append(SchemaColumn(
            name=col_data['name'],
            type=col_data['type'],
            pic=col_data['pic'],
            description=col_data['description'],
            scale=scale,
            signed=signed,
            comp3=False,  # Will be set from internal_precision if present
            domain=col_data.get('domain'),  # Optional domain list
            domain_weights=col_data.get('domain_weights'),  # Optional weights
            packed_hex=col_data.get('packed_hex'),  # Optional packed hex spec
            zoned_overpunch=col_data.get('zoned_overpunch')  # Optional zoned overpunch spec
        ))
    
    # Parse output columns
    output_columns = []
    for col_data in data['output']['columns']:
        if 'name' not in col_data:
            raise ValueError("Output column missing required field: name")
        if 'type' not in col_data:
            raise ValueError(f"Output column {col_data.get('name', '?')} missing required field: type")
        if 'pic' not in col_data:
            raise ValueError(f"Output column {col_data.get('name', '?')} missing required field: pic")
        if 'description' not in col_data:
            raise ValueError(f"Output column {col_data.get('name', '?')} missing required field: description")
        
        signed, total_digits, scale_from_pic = parse_pic(col_data['pic'])
        
        scale = col_data.get('scale', scale_from_pic if col_data['type'] in ('decimal', 'integer') else None)
        
        output_columns.append(SchemaColumn(
            name=col_data['name'],
            type=col_data['type'],
            pic=col_data['pic'],
            description=col_data['description'],
            scale=scale,
            signed=signed,
            comp3=False  # Will be set from internal_precision if present
        ))
    
    # Check internal_precision for COMP-3 fields
    internal_precision = data.get('internal_precision')
    if internal_precision:
        for field_name, field_spec in internal_precision.items():
            if 'COMP-3' in field_spec.get('pic', ''):
                # Mark the column as COMP-3
                for col in input_columns + output_columns:
                    if col.name == field_name:
                        col.comp3 = True
    
    # Parse optional batch input and control break fields
    case_rows = data.get('case_rows')
    if case_rows is not None:
        if 'min' not in case_rows or 'max' not in case_rows:
            raise ValueError("case_rows must have 'min' and 'max' fields")
    
    output_key = data.get('output_key')
    if output_key is not None and not isinstance(output_key, list):
        raise ValueError("output_key must be a list of field names")
    
    group_key = data.get('group_key')
    subtotal = data.get('subtotal')
    grand_total_key = data.get('grand_total_key')
    
    cobc_flags = data.get('cobc_flags')
    if cobc_flags is not None and not isinstance(cobc_flags, list):
        raise ValueError("cobc_flags must be a list of strings")
    
    tie_strategy = data.get('tie_strategy')
    if tie_strategy is not None and not isinstance(tie_strategy, str):
        raise ValueError("tie_strategy must be a string")
    
    return Schema(
        program_name=data['program'],
        description=data['description'],
        input_file=data['input']['file'],
        input_columns=input_columns,
        output_file=data['output']['file'],
        output_columns=output_columns,
        internal_precision=internal_precision,
        case_rows=case_rows,
        output_key=output_key,
        group_key=group_key,
        subtotal=subtotal,
        grand_total_key=grand_total_key,
        cobc_flags=cobc_flags,
        tie_strategy=tie_strategy
    )
