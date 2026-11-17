"""Test vendored UI dependencies."""

import hashlib
from pathlib import Path


def test_htmx_vendored():
    """Verify htmx.min.js file size and SHA-256 hash."""
    htmx_path = Path("coroner/ui/static/htmx.min.js")
    
    assert htmx_path.exists(), f"htmx.min.js not found at {htmx_path}"
    
    content = htmx_path.read_bytes()
    
    # Check size
    assert len(content) == 50917, f"Expected 50917 bytes, got {len(content)}"
    
    # Check SHA-256 hash
    computed_hash = hashlib.sha256(content).hexdigest()
    expected_hash = "e209dda5c8235479f3166defc7750e1dbcd5a5c1808b7792fc2e6733768fb447"
    
    assert computed_hash == expected_hash, (
        f"SHA-256 mismatch:\n"
        f"  Expected: {expected_hash}\n"
        f"  Got:      {computed_hash}"
    )
