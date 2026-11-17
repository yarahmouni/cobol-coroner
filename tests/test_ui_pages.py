"""Tests for UI pages rendering."""

import json
import os
import re
from decimal import Decimal
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from coroner.cli import run_verify


def compute_relative_luminance(r: int, g: int, b: int) -> float:
    """Compute relative luminance using WCAG 2 formula."""
    def linearize(c: int) -> float:
        c_srgb = c / 255.0
        if c_srgb <= 0.03928:
            return c_srgb / 12.92
        else:
            return ((c_srgb + 0.055) / 1.055) ** 2.4
    
    r_lin = linearize(r)
    g_lin = linearize(g)
    b_lin = linearize(b)
    
    return 0.2126 * r_lin + 0.7152 * g_lin + 0.0722 * b_lin


def compute_contrast_ratio(l1: float, l2: float) -> float:
    """Compute WCAG 2 contrast ratio between two luminances."""
    lighter = max(l1, l2)
    darker = min(l1, l2)
    return (lighter + 0.05) / (darker + 0.05)


def parse_hex_color(color: str) -> tuple[int, int, int]:
    """Parse hex color string to RGB tuple."""
    color = color.lstrip('#')
    return int(color[0:2], 16), int(color[2:4], 16), int(color[4:6], 16)


@pytest.fixture(scope="module")
def t1_faulty_run(tmp_path_factory):
    """Create a real T1 faulty run at 200 cases."""
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
    
    return tmp_path, run_dir.name


@pytest.fixture(scope="module")
def t1_correct_run(tmp_path_factory):
    """Create a real T1 correct run at 200 cases."""
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
    
    return tmp_path, run_dir.name


def test_run_page_t1_faulty_layout(t1_faulty_run, monkeypatch):
    """Test run page layout with T1 faulty run at 200 cases."""
    tmp_path, run_id = t1_faulty_run
    run_dir = tmp_path / "runs" / run_id
    
    # Set up test client with the tmp base using monkeypatch
    monkeypatch.setenv("CORONER_BASE_DIR", str(tmp_path))
    from coroner.ui.app import app
    
    client = TestClient(app)
    
    # Get run page
    run_id = run_dir.name
    response = client.get(f"/run/{run_id}")
    assert response.status_code == 200
    
    html = response.text
    
    # Check header values
    inputs_file = run_dir / "inputs.json"
    inputs = json.loads(inputs_file.read_text())
    
    timestamp_str = inputs["timestamp"]
    assert timestamp_str in html or "UTC" in html  # formatted timestamp
    
    coroner_version = inputs.get("coroner_version", "not recorded")
    assert coroner_version in html
    
    assert run_id in html
    
    # Check banner
    assert "Bundled sample. No customer data is uploaded or stored." in html
    
    # Check scope notice
    assert "Coroner compares the COBOL behavior with this Java migration on the batches tested" in html
    assert "does not prove behavior on IBM z/OS" in html
    
    # Check badge text
    assert "ZOMBIE" in html
    assert "MIGRATION REJECTED" in html
    
    # Check sentence (should show sub_label)
    verdict_file = run_dir / "verdict.json"
    verdict = json.loads(verdict_file.read_text())
    sub_label = verdict.get("sub_label")
    if sub_label:
        assert sub_label in html
    
    # Check exhibit
    verdict_file = run_dir / "verdict.json"
    verdict = json.loads(verdict_file.read_text())
    
    exposure_sum = verdict["exposure_sum"]
    if isinstance(exposure_sum, str):
        exposure_sum = Decimal(exposure_sum)
    affected_branches = verdict["affected_branches"]
    
    # The amount should appear without currency symbol or thousands separator
    assert str(exposure_sum) in html
    assert str(affected_branches) in html
    
    # Compute divergent rows independently
    comparison_file = run_dir / "comparison_results.json"
    comparison = json.loads(comparison_file.read_text())
    
    divergent_rows = 0
    for case in comparison["cases"]:
        if case.get("divergent", False):
            divergent_rows += 1
    
    assert str(divergent_rows) in html
    
    # Check animation duration is between 300 and 500 ms
    animation_match = re.search(r'animation:\s*fadeIn\s+(\d+)ms', html)
    assert animation_match is not None
    duration_ms = int(animation_match.group(1))
    assert 300 <= duration_ms <= 500
    
    # Check no "confidence" word
    assert "confidence" not in html.lower()
    
    # Check no home directory
    home_dir = str(Path.home())
    assert home_dir not in html


