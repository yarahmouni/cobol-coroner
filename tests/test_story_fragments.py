"""Tests for the story fragment routes: the gate check, Run it yourself and job polling.

The routes under /story call the route functions of coroner/ui/app.py, so the tests compare their
answers with the answers of the API routes and use the real engine, worker and replay. Tests that
need runs use the session fixture `story_runs` (a real catalog in a temporary base directory).
"""
import importlib
import json
import shutil
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from coroner.ui.app import app, clear_gate_check_cache, reset_rate_limiter

from story_html import anchors, has_live_region_root, into_container, live_regions, tags, visible_text

REPO_ROOT = Path(__file__).resolve().parent.parent
ui_app = importlib.import_module("coroner.ui.app")

BAD_RUN_ID = '"><img src=x onerror=alert(1)>'


@pytest.fixture(autouse=True)
def clean_state():
    clear_gate_check_cache()
    reset_rate_limiter()
    yield
    clear_gate_check_cache()
    reset_rate_limiter()


def _t1_run_ids(base: Path):
    catalog = json.loads((base / "runs" / "trap_catalog.json").read_text())
    entry = next(trap for trap in catalog["traps"] if trap["id"] == "T1")
    return entry["faulty_run_id"], entry["correct_run_id"]


def _form_values(page: str) -> dict:
    """name -> value of every hidden input of the fragment."""
    return {a["name"]: a["value"] for t, a in tags(page, "input") if a.get("type") == "hidden"}


def _alert_text(page: str) -> str:
    assert has_live_region_root(page)
    assert [a for t, a in tags(page) if a.get("role") == "alert"]
    return visible_text(page)


@pytest.fixture
def empty_base(tmp_path, monkeypatch):
    monkeypatch.setenv("CORONER_BASE_DIR", str(tmp_path))
    return TestClient(app), tmp_path


@pytest.fixture
def run_env(tmp_path, monkeypatch):
    """A client with its own base and exchange directories (for Run it yourself)."""
    base = tmp_path / "base"
    exchange = tmp_path / "exchange"
    base.mkdir()
    exchange.mkdir()
    monkeypatch.setenv("CORONER_BASE_DIR", str(base))
    monkeypatch.setenv("CORONER_EXCHANGE_DIR", str(exchange))
    return TestClient(app), base, exchange


@pytest.fixture
def edited_copy(story_runs, tmp_path, monkeypatch):
    copy = tmp_path / "base_copy"
    shutil.copytree(story_runs.base, copy)
    monkeypatch.setenv("CORONER_BASE_DIR", str(copy))
    return TestClient(app), copy


# ------------------------------------------------------------------ gate check: real replays (slow)


@pytest.mark.slow
def test_gate_fragment_blocks_the_t1_faulty_run_with_the_endpoint_message(story_runs, story_client):
    faulty, _ = _t1_run_ids(story_runs.base)
    fragment = story_client.post("/story/gate-check", data={"run_id": faulty, "view": "business"})
    assert fragment.status_code == 200
    assert has_live_region_root(fragment.text)
    # Same certificate: the API answers from the cache the fragment filled.
    api = story_client.post("/api/gate-check", data={"run_id": faulty}).json()
    assert api["status"] == "blocked" and api["exit_code"] == 1
    assert api["message"] == "This ZOMBIE migration cannot be committed"
    text = visible_text(fragment.text)
    assert api["message"] in text
    assert f"Exit code {api['exit_code']}" in text
    assert any("zombie" in a.get("class", "").split() for t, a in tags(fragment.text, "div"))
    assert "<svg" in fragment.text and "<rect" in fragment.text


