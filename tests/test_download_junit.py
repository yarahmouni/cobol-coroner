"""Retry logic of scripts/download_junit.py, driven by a local HTTP server."""
import hashlib
import importlib.util
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "download_junit.py"
PAYLOAD = b"fake jar bytes for the retry test"
PAYLOAD_SHA256 = hashlib.sha256(PAYLOAD).hexdigest()


def load_script():
    spec = importlib.util.spec_from_file_location("download_junit", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def server():
    """Local server answering 404 `failures` times, then serving PAYLOAD."""
    state = {"failures": 0, "requests": 0}

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            state["requests"] += 1
            if state["requests"] <= state["failures"]:
                self.send_error(404)
                return
            self.send_response(200)
            self.send_header("Content-Length", str(len(PAYLOAD)))
            self.end_headers()
            self.wfile.write(PAYLOAD)

        def log_message(self, *args):
            pass

    httpd = HTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    state["url"] = f"http://127.0.0.1:{httpd.server_port}/jar"
    yield state
    httpd.shutdown()
    httpd.server_close()
    thread.join()


def run(module, state, tmp_path, sha256=PAYLOAD_SHA256, waits=None):
    waits = [] if waits is None else waits
    code = module.main(
        url=state["url"],
        expected_sha256=sha256,
        jar_dir=tmp_path,
        first_wait=0,
        sleep=waits.append,
    )
    return code, tmp_path / module.JAR_NAME


def test_succeeds_on_third_attempt(server, tmp_path, capsys):
    server["failures"] = 2
    code, jar = run(load_script(), server, tmp_path)
    assert code == 0
    assert server["requests"] == 3
    assert jar.read_bytes() == PAYLOAD
    err = capsys.readouterr().err
    assert "attempt 1 of 4 failed" in err
    assert "attempt 2 of 4 failed" in err
    assert "attempt 3" not in err


def test_fails_when_every_attempt_fails(server, tmp_path, capsys):
    server["failures"] = 100
    code, jar = run(load_script(), server, tmp_path)
    assert code != 0
    assert server["requests"] == 4
    assert not jar.exists()
    assert "attempt 4 of 4 failed" in capsys.readouterr().err


def test_wait_grows_between_attempts(server, tmp_path):
    module = load_script()
    server["failures"] = 100
    waits = []
    code = module.main(
        url=server["url"],
        expected_sha256=PAYLOAD_SHA256,
        jar_dir=tmp_path,
        first_wait=2,
        sleep=waits.append,
    )
    assert code != 0
    assert waits == [2, 4, 8]


def test_wrong_hash_still_fails_and_removes_file(server, tmp_path, capsys):
    code, jar = run(load_script(), server, tmp_path, sha256="0" * 64)
    assert code != 0
    assert server["requests"] == 1
    assert not jar.exists()
    assert "SHA-256 mismatch" in capsys.readouterr().err


def test_defaults_unchanged():
    module = load_script()
    assert module.DEFAULT_SHA256 == "e62b96ac475dbcde8599ea905d088f65d90778f86e259b856a49fa5c4ea256ec"
    assert module.DEFAULT_URL.endswith("/6.1.3/junit-platform-console-standalone-6.1.3.jar")
    assert module.DEFAULT_JAR_DIR == Path("build/junit")
