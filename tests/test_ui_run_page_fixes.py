"""Tests for UI run page owner-approved fixes."""
import json
import re
from decimal import Decimal
from pathlib import Path

import pytest
from starlette.testclient import TestClient


def test_card_rendered_from_card_txt(t1_faulty_run, monkeypatch):
    """Test that card is rendered from card.txt with Given/When/Then structure."""
    run_id, base = t1_faulty_run
    
    monkeypatch.setenv("CORONER_BASE_DIR", str(base))
    from coroner.ui.app import app
    
    client = TestClient(app)
    
    response = client.get(f"/run/{run_id}")
    assert response.status_code == 200
    
    html = response.text
    
    # Read card.txt to check its content appears
    card_file = base / "runs" / run_id / "card.txt"
    assert card_file.exists()
    
    card_text = card_file.read_text()
    
    # Check that Given/When/Then structure appears
    assert "Given" in card_text
    assert "When" in card_text
    assert "Then" in card_text
    assert "COBOL lines involved:" in card_text
    
    # Check that these key elements appear in the HTML
    assert "Given" in html
    assert "When" in html or "when" in html.lower()
    assert "Then" in html or "then" in html.lower()
    
    # Check that COBOL file reference appears (with shortened path)
    assert "MATCH-MERGE.cob:" in html
    
    # Check that no home directory paths appear
    home_dir = str(Path.home())
    assert home_dir not in html


def test_chart_bars_use_neutral_colors(t1_faulty_run, monkeypatch):
    """Test that chart bars use neutral CSS variables, not verdict colors."""
    run_id, base = t1_faulty_run
    
    monkeypatch.setenv("CORONER_BASE_DIR", str(base))
    from coroner.ui.app import app
    
    client = TestClient(app)
    
    response = client.get(f"/run/{run_id}")
    assert response.status_code == 200
    
    html = response.text
    
    # Check that charts use --chart-cobol and --chart-java variables
    assert "var(--chart-cobol)" in html
    assert "var(--chart-java)" in html
    
    # Check that charts do NOT use old hardcoded colors in bars
    # Find chart bar sections (between "Branch Subtotals" and next exhibit)
    chart_section_match = re.search(
        r'Branch Subtotals.*?(?=<div class="exhibit"|$)',
        html,
        re.DOTALL
    )
    
    if chart_section_match:
        chart_html = chart_section_match.group(0)
        # In chart bars, should not use old green (#4ade80) hardcoded
        assert "#4ade80" not in chart_html


def test_css_variables_define_neutral_chart_colors():
    """Test that CSS variables define neutral chart colors in both modes."""
    # Read base.html
    base_html = (Path("coroner/ui/templates/base.html")).read_text()
    
    # Check dark mode defines chart colors
    assert "--chart-cobol:" in base_html
    assert "--chart-java:" in base_html
    
    # Check light mode defines chart colors
    light_section = re.search(r':root\.light\s*\{(.*?)\}', base_html, re.DOTALL)
    assert light_section is not None
    light_css = light_section.group(1)
    assert "--chart-cobol:" in light_css
    assert "--chart-java:" in light_css
    
    # Check print mode defines chart colors
    print_section = re.search(r'@media print\s*\{.*?:root\s*\{(.*?)\}', base_html, re.DOTALL)
    assert print_section is not None
    print_css = print_section.group(1)
    assert "--chart-cobol:" in print_css
    assert "--chart-java:" in print_css


def test_chart_color_contrast(t1_faulty_run, monkeypatch):
    """Test that chart bar colors have sufficient contrast against panel background."""
    run_id, base = t1_faulty_run
    
    # Read CSS to extract colors
    base_html = (Path("coroner/ui/templates/base.html")).read_text()
    
    # Extract dark mode colors
    dark_panel = re.search(r'--panel-bg:\s*(#[0-9a-fA-F]{6})', base_html)
    dark_chart_cobol = re.search(r'--chart-cobol:\s*(#[0-9a-fA-F]{6})', base_html)
    dark_chart_java = re.search(r'--chart-java:\s*(#[0-9a-fA-F]{6})', base_html)
    
    assert dark_panel and dark_chart_cobol and dark_chart_java
    
    panel_bg = dark_panel.group(1)
    cobol_color = dark_chart_cobol.group(1)
    java_color = dark_chart_java.group(1)
    
    # Compute relative luminance (simplified check: just ensure they're different enough)
    def hex_to_rgb(hex_color):
        hex_color = hex_color.lstrip("#")
        return tuple(int(hex_color[i:i+2], 16) / 255 for i in (0, 2, 4))
    
    def relative_luminance(rgb):
        r, g, b = rgb
        # Simplified sRGB luminance
        return 0.2126 * r + 0.7152 * g + 0.0722 * b
    
    def contrast_ratio(color1, color2):
        l1 = relative_luminance(hex_to_rgb(color1))
        l2 = relative_luminance(hex_to_rgb(color2))
        lighter = max(l1, l2)
        darker = min(l1, l2)
        return (lighter + 0.05) / (darker + 0.05)
    
    # Check contrast ratios are at least 3:1
    contrast_cobol = contrast_ratio(cobol_color, panel_bg)
    contrast_java = contrast_ratio(java_color, panel_bg)
    
    assert contrast_cobol >= 3.0, f"COBOL bar contrast {contrast_cobol:.2f} < 3:1"
    assert contrast_java >= 3.0, f"Java bar contrast {contrast_java:.2f} < 3:1"