@pytest.mark.slow
def test_gate_result_is_announced_by_exactly_one_live_region_on_the_real_step_page(story_runs, story_client):
    """R-138 finding: the gate result used to sit in two live regions (the container and the fragment)."""
    faulty, correct = _t1_run_ids(story_runs.base)
    step4 = story_client.get("/story/step/4").text
    step7 = story_client.get("/story/step/7").text
    assert live_regions(step4) == 0 and live_regions(step7) == 0
    for page, run_id in ((step4, faulty), (step7, correct)):
        reset_rate_limiter()  # the second replay must not meet the 1 per 10 seconds bucket
        fragment = story_client.post("/story/gate-check", data={"run_id": run_id}).text
        assert "Exit code" in visible_text(fragment)
        assert live_regions(fragment) == 1
        assert live_regions(into_container(page, "gate-result", fragment)) == 1


@pytest.mark.slow
def test_gate_fragment_allows_the_t1_correct_run_with_the_endpoint_message(story_runs, story_client):
    _, correct = _t1_run_ids(story_runs.base)
    fragment = story_client.post("/story/gate-check", data={"run_id": correct})
    api = story_client.post("/api/gate-check", data={"run_id": correct}).json()
    assert api["status"] == "allowed" and api["exit_code"] == 0
    assert api["message"] == "Commit allowed"
    text = visible_text(fragment.text)
    assert api["message"] in text and "Exit code 0" in text
    assert has_live_region_root(fragment.text)
    assert any("alive" in a.get("class", "").split() for t, a in tags(fragment.text, "div"))
    assert "<circle" in fragment.text


@pytest.mark.slow
def test_gate_fragment_shows_an_invalid_certificate_with_the_amber_triangle(edited_copy):
    client, base = edited_copy
    faulty, _ = _t1_run_ids(base)
    path = base / "runs" / faulty / "certificate.json"
    certificate = json.loads(path.read_text())
    certificate["status"] = "ALIVE"
    path.write_text(json.dumps(certificate, indent=2, sort_keys=True))

    fragment = client.post("/story/gate-check", data={"run_id": faulty})
    api = client.post("/api/gate-check", data={"run_id": faulty}).json()
    assert api["status"] == "blocked"
    assert api["message"] == "Certificate invalid or does not match the audited files"
    assert api["message"] in visible_text(fragment.text)
    assert any("invalid" in a.get("class", "").split() for t, a in tags(fragment.text, "div"))
    assert "<polygon" in fragment.text
    assert has_live_region_root(fragment.text)


@pytest.mark.slow
def test_gate_fragment_shares_the_cache_and_the_rate_limit_of_the_api(story_runs, story_client, monkeypatch):
    """The fragment is not a second endpoint: it hits the cache and the 1-per-window bucket of /api/gate-check."""
    monkeypatch.setenv("CORONER_GATE_CHECK_RATE_WINDOW", "3600")
    faulty, correct = _t1_run_ids(story_runs.base)

    # The API replays the faulty run and uses the bucket. The fragment for the same
    # certificate is a cache hit: no 429, the same message.
    api = story_client.post("/api/gate-check", data={"run_id": faulty})
    assert api.status_code == 200
    cached = story_client.post("/story/gate-check", data={"run_id": faulty})
    assert api.json()["message"] in visible_text(cached.text)
    assert not [a for t, a in tags(cached.text) if a.get("role") == "alert"]

    # A different certificate needs a replay, and the bucket is used up: both routes answer 429.
    blocked_fragment = story_client.post("/story/gate-check", data={"run_id": correct})
    blocked_api = story_client.post("/api/gate-check", data={"run_id": correct})
    assert blocked_api.status_code == 429
    text = _alert_text(blocked_fragment.text)
    assert blocked_api.json()["detail"] in text


