#!/usr/bin/env python3
"""Record demo videos for documentation using Playwright."""
import argparse
import json
import shutil
import sys
import time
from pathlib import Path


def check_disk_space(out_dir: Path, threshold_gb: float = 5.0):
    """Check if enough disk space is available."""
    stat = shutil.disk_usage(out_dir)
    free_gb = stat.free / (1024 ** 3)
    
    if free_gb < threshold_gb:
        print(f"ERROR: Only {free_gb:.2f} GB free disk space available", file=sys.stderr)
        print(f"Need at least {threshold_gb:.0f} GB free to record safely", file=sys.stderr)
        sys.exit(2)


def get_bundled_run_ids():
    """Get bundled demo run IDs from runs directory."""
    # These are the deterministic run IDs from the docker-compose init
    # T1 faulty: f584d5f35228
    # T1 correct: 29c15f04407b
    return {
        "t1_faulty": "f584d5f35228",
        "t1_correct": "29c15f04407b"
    }


def record_title_card(page, out_dir: Path):
    """Record title card scene."""
    print("Recording title card...")
    
    # Navigate to a simple title page (would need to be built)
    # For now, skip - needs title page HTML
    print("  SKIPPED scene title_card: needs title page HTML")
    return None


def record_problem(page, out_dir: Path):
    """Record problem statement scene."""
    print("Recording problem scene...")
    
    # This would navigate to a problem slide page
    print("  SKIPPED scene problem: needs problem slide page")
    return None


def record_zombie_verdict(page, out_dir: Path, url: str):
    """Record T1 ZOMBIE verdict page."""
    print("Recording ZOMBIE verdict scene...")
    
    run_ids = get_bundled_run_ids()
    run_id = run_ids["t1_faulty"]
    
    # Navigate to run page
    page.goto(f"{url}/run/{run_id}")
    page.wait_for_load_state("networkidle")
    time.sleep(1)  # Let animations settle
    
    # Record video
    video_path = out_dir / "zombie_verdict.webm"
    print(f"  Recording to {video_path}")
    
    # This is a placeholder - actual recording would be done via context.new_page with record_video
    return video_path


def record_alive_verdict(page, out_dir: Path, url: str):
    """Record T1 ALIVE verdict page."""
    print("Recording ALIVE verdict scene...")
    
    run_ids = get_bundled_run_ids()
    run_id = run_ids["t1_correct"]
    
    # Navigate to run page
    page.goto(f"{url}/run/{run_id}")
    page.wait_for_load_state("networkidle")
    time.sleep(1)
    
    video_path = out_dir / "alive_verdict.webm"
    print(f"  Recording to {video_path}")
    
    return video_path


def record_tamper(page, out_dir: Path, url: str):
    """Record Tamper scene showing INVALID result."""
    print("Recording Tamper scene...")
    
    run_ids = get_bundled_run_ids()
    run_id = run_ids["t1_faulty"]
    
    # Navigate to tamper page
    page.goto(f"{url}/tamper?run_id={run_id}")
    page.wait_for_load_state("networkidle")
    time.sleep(0.5)
    
    # Edit a field (change cases_divergent)
    cases_divergent_input = page.locator('input[name="cases_divergent"]')
    current_value = cases_divergent_input.input_value()
    new_value = str(int(current_value) + 1)
    cases_divergent_input.fill(new_value)
    
    # Submit
    page.click('button[type="submit"]')
    
    # Wait for INVALID result
    page.wait_for_selector("text=Certificate: INVALID", timeout=30000)
    time.sleep(1)
    
    video_path = out_dir / "tamper_invalid.webm"
    print(f"  Recording to {video_path}")
    
    return video_path


def record_matrix(page, out_dir: Path, url: str):
    """Record Detection Matrix page."""
    print("Recording matrix scene...")
    
    page.goto(f"{url}/matrix")
    page.wait_for_load_state("networkidle")
    time.sleep(1)
    
    video_path = out_dir / "matrix.webm"
    print(f"  Recording to {video_path}")
    
    return video_path


