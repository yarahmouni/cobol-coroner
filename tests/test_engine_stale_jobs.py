"""Jobs left "running" by an engine that stopped must not block the queue (p389)."""
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from coroner.engine_worker import STALE_JOB_REASON, recover_stale_jobs

REPO_ROOT = Path(__file__).resolve().parents[1]

RUNNING_IDS = ["a26c32ac9511", "a26c32ac9512", "a26c32ac9513"]
QUEUED_ID = "b26c32ac9514"
DONE_ID = "c26c32ac9515"
ERROR_ID = "d26c32ac9516"


def dead_process_group() -> int:
    """Return a process group id that belonged to a process that has ended."""
    proc = subprocess.Popen([sys.executable, "-c", "pass"], start_new_session=True)
    proc.wait()
    with pytest.raises(ProcessLookupError):
        os.killpg(proc.pid, 0)
    return proc.pid


def write_job(jobs_dir: Path, job_id: str, status: dict) -> Path:
    """Write a job folder the way the API and the worker write it."""
    job_dir = jobs_dir / job_id
    job_dir.mkdir(parents=True)
    request = {"job_id": job_id, "sample": "T1", "port": "faulty", "seed": 42, "cases": 200}
    (job_dir / "request.json").write_text(json.dumps(request, indent=2))
    (job_dir / "status.json").write_text(json.dumps(status, indent=2))
    return job_dir


def write_running_job(jobs_dir: Path, job_id: str, pgid: int) -> Path:
    now = time.time()
    return write_job(
        jobs_dir, job_id, {"status": "running", "queued_at": now - 30, "started_at": now - 20, "pgid": pgid}
    )


def read_status(job_dir: Path) -> dict:
    return json.loads((job_dir / "status.json").read_text())


@pytest.fixture
def exchange(tmp_path, monkeypatch):
    """Temporary exchange folder and base directory, queue limit 3."""
    exchange_dir = tmp_path / "exchange"
    (exchange_dir / "jobs").mkdir(parents=True)
    monkeypatch.setenv("CORONER_BASE_DIR", str(tmp_path / "base"))
    monkeypatch.setenv("CORONER_EXCHANGE_DIR", str(exchange_dir))
    monkeypatch.setenv("CORONER_MAX_QUEUE_LENGTH", "3")
    return exchange_dir


@pytest.fixture(autouse=True)
def reset_limits():
    from coroner.ui.app import reset_rate_limiter

    reset_rate_limiter()
    yield
    reset_rate_limiter()


RUN_FORM = {"sample": "T1", "port": "faulty", "seed": 42, "cases": 200}


def test_three_stale_running_jobs_block_run_audit_until_recovery(exchange):
    """Reproduction: 3 stale running jobs give 429; recovery frees the queue."""
    from coroner.ui.app import app

    jobs_dir = exchange / "jobs"
    pgid = dead_process_group()
    job_dirs = [write_running_job(jobs_dir, job_id, pgid) for job_id in RUNNING_IDS]
    client = TestClient(app)

    # The bug: the queue is full of jobs that nothing is running.
    blocked = client.post("/api/run", data=RUN_FORM)
    assert blocked.status_code == 429
    assert "Queue full" in blocked.json()["detail"]
    for job_id in RUNNING_IDS:
        assert client.get(f"/api/job/{job_id}/status").json()["status"] == "running"

    # The engine starts and recovers.
    assert sorted(recover_stale_jobs()) == RUNNING_IDS

    accepted = client.post("/api/run", data=RUN_FORM)
    assert accepted.status_code == 202
    assert read_status(jobs_dir / accepted.json()["job_id"])["status"] == "queued"

    for job_id, job_dir in zip(RUNNING_IDS, job_dirs):
        body = client.get(f"/api/job/{job_id}/status").json()
        assert body["status"] == "error"
        assert body["reason"] == STALE_JOB_REASON
        stored = read_status(job_dir)
        assert isinstance(stored["completed_at"], float)
        assert not (job_dir / "status.tmp").exists()


