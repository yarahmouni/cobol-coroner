"""Test FastAPI UI app."""

import re
from pathlib import Path

from fastapi.testclient import TestClient

from coroner.ui.app import app


client = TestClient(app)


def test_index_page_loads():
    """Test that the index page loads."""
    response = client.get("/")
    assert response.status_code == 200
    assert "COBOL Coroner" in response.text


def test_htmx_script_reference():
    """Test that the base page references the local htmx.min.js."""
    response = client.get("/")
    assert response.status_code == 200
    
    # Must reference the local htmx file
    assert "/static/htmx.min.js" in response.text
    
    # Must not reference any external URL for scripts (allow xmlns in SVG)
    # Check that http:// or https:// only appears in SVG xmlns, not in script src
    import re
    # Find all script src attributes
    script_srcs = re.findall(r'<script[^>]+src=["\']([^"\']+)["\']', response.text)
    for src in script_srcs:
        assert not src.startswith("http://") and not src.startswith("https://"), f"External script URL found: {src}"


def test_htmx_static_file_served():
    """Test that htmx.min.js is served correctly."""
    response = client.get("/static/htmx.min.js")
    assert response.status_code == 200
    assert len(response.content) == 50917


def test_invalid_run_id_rejected():
    """Test that an invalid run_id is rejected with 404 before any file access."""
    # Path traversal attempt
    response = client.get("/run/../etc")
    assert response.status_code == 404
    
    # Too short
    response = client.get("/run/abc")
    assert response.status_code == 404
    
    # Too long
    response = client.get("/run/abcdef123456789")
    assert response.status_code == 404
    
    # Uppercase
    response = client.get("/run/ABCDEF123456")
    assert response.status_code == 404
    
    # Special characters
    response = client.get("/run/abc-def12345")
    assert response.status_code == 404


def compute_relative_luminance(r: int, g: int, b: int) -> float:
    """Compute relative luminance using WCAG 2 formula.
    
    Args:
        r, g, b: RGB values in range 0-255
        
    Returns:
        Relative luminance (0-1)
    """
    def linearize(c: int) -> float:
        """Linearize an 8-bit color channel."""
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
    """Compute WCAG 2 contrast ratio between two luminances.
    
    Args:
        l1, l2: Relative luminances (0-1)
        
    Returns:
        Contrast ratio (1-21)
    """
    lighter = max(l1, l2)
    darker = min(l1, l2)
    return (lighter + 0.05) / (darker + 0.05)


def parse_hex_color(hex_color: str) -> tuple[int, int, int]:
    """Parse hex color to RGB tuple.
    
    Args:
        hex_color: Hex color string like "#1a1a1a" or "1a1a1a"
        
    Returns:
        RGB tuple (r, g, b) in range 0-255
    """
    hex_color = hex_color.lstrip("#")
    return (
        int(hex_color[0:2], 16),
        int(hex_color[2:4], 16),
        int(hex_color[4:6], 16),
    )


def test_wcag_contrast_ratios():
    """Test that all text meets WCAG 2 contrast ratio requirements (at least 4.5:1)."""
    # Read the base template to extract CSS color values
    base_template = Path("coroner/ui/templates/base.html")
    assert base_template.exists()
    
    css_content = base_template.read_text()
    
    # Extract CSS custom properties (look for the new names)
    bg_match = re.search(r'--bg-color:\s*([#0-9a-fA-F]+)', css_content)
    text_match = re.search(r'--text-color:\s*([#0-9a-fA-F]+)', css_content)
    alive_bg_match = re.search(r'--alive-bg:\s*([#0-9a-fA-F]+)', css_content)
    alive_color_match = re.search(r'--alive-color:\s*([#0-9a-fA-F]+)', css_content)
    zombie_bg_match = re.search(r'--zombie-bg:\s*([#0-9a-fA-F]+)', css_content)
    zombie_color_match = re.search(r'--zombie-color:\s*([#0-9a-fA-F]+)', css_content)
    error_bg_match = re.search(r'--error-bg:\s*([#0-9a-fA-F]+)', css_content)
    error_color_match = re.search(r'--error-color:\s*([#0-9a-fA-F]+)', css_content)
    
    assert bg_match, "Background color not found in CSS"
    assert text_match, "Text color not found in CSS"
    assert alive_bg_match, "ALIVE background color not found in CSS"
    assert alive_color_match, "ALIVE color not found in CSS"
    assert zombie_bg_match, "ZOMBIE background color not found in CSS"
    assert zombie_color_match, "ZOMBIE color not found in CSS"
    assert error_bg_match, "ERROR background color not found in CSS"
    assert error_color_match, "ERROR color not found in CSS"
    
    # Parse colors
    bg_color = parse_hex_color(bg_match.group(1))
    text_color = parse_hex_color(text_match.group(1))
    alive_bg_color = parse_hex_color(alive_bg_match.group(1))
    alive_text_color = parse_hex_color(alive_color_match.group(1))
    zombie_bg_color = parse_hex_color(zombie_bg_match.group(1))
    zombie_text_color = parse_hex_color(zombie_color_match.group(1))
    error_bg_color = parse_hex_color(error_bg_match.group(1))
    error_text_color = parse_hex_color(error_color_match.group(1))
    
    # Compute luminances
    bg_lum = compute_relative_luminance(*bg_color)
    text_lum = compute_relative_luminance(*text_color)
    alive_bg_lum = compute_relative_luminance(*alive_bg_color)
    alive_text_lum = compute_relative_luminance(*alive_text_color)
    zombie_bg_lum = compute_relative_luminance(*zombie_bg_color)
    zombie_text_lum = compute_relative_luminance(*zombie_text_color)
    error_bg_lum = compute_relative_luminance(*error_bg_color)
    error_text_lum = compute_relative_luminance(*error_text_color)
    
    # Compute contrast ratios
    text_ratio = compute_contrast_ratio(bg_lum, text_lum)
    alive_ratio = compute_contrast_ratio(alive_bg_lum, alive_text_lum)
    zombie_ratio = compute_contrast_ratio(zombie_bg_lum, zombie_text_lum)
    error_ratio = compute_contrast_ratio(error_bg_lum, error_text_lum)
    
    # Assert WCAG 2 AA requirement: at least 4.5:1
    assert text_ratio >= 4.5, (
        f"Text contrast ratio {text_ratio:.2f}:1 is below 4.5:1 "
        f"(background {bg_match.group(1)} vs text {text_match.group(1)})"
    )
    
    assert alive_ratio >= 4.5, (
        f"ALIVE contrast ratio {alive_ratio:.2f}:1 is below 4.5:1 "
        f"(background {alive_bg_match.group(1)} vs text {alive_color_match.group(1)})"
    )
    
    assert zombie_ratio >= 4.5, (
        f"ZOMBIE contrast ratio {zombie_ratio:.2f}:1 is below 4.5:1 "
        f"(background {zombie_bg_match.group(1)} vs text {zombie_color_match.group(1)})"
    )
    
    assert error_ratio >= 4.5, (
        f"ERROR contrast ratio {error_ratio:.2f}:1 is below 4.5:1 "
        f"(background {error_bg_match.group(1)} vs text {error_color_match.group(1)})"
    )
