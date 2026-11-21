"""
Rebuilding the derived catalog files never touches an existing run (owner rule, 2026-11-21).

The only files in runs/ that are computed from runs and are not run folders are
runs/trap_catalog.json and runs/trap_catalog.txt. These tests make real engine runs in
temporary base directories, put a stale catalog in place, rebuild with
`python -m coroner traps --from-runs`, and check that every file of every run folder is
byte for byte and mtime identical while the catalog is rebuilt. No mocks. The repository
runs/ folder is never written.
"""
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from collections import namedtuple
from pathlib import Path

import pytest

from coroner.catalog.legacy_variant import generate_half_even_variant
from coroner.cli import run_verify
from coroner.ui.app import replay_with_timeout

REPO = Path(__file__).resolve().parent.parent
T2_DIR = REPO / "samples" / "traps" / "T2-rounding"
BUNDLED_IDS = ["f584d5f35228", "29c15f04407b", "df4d7929ce44", "08d14a07bcdb"]
PHANTOM_MINUS = "The Phantom Minus"

pytestmark = pytest.mark.slow


def snapshot(base: Path) -> dict:
    """Every folder and file under every run folder: path, SHA-256, size and mtime."""
    snap = {}
    runs_dir = base / "runs"
    for run_dir in sorted(p for p in runs_dir.iterdir() if p.is_dir()):
        snap[run_dir.name] = ("dir",)
        for path in sorted(run_dir.rglob("*")):
            key = path.relative_to(runs_dir).as_posix()
            if path.is_dir():
                snap[key] = ("dir",)
            else:
                stat = path.stat()
                snap[key] = (hashlib.sha256(path.read_bytes()).hexdigest(), stat.st_size, stat.st_mtime_ns)
    return snap


def given_lines(card_text):
    """The lines of a card from its first "Given" line up to, not including, the "When" line."""
    lines = card_text.splitlines()
    start = next(i for i, line in enumerate(lines) if line.startswith("Given"))
    end = next(i for i, line in enumerate(lines) if line.startswith("When"))
    assert start < end
    return lines[start:end]


def catalog_trap(base: Path, trap_id: str) -> dict:
    catalog = json.loads((base / "runs" / "trap_catalog.json").read_text())
    return next(t for t in catalog["traps"] if t["id"] == trap_id)


def put_stale_catalog(base: Path) -> bytes:
    """Replace the catalog by a stale copy: T3 case_name and T1 card are "stale". Returns its JSON bytes."""
    json_path = base / "runs" / "trap_catalog.json"
    catalog = json.loads(json_path.read_text())
    for trap in catalog["traps"]:
        if trap["id"] == "T3":
            trap["case_name"] = "stale"
        if trap["id"] == "T1":
            trap["card"] = "stale"
    json_path.write_text(json.dumps(catalog, indent=2, sort_keys=True))
    (base / "runs" / "trap_catalog.txt").write_text("stale\n")
    assert catalog_trap(base, "T3")["case_name"] == "stale"
    assert catalog_trap(base, "T1")["card"] == "stale"
    return json_path.read_bytes()


def traps_from_runs(base: Path, cases: int, seed: int = 42) -> subprocess.CompletedProcess:
    """The real CLI: python -m coroner traps --from-runs, with CORONER_BASE_DIR set."""
    env = os.environ.copy()
    env["CORONER_BASE_DIR"] = str(base)
    return subprocess.run(
        [sys.executable, "-m", "coroner", "traps", "--from-runs", "--cases", str(cases), "--seed", str(seed)],
        cwd=REPO, env=env, capture_output=True, text=True, timeout=900,
    )


def assert_catalog_rebuilt(base: Path):
    """T3 has its registry name and the T1 card has the Given lines of that run's card.txt."""
    assert catalog_trap(base, "T3")["case_name"] == PHANTOM_MINUS
    t1 = catalog_trap(base, "T1")
    card_txt = (base / "runs" / t1["faulty_run_id"] / "card.txt").read_text()
    assert t1["card"] != "stale"
    assert given_lines(t1["card"]) == given_lines(card_txt)
    assert "stale" not in (base / "runs" / "trap_catalog.txt").read_text()
    text = (base / "runs" / "trap_catalog.txt").read_text()
    assert given_lines(text[text.index("== Case 1 "):]) == given_lines(card_txt)


