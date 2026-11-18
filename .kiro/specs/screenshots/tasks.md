# Screenshots tasks

- [ ] **Task 1**: pyproject.toml optional extra and README third-party section
  - Add `screenshots = ["playwright==1.64.1", "pillow==13.0.0"]` to optional-dependencies
  - Add playwright (Apache-2.0) and Pillow (MIT-CMU) to README "Third-party components"
  - Note that `python -m playwright install chromium` downloads a browser
  - Done when: `pip install -e ".[screenshots]"` installs both, licenses in README

- [ ] **Task 2**: scripts/make_screenshots.py skeleton and temp workspace
  - Create scripts/make_screenshots.py with main(), setup_temp_workspace(), cleanup()
  - Use tempfile.mkdtemp with prefix coroner_screenshots_
  - Done when: script creates temp dir, prints it, cleans up on exit

- [ ] **Task 3**: Produce real runs (T1 faulty, T1 correct, catalog)
  - produce_runs(base_dir) runs engine via subprocess with CORONER_BASE_DIR
  - T1 faulty: samples/traps/T1-ebcdic-sort-mismatch/BRANCH-TOTALS.cob with faulty/BranchTotals.java
  - T1 correct: same COBOL with correct/BranchTotals.java
  - Catalog: `python -m coroner traps`
  - Parse run_ids from CLI output
  - Done when: function returns {"t1_zombie": run_id, "t1_alive": run_id}, catalog exists in temp_dir/runs/

- [ ] **Task 4**: Start and stop UI server
  - start_ui_server(base_dir): find free port, start uvicorn with CORONER_BASE_DIR, wait for health
  - stop_ui_server(): terminate process
  - Done when: server starts, responds to /, stops cleanly

- [ ] **Task 5**: Playwright screenshots (dark T1 ZOMBIE, light T1 ALIVE, matrix)
  - Install playwright, launch headless chromium, viewport 1280x800
  - t1-zombie-dark.png: navigate to T1 faulty run page, default dark theme
  - alive-light.png: set localStorage coronerTheme=light, navigate to T1 correct, reload
  - matrix.png: navigate to /matrix
  - Save with Pillow optimize=True
  - Done when: three PNGs in docs/screenshots/, readable in an image viewer

- [ ] **Task 6**: Tamper certificate and verify-invalid.png
  - Copy T1 faulty run dir, modify certificate.json (cases_divergent + 1)
  - Navigate to tampered run page, click Verify button, wait for "Certificate: INVALID"
  - Screenshot verify-invalid.png
  - Done when: PNG shows INVALID verdict, caption states "Verify on a copy of a real certificate with one field changed"

- [ ] **Task 7**: Commit blocked screenshot
  - capture_commit_blocked(): git clone --local, hooks path .githooks
  - Replace Java from .kiro/coroner-scope.json with HALF_EVEN variant
  - Stage and run `git commit -m "Port credit fees"`, capture output and exit code
  - Sanitize output (replace clone path with "repo", check for home paths)
  - Render as terminal HTML, screenshot with Playwright
  - Done when: commit-blocked.png shows blocked commit, no home paths

- [ ] **Task 8**: Demo GIF
  - capture_demo_gif(page, port, run_id): navigate from / to T1 faulty run
  - Capture frames at ~8 fps (page.screenshot every 125 ms)
  - Pause on verdict and example, scroll to branch chart
  - Build GIF with Pillow (width 960, reduced palette, merge duplicates)
  - Fail if < 10 s or >= 5 MB
  - Done when: demo.gif plays 10-15 s, under 5 MB

- [ ] **Task 9**: Script output and reporting
  - Print each output file with size
  - Never prints a home directory path, a temporary directory path or the clone path
  - Done when: running script shows 6 files with sizes, no home or temp paths

- [ ] **Task 10**: Makefile target
  - Add `screenshots:` target running `$(PYTHON) scripts/make_screenshots.py`
  - Done when: `make screenshots` runs the script

- [ ] **Task 11**: README integration
  - demo.gif right under title/intro
  - "Screenshots" section with five PNGs, alt text and captions
  - Note that images are from `make screenshots`
  - No hardcoded numbers in captions
  - Done when: README shows GIF and screenshots

- [ ] **Task 12**: Static tests tests/test_screenshots_static.py
  - test_readme_images_exist(): parse markdown, check paths and alt text
  - test_demo_gif_size(): under 5 MB
  - test_no_hardcoded_numbers(): no trap detection counts in script
  - Done when: pytest tests/test_screenshots_static.py passes without running browser