@pytest.mark.slow
def test_gate_fragment_429_shows_the_retry_after_seconds_of_the_response(story_runs, story_client, monkeypatch):
    monkeypatch.setenv("CORONER_GATE_CHECK_RATE_WINDOW", "3600")
    original = ui_app.gate_check
    responses = []

    async def recording(request, run_id):
        response = await original(request, run_id=run_id)
        responses.append(response)
        return response

    monkeypatch.setattr(ui_app, "gate_check", recording)
    faulty, correct = _t1_run_ids(story_runs.base)
    story_client.post("/story/gate-check", data={"run_id": faulty})
    fragment = story_client.post("/story/gate-check", data={"run_id": correct, "view": "engineer"})

    assert [r.status_code for r in responses] == [200, 429]
    seconds = responses[1].headers["Retry-After"]
    assert int(seconds) > 0
    text = _alert_text(fragment.text)
    assert f"Try again in {seconds} seconds." in text
    assert "Rate limit exceeded for gate-check" in text
    # No automatic retry: the only way on is the visitor's button, which carries the same values.
    assert "hx-trigger" not in fragment.text
    form = [a for t, a in tags(fragment.text, "form")]
    assert len(form) == 1 and form[0]["hx-post"] == "/story/gate-check"
    assert _form_values(fragment.text) == {"run_id": correct, "view": "engineer"}
    assert "Check again" in text


@pytest.mark.slow
def test_gate_fragment_503_when_the_replay_does_not_complete_and_a_new_replay_starts_next(story_runs, story_client, monkeypatch):
    monkeypatch.setenv("CORONER_REPLAY_TIMEOUT", "1")
    monkeypatch.setenv("CORONER_GATE_CHECK_RATE_WINDOW", "1")
    _, correct = _t1_run_ids(story_runs.base)

    first = story_client.post("/story/gate-check", data={"run_id": correct})
    text = _alert_text(first.text)
    assert "Replay did not complete, try again" in text
    assert "Try again in 1 second." in text
    assert "Check again" in text
    first_group = ui_app.get_last_replay_pgid()
    assert first_group is not None

    time.sleep(1.2)
    second = story_client.post("/story/gate-check", data={"run_id": correct})
    assert "Replay did not complete, try again" in _alert_text(second.text)
    assert ui_app.get_last_replay_pgid() != first_group

    # Nothing was cached: with the normal timeout the real answer comes back.
    monkeypatch.delenv("CORONER_REPLAY_TIMEOUT")
    time.sleep(1.2)
    third = story_client.post("/story/gate-check", data={"run_id": correct})
    assert "Commit allowed" in visible_text(third.text)


@pytest.mark.slow
def test_gate_fragment_makes_the_same_rate_limit_calls_as_the_api(story_runs, story_client, monkeypatch):
    """The fragment adds no limiter: the checks made through it equal those of POST /api/gate-check."""
    faulty, _ = _t1_run_ids(story_runs.base)
    original = ui_app.check_rate_limit
    keys = []

    def recording(key, limit, window):
        keys.append((key, limit, window))
        return original(key, limit, window)

    monkeypatch.setattr(ui_app, "check_rate_limit", recording)
    assert story_client.post("/api/gate-check", data={"run_id": faulty}).status_code == 200
    api_keys = list(keys)

    keys.clear()
    clear_gate_check_cache()
    reset_rate_limiter()
    assert "cannot be committed" in visible_text(story_client.post("/story/gate-check", data={"run_id": faulty}).text)
    assert api_keys and keys == api_keys
    assert any(key.startswith("endpoint:/api/gate-check:ip:") for key, _, _ in keys)


# ------------------------------------------------------------------ gate check: errors without a replay (fast)


def test_gate_fragment_unknown_run_is_an_alert_without_a_retry_button(empty_base):
    client, _ = empty_base
    response = client.post("/story/gate-check", data={"run_id": "999999999999"})
    assert response.status_code == 200
    text = _alert_text(response.text)
    assert "Certificate not found" in text
    assert not tags(response.text, "form")


def test_gate_fragment_invalid_run_id_is_an_alert(empty_base):
    client, _ = empty_base
    for data in ({"run_id": "invalid"}, {"run_id": ""}, {}):
        response = client.post("/story/gate-check", data=data)
        assert response.status_code == 200
        assert "Invalid run_id" in _alert_text(response.text)


def test_gate_fragment_certificate_over_one_megabyte_is_an_alert(empty_base):
    client, base = empty_base
    run_dir = base / "runs" / "0123456789ab"
    run_dir.mkdir(parents=True)
    (run_dir / "certificate.json").write_bytes(b" " * (1024 * 1024 + 1))
    api = client.post("/api/gate-check", data={"run_id": "0123456789ab"})
    assert api.status_code == 413
    text = _alert_text(client.post("/story/gate-check", data={"run_id": "0123456789ab"}).text)
    assert api.json()["detail"] in text
    assert not tags(client.post("/story/gate-check", data={"run_id": "0123456789ab"}).text, "form")