def scratch_folders(base: Path) -> list:
    """Scratch folders the rebuild or the init script may leave in build/ (there must be none)."""
    build = base / "build"
    if not build.exists():
        return []
    return sorted(p.name for p in build.iterdir() if p.name.startswith((".catalog-scratch-", ".init-")))


def assert_replay_valid(base: Path, run_id: str):
    """The real replay of the Verify route (a child process running coroner verify <certificate> --json)."""
    certificate = base / "runs" / run_id / "certificate.json"
    result = replay_with_timeout(str(certificate), str(base), 180)
    assert result.valid, f"certificate of {run_id} is not VALID: {result.reason}"


Pristine = namedtuple("Pristine", "base cases visitor_id")


@pytest.fixture(scope="module")
def pristine(story_runs, tmp_path_factory):
    """
    A base directory with the real catalog runs of `story_runs` (copied, mtimes kept) and one
    visitor-style run made by the real engine before any rebuild: T2 faulty, 20 cases, seed 7.
    The session fixture itself is never modified.
    """
    base = tmp_path_factory.mktemp("catalog_pristine")
    shutil.copytree(story_runs.base / "runs", base / "runs")

    cobol = next(T2_DIR.glob("*.cob"))
    java = next((T2_DIR / "java" / "faulty").glob("*.java"))
    copybooks = T2_DIR / "copybooks"
    verdict, run_dir = run_verify(
        cobol_path=str(cobol),
        java_path=str(java),
        schema_path=str(T2_DIR / "schema.json"),
        copybooks_dir=str(copybooks if copybooks.exists() else T2_DIR),
        num_cases=20,
        seed=7,
        timings=False,
        base_dir=str(base),
    )
    assert verdict.status == "ZOMBIE"
    return Pristine(base, story_runs.cases, run_dir.name)


@pytest.fixture
def working_base(pristine, tmp_path):
    """A private copy of the pristine runs/ folder (file mtimes kept by shutil.copy2)."""
    base = tmp_path / "base"
    shutil.copytree(pristine.base / "runs", base / "runs")
    return base


def test_rebuild_touches_no_existing_run(story_runs, pristine, working_base):
    base = working_base
    t1_faulty_id = catalog_trap(base, "T1")["faulty_run_id"]
    assert pristine.visitor_id not in {t["faulty_run_id"] for t in story_runs.catalog["traps"] if "faulty_run_id" in t}
    assert (base / "runs" / pristine.visitor_id / "certificate.json").is_file()

    before = snapshot(base)
    assert pristine.visitor_id in before
    run_folders = {key for key in before if re.fullmatch(r"[0-9a-f]{12}", key)}
    assert len(run_folders) == 11  # 10 catalog runs and the visitor run
    # runs/temp is the engine's scratch folder (generate_cases); it is in the snapshot too
    assert "temp/generated_cases.csv" in before

    put_stale_catalog(base)

    first = traps_from_runs(base, pristine.cases)
    assert first.returncode == 0, first.stdout + first.stderr
    second = traps_from_runs(base, pristine.cases)
    assert second.returncode == 0, second.stdout + second.stderr

    # Not one byte or mtime of any run folder changed, none added or removed
    after = snapshot(base)
    changed = sorted(k for k in before.keys() | after.keys() if before.get(k) != after.get(k))
    assert changed == [], f"{len(changed)} run files changed, for example {changed[:5]}"

    # The engine was not called for any trap port: every run was found on disk
    for output in (first.stdout, second.stdout):
        assert output.count("Kept existing run") == 10
        assert "generating it" not in output

    assert_catalog_rebuilt(base)
    # Same catalog as the one the engine produced in the default mode
    assert json.loads((base / "runs" / "trap_catalog.json").read_text()) == json.loads(json.dumps(story_runs.catalog))
    assert (base / "runs" / "trap_catalog.txt").read_text() == (story_runs.base / "runs" / "trap_catalog.txt").read_text()

    # No temporary file left in runs/ or scratch folder in build/
    assert sorted(p.name for p in (base / "runs").iterdir() if p.is_file()) == ["trap_catalog.json", "trap_catalog.txt"]
    assert scratch_folders(base) == []

    # Verify keeps working on a run made before the rebuild, bundled or visitor
    assert_replay_valid(base, t1_faulty_id)
    assert_replay_valid(base, pristine.visitor_id)
    assert snapshot(base) == before


