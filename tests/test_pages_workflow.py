"""Tests of .github/workflows/pages.yml, which publishes docs/static/ to GitHub Pages.

The workflow is parsed, not run. PyYAML (YAML 1.1) loads the key `on` as the boolean True.
"""
import re
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "pages.yml"
STATIC = REPO_ROOT / "docs" / "static"


def load():
    return yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))


def steps():
    return load()["jobs"]["deploy"]["steps"]


def test_triggers_are_push_to_main_on_the_static_folder_and_manual():
    triggers = load()[True]
    assert set(triggers) == {"push", "workflow_dispatch"}
    assert triggers["push"]["branches"] == ["main"]
    assert sorted(triggers["push"]["paths"]) == [".github/workflows/pages.yml", "docs/static/**"]


def test_permissions_are_the_three_pages_needs_and_nothing_else():
    assert load()["permissions"] == {"contents": "read", "pages": "write", "id-token": "write"}


def test_one_pages_concurrency_group_that_never_cancels_a_running_deploy():
    assert load()["concurrency"] == {"group": "pages", "cancel-in-progress": False}


def test_the_job_deploys_to_the_github_pages_environment_with_its_url():
    job = load()["jobs"]["deploy"]
    assert job["environment"]["name"] == "github-pages"
    assert job["environment"]["url"] == "${{ steps.deployment.outputs.page_url }}"
    deploy = [step for step in job["steps"] if step.get("id") == "deployment"]
    assert len(deploy) == 1 and deploy[0]["uses"].startswith("actions/deploy-pages@")


def test_only_the_static_folder_is_uploaded():
    uploads = [step for step in steps() if step.get("uses", "").startswith("actions/upload-pages-artifact@")]
    assert len(uploads) == 1
    assert uploads[0]["with"] == {"path": "docs/static"}


def test_the_steps_are_the_four_expected_actions_in_order():
    names = [step["uses"].split("@")[0] for step in steps()]
    assert names == [
        "actions/checkout",
        "actions/configure-pages",
        "actions/upload-pages-artifact",
        "actions/deploy-pages",
    ]
    assert all("run" not in step for step in steps()), "no shell step: only the four pinned actions"


def test_every_uses_is_pinned_to_a_full_commit_sha_with_the_version_in_a_comment():
    text = WORKFLOW.read_text(encoding="utf-8")
    lines = [line for line in text.splitlines() if "uses:" in line]
    assert len(lines) == 4
    for line in lines:
        assert re.search(r"uses:\s*[\w./-]+@[0-9a-f]{40}\s+# v\d+\.\d+\.\d+$", line), line
    for step in steps():
        assert re.fullmatch(r"[\w./-]+@[0-9a-f]{40}", step["uses"]), step["uses"]


def test_the_workflow_has_no_dash_characters():
    text = WORKFLOW.read_text(encoding="utf-8")
    assert chr(0x2014) not in text and chr(0x2013) not in text


def test_the_static_page_links_work_from_a_site_root():
    """Every link in docs/static/index.html is an https link or a relative file next to the page."""
    html = (STATIC / "index.html").read_text(encoding="utf-8")
    hrefs = re.findall(r'href="([^"]*)"', html)
    assert hrefs
    relative = [href for href in hrefs if not href.startswith("https://")]
    assert relative, "the page links its certificates and cases file"
    for href in relative:
        assert not href.startswith(("/", "http:", "../", "#")), f"not relative to the page: {href}"
        assert (STATIC / href).is_file(), f"link target missing from docs/static: {href}"
    assert "src=" not in html, "the page loads nothing"
