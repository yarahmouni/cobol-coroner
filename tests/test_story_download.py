"""Tests for the download route of a run (GET /run/<run id>/download/<file name>).

The story links its Exhibits to this route. It serves a fixed list of file names of one run
folder; the run id has a fixed pattern and no path ever comes from the request.
"""
import json
import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from coroner.ui import story
from coroner.ui.app import DOWNLOAD_FILE_NAMES, app

SERVED = ("certificate.json", "failure_report.json", "minimal_case_input.csv", "ZombieRegressionTest.java")
REFUSED = (
    "inputs.json", "verdict.json", "comparison_results.json", "generated_cases.csv", "card.txt",
    "branch_reconciliation.json", "failure_report.JSON", "ZombieRegressionTest.java.bak",
    "certificate.json%00.txt", "run_error.txt",
)
# A slash in the name (also encoded) never reaches the route: the router answers 404 itself.
REFUSED_BY_THE_ROUTER = ("..%2Fcertificate.json", "%2e%2e%2finputs.json", "a/b.json")


def _t1_faulty_dir(base: Path) -> Path:
    catalog = json.loads((base / "runs" / "trap_catalog.json").read_text())
    entry = next(trap for trap in catalog["traps"] if trap["id"] == "T1")
    return base / "runs" / entry["faulty_run_id"]


def test_every_exhibit_of_the_story_can_be_downloaded():
    assert [file_name for _, file_name in story.EXHIBIT_FILES] == list(SERVED)
    assert set(DOWNLOAD_FILE_NAMES) == set(SERVED)


@pytest.mark.slow
@pytest.mark.parametrize("name", SERVED)
def test_fixed_names_are_served_with_the_exact_bytes_of_the_run(story_runs, story_client, name):
    run_dir = _t1_faulty_dir(story_runs.base)
    response = story_client.get(f"/run/{run_dir.name}/download/{name}")
    assert response.status_code == 200
    assert response.content == (run_dir / name).read_bytes()
    assert f'filename="{name}"' in response.headers["content-disposition"]


@pytest.mark.slow
@pytest.mark.parametrize("name", REFUSED)
def test_any_other_name_is_refused_even_when_the_file_exists(story_runs, story_client, name):
    run_dir = _t1_faulty_dir(story_runs.base)
    response = story_client.get(f"/run/{run_dir.name}/download/{name}")
    assert response.status_code == 404
    assert response.json() == {"detail": "File not found"}


@pytest.mark.slow
@pytest.mark.parametrize("name", REFUSED_BY_THE_ROUTER)
def test_a_name_with_a_slash_never_reaches_the_route_and_is_404(story_runs, story_client, name):
    run_dir = _t1_faulty_dir(story_runs.base)
    assert story_client.get(f"/run/{run_dir.name}/download/{name}").status_code == 404


@pytest.mark.slow
@pytest.mark.parametrize("run_id", ["invalid123", "ABCDEF123456", "..", "%2e%2e", "0" * 13, "0" * 11])
def test_a_run_id_that_does_not_have_the_fixed_pattern_is_refused(story_client, run_id):
    assert story_client.get(f"/run/{run_id}/download/certificate.json").status_code in (404, 422)


@pytest.mark.slow
def test_an_unknown_run_and_a_missing_file_are_404(story_runs, story_client, tmp_path, monkeypatch):
    assert story_client.get(f"/run/{'0' * 12}/download/certificate.json").json() == {"detail": "Run not found"}
    copy = tmp_path / "base_copy"
    shutil.copytree(story_runs.base, copy)
    monkeypatch.setenv("CORONER_BASE_DIR", str(copy))
    run_dir = _t1_faulty_dir(copy)
    (run_dir / "failure_report.json").unlink()
    client = TestClient(app)
    response = client.get(f"/run/{run_dir.name}/download/failure_report.json")
    assert response.status_code == 404 and response.json() == {"detail": "File not found"}
    assert client.get(f"/run/{run_dir.name}/download/certificate.json").status_code == 200