def test_existing_folder_not_found_by_inputs_json_stops_the_rebuild(pristine, working_base):
    base = working_base
    t2_faulty_id = catalog_trap(base, "T2")["faulty_run_id"]
    (base / "runs" / t2_faulty_id / "inputs.json").unlink()

    stale_json = put_stale_catalog(base)
    stale_txt = (base / "runs" / "trap_catalog.txt").read_bytes()
    before = snapshot(base)

    result = traps_from_runs(base, pristine.cases)

    assert result.returncode == 2, result.stdout + result.stderr
    assert "already exists" in result.stderr
    assert t2_faulty_id in result.stderr
    assert snapshot(base) == before
    assert (base / "runs" / "trap_catalog.json").read_bytes() == stale_json
    assert (base / "runs" / "trap_catalog.txt").read_bytes() == stale_txt
    assert sorted(p.name for p in (base / "runs").iterdir() if p.is_file()) == ["trap_catalog.json", "trap_catalog.txt"]
    assert scratch_folders(base) == []


def test_missing_run_is_generated_once_and_nothing_else_changes(story_runs, pristine, working_base):
    base = working_base
    t3_faulty_id = catalog_trap(base, "T3")["faulty_run_id"]
    shutil.rmtree(base / "runs" / t3_faulty_id)
    put_stale_catalog(base)
    before = snapshot(base)

    result = traps_from_runs(base, pristine.cases)

    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stdout.count("Kept existing run") == 9
    assert f"Generated run {t3_faulty_id} for T3 faulty" in result.stdout

    after = snapshot(base)
    regenerated = {key for key in after if key == t3_faulty_id or key.startswith(t3_faulty_id + "/")}
    assert regenerated
    assert {k: v for k, v in after.items() if k not in regenerated} == before
    assert (base / "runs" / t3_faulty_id / "verdict.json").is_file()
    assert_catalog_rebuilt(base)
    assert json.loads((base / "runs" / "trap_catalog.json").read_text()) == json.loads(json.dumps(story_runs.catalog))
    assert_replay_valid(base, t3_faulty_id)
    assert scratch_folders(base) == []


def test_init_script_keeps_runs_and_rebuilds_the_catalog(tmp_path):
    """
    scripts/init_demo_runs.sh on a base that already holds the bundled runs (a redeploy that keeps
    its volume): it exits 0 with its final line, rebuilds a stale catalog and leaves every run
    folder byte for byte identical. The first start of the same base is checked first.
    """
    base = tmp_path / "data"
    variant = tmp_path / "variants" / "build" / "variants" / "CreditFees.java"
    generate_half_even_variant(str(REPO / "samples/credit-fees/java/CreditFees.java"), str(variant))

    env = os.environ.copy()
    env.update({
        "CORONER_BASE_DIR": str(base),
        "PYTHON": sys.executable,
        "CORONER_VARIANT_JAVA": str(variant),
    })

    def run_script():
        return subprocess.run(
            ["bash", "scripts/init_demo_runs.sh"],
            cwd=REPO, env=env, capture_output=True, text=True, timeout=1500,
        )

    def last_line(result):
        return [line for line in result.stdout.splitlines() if line.strip()][-1]

    first = run_script()
    assert first.returncode == 0, f"stdout: {first.stdout}\nstderr: {first.stderr}"
    assert last_line(first) == "Bundled demo runs generated."
    assert "Bundled runs kept: none; generated: " + " ".join(BUNDLED_IDS) in first.stdout
    for run_id in BUNDLED_IDS:
        assert (base / "runs" / run_id / "certificate.json").is_file()
    assert (base / "runs" / "trap_catalog.json").is_file()
    assert (base / "runs" / "trap_catalog.txt").is_file()
    assert_catalog_rebuilt(base)

    before = snapshot(base)
    put_stale_catalog(base)

    second = run_script()
    assert second.returncode == 0, f"stdout: {second.stdout}\nstderr: {second.stderr}"
    assert_catalog_rebuilt(base)
    assert last_line(second) == "Bundled demo runs generated."
    assert "Bundled runs kept: " + " ".join(BUNDLED_IDS) + "; generated: none" in second.stdout
    assert "Bundled demo runs already exist" not in second.stdout
    assert "generating it" not in second.stdout

    assert snapshot(base) == before
    assert not list((base / "build").glob(".init-*"))
    assert not list((base / "build").glob(".catalog-scratch-*"))
    assert_replay_valid(base, BUNDLED_IDS[0])


