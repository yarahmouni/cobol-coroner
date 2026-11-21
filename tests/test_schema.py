"""Tests for schema parsing."""

import json
import pytest
import tempfile
import os
from coroner.parse.schema import load_schema, parse_pic, SchemaColumn, Schema, GeneratorScriptError


def test_parse_pic_signed_decimal():
    """Test parsing S9(7)V99 PIC clause."""
    signed, digits, scale = parse_pic('S9(7)V99')
    assert signed is True
    assert digits == 9
    assert scale == 2


def test_parse_pic_string():
    """Test parsing X(10) PIC clause."""
    signed, digits, scale = parse_pic('X(10)')
    assert signed is False
    assert digits == 10
    assert scale == 0


def test_parse_pic_unsigned_decimal():
    """Test parsing V9(5) PIC clause."""
    signed, digits, scale = parse_pic('V9(5)')
    assert signed is False
    assert digits == 5
    assert scale == 5


def test_parse_pic_integer():
    """Test parsing 9(3) PIC clause."""
    signed, digits, scale = parse_pic('9(3)')
    assert signed is False
    assert digits == 3
    assert scale == 0


def test_parse_pic_edited_with_sign():
    """Test parsing +9(7).99 PIC clause."""
    signed, digits, scale = parse_pic('+9(7).99')
    assert signed is True
    assert digits == 9
    assert scale == 2


def test_load_valid_schema():
    """Test loading a valid schema.json file."""
    schema_data = {
        "program": "TEST-PROGRAM",
        "description": "Test program",
        "input": {
            "file": "input.csv",
            "columns": [
                {
                    "name": "ID",
                    "type": "string",
                    "pic": "X(10)",
                    "description": "Identifier"
                },
                {
                    "name": "AMOUNT",
                    "type": "decimal",
                    "pic": "S9(7)V99",
                    "scale": 2,
                    "description": "Amount"
                }
            ]
        },
        "output": {
            "file": "output.csv",
            "columns": [
                {
                    "name": "ID",
                    "type": "string",
                    "pic": "X(10)",
                    "description": "Identifier"
                },
                {
                    "name": "RESULT",
                    "type": "decimal",
                    "pic": "+9(7).99",
                    "scale": 2,
                    "description": "Result"
                }
            ]
        }
    }
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump(schema_data, f)
        temp_path = f.name
    
    try:
        schema = load_schema(temp_path)
        assert schema.program_name == "TEST-PROGRAM"
        assert schema.description == "Test program"
        assert schema.input_file == "input.csv"
        assert schema.output_file == "output.csv"
        assert len(schema.input_columns) == 2
        assert len(schema.output_columns) == 2
        
        # Check first input column
        assert schema.input_columns[0].name == "ID"
        assert schema.input_columns[0].type == "string"
        assert schema.input_columns[0].pic == "X(10)"
        assert schema.input_columns[0].signed is False
        
        # Check second input column
        assert schema.input_columns[1].name == "AMOUNT"
        assert schema.input_columns[1].type == "decimal"
        assert schema.input_columns[1].scale == 2
        assert schema.input_columns[1].signed is True
    finally:
        os.unlink(temp_path)


def test_load_schema_missing_required_field():
    """Test that missing required field raises ValueError."""
    schema_data = {
        "program": "TEST-PROGRAM",
        "description": "Test program",
        "input": {
            "file": "input.csv",
            "columns": []
        }
        # Missing "output" field
    }
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump(schema_data, f)
        temp_path = f.name
    
    try:
        with pytest.raises(ValueError, match="Missing required field: output"):
            load_schema(temp_path)
    finally:
        os.unlink(temp_path)