def test_duplicate_headline_row_removed(t1_faulty_run, monkeypatch):
    """Test that duplicate headline row is removed."""
    run_id, base = t1_faulty_run
    
    monkeypatch.setenv("CORONER_BASE_DIR", str(base))
    from coroner.ui.app import app
    
    client = TestClient(app)
    
    response = client.get(f"/run/{run_id}")
    assert response.status_code == 200
    
    html = response.text
    
    # Count headline elements (class="headline")
    headline_count = html.count('class="headline"')
    
    # Exhibit 1 has 4 headlines (exposure sum, branches affected, divergent rows, grand total matches)
    # Certificate panel may have up to 4 headlines
    # Total: at most 8
    assert headline_count <= 8, f"Too many headline elements: {headline_count}"
    
    # Check that "Cases and coverage info" comment is removed
    assert "Cases and coverage info" not in html


def test_suspense_line_in_exhibit_1(t1_faulty_run, monkeypatch):
    """Test that suspense difference appears in Exhibit 1."""
    run_id, base = t1_faulty_run
    
    monkeypatch.setenv("CORONER_BASE_DIR", str(base))
    from coroner.ui.app import app
    
    client = TestClient(app)
    
    response = client.get(f"/run/{run_id}")
    assert response.status_code == 200
    
    html = response.text
    
    # Read verdict to get suspense_difference
    verdict_file = base / "runs" / run_id / "verdict.json"
    verdict = json.loads(verdict_file.read_text())
    
    suspense_diff = verdict.get("suspense_difference")
    if suspense_diff:
        suspense_decimal = Decimal(suspense_diff)
        # Format with two decimals
        expected_amount = f"{abs(suspense_decimal):.2f}"
        
        # Check the line appears
        assert "Posted to suspense instead of a branch:" in html
        assert expected_amount in html


def test_exposure_amounts_two_decimals(t1_faulty_run, monkeypatch):
    """Test that all amounts are formatted with two decimals."""
    run_id, base = t1_faulty_run
    
    monkeypatch.setenv("CORONER_BASE_DIR", str(base))
    from coroner.ui.app import app
    
    client = TestClient(app)
    
    response = client.get(f"/run/{run_id}")
    assert response.status_code == 200
    
    html = response.text
    
    # Read verdict
    verdict_file = base / "runs" / run_id / "verdict.json"
    verdict = json.loads(verdict_file.read_text())
    
    # Check exposure_sum has two decimals in HTML
    exposure_sum = Decimal(verdict["exposure_sum"])
    formatted_exposure = f"{exposure_sum:.2f}"
    assert formatted_exposure in html
    
    # Check suspense_difference has two decimals
    if "suspense_difference" in verdict:
        susp_diff = Decimal(verdict["suspense_difference"])
        formatted_susp = f"{abs(susp_diff):.2f}"
        assert formatted_susp in html


def test_business_fix_before_technical_fix(t1_faulty_run, monkeypatch):
    """Test that business_fix appears before technical fix_sentence in Exhibit 6."""
    run_id, base = t1_faulty_run
    
    monkeypatch.setenv("CORONER_BASE_DIR", str(base))
    from coroner.ui.app import app
    
    client = TestClient(app)
    
    response = client.get(f"/run/{run_id}")
    assert response.status_code == 200
    
    html = response.text
    
    # Read trap metadata
    trap_json = Path("samples/traps/T1-ebcdic-match-merge/trap.json")
    trap = json.loads(trap_json.read_text())
    
    business_fix = trap["business_fix"]
    fix_sentence = trap["fix_sentence"]
    
    # Both must appear
    assert business_fix in html
    assert fix_sentence in html
    
    # business_fix must appear before fix_sentence
    business_pos = html.find(business_fix)
    technical_pos = html.find(fix_sentence)
    
    assert business_pos > 0
    assert technical_pos > 0
    assert business_pos < technical_pos, "Business fix must appear before technical fix"
    
    # Check that "Technical fix:" label appears
    assert "Technical fix:" in html