# A catalog problem must never keep the live site from starting (owner rule, 2026-11-21).
# docker-compose.yml makes coroner-api wait for coroner-init to exit 0, so the init script
# must exit 0 when only the catalog rebuild fails.

WARNING_KEPT = (
    "WARNING: catalog rebuild failed (exit 2); "
    "the previous catalog files are kept and the site starts with them."
)
WARNING_NO_CATALOG = (
    "WARNING: catalog rebuild failed (exit 2); "
    "no catalog file exists yet, the Detection Matrix has no data until a rebuild succeeds."
)


def last_stdout_line(result):
    return [line for line in result.stdout.splitlines() if line.strip()][-1]


def run_init_script(base: Path, variant: Path, python: str = None) -> subprocess.CompletedProcess:
    """The real scripts/init_demo_runs.sh on a base directory (what coroner-init runs)."""
    env = os.environ.copy()
    env.update({
        "CORONER_BASE_DIR": str(base),
        "PYTHON": python or sys.executable,
        "CORONER_VARIANT_JAVA": str(variant),
    })
    return subprocess.run(
        ["bash", "scripts/init_demo_runs.sh"],
        cwd=REPO, env=env, capture_output=True, text=True, timeout=1500,
    )


def free_port() -> int:
    import socket

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class RealApi:
    """The real API (uvicorn coroner.ui.app:app) on a free port, serving a given base directory."""

    def __init__(self, base: Path, workdir: Path):
        self.port = free_port()
        self.url = f"http://127.0.0.1:{self.port}"
        env = os.environ.copy()
        env["CORONER_BASE_DIR"] = str(base)
        env["CORONER_EXCHANGE_DIR"] = str(workdir / "exchange")
        self.log = open(workdir / "uvicorn.log", "w")
        self.process = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "coroner.ui.app:app", "--host", "127.0.0.1", "--port", str(self.port)],
            cwd=REPO, env=env, stdout=self.log, stderr=subprocess.STDOUT,
        )

    def wait_ready(self):
        import time

        import httpx

        for _ in range(120):
            if self.process.poll() is not None:
                break
            try:
                if httpx.get(self.url + "/", timeout=2.0).status_code == 200:
                    return
            except httpx.HTTPError:
                pass
            time.sleep(0.25)
        self.log.flush()
        pytest.fail("the API did not become ready:\n" + Path(self.log.name).read_text())

    def stop(self):
        self.process.terminate()
        try:
            self.process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            self.process.kill()
            self.process.wait(timeout=10)
        self.log.close()