def test_load_schema_invalid_json():
    """Test that invalid JSON raises ValueError."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        f.write("{invalid json content")
        temp_path = f.name
    
    try:
        with pytest.raises(ValueError, match="Invalid JSON"):
            load_schema(temp_path)
    finally:
        os.unlink(temp_path)


def test_load_schema_missing_file():
    """Test that missing file raises ValueError."""
    with pytest.raises(ValueError, match="Schema file not found"):
        load_schema("/nonexistent/path/schema.json")


def test_load_schema_missing_column_field():
    """Test that missing column field raises ValueError."""
    schema_data = {
        "program": "TEST-PROGRAM",
        "description": "Test program",
        "input": {
            "file": "input.csv",
            "columns": [
                {
                    "name": "ID",
                    "type": "string",
                    "pic": "X(10)"
                    # Missing "description" field
                }
            ]
        },
        "output": {
            "file": "output.csv",
            "columns": []
        }
    }
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump(schema_data, f)
        temp_path = f.name
    
    try:
        with pytest.raises(ValueError, match="missing required field: description"):
            load_schema(temp_path)
    finally:
        os.unlink(temp_path)


def test_load_credit_fees_schema():
    """Test loading the actual credit-fees schema.json."""
    schema = load_schema('samples/credit-fees/schema.json')
    
    assert schema.program_name == "CREDIT-FEES"
    assert len(schema.input_columns) == 6
    assert len(schema.output_columns) == 4
    
    # Check input columns
    assert schema.input_columns[0].name == "CASE-ID"
    assert schema.input_columns[0].type == "string"
    
    assert schema.input_columns[1].name == "PRINCIPAL"
    assert schema.input_columns[1].type == "decimal"
    assert schema.input_columns[1].scale == 2
    assert schema.input_columns[1].signed is True
    
    assert schema.input_columns[2].name == "FEE-RATE"
    assert schema.input_columns[2].type == "decimal"
    assert schema.input_columns[2].scale == 5
    
    # Check output columns
    assert schema.output_columns[0].name == "CASE-ID"
    assert schema.output_columns[1].name == "FEE-AMOUNT"
    assert schema.output_columns[1].type == "decimal"
    assert schema.output_columns[1].scale == 2
    assert schema.output_columns[1].signed is True
    
    # Check internal precision
    assert schema.internal_precision is not None
    assert "FEE-AMOUNT" in schema.internal_precision


def test_parse_pic_unparseable():
    """Test that unparseable PIC clause raises ValueError."""
    with pytest.raises(ValueError, match="Cannot parse PIC clause"):
        parse_pic("INVALID")


def test_load_schema_missing_input_file():
    """Test that missing input.file raises ValueError."""
    schema_data = {
        "program": "TEST-PROGRAM",
        "description": "Test program",
        "input": {
            "columns": []
        },
        "output": {
            "file": "output.csv",
            "columns": []
        }
    }
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump(schema_data, f)
        temp_path = f.name
    
    try:
        with pytest.raises(ValueError, match="Missing required field: input.file"):
            load_schema(temp_path)
    finally:
        os.unlink(temp_path)


GENERATOR_SCHEMA = {
    "program": "TEST-PROGRAM",
    "description": "Test program",
    "input": {"file": "in.csv", "columns": [
        {"name": "CASE-ID", "type": "string", "pic": "X(10)", "description": "id"}]},
    "output": {"file": "out.csv", "columns": [
        {"name": "CASE-ID", "type": "string", "pic": "X(10)", "description": "id"}]},
}


def write_schema_with_script(folder, declared):
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / "schema.json"
    path.write_text(json.dumps(dict(GENERATOR_SCHEMA, generator_script=declared)))
    return path


def test_schema_without_generator_script_has_none(tmp_path):
    path = tmp_path / "schema.json"
    path.write_text(json.dumps(GENERATOR_SCHEMA))
    schema = load_schema(str(path))
    assert schema.generator_script is None
    assert schema.generator_script_path is None


def test_generator_script_is_relative_to_the_schema_folder(tmp_path):
    (tmp_path / "scripts").mkdir()
    (tmp_path / "scripts" / "gen.py").write_text("def generate_cases(schema, rng, num_cases):\n    return []\n")
    schema = load_schema(str(write_schema_with_script(tmp_path, "scripts/gen.py")))
    assert schema.generator_script == "scripts/gen.py"
    assert schema.generator_script_path == str((tmp_path / "scripts" / "gen.py").resolve())


def test_generator_script_must_be_a_non_empty_string(tmp_path):
    for bad in ("", 5, ["gen.py"]):
        path = write_schema_with_script(tmp_path, bad)
        with pytest.raises(ValueError, match="generator_script must be a non-empty string"):
            load_schema(str(path))


def test_generator_script_directory_is_not_a_script(tmp_path):
    (tmp_path / "scripts").mkdir()
    with pytest.raises(GeneratorScriptError, match="not found"):
        load_schema(str(write_schema_with_script(tmp_path, "scripts")))