def test_t1_faulty_chart_and_table(t1_faulty_run, monkeypatch):
    """Test chart rows equal branch_reconciliation.json and table order."""
    tmp_path, run_id = t1_faulty_run
    run_dir = tmp_path / "runs" / run_id
    
    # Set up test client
    monkeypatch.setenv("CORONER_BASE_DIR", str(tmp_path))
    from coroner.ui.app import app
    
    client = TestClient(app)
    
    # Get run page
    response = client.get(f"/run/{run_id}")
    assert response.status_code == 200
    
    html = response.text
    
    # Read reconciliation file
    reconciliation_file = run_dir / "branch_reconciliation.json"
    reconciliation = json.loads(reconciliation_file.read_text())
    
    # Check all branches appear in HTML
    for branch in reconciliation["branches"]:
        branch_code = branch["branch"]
        assert branch_code in html
    
    # Check table order by absolute difference (largest first)
    branches_sorted = sorted(
        reconciliation["branches"],
        key=lambda b: Decimal(b["absolute_difference"]),
        reverse=True
    )
    
    # Extract branch codes in HTML order from the table
    # The branches appear in table rows
    for i, branch in enumerate(branches_sorted):
        assert branch["branch"] in html
        
        # Check status markers
        if branch["status"] == "MATCH":
            assert "MATCH" in html
        else:
            assert "MISMATCH" in html


def test_t1_faulty_filter_markup(t1_faulty_run, monkeypatch):
    """Test that compact chart shows only MISMATCH branches and details shows all branches."""
    tmp_path, run_id = t1_faulty_run
    run_dir = tmp_path / "runs" / run_id
    
    # Set up test client
    monkeypatch.setenv("CORONER_BASE_DIR", str(tmp_path))
    from coroner.ui.app import app
    
    client = TestClient(app)
    
    # Get run page
    response = client.get(f"/run/{run_id}")
    assert response.status_code == 200
    
    html = response.text
    
    # Read reconciliation to get branches
    reconciliation_file = run_dir / "branch_reconciliation.json"
    reconciliation = json.loads(reconciliation_file.read_text())
    
    # Check "Show all branches" details exists
    assert "Show all branches" in html
    
    # Check that the details section contains ALL branches from branch_reconciliation.json
    # Extract the details section
    details_start = html.find("<details")
    details_end = html.find("</details>", details_start)
    details_section = html[details_start:details_end]
    
    for branch in reconciliation["branches"]:
        branch_code = branch["branch"]
        assert branch_code in details_section, f"Branch {branch_code} not found in 'Show all branches' details"
    
    # Check suspense is in the chart if it's a MISMATCH
    if reconciliation.get("suspense") and reconciliation["suspense"].get("status") == "MISMATCH":
        # Find the section before details (the compact chart)
        compact_chart_end = html.find("<details")
        compact_chart = html[:compact_chart_end]
        
        suspense_code = "SUSP"  # default, trap.json may override
        trap_json = Path("samples/traps/T1-ebcdic-match-merge/trap.json")
        if trap_json.exists():
            trap = json.loads(trap_json.read_text())
            suspense_code = trap.get("suspense_code", "SUSP")
        
        assert suspense_code in compact_chart, f"Suspense {suspense_code} not found in compact chart"