@pytest.fixture(scope="module")
def started_base(tmp_path_factory):
    """
    A base directory as left by a first start of coroner-init: the four bundled runs, the ten
    catalog runs and a good catalog. Never modified: every test works on a copy of its runs/.
    """
    root = tmp_path_factory.mktemp("init_started")
    base = root / "data"
    variant = root / "variants" / "build" / "variants" / "CreditFees.java"
    generate_half_even_variant(str(REPO / "samples/credit-fees/java/CreditFees.java"), str(variant))
    result = run_init_script(base, variant)
    assert result.returncode == 0, f"stdout: {result.stdout}\nstderr: {result.stderr}"
    assert last_stdout_line(result) == "Bundled demo runs generated."
    assert (base / "runs" / "trap_catalog.json").is_file()
    for run_id in BUNDLED_IDS:
        assert (base / "runs" / run_id / "certificate.json").is_file()
    return base, variant


def broken_copy(started_base, tmp_path, drop_catalog: bool):
    """
    A copy of the started base in which the catalog rebuild must fail the way R-156 tests force
    it: a run folder that exists but is not found by inputs.json (T2 faulty, inputs.json removed).
    With drop_catalog, the two catalog files are removed as well.
    """
    source, variant = started_base
    base = tmp_path / "data"
    shutil.copytree(source / "runs", base / "runs")
    t2_faulty_id = catalog_trap(base, "T2")["faulty_run_id"]
    (base / "runs" / t2_faulty_id / "inputs.json").unlink()
    if drop_catalog:
        (base / "runs" / "trap_catalog.json").unlink()
        (base / "runs" / "trap_catalog.txt").unlink()
    return base, variant


def get_page(client, url):
    import html

    response = client.get(url)
    return response.status_code, html.unescape(response.text)


def test_catalog_failure_does_not_stop_init_and_the_api_serves_the_kept_catalog(started_base, tmp_path):
    from coroner.cases import case_label, load_cases_registry

    import httpx

    base, variant = broken_copy(started_base, tmp_path, drop_catalog=False)
    kept_json = (base / "runs" / "trap_catalog.json").read_bytes()
    kept_txt = (base / "runs" / "trap_catalog.txt").read_bytes()
    kept_catalog = json.loads(kept_json)
    before = snapshot(base)

    result = run_init_script(base, variant)

    # The rebuild failed (the script prints its output), the script did not
    assert result.returncode == 0, f"stdout: {result.stdout}\nstderr: {result.stderr}"
    assert "already exists" in result.stdout
    assert WARNING_KEPT in result.stdout.splitlines()
    assert WARNING_NO_CATALOG not in result.stdout
    assert last_stdout_line(result) == "Bundled demo runs generated."
    assert "Bundled runs kept: " + " ".join(BUNDLED_IDS) + "; generated: none" in result.stdout

    # The previous catalog is byte for byte unchanged, no run file changed, no partial or temporary file
    assert (base / "runs" / "trap_catalog.json").read_bytes() == kept_json
    assert (base / "runs" / "trap_catalog.txt").read_bytes() == kept_txt
    assert snapshot(base) == before
    assert sorted(p.name for p in (base / "runs").iterdir() if p.is_file()) == ["trap_catalog.json", "trap_catalog.txt"]
    assert scratch_folders(base) == []

    # The real API starts on that base and serves the existing runs and the kept catalog
    registry = load_cases_registry()
    t1 = next(t for t in kept_catalog["traps"] if t["id"] == "T1")
    api = RealApi(base, tmp_path)
    try:
        api.wait_ready()
        with httpx.Client(timeout=30.0) as client:
            status, _ = get_page(client, api.url + "/")
            assert status == 200
            status, matrix = get_page(client, api.url + "/matrix")
            assert status == 200
            assert "Detection Matrix not available yet" not in matrix
            for trap in kept_catalog["traps"]:
                assert case_label(trap["id"], registry) in matrix
            assert f"{t1['cases_detected']} of {t1['cases_generated']}" in matrix
            for run_id in BUNDLED_IDS:
                status, _ = get_page(client, f"{api.url}/run/{run_id}")
                assert status == 200, f"GET /run/{run_id} gave {status}"
    finally:
        api.stop()