def test_favicon_returns_204():
    """Test that /favicon.ico returns 204 No Content."""
    from coroner.ui.app import app
    
    client = TestClient(app)
    
    response = client.get("/favicon.ico")
    assert response.status_code == 204
    assert len(response.content) == 0


def test_favicon_inline_svg_in_html():
    """Test that base.html includes inline SVG favicon."""
    base_html = Path("coroner/ui/templates/base.html").read_text()
    
    # Check for inline data: favicon
    assert 'rel="icon"' in base_html
    assert 'href="data:image/svg+xml,' in base_html
    assert "viewBox='0 0 32 32'" in base_html or 'viewBox="0 0 32 32"' in base_html


def test_trap_json_files_have_business_fix():
    """Test that all trap.json files (T1-T5) have business_fix field."""
    for trap_id in ["T1", "T2", "T3", "T4", "T5"]:
        trap_files = list(Path("samples/traps").glob(f"{trap_id}-*/trap.json"))
        assert len(trap_files) == 1, f"Expected exactly one trap.json for {trap_id}"
        
        trap_file = trap_files[0]
        trap_data = json.loads(trap_file.read_text())
        
        assert "business_fix" in trap_data, f"{trap_file} missing business_fix"
        assert "fix_sentence" in trap_data, f"{trap_file} missing fix_sentence"
        
        # business_fix should be business-worded, not technical
        business_fix = trap_data["business_fix"]
        assert len(business_fix) > 10, f"{trap_file} business_fix too short"
        
        # Should not be identical to fix_sentence
        assert business_fix != trap_data["fix_sentence"], f"{trap_file} business_fix equals fix_sentence"



def test_all_branches_match_wording(monkeypatch):
    """Test that when there are no MISMATCH branches, the line says 'All N branches match'."""
    # Use T1 correct run which should have all branches matching
    from coroner.cli import run_verify
    import tempfile
    
    with tempfile.TemporaryDirectory() as tmpdir:
        cobol_file = Path("samples/traps/T1-ebcdic-match-merge/MATCH-MERGE.cob").resolve()
        copybooks = Path("samples/traps/T1-ebcdic-match-merge/copybooks").resolve()
        java_file = Path("samples/traps/T1-ebcdic-match-merge/java/correct/MatchMerge.java").resolve()
        schema_file = Path("samples/traps/T1-ebcdic-match-merge/schema.json").resolve()
        
        assert cobol_file.exists(), "T1 sample is required for the UI run page test"
        
        verdict, run_dir = run_verify(
            cobol_path=str(cobol_file),
            copybooks_dir=str(copybooks),
            java_path=str(java_file),
            schema_path=str(schema_file),
            num_cases=200,
            seed=42,
            timings=False,
            base_dir=tmpdir,
        )
        
        # Should be ALIVE
        assert verdict.status == "ALIVE"
        
        # Read reconciliation to count branches
        recon_file = run_dir / "branch_reconciliation.json"
        assert recon_file.exists()
        
        recon_data = json.loads(recon_file.read_text())
        branches = recon_data.get("branches", [])
        
        # Count MISMATCH branches
        mismatch_count = sum(1 for b in branches if b.get("status") == "MISMATCH")
        total_branches = len(branches)
        
        # For ALIVE run, should have 0 mismatches
        assert mismatch_count == 0, f"Expected 0 mismatches, found {mismatch_count}"
        assert total_branches > 0, "Expected at least one branch"
        
        # Set up UI
        monkeypatch.setenv("CORONER_BASE_DIR", tmpdir)
        from coroner.ui.app import app
        
        client = TestClient(app)
        
        response = client.get(f"/run/{run_dir.name}")
        assert response.status_code == 200
        
        html = response.text
        
        # Strip HTML comments and tags to check visible text only
        # Remove HTML comments
        visible_text = re.sub(r'<!--.*?-->', '', html, flags=re.DOTALL)
        # Remove HTML tags
        visible_text = re.sub(r'<[^>]+>', '', visible_text)
        
        # Should say "All N branches match" not "N other branches match"
        assert f"All {total_branches} branches match" in visible_text, \
            f"Expected 'All {total_branches} branches match', not found in visible text"
        
        # Should NOT say "other branches match" in visible text
        assert "other branch" not in visible_text.lower(), \
            "'other branches' found in visible text when all branches match"