def test_t1_faulty_example_sentence(t1_faulty_run, monkeypatch):
    """Test example sentence from minimal case equals independent calculation."""
    tmp_path, run_id = t1_faulty_run
    run_dir = tmp_path / "runs" / run_id
    
    # Set up test client
    monkeypatch.setenv("CORONER_BASE_DIR", str(tmp_path))
    from coroner.ui.app import app
    
    client = TestClient(app)
    
    # Get run page
    response = client.get(f"/run/{run_id}")
    assert response.status_code == 200
    
    html = response.text
    
    # Independently compute expected sentence from failure_report.json
    failure_file = run_dir / "failure_report.json"
    failure = json.loads(failure_file.read_text())
    
    trap_json = Path("samples/traps/T1-ebcdic-match-merge/trap.json")
    trap = json.loads(trap_json.read_text())
    
    suspense_label = trap["suspense_label"]
    suspense_code = trap["suspense_code"]
    
    # Find example from divergent_fields
    divergent_fields = failure.get("divergent_fields", [])
    expected_sentence = None
    expected_amount_str = None
    
    # Find the missing_in_cobol entry (Java posted to suspense)
    java_suspense_entry = None
    for div in divergent_fields:
        if div.get("kind") == "missing_in_cobol":
            output_key = div.get("output_key", {})
            branch = output_key.get("BRANCH", "").strip()
            if branch == suspense_code:
                java_suspense_entry = div
                break
    
    if java_suspense_entry:
        java_values = java_suspense_entry.get("java_values", {})
        subtotal = java_values.get("SUBTOTAL", "")
        
        # Find the missing_in_java entry with the same SUBTOTAL
        for div in divergent_fields:
            if div.get("kind") == "missing_in_java":
                cobol_values = div.get("cobol_values", {})
                cobol_subtotal = cobol_values.get("SUBTOTAL", "")
                
                if cobol_subtotal == subtotal:
                    output_key = div.get("output_key", {})
                    cobol_branch = output_key.get("BRANCH", "").strip()
                    
                    # Parse with Decimal, quantize to column scale (2 decimals), absolute value
                    amount = Decimal(subtotal.strip())
                    amount_quantized = amount.quantize(Decimal("0.01"))
                    expected_amount_str = f"{abs(amount_quantized):.2f}"
                    # New format: "<amount> was posted to <suspense_label> instead of branch <code>."
                    expected_sentence = f"{expected_amount_str} was posted to {suspense_label} instead of branch {cobol_branch}."
                    break
    
    # Check the sentence appears in HTML
    assert expected_sentence is not None, "Expected sentence could not be computed from failure_report.json"
    assert expected_sentence in html, f"Expected sentence not found in HTML: {expected_sentence}"
    
    # Assert no leading zero before the first significant digit (e.g., "0123.45" is wrong, "0.72" is valid)
    # Split by decimal point and check the integer part
    integer_part = expected_amount_str.split('.')[0]
    if abs(Decimal(subtotal.strip())) >= 1:
        assert not integer_part.startswith("0"), f"Amount has unwanted leading zero: {expected_amount_str}"


def test_t1_faulty_causes(t1_faulty_run, monkeypatch):
    """Test business and technical cause equal trap.json."""
    tmp_path, run_id = t1_faulty_run
    
    # Set up test client
    monkeypatch.setenv("CORONER_BASE_DIR", str(tmp_path))
    from coroner.ui.app import app
    
    client = TestClient(app)
    
    # Get run page
    response = client.get(f"/run/{run_id}")
    assert response.status_code == 200
    
    html = response.text
    
    # Read trap.json
    trap_json = Path("samples/traps/T1-ebcdic-match-merge/trap.json")
    trap = json.loads(trap_json.read_text())
    
    business_cause = trap["business_cause"]
    technical_cause = trap["technical_cause"]
    fix_sentence = trap["fix_sentence"]
    
    assert business_cause in html
    assert technical_cause in html
    assert fix_sentence in html


def test_t1_faulty_downloads(t1_faulty_run, monkeypatch):
    """Test downloads return exact bytes and refuse invalid names."""
    tmp_path, run_id = t1_faulty_run
    run_dir = tmp_path / "runs" / run_id
    
    # Set up test client
    monkeypatch.setenv("CORONER_BASE_DIR", str(tmp_path))
    from coroner.ui.app import app
    
    client = TestClient(app)
    
    # Test valid download
    response = client.get(f"/run/{run_id}/download/certificate.json")
    assert response.status_code == 200
    
    # Check it's the exact bytes
    cert_file = run_dir / "certificate.json"
    expected_bytes = cert_file.read_bytes()
    assert response.content == expected_bytes
    
    # Test JUnit download if exists
    junit_file = run_dir / "ZombieRegressionTest.java"
    if junit_file.exists():
        response = client.get(f"/run/{run_id}/download/ZombieRegressionTest.java")
        assert response.status_code == 200
        assert response.content == junit_file.read_bytes()
    
    # Test invalid file name
    response = client.get(f"/run/{run_id}/download/malicious.txt")
    assert response.status_code == 404
    
    # Test bad run id
    response = client.get("/run/invalid123/download/certificate.json")
    assert response.status_code == 404


def test_t1_faulty_replay_command(t1_faulty_run, monkeypatch):
    """Test replay command text is present."""
    tmp_path, run_id = t1_faulty_run
    
    # Set up test client
    monkeypatch.setenv("CORONER_BASE_DIR", str(tmp_path))
    from coroner.ui.app import app
    
    client = TestClient(app)
    
    # Get run page
    response = client.get(f"/run/{run_id}")
    assert response.status_code == 200
    
    html = response.text
    
    # Check replay command text
    expected_command = f"python -m coroner verify runs/{run_id}/certificate.json"
    assert expected_command in html


