"""Tests for the story shell: routing, views, positioning sentence, headers, keyboard script.

All fast: no run is needed. Steps 2 and 3 are asked for with an empty base directory, where they
show the typed "Bundled demo runs missing" alert, and the shell around them is still checked.
"""
import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from coroner.ui.app import app

from story_html import anchors, tags, visible_text

REPO_ROOT = Path(__file__).resolve().parent.parent
UI_DIR = REPO_ROOT / "coroner" / "ui"

POSITIONING = (
    "Coroner does not translate COBOL. AWS Transform, Kiro, an LLM or a human migrates COBOL "
    "to Java. Coroner independently verifies the result."
)
STEP_TITLES = [
    "Bank process", "COBOL result", "Java migration", "Coroner compares",
    "Where and why", "Apply the fix", "ALIVE certificate", "Try to cheat",
]


@pytest.fixture
def client(tmp_path, monkeypatch):
    """Client with an empty base directory (no catalog, no runs)."""
    monkeypatch.setenv("CORONER_BASE_DIR", str(tmp_path))
    return TestClient(app)


def _view_links(page):
    """The two links inside the navigation labelled View, in page order."""
    links = []
    inside = False
    for tag, attrs in tags(page):
        if tag == "nav":
            inside = attrs.get("aria-label") == "View"
        elif tag == "a" and inside:
            links.append(attrs)
    assert len(links) == 2
    return links


def test_full_page_has_positioning_sentence_step_counter_and_view_links(client):
    response = client.get("/story/step/1")
    assert response.status_code == 200
    page = response.text
    assert POSITIONING in visible_text(page)
    assert "Step 1 of 8" in visible_text(page)
    business, engineer = _view_links(page)
    assert business["href"] == "/story/step/1?view=business"
    assert engineer["href"] == "/story/step/1?view=engineer"
    assert business.get("aria-current") == "true"
    assert "aria-current" not in engineer
    assert page.count("<main") == 1 and 'id="story-content"' in page


def test_engineer_view_marks_the_engineer_link_current(client):
    business, engineer = _view_links(client.get("/story/step/1?view=engineer").text)
    assert engineer.get("aria-current") == "true"
    assert "aria-current" not in business


@pytest.mark.parametrize("view", ["admin", "", "ENGINEER", "engineer ", "<script>"])
def test_unknown_view_gives_business(client, view):
    page = client.get("/story/step/1", params={"view": view}).text
    business, engineer = _view_links(page)
    assert business.get("aria-current") == "true"
    assert "aria-current" not in engineer
    next_link = [a for a in anchors(page) if a.get("class") == "story-next"][0]
    assert next_link["href"] == "/story/step/2?view=business"
    # The unknown value is not echoed back into the page.
    assert "script" not in next_link["href"]
    assert "&lt;script" not in page


def test_start_route_is_step_1(client):
    response = client.get("/story")
    assert response.status_code == 200
    assert "Step 1 of 8" in visible_text(response.text)
    assert POSITIONING in visible_text(response.text)


def test_htmx_request_gets_the_fragment_without_the_shell(client):
    response = client.get("/story/step/1", headers={"HX-Request": "true"})
    assert response.status_code == 200
    assert "<html" not in response.text.lower()
    assert "<body" not in response.text.lower()
    assert "Step 1 of 8" in visible_text(response.text)
    assert 'id="step-heading"' in response.text
    assert POSITIONING not in visible_text(response.text)


def test_history_restore_request_gets_the_full_page(client):
    """htmx asks for the whole page when it restores history after Back or Forward."""
    response = client.get(
        "/story/step/2", headers={"HX-Request": "true", "HX-History-Restore-Request": "true"},
    )
    assert "<html" in response.text.lower()
    assert POSITIONING in visible_text(response.text)


@pytest.mark.parametrize("step", ["0", "9", "99", "100", "1000", "abc", "-1", "1.5", "%C2%B2", "01x"])
def test_step_outside_1_to_8_redirects_to_step_1(client, step):
    response = client.get(f"/story/step/{step}", follow_redirects=False)
    assert response.status_code == 302
    assert response.headers["location"] == "/story/step/1?view=business"


def test_redirect_carries_the_view(client):
    response = client.get("/story/step/9?view=engineer", follow_redirects=False)
    assert response.headers["location"] == "/story/step/1?view=engineer"


