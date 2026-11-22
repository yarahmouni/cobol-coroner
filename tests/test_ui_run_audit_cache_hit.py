"""Home page: a Run audit that matches an existing run shows the same verdict box as a finished job.

The runs are real engine audits (fixtures t1_faulty_200 and t1_correct_200: T1, 200 cases, seed 42, the
default values of the form). They are copied into a temporary base directory, so the repository runs/
folder is never read or written. Expected values are read from each run's verdict.json.

The browser test needs the `screenshots` extra (Playwright). Where Playwright's own Chromium does not
run, point SCREENSHOT_CHANNEL at an installed browser, for example SCREENSHOT_CHANNEL=chrome.
"""
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

REPO_ROOT = Path(__file__).resolve().parent.parent
INDEX_TEMPLATE = REPO_ROOT / "coroner" / "ui" / "templates" / "index.html"
REUSED_NOTE = "Same inputs as an existing run: result reused."


def _write_index(base: Path, entries: dict) -> None:
    """Record each (sample, port, seed, cases) -> run id in the base directory with the app's own function."""
    os.environ["CORONER_BASE_DIR"] = str(base)
    from coroner.ui.app import update_run_index

    for (sample, port, seed, cases), run_id in entries.items():
        update_run_index(sample, port, seed, cases, run_id)


def _client(base: Path, exchange: Path) -> TestClient:
    os.environ["CORONER_BASE_DIR"] = str(base)
    os.environ["CORONER_EXCHANGE_DIR"] = str(exchange)
    from coroner.ui.app import app

    return TestClient(app)


def _post(client: TestClient, port: str, seed: int = 42, cases: int = 200):
    return client.post("/api/run", json={"sample": "T1", "port": port, "seed": seed, "cases": cases})


@pytest.fixture
def indexed_base(tmp_path, t1_faulty_200, t1_correct_200, copy_runs):
    """A temporary base with copies of the two real runs, indexed as the form defaults, and an empty exchange."""
    base = tmp_path / "base"
    copy_runs(t1_faulty_200.base, base, t1_faulty_200.run_id)
    copy_runs(t1_correct_200.base, base, t1_correct_200.run_id)
    _write_index(base, {
        ("T1", "faulty", 42, 200): t1_faulty_200.run_id,
        ("T1", "correct", 42, 200): t1_correct_200.run_id,
    })
    exchange = tmp_path / "exchange"
    exchange.mkdir()
    return base, exchange


def test_cache_hit_of_a_zombie_run_carries_the_verdict_counts_and_exposure(indexed_base, t1_faulty_200):
    base, exchange = indexed_base
    verdict = json.loads((t1_faulty_200.run_dir / "verdict.json").read_text())
    response = _post(_client(base, exchange), "faulty")

    assert response.status_code == 200
    data = response.json()
    assert data["run_id"] == t1_faulty_200.run_id
    assert data["cached"] is True
    assert data["verdict"] == verdict["status"] == "ZOMBIE"
    assert data["cases_divergent"] == verdict["cases_divergent"] > 0
    assert data["cases_total"] == verdict["cases_total"] == 200
    noun = "branch" if verdict["affected_branches"] == 1 else "branches"
    assert data["exposure_line"] == f"Exposure: {verdict['exposure_sum']} across {verdict['affected_branches']} {noun}"
    # no job was created
    assert not (exchange / "jobs").exists() or not list((exchange / "jobs").iterdir())


def test_cache_hit_of_an_alive_run_carries_the_counts_and_no_exposure(indexed_base, t1_correct_200):
    base, exchange = indexed_base
    verdict = json.loads((t1_correct_200.run_dir / "verdict.json").read_text())
    response = _post(_client(base, exchange), "correct")

    assert response.status_code == 200
    data = response.json()
    assert data["run_id"] == t1_correct_200.run_id
    assert data["cached"] is True
    assert data["verdict"] == verdict["status"] == "ALIVE"
    assert data["cases_divergent"] == verdict["cases_divergent"] == 0
    assert data["cases_total"] == verdict["cases_total"] == 200
    assert data["exposure_line"] is None


def test_cache_hit_of_a_run_without_verdict_json_has_the_old_fields_only(indexed_base, t1_faulty_200):
    base, exchange = indexed_base
    broken_id = "abcdef012345"
    shutil.copytree(base / "runs" / t1_faulty_200.run_id, base / "runs" / broken_id)
    (base / "runs" / broken_id / "verdict.json").unlink()
    _write_index(base, {("T1", "faulty", 43, 200): broken_id})

    response = _post(_client(base, exchange), "faulty", seed=43)

    assert response.status_code == 200
    assert response.json() == {"run_id": broken_id, "cached": True}