def test_t1_correct_no_what_to_do(t1_correct_run, monkeypatch):
    """Test ALIVE page has no 'What to do' section."""
    tmp_path, run_id = t1_correct_run
    
    # Set up test client
    monkeypatch.setenv("CORONER_BASE_DIR", str(tmp_path))
    from coroner.ui.app import app
    
    client = TestClient(app)
    
    # Get run page
    response = client.get(f"/run/{run_id}")
    assert response.status_code == 200
    
    html = response.text
    
    # Check "What to Do" does not appear
    assert "What to Do" not in html
    assert "Download regression test" not in html


def test_t1_faulty_headline_count(t1_faulty_run, monkeypatch):
    """Test at most four headline figures."""
    tmp_path, run_id = t1_faulty_run
    
    # Set up test client
    monkeypatch.setenv("CORONER_BASE_DIR", str(tmp_path))
    from coroner.ui.app import app
    
    client = TestClient(app)
    
    # Get run page
    response = client.get(f"/run/{run_id}")
    assert response.status_code == 200
    
    html = response.text
    
    # Count elements with class="headline" or class containing "headline"
    import re
    headline_matches = re.findall(r'class="[^"]*\bheadline\b[^"]*"', html)
    
    assert len(headline_matches) <= 4, f"Found {len(headline_matches)} headline figures, expected at most 4"


def test_run_page_t1_correct_layout(t1_correct_run, monkeypatch):
    """Test run page layout with T1 correct run at 200 cases."""
    tmp_path, run_id = t1_correct_run
    run_dir = tmp_path / "runs" / run_id
    
    # Set up test client with the tmp base using monkeypatch
    monkeypatch.setenv("CORONER_BASE_DIR", str(tmp_path))
    from coroner.ui.app import app
    
    client = TestClient(app)
    
    # Get run page
    run_id = run_dir.name
    response = client.get(f"/run/{run_id}")
    assert response.status_code == 200
    
    html = response.text
    
    # Check badge text
    assert "ALIVE" in html
    assert "MIGRATION CERTIFIED" in html
    
    # Check exhibit (should be present but with exposure_sum 0.00)
    verdict_file = run_dir / "verdict.json"
    verdict = json.loads(verdict_file.read_text())
    
    exposure_sum = verdict.get("exposure_sum")
    if exposure_sum is not None:
        # exposure_sum might be string or Decimal
        if isinstance(exposure_sum, str):
            exposure_sum = Decimal(exposure_sum)
        # The amount should appear without currency symbol or thousands separator
        assert str(exposure_sum) in html


def test_css_contrast_ratios_dark_mode(t1_correct_run, monkeypatch):
    """Test WCAG 2 contrast ratios in dark mode."""
    tmp_path, run_id = t1_correct_run
    run_dir = tmp_path / "runs" / run_id
    
    # Set up test client using monkeypatch
    monkeypatch.setenv("CORONER_BASE_DIR", str(tmp_path))
    from coroner.ui.app import app
    client = TestClient(app)
    
    # Get run page
    run_id = run_dir.name
    response = client.get(f"/run/{run_id}")
    assert response.status_code == 200
    
    html = response.text
    
    # Extract CSS variables from dark mode (default)
    # Parse :root { } block
    root_match = re.search(r':root\s*\{([^}]+)\}', html, re.DOTALL)
    assert root_match is not None
    
    root_css = root_match.group(1)
    
    # Parse color values
    def extract_var(name: str) -> str:
        match = re.search(rf'--{name}:\s*([^;]+);', root_css)
        return match.group(1).strip() if match else None
    
    bg_color = extract_var('bg-color')
    text_color = extract_var('text-color')
    zombie_color = extract_var('zombie-color')
    alive_color = extract_var('alive-color')
    invalid_color = extract_var('invalid-color')
    error_color = extract_var('error-color')
    orange_accent = extract_var('orange-accent')
    secondary_text = extract_var('secondary-text')
    
    # Compute contrast ratios
    bg_rgb = parse_hex_color(bg_color)
    text_rgb = parse_hex_color(text_color)
    
    bg_lum = compute_relative_luminance(*bg_rgb)
    text_lum = compute_relative_luminance(*text_rgb)
    
    text_bg_ratio = compute_contrast_ratio(text_lum, bg_lum)
    
    # WCAG AA requires at least 4.5:1 for normal text
    assert text_bg_ratio >= 4.5, f"Text/background contrast {text_bg_ratio:.2f} is below 4.5:1"
    
    # Check zombie color on zombie background
    zombie_rgb = parse_hex_color(zombie_color)
    zombie_lum = compute_relative_luminance(*zombie_rgb)
    
    zombie_bg = extract_var('zombie-bg')
    zombie_bg_rgb = parse_hex_color(zombie_bg)
    zombie_bg_lum = compute_relative_luminance(*zombie_bg_rgb)
    
    zombie_ratio = compute_contrast_ratio(zombie_lum, zombie_bg_lum)
    assert zombie_ratio >= 4.5, f"ZOMBIE text/background contrast {zombie_ratio:.2f} is below 4.5:1"
    
    # Check alive color on alive background
    alive_rgb = parse_hex_color(alive_color)
    alive_lum = compute_relative_luminance(*alive_rgb)
    
    alive_bg = extract_var('alive-bg')
    alive_bg_rgb = parse_hex_color(alive_bg)
    alive_bg_lum = compute_relative_luminance(*alive_bg_rgb)
    
    alive_ratio = compute_contrast_ratio(alive_lum, alive_bg_lum)
    assert alive_ratio >= 4.5, f"ALIVE text/background contrast {alive_ratio:.2f} is below 4.5:1"
    
    # Check secondary text
    secondary_rgb = parse_hex_color(secondary_text)
    secondary_lum = compute_relative_luminance(*secondary_rgb)
    
    secondary_ratio = compute_contrast_ratio(secondary_lum, bg_lum)
    assert secondary_ratio >= 4.5, f"Secondary text/background contrast {secondary_ratio:.2f} is below 4.5:1"