@pytest.mark.parametrize("view", ["business", "engineer"])
def test_next_and_back_carry_the_view_and_are_links(client, view):
    page = client.get(f"/story/step/2?view={view}").text
    by_class = {attrs["class"]: attrs for attrs in anchors(page) if attrs.get("class") in ("story-back", "story-next")}
    assert by_class["story-back"]["href"] == f"/story/step/1?view={view}"
    assert by_class["story-next"]["href"] == f"/story/step/3?view={view}"
    for link in by_class.values():
        assert link["hx-get"] == link["href"]
        assert link["hx-target"] == "#story-content"
        assert link["hx-push-url"] == "true"
    for link in _view_links(page):
        assert link["href"] in (f"/story/step/2?view=business", f"/story/step/2?view=engineer")
        assert link["hx-get"] == link["href"]


def test_first_step_has_no_back_and_last_step_finishes_at_the_home_page(client):
    first = client.get("/story/step/1").text
    assert not [a for a in anchors(first) if a.get("class") == "story-back"]
    last = client.get("/story/step/8").text
    next_links = [a for a in anchors(last) if a.get("class") == "story-next"]
    assert len(next_links) == 1
    assert next_links[0]["href"] == "/"
    assert "hx-get" not in next_links[0]
    assert "Finish" in visible_text(last)
    assert "Step 8 of 8" in visible_text(last)


@pytest.mark.parametrize("step", range(1, 9))
def test_every_step_has_its_title_as_a_focusable_heading(client, step):
    page = client.get(f"/story/step/{step}").text
    headings = [attrs for tag, attrs in tags(page, "h2") if attrs.get("id") == "step-heading"]
    assert len(headings) == 1
    assert headings[0]["tabindex"] == "-1"
    assert re.search(rf'<h2 id="step-heading" tabindex="-1">{STEP_TITLES[step - 1]}</h2>', page)
    assert f"Step {step} of 8" in visible_text(page)


@pytest.mark.parametrize("path, headers", [
    ("/story", {}),
    ("/story/step/3", {}),
    ("/story/step/3", {"HX-Request": "true"}),
    ("/story/step/0", {}),
])
def test_story_pages_are_no_store_and_vary_on_htmx_headers(client, path, headers):
    response = client.get(path, headers=headers, follow_redirects=False)
    assert response.headers["cache-control"] == "no-store"
    assert "HX-Request" in response.headers["vary"]


def test_step_with_missing_runs_shows_the_typed_alert_and_no_numbers(client):
    page = client.get("/story/step/2").text
    assert "Bundled demo runs missing. Run docker compose up to generate them." in visible_text(page)
    assert [a for _, a in tags(page) if a.get("role") == "alert"]
    assert "<table" not in page
    assert "transactions" not in visible_text(page)


def test_story_template_has_no_inline_script_and_loads_story_js_deferred():
    template = (UI_DIR / "templates" / "story.html").read_text()
    assert "<script>" not in template
    assert '<script src="/static/story.js" defer></script>' in template


def test_story_js_is_served_and_has_the_guards_the_spec_describes():
    response = TestClient(app).get("/static/story.js")
    assert response.status_code == 200
    script = response.text
    for guard in ("ctrlKey", "metaKey", "altKey", "shiftKey", "INPUT", "SELECT", "TEXTAREA", "BUTTON"):
        assert guard in script
    for handler in ("ArrowRight", "ArrowLeft", "Escape", "htmx:afterSwap", "step-heading", "story-content"):
        assert handler in script
    assert "Enter" not in script
    # The arrow keys scroll a focused listing region, so the shortcut must stay out of it.
    assert 'closest(\'[role="region"]\')' in script


def test_story_post_bodies_are_limited_like_the_api(client):
    """The story fragment routes get the 16 KB body limit of /api/*."""
    response = client.post("/story/gate-check", data={"run_id": "0" * (17 * 1024)})
    assert response.status_code == 413
    assert "no-store" in response.headers["cache-control"]


def test_new_story_files_have_no_em_dash():
    files = [
        UI_DIR / "story.py", UI_DIR / "story_routes.py", UI_DIR / "static" / "story.js",
        *sorted((UI_DIR / "templates").glob("story*.html")),
    ]
    assert len(files) >= 10
    for path in files:
        assert "\u2014" not in path.read_text(), path.name
