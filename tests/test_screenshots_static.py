"""Static tests for screenshots (no browser execution)."""
import re
from pathlib import Path


def test_readme_images_exist():
    """Every image referenced in README exists under docs/screenshots/."""
    readme = Path("README.md").read_text()
    
    # Parse markdown image syntax ![alt](path)
    for match in re.finditer(r'!\[([^\]]+)\]\(([^)]+)\)', readme):
        alt_text, path = match.groups()
        
        if path.startswith("docs/screenshots/"):
            assert Path(path).exists(), f"Image {path} not found"
            assert alt_text.strip(), f"Image {path} has empty alt text"


def test_demo_gif_size():
    """demo.gif is under 5 MB."""
    gif_path = Path("docs/screenshots/demo.gif")
    
    if gif_path.exists():
        size_mb = gif_path.stat().st_size / (1024 * 1024)
        assert size_mb < 5, f"demo.gif is {size_mb:.2f} MB, must be under 5 MB"


def test_no_hardcoded_verdict_numbers():
    """Screenshot script has no hardcoded trap detection numbers."""
    script_path = Path("scripts/make_screenshots.py")
    
    if not script_path.exists():
        return  # Script not created yet
    
    script = script_path.read_text()
    
    # These are the measured trap detection counts that should not be hardcoded
    forbidden = ["682", "856", "429", "87", "602"]
    
    for num in forbidden:
        # Check if the number appears as a standalone word (not in filenames, etc.)
        pattern = r'\b' + num + r'\b'
        if re.search(pattern, script):
            # Make sure it's not in a comment explaining what not to do
            lines_with_num = [
                line for line in script.split('\n')
                if re.search(pattern, line) and "forbidden" not in line.lower()
            ]
            if lines_with_num:
                assert False, f"Hardcoded trap detection number {num} found in script: {lines_with_num[0]}"
