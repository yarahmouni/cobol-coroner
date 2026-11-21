"""Property-based test of the two T1 Java ports (jqwik), run through `make pbt`."""
import importlib.util
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
PROPERTIES = (
    "correctPortConservesTheTotal",
    "totalIsConservedEvenByTheFaultyPort",
    "faultyPortPostsBranch001ToSuspense",
)


def load_download_script():
    spec = importlib.util.spec_from_file_location("download_junit", REPO / "scripts" / "download_junit.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_jqwik_jars_are_pinned_and_used_by_the_make_target():
    module = load_download_script()
    makefile = (REPO / "Makefile").read_text(encoding="utf-8")
    assert len(module.JQWIK_JARS) == 2
    for name, url, sha256 in module.JQWIK_JARS:
        assert re.fullmatch(r"[0-9a-f]{64}", sha256)
        assert url.startswith("https://repo1.maven.org/maven2/net/jqwik/")
        assert url.endswith("/" + name)
        assert f"build/junit/{name}" in makefile


@pytest.mark.slow
def test_jqwik_properties_pass():
    if shutil.which("javac") is None:
        pytest.skip("javac is not installed")
    result = subprocess.run(
        ["make", "pbt", f"PYTHON={sys.executable}"],
        cwd=REPO, capture_output=True, text=True, encoding="utf-8", timeout=600,
    )
    out = result.stdout
    assert result.returncode == 0, out[-3000:] + result.stderr[-1000:]
    for name in PROPERTIES:
        assert re.search(rf"{name}( \d+ ms)? \u2714", out), f"property {name} not reported as passed:\n{out[-3000:]}"
        report = re.search(rf"MatchMergeProperties:{name} = .*?tries = (\d+).*?checks = (\d+)", out, re.DOTALL)
        assert report, f"no jqwik report for {name}"
        tries, checks = int(report.group(1)), int(report.group(2))
        assert tries > 0 and checks > 0, f"{name}: tries {tries}, checks {checks}"
    assert re.search(r"\[\s*3 tests successful\s*\]", out)
    assert re.search(r"\[\s*0 tests failed\s*\]", out)