def test_gate_fragment_unreadable_certificate_is_an_alert_with_a_retry_button(empty_base):
    client, base = empty_base
    run_dir = base / "runs" / "0123456789ab"
    run_dir.mkdir(parents=True)
    (run_dir / "certificate.json").write_text("{broken")
    api = client.post("/api/gate-check", data={"run_id": "0123456789ab"})
    assert api.status_code == 500
    page = client.post("/story/gate-check", data={"run_id": "0123456789ab"}).text
    assert api.json()["detail"] in _alert_text(page)
    assert _form_values(page)["run_id"] == "0123456789ab"


def test_gate_fragment_escapes_the_run_id_it_puts_back_into_the_retry_form(empty_base, monkeypatch):
    client, _ = empty_base
    monkeypatch.setattr(ui_app, "check_rate_limit", lambda key, limit, window: 5)
    page = client.post("/story/gate-check", data={"run_id": BAD_RUN_ID, "view": "engineer"}).text
    assert "<img" not in page
    assert "&gt;&lt;img" in page
    assert _form_values(page) == {"run_id": BAD_RUN_ID, "view": "engineer"}
    assert "Try again in 5 seconds." in _alert_text(page)


# ------------------------------------------------------------------ Run it yourself (fast and slow)


VALID_RUN = {"port": "faulty", "seed": "42", "cases": "20", "view": "engineer"}


def test_run_fragment_422_shows_a_plain_sentence_not_the_validation_report(run_env):
    client, _, _ = run_env
    for bad in ({"port": "faulty", "seed": "-1", "cases": "20"},
                {"port": "faulty", "seed": "abc", "cases": "20"},
                {"port": "other", "seed": "42", "cases": "20"},
                {"port": "faulty", "seed": "42", "cases": "9"},
                {}):
        api = client.post("/api/run", data={"sample": "T1", **bad})
        assert api.status_code == 422
        response = client.post("/story/run", data=bad)
        assert response.status_code == 200
        text = _alert_text(response.text)
        assert "The audit was not started. Check that the seed" in text
        assert "validation error" not in text and "pydantic" not in text
        assert not tags(response.text, "form")
        reset_rate_limiter()


def test_run_fragment_202_returns_a_polling_region_that_carries_the_view(run_env):
    client, _, exchange = run_env
    response = client.post("/story/run", data=VALID_RUN)
    assert response.status_code == 200
    assert has_live_region_root(response.text)
    region = [a for t, a in tags(response.text, "div") if "hx-get" in a][0]
    job_id = region["hx-get"].split("/story/job/")[1].split("?")[0]
    assert (exchange / "jobs" / job_id / "request.json").is_file()
    assert region["hx-get"] == f"/story/job/{job_id}?view=engineer"
    assert region["hx-trigger"] == "every 2s"
    assert region["hx-swap"] == "outerHTML"
    assert region["role"] == "status" and region["aria-live"] == "polite"
    request = json.loads((exchange / "jobs" / job_id / "request.json").read_text())
    assert (request["sample"], request["port"], request["seed"], request["cases"]) == ("T1", "faulty", 42, 20)
    assert "queued" in visible_text(response.text)


def test_run_fragment_429_for_a_second_audit_shows_the_retry_time_and_a_retry_form(run_env):
    client, _, _ = run_env
    assert client.post("/story/run", data=VALID_RUN).status_code == 200
    second = client.post("/story/run", data=VALID_RUN)
    api = client.post("/api/run", data={"sample": "T1", **{k: v for k, v in VALID_RUN.items() if k != "view"}})
    assert api.status_code == 429
    text = _alert_text(second.text)
    assert api.json()["detail"] in text
    assert f"Try again in {api.headers['Retry-After']} seconds." in text
    assert _form_values(second.text) == VALID_RUN
    form = [a for t, a in tags(second.text, "form")][0]
    assert form["hx-post"] == "/story/run"