def record_scene(scene_id: str, page, out_dir: Path, url: str):
    """Record a single scene by ID."""
    scenes = {
        "title_card": record_title_card,
        "problem": record_problem,
        "zombie_verdict": record_zombie_verdict,
        "alive_verdict": record_alive_verdict,
        "tamper": record_tamper,
        "matrix": record_matrix,
    }
    
    if scene_id not in scenes:
        print(f"ERROR: Unknown scene '{scene_id}'", file=sys.stderr)
        print(f"Available scenes: {', '.join(scenes.keys())}", file=sys.stderr)
        sys.exit(1)
    
    return scenes[scene_id](page, out_dir, url)


def launch_browser(playwright):
    """Launch browser with optional channel."""
    import os
    channel = os.environ.get("SCREENSHOT_CHANNEL", "")
    if channel:
        return playwright.chromium.launch(headless=True, channel=channel)
    else:
        return playwright.chromium.launch(headless=True)


def report_sizes(out_dir: Path):
    """Report file sizes in output directory."""
    print("\nRecorded videos:")
    
    total_size = 0
    for video_file in sorted(out_dir.glob("*")):
        if video_file.is_file():
            size_mb = video_file.stat().st_size / (1024 ** 2)
            print(f"  {video_file.name}: {size_mb:.2f} MB")
            total_size += video_file.stat().st_size
    
    total_mb = total_size / (1024 ** 2)
    print(f"\nTotal size: {total_mb:.2f} MB")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Record demo videos with Playwright")
    parser.add_argument(
        "--url",
        default="http://127.0.0.1:8000",
        help="Base URL of the running UI (default: http://127.0.0.1:8000)"
    )
    parser.add_argument(
        "--out",
        default=str(Path.home() / "dev" / "lazarus-recordings"),
        help="Output directory (default: ~/dev/lazarus-recordings)"
    )
    parser.add_argument(
        "--scene",
        default="all",
        help="Scene to record (default: all)"
    )
    parser.add_argument(
        "--min-free-gb",
        type=float,
        default=5.0,
        help="Minimum free disk space in GB (default: 5.0)"
    )
    
    args = parser.parse_args()
    
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    
    # Check disk space before importing Playwright
    check_disk_space(out_dir, threshold_gb=args.min_free_gb)
    
    # Import Playwright only after disk space check
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("ERROR: Playwright not installed", file=sys.stderr)
        print("Install with: pip install -e '.[screenshots]'", file=sys.stderr)
        print("Then run: python -m playwright install chromium", file=sys.stderr)
        sys.exit(1)
    
    # Available scenes (those that don't need unbuilt pages)
    available_scenes = ["zombie_verdict", "alive_verdict", "tamper", "matrix"]
    skipped_scenes = []
    
    with sync_playwright() as p:
        browser = launch_browser(p)
        
        # Create context with video recording
        context = browser.new_context(
            viewport={'width': 1280, 'height': 720},
            device_scale_factor=1,
            record_video_dir=str(out_dir),
            record_video_size={'width': 1280, 'height': 720}
        )
        
        page = context.new_page()
        
        if args.scene == "all":
            # Record all available scenes
            for scene_id in available_scenes:
                try:
                    record_scene(scene_id, page, out_dir, args.url)
                except Exception as e:
                    print(f"  ERROR recording {scene_id}: {e}", file=sys.stderr)
            
            # Check which scenes would be skipped
            all_scenes = ["title_card", "problem"] + available_scenes
            skipped_scenes = [s for s in ["title_card", "problem"] if s not in available_scenes]
            
        else:
            # Record specific scene
            try:
                result = record_scene(args.scene, page, out_dir, args.url)
                if result is None:
                    skipped_scenes.append(args.scene)
            except Exception as e:
                print(f"ERROR recording scene: {e}", file=sys.stderr)
                sys.exit(1)
        
        # Close context to save videos
        context.close()
        browser.close()
    
    # Report results
    report_sizes(out_dir)
    
    if skipped_scenes:
        print(f"\nSKIPPED scenes: {', '.join(skipped_scenes)}")
        print("These scenes need pages that are not built yet")
        sys.exit(3)
    
    sys.exit(0)


if __name__ == "__main__":
    main()