def test_recovery_message_has_no_path_or_host_detail():
    reason = STALE_JOB_REASON
    assert "stopped while this audit was running" in reason
    assert "again" in reason
    for forbidden in ("/", "\\", "pid", "pgid", "container", "docker"):
        assert forbidden not in reason.lower()


def test_recovery_leaves_queued_done_and_error_jobs_untouched(exchange):
    jobs_dir = exchange / "jobs"
    now = time.time()
    queued = write_job(jobs_dir, QUEUED_ID, {"status": "queued", "queued_at": now})
    done = write_job(
        jobs_dir, DONE_ID, {"status": "done", "queued_at": now - 9, "started_at": now - 8, "run_id": "0123456789ab"}
    )
    errored = write_job(jobs_dir, ERROR_ID, {"status": "error", "reason": "timeout", "queued_at": now - 5})
    running = write_running_job(jobs_dir, RUNNING_IDS[0], dead_process_group())
    before = {path: (path / "status.json").read_bytes() for path in (queued, done, errored)}

    assert recover_stale_jobs() == [RUNNING_IDS[0]]

    for path, content in before.items():
        assert (path / "status.json").read_bytes() == content
    assert read_status(running)["status"] == "error"
    assert read_status(running)["started_at"] < now

    # The queued job is still the one the worker would run next.
    from coroner.engine_worker import find_oldest_queued_job

    assert find_oldest_queued_job() == queued


def test_recovery_skips_unreadable_status_and_missing_folder(exchange, tmp_path, monkeypatch):
    jobs_dir = exchange / "jobs"
    broken = jobs_dir / "e26c32ac9517"
    broken.mkdir()
    (broken / "status.json").write_text("{not json")
    (jobs_dir / "f26c32ac9518").mkdir()
    (jobs_dir / "stray-file.txt").write_text("x")
    write_running_job(jobs_dir, RUNNING_IDS[0], dead_process_group())

    assert recover_stale_jobs() == [RUNNING_IDS[0]]
    assert (broken / "status.json").read_text() == "{not json"

    monkeypatch.setenv("CORONER_EXCHANGE_DIR", str(tmp_path / "no-such-folder"))
    assert recover_stale_jobs() == []


def wait_for_status(job_dir: Path, wanted: str, timeout: float = 8.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            if read_status(job_dir)["status"] == wanted:
                return True
        except (OSError, json.JSONDecodeError, KeyError):
            pass
        time.sleep(0.1)
    return False


@pytest.mark.parametrize(
    "command, extra_env",
    [
        ([sys.executable, "-m", "coroner.engine_worker"], {}),
        # The compose file starts the engine this way.
        ([sys.executable, "-m", "coroner.ui.app"], {"CORONER_ENGINE_MODE": "worker"}),
    ],
    ids=["engine_worker_main", "compose_entry_point"],
)
def test_worker_process_recovers_stale_job_at_start(exchange, command, extra_env):
    jobs_dir = exchange / "jobs"
    stale = write_running_job(jobs_dir, RUNNING_IDS[0], dead_process_group())
    env = {**os.environ, "CORONER_EXCHANGE_DIR": str(exchange), **extra_env}

    proc = subprocess.Popen(
        command,
        cwd=REPO_ROOT,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        start_new_session=True,
    )
    try:
        recovered = wait_for_status(stale, "error")
    finally:
        proc.terminate()
        try:
            _, stderr = proc.communicate(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            _, stderr = proc.communicate()

    assert recovered, f"stale job still {read_status(stale)['status']}; worker stderr: {stderr}"
    data = read_status(stale)
    assert data["reason"] == STALE_JOB_REASON
    assert f"Recovered stale running job: {RUNNING_IDS[0]}" in stderr
    assert "Recovered 1 stale running job(s)" in stderr