def test_run_fragment_makes_the_same_rate_limit_calls_as_the_api(run_env, monkeypatch):
    client, _, _ = run_env
    original = ui_app.check_rate_limit
    keys = []

    def recording(key, limit, window):
        keys.append((key, limit, window))
        return original(key, limit, window)

    monkeypatch.setattr(ui_app, "check_rate_limit", recording)
    client.post("/api/run", data={"sample": "T1", "port": "faulty", "seed": "42", "cases": "20"})
    api_keys = list(keys)
    keys.clear()
    reset_rate_limiter()
    client.post("/story/run", data=VALID_RUN)
    assert api_keys and keys[:len(api_keys)] == api_keys
    assert any(key.startswith("endpoint:/api/run:ip:") for key, _, _ in keys)


def test_fragment_routes_hold_no_limiter_replay_or_audit_code_of_their_own():
    source = (REPO_ROOT / "coroner" / "ui" / "story_routes.py").read_text()
    for forbidden in ("check_rate_limit", "RateLimiter", "replay_with_timeout", "subprocess", "run_verify", "execute_job"):
        assert forbidden not in source


def test_job_fragment_unknown_and_invalid_ids_are_alerts(run_env):
    client, _, _ = run_env
    assert "Invalid job_id" in _alert_text(client.get("/story/job/not-a-job-id").text)
    assert "Job not found" in _alert_text(client.get("/story/job/0123456789ab").text)


def test_job_fragment_error_status_shows_the_reason_in_an_alert(run_env):
    client, _, exchange = run_env
    job_dir = exchange / "jobs" / "0123456789ab"
    job_dir.mkdir(parents=True)
    (job_dir / "status.json").write_text(json.dumps({"status": "error", "reason": "timeout"}))
    text = _alert_text(client.get("/story/job/0123456789ab?view=engineer").text)
    assert "timeout" in text
    assert "hx-trigger" not in client.get("/story/job/0123456789ab").text


@pytest.mark.slow
def test_run_it_yourself_end_to_end_with_the_real_worker(run_env):
    from coroner.engine_worker import execute_job

    client, base, exchange = run_env
    started = client.post("/story/run", data=VALID_RUN)
    region = [a for t, a in tags(started.text, "div") if "hx-get" in a][0]
    poll_url = region["hx-get"]
    job_id = poll_url.split("/story/job/")[1].split("?")[0]

    waiting = client.get(poll_url)
    assert "queued" in visible_text(waiting.text)
    assert [a for t, a in tags(waiting.text, "div") if a.get("hx-trigger") == "every 2s"]

    execute_job(exchange / "jobs" / job_id)
    done = client.get(poll_url)

    run_dirs = [p for p in (base / "runs").iterdir() if p.is_dir()]
    assert len(run_dirs) == 1
    run_id = run_dirs[0].name
    verdict = json.loads((run_dirs[0] / "verdict.json").read_text())
    text = visible_text(done.text)
    assert has_live_region_root(done.text)
    assert "Your run" in text
    assert verdict["status"] in text
    assert f"{verdict['cases_divergent']} of {verdict['cases_total']} batches diverge" in text
    assert verdict["cases_total"] == 20
    assert [a["href"] for a in anchors(done.text)] == [f"/run/{run_id}"]
    # Polling stops: the finished result has no trigger.
    assert "hx-trigger" not in done.text and "hx-get" not in done.text

    # Identical parameters: the engine's run is reused, nothing new starts.
    again = client.post("/story/run", data=VALID_RUN)
    again_text = visible_text(again.text)
    assert "This exact audit already exists." in again_text
    assert f"{verdict['cases_divergent']} of {verdict['cases_total']} batches diverge" in again_text
    assert [a["href"] for a in anchors(again.text)] == [f"/run/{run_id}"]
    assert "hx-trigger" not in again.text
    assert not list((exchange / "jobs").iterdir())
