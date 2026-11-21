"""The home page must not scroll sideways at phone width (R-141: it overflowed by 26 px).

A real browser (Playwright) loads / from a real uvicorn server at 375 px wide. The server
reads a temporary base directory that holds one real engine run, so the Recent Runs table
is on the page. The repository runs/ folder is never read or written.

Needs the `screenshots` extra (Playwright). Where Playwright's own Chromium does not run,
point SCREENSHOT_CHANNEL at an installed browser, for example SCREENSHOT_CHANNEL=chrome.
These tests are slow: they start a server and a browser.
"""
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

import pytest

from coroner.cli import run_verify

T1 = Path("samples/traps/T1-ebcdic-match-merge")
PHONE_WIDTH = 375


@pytest.fixture(scope="module")
def home_server(tmp_path_factory):
    base = tmp_path_factory.mktemp("home_375")
    run_verify(
        cobol_path=str((T1 / "MATCH-MERGE.cob").resolve()),
        copybooks_dir=str((T1 / "copybooks").resolve()),
        java_path=str((T1 / "java" / "faulty" / "MatchMerge.java").resolve()),
        schema_path=str((T1 / "schema.json").resolve()),
        num_cases=10,
        seed=42,
        base_dir=str(base),
    )
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    process = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "coroner.ui.app:app",
         "--host", "127.0.0.1", "--port", str(port), "--log-level", "warning"],
        env={**os.environ, "CORONER_BASE_DIR": str(base)},
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    try:
        for _ in range(100):
            with socket.socket() as probe:
                probe.settimeout(0.2)
                if probe.connect_ex(("127.0.0.1", port)) == 0:
                    break
            time.sleep(0.1)
        else:
            raise RuntimeError("UI server did not start")
        yield f"http://127.0.0.1:{port}"
    finally:
        process.terminate()
        process.wait(timeout=10)


@pytest.fixture(scope="module")
def phone_page(home_server):
    from playwright.sync_api import sync_playwright

    channel = os.environ.get("SCREENSHOT_CHANNEL", "")
    with sync_playwright() as playwright:
        options = {"headless": True}
        if channel:
            options["channel"] = channel
        browser = playwright.chromium.launch(**options)
        page = browser.new_page(viewport={"width": PHONE_WIDTH, "height": 800})
        page.goto(home_server + "/")
        page.wait_for_selector("#recent-runs-heading")
        yield page
        browser.close()


@pytest.mark.slow
def test_home_page_has_no_horizontal_overflow_at_375_px(phone_page):
    widths = phone_page.evaluate(
        "() => ({page: document.documentElement.scrollWidth, window: window.innerWidth})"
    )
    assert widths["window"] == PHONE_WIDTH
    assert widths["page"] <= PHONE_WIDTH, f"home page is {widths['page']} px wide at {PHONE_WIDTH} px"


@pytest.mark.slow
def test_recent_runs_table_is_inside_a_scrolling_box_at_375_px(phone_page):
    box = phone_page.evaluate(
        """() => {
            const region = document.querySelector('#recent-runs-heading + .table-scroll');
            const table = region.querySelector('table');
            return {
                overflowX: getComputedStyle(region).overflowX,
                boxRight: Math.round(region.getBoundingClientRect().right),
                tableRows: table.querySelectorAll('tbody tr').length,
            };
        }"""
    )
    assert box["tableRows"] >= 1
    assert box["overflowX"] in ("auto", "scroll")
    assert box["boxRight"] <= PHONE_WIDTH


@pytest.mark.slow
def test_run_audit_form_stays_inside_the_screen_at_375_px(phone_page):
    form = phone_page.evaluate(
        "() => { const r = document.querySelector('#run-audit-form').getBoundingClientRect();"
        " return {left: Math.round(r.left), right: Math.round(r.right)}; }"
    )
    assert form["left"] >= 0
    assert form["right"] <= PHONE_WIDTH