def test_catalog_failure_with_no_catalog_file_still_starts(started_base, tmp_path):
    import httpx

    base, variant = broken_copy(started_base, tmp_path, drop_catalog=True)
    before = snapshot(base)

    result = run_init_script(base, variant)

    assert result.returncode == 0, f"stdout: {result.stdout}\nstderr: {result.stderr}"
    assert WARNING_NO_CATALOG in result.stdout.splitlines()
    assert WARNING_KEPT not in result.stdout
    assert last_stdout_line(result) == "Bundled demo runs generated."

    # Nothing was invented: no catalog file, no run file changed, no temporary file
    assert snapshot(base) == before
    assert [p.name for p in (base / "runs").iterdir() if p.is_file()] == []
    assert scratch_folders(base) == []

    api = RealApi(base, tmp_path)
    try:
        api.wait_ready()
        with httpx.Client(timeout=30.0) as client:
            status, _ = get_page(client, api.url + "/")
            assert status == 200
            status, matrix = get_page(client, api.url + "/matrix")
            assert status == 200
            assert "Detection Matrix not available yet" in matrix
            status, _ = get_page(client, f"{api.url}/run/{BUNDLED_IDS[0]}")
            assert status == 200
    finally:
        api.stop()


def test_bundled_run_failure_still_exits_2(started_base, tmp_path):
    """Only the catalog step became non-fatal: a failing bundled run keeps its exit 2."""
    source, _ = started_base
    base = tmp_path / "data"
    shutil.copytree(source / "runs", base / "runs")
    # The HALF_EVEN bundled run is missing and its Java file does not exist, so generating it fails
    shutil.rmtree(base / "runs" / BUNDLED_IDS[3])
    result = run_init_script(base, tmp_path / "no-such-variant" / "CreditFees.java")
    assert result.returncode == 2, f"stdout: {result.stdout}\nstderr: {result.stderr}"
    assert "Bundled demo runs generated." not in result.stdout
    assert "WARNING: catalog rebuild failed" not in result.stdout


def test_missing_catalog_file_after_a_successful_rebuild_does_not_stop_init(started_base, tmp_path):
    """
    The rebuild exits 0 but trap_catalog.txt is missing afterwards: the script warns and still
    exits 0, so coroner-api starts. PYTHON points to a wrapper that runs the real python and, only
    for "-m coroner traps", deletes runs/trap_catalog.txt with pathlib after the real command,
    keeping the exit code of the real command.
    """
    import shlex

    import httpx

    source, variant = started_base
    base = tmp_path / "data"
    shutil.copytree(source / "runs", base / "runs")
    before = snapshot(base)

    wrapper = tmp_path / "python-wrapper.sh"
    real = shlex.quote(sys.executable)
    wrapper.write_text(
        "#!/usr/bin/env bash\n"
        f"{real} \"$@\"\n"
        "rc=$?\n"
        "if [ \"$1\" = \"-m\" ] && [ \"$2\" = \"coroner\" ] && [ \"$3\" = \"traps\" ]; then\n"
        f"    {real} -c \"import os, pathlib; "
        "pathlib.Path(os.environ['CORONER_BASE_DIR'], 'runs', 'trap_catalog.txt').unlink(missing_ok=True)\"\n"
        "fi\n"
        "exit $rc\n"
    )
    wrapper.chmod(0o755)

    result = run_init_script(base, variant, python=str(wrapper))

    assert result.returncode == 0, f"stdout: {result.stdout}\nstderr: {result.stderr}"
    lines = result.stdout.splitlines()
    assert (
        "WARNING: catalog rebuild reported success but trap_catalog.txt is missing; "
        "the site starts without it."
    ) in lines
    assert not any("trap_catalog.json is missing" in line for line in lines)
    assert "WARNING: catalog rebuild failed" not in result.stdout
    assert last_stdout_line(result) == "Bundled demo runs generated."
    assert not (base / "runs" / "trap_catalog.txt").exists()
    assert (base / "runs" / "trap_catalog.json").is_file()
    after = snapshot(base)
    assert {k: v for k, v in after.items() if k in before} == before

    api = RealApi(base, tmp_path)
    try:
        api.wait_ready()
        with httpx.Client(timeout=30.0) as client:
            assert client.get(api.url + "/").status_code == 200
    finally:
        api.stop()