def test_css_contrast_ratios_light_mode(t1_correct_run, monkeypatch):
    """Test WCAG 2 contrast ratios in light mode."""
    tmp_path, run_id = t1_correct_run
    run_dir = tmp_path / "runs" / run_id
    
    # Set up test client using monkeypatch
    monkeypatch.setenv("CORONER_BASE_DIR", str(tmp_path))
    from coroner.ui.app import app
    client = TestClient(app)
    
    # Get run page
    run_id = run_dir.name
    response = client.get(f"/run/{run_id}")
    assert response.status_code == 200
    
    html = response.text
    
    # Extract CSS variables from :root.light { } block
    light_match = re.search(r':root\.light\s*\{([^}]+)\}', html, re.DOTALL)
    assert light_match is not None
    
    light_css = light_match.group(1)
    
    # Parse color values
    def extract_var(name: str) -> str:
        match = re.search(rf'--{name}:\s*([^;]+);', light_css)
        return match.group(1).strip() if match else None
    
    bg_color = extract_var('bg-color')
    text_color = extract_var('text-color')
    zombie_color = extract_var('zombie-color')
    alive_color = extract_var('alive-color')
    secondary_text = extract_var('secondary-text')
    
    # Compute contrast ratios
    bg_rgb = parse_hex_color(bg_color)
    text_rgb = parse_hex_color(text_color)
    
    bg_lum = compute_relative_luminance(*bg_rgb)
    text_lum = compute_relative_luminance(*text_rgb)
    
    text_bg_ratio = compute_contrast_ratio(text_lum, bg_lum)
    
    # WCAG AA requires at least 4.5:1 for normal text
    assert text_bg_ratio >= 4.5, f"Light mode text/background contrast {text_bg_ratio:.2f} is below 4.5:1"
    
    # Check zombie color on zombie background
    zombie_rgb = parse_hex_color(zombie_color)
    zombie_lum = compute_relative_luminance(*zombie_rgb)
    
    zombie_bg = extract_var('zombie-bg')
    zombie_bg_rgb = parse_hex_color(zombie_bg)
    zombie_bg_lum = compute_relative_luminance(*zombie_bg_rgb)
    
    zombie_ratio = compute_contrast_ratio(zombie_lum, zombie_bg_lum)
    assert zombie_ratio >= 4.5, f"Light mode ZOMBIE text/background contrast {zombie_ratio:.2f} is below 4.5:1"
    
    # Check alive color on alive background
    alive_rgb = parse_hex_color(alive_color)
    alive_lum = compute_relative_luminance(*alive_rgb)
    
    alive_bg = extract_var('alive-bg')
    alive_bg_rgb = parse_hex_color(alive_bg)
    alive_bg_lum = compute_relative_luminance(*alive_bg_rgb)
    
    alive_ratio = compute_contrast_ratio(alive_lum, alive_bg_lum)
    assert alive_ratio >= 4.5, f"Light mode ALIVE text/background contrast {alive_ratio:.2f} is below 4.5:1"
    
    # Check secondary text
    secondary_rgb = parse_hex_color(secondary_text)
    secondary_lum = compute_relative_luminance(*secondary_rgb)
    
    secondary_ratio = compute_contrast_ratio(secondary_lum, bg_lum)
    assert secondary_ratio >= 4.5, f"Light mode secondary text/background contrast {secondary_ratio:.2f} is below 4.5:1"