def test_cache_hit_of_a_run_with_unreadable_verdict_json_has_the_old_fields_only(indexed_base, t1_faulty_200):
    base, exchange = indexed_base
    broken_id = "abcdef012346"
    shutil.copytree(base / "runs" / t1_faulty_200.run_id, base / "runs" / broken_id)
    (base / "runs" / broken_id / "verdict.json").write_text("{not json")
    _write_index(base, {("T1", "faulty", 44, 200): broken_id})

    response = _post(_client(base, exchange), "faulty", seed=44)

    assert response.status_code == 200
    assert response.json() == {"run_id": broken_id, "cached": True}


def test_done_job_and_cache_hit_give_the_same_result_fields(indexed_base, t1_faulty_200):
    """The job status and the cache-hit answer read the run through one helper."""
    from coroner.ui.pages import run_result_summary

    base, exchange = indexed_base
    summary = run_result_summary(base / "runs" / t1_faulty_200.run_id)
    data = _post(_client(base, exchange), "faulty").json()
    assert {key: data[key] for key in summary} == summary


# ------------------------------------------------------------------ the page script


def test_script_renders_both_paths_with_one_function_and_textcontent_only():
    template = INDEX_TEMPLATE.read_text()
    script = "\n".join(re.findall(r"<script\b[^>]*>(.*?)</script>", template, flags=re.DOTALL | re.IGNORECASE))
    assert script.count("function renderResult(") == 1
    assert "renderResult(resultDiv, data, false)" in script
    assert "renderResult(resultDiv, response, true)" in script
    assert REUSED_NOTE in script
    function = script[script.index("function renderResult("):]
    function = function[:function.index("\n}\n") + 3]
    assert "innerHTML" not in function
    assert "Cached result: " in function  # the fallback when no verdict is recorded


# ------------------------------------------------------------------ the browser


@pytest.fixture
def home_server(indexed_base):
    base, exchange = indexed_base
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    process = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "coroner.ui.app:app",
         "--host", "127.0.0.1", "--port", str(port), "--log-level", "warning"],
        env={**os.environ, "CORONER_BASE_DIR": str(base), "CORONER_EXCHANGE_DIR": str(exchange)},
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


@pytest.mark.slow
def test_browser_submitting_an_existing_run_shows_the_verdict_box(home_server, t1_faulty_200, t1_correct_200):
    from playwright.sync_api import sync_playwright

    channel = os.environ.get("SCREENSHOT_CHANNEL", "")
    faulty = json.loads((t1_faulty_200.run_dir / "verdict.json").read_text())
    with sync_playwright() as playwright:
        options = {"headless": True}
        if channel:
            options["channel"] = channel
        browser = playwright.chromium.launch(**options)
        try:
            page = browser.new_page()
            page.goto(home_server + "/")

            # the form defaults: seed 42, 200 cases; T1 faulty is an existing run
            page.select_option("#sample", "T1")
            page.select_option("#port", "faulty")
            assert page.input_value("#seed") == "42"
            assert page.input_value("#cases") == "200"
            page.click("#run-audit-form button[type=submit]")
            page.wait_for_selector("#audit-result .verdict-badge.zombie")

            text = page.inner_text("#audit-result")
            assert "ZOMBIE" in text
            assert f"{faulty['cases_divergent']} of {faulty['cases_total']} cases diverge." in text
            assert page.inner_text("#exposure-text") == (
                f"Exposure: {faulty['exposure_sum']} across {faulty['affected_branches']} branches"
            )
            assert page.inner_text("#reused-note") == REUSED_NOTE
            assert "Cached result" not in text
            link = page.locator("#audit-result a", has_text="Open the run")
            assert link.get_attribute("href") == f"/run/{t1_faulty_200.run_id}"

            # the correct port: ALIVE, no exposure line
            page.select_option("#port", "correct")
            page.click("#run-audit-form button[type=submit]")
            page.wait_for_selector("#audit-result .verdict-badge.alive")
            text = page.inner_text("#audit-result")
            assert "ALIVE" in text
            assert "0 of 200 cases diverge." in text
            assert page.locator("#exposure-text").count() == 0
            assert page.inner_text("#reused-note") == REUSED_NOTE
            assert page.locator("#audit-result a", has_text="Open the run").get_attribute(
                "href") == f"/run/{t1_correct_200.run_id}"
        finally:
            browser.close()
