"""Tests for the story shell: routing, views, positioning sentence, headers, keyboard script.

All fast: no run is needed. Steps 2 and 3 are asked for with an empty base directory, where they
show the typed "Bundled demo runs missing" alert, and the shell around them is still checked.
"""
import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from coroner.ui.app import app

from story_html import anchors, into_container, live_regions, live_regions_within, tags, visible_text

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


# ------------------------------------------------------------------ home page, navigation, 375 px, contrast


def _story_style(page: str) -> str:
    """The text of the story stylesheet block (the one that holds the 375 px rules)."""
    blocks = re.findall(r"<style>(.*?)</style>", page, re.S)
    found = [b for b in blocks if "@media (max-width: 480px)" in b]
    assert len(found) == 1
    return found[0]


def test_home_page_has_the_two_story_links_and_the_matrix_link(client):
    page = client.get("/").text
    by_href = {a["href"]: a for a in anchors(page) if a["href"] in ("/story", "/fool", "/matrix")}
    assert set(by_href) == {"/story", "/fool", "/matrix"}
    assert "story-cta" in by_href["/story"]["class"].split()
    text = visible_text(page)
    assert "Try the bank failure" in text and "Can you fool Coroner?" in text
    assert client.get("/story").status_code == 200 and client.get("/fool").status_code == 200


def test_story_and_fool_pages_link_to_each_other_to_the_home_page_and_the_matrix(client):
    story = {a["href"] for a in anchors(client.get("/story/step/1").text)}
    fool = {a["href"] for a in anchors(client.get("/fool").text)}
    assert {"/", "/fool", "/matrix"} <= story
    assert {"/", "/story/step/1?view=business", "/matrix"} <= fool
    # The story and fool pages keep their link to the other one in the Engineer view.
    assert "/story/step/1?view=engineer" in {a["href"] for a in anchors(client.get("/fool?view=engineer").text)}


@pytest.mark.parametrize("path", ["/", "/story/step/1", "/fool"])
def test_home_story_and_fool_pages_carry_the_375_px_rules(client, path):
    css = _story_style(client.get(path).text)
    query = re.search(r"@media \(max-width: (\d+)px\)", css)
    assert int(query.group(1)) >= 375
    phone = css[css.index("@media (max-width: 480px)"):]
    for rule in (
        "min-height: 44px",           # tap targets
        "font-size: 1rem",            # 16 px text
        "flex-direction: column",     # one column
        "overflow-x: auto",           # tables and listings scroll inside their box
        "grid-template-columns: 1fr",
        "width: 100%",
    ):
        assert rule in phone, rule


def test_home_story_stylesheet_uses_only_the_variables_of_the_page_theme(client):
    page = client.get("/fool").text
    css = _story_style(page)
    assert not re.search(r"#[0-9a-fA-F]{3,8}\b", css)
    assert "rgb(" not in css and "hsl(" not in css
    root = re.search(r":root\s*\{([^}]+)\}", page, re.S).group(1)
    light = re.search(r":root\.light\s*\{([^}]+)\}", page, re.S).group(1)
    for name in set(re.findall(r"var\(--([a-z-]+)\)", css)):
        assert f"--{name}:" in root and f"--{name}:" in light, name


def _colors(block: str) -> dict:
    return {name: value.strip() for name, value in re.findall(r"--([a-z-]+):\s*([^;]+);", block)}


@pytest.mark.parametrize("mode", ["dark", "light"])
def test_home_story_colors_keep_the_contrast_ratios_of_the_ui_tests(client, mode):
    from test_ui_pages import compute_contrast_ratio, compute_relative_luminance, parse_hex_color

    page = client.get("/story/step/1").text
    root = re.search(r":root\s*\{([^}]+)\}", page, re.S).group(1)
    light = re.search(r":root\.light\s*\{([^}]+)\}", page, re.S).group(1)
    colors = _colors(root if mode == "dark" else light)

    def ratio(foreground: str, background: str) -> float:
        return compute_contrast_ratio(
            compute_relative_luminance(*parse_hex_color(colors[foreground])),
            compute_relative_luminance(*parse_hex_color(colors[background])),
        )

    css = _story_style(page)
    used = set(re.findall(r"var\(--([a-z-]+)\)", css))
    # Text colors of the new rules on the two backgrounds they are drawn on.
    assert {"text-color", "secondary-text", "panel-bg"} <= used
    for foreground in ("text-color", "secondary-text"):
        for background in ("bg-color", "panel-bg"):
            assert ratio(foreground, background) >= 4.5, (mode, foreground, background)
    # The "Try the bank failure" link: white 20 px bold text (large text, 3:1) on the accent color.
    white = compute_relative_luminance(255, 255, 255)
    accent = compute_relative_luminance(*parse_hex_color(colors["orange-accent"]))
    assert compute_contrast_ratio(white, accent) >= 3.0


# ------------------------------------------------------------------ one live region per async result


def _render(name, **context):
    from coroner.ui.app import templates
    return templates.env.get_template(name).render(**context)


def _containers():
    """(container id, page text holding the empty container) for the three story actions."""
    from coroner.ui.app import templates

    macros = templates.env.get_template("story_macros.html").module
    run_form = {"port": "faulty", "seed": 42, "cases": 200, "bounds": None}
    tamper = {
        "run_id": "0123456789ab", "status_choices": ["ALIVE", "ZOMBIE"],
        "fields": {"status": "ZOMBIE", "cases_total": 1, "cases_divergent": 1, "random_seed": 1},
    }
    return {
        "gate-result": str(macros.gate_section("0123456789ab", "business", "intro")),
        "run-result": str(macros.run_section(run_form, "business", "intro")),
        "tamper-result": _render("story_step_8.html", tamper=tamper, view="business", engineer={}),
    }


def _fragments():
    """Every fragment template that is swapped into a container, with the container it goes to."""
    result = {"id": "0123456789ab", "status": "ZOMBIE", "cases_divergent": 3, "cases_total": 9}
    return [
        ("gate-result", _render("story_gate_result.html", kind="zombie", heading="h", exit_code=1)),
        ("gate-result", _render("story_gate_result.html", kind="alive", heading="h", exit_code=0)),
        ("gate-result", _render("story_alert.html", message="m", retry_action="gate", run_id="0123456789ab", view="business", retry_after="5")),
        ("run-result", _render("story_job.html", job_id="0123456789ab", job_status="queued", view="business")),
        ("run-result", _render("story_run_result.html", result={**result, "run_id": result["id"]}, cached=False)),
        ("run-result", _render("story_alert.html", message="m", retry_action="run", port="faulty", seed="1", cases="10", view="business")),
        ("tamper-result", _render("story_tamper_result.html", kind="invalid", result_html="<p>Certificate: INVALID</p>")),
        ("tamper-result", _render("story_alert.html", message="m", retry_action="tamper", run_id="0123456789ab", fields={"status": "ALIVE"}, view="business")),
    ]


def test_every_story_result_container_is_empty_and_not_a_live_region_itself():
    for element_id, page in _containers().items():
        assert live_regions_within(page, element_id) == 0, element_id


def test_every_story_result_has_exactly_one_live_region_once_swapped_in():
    containers = _containers()
    fragments = _fragments()
    assert {element_id for element_id, _ in fragments} == set(containers)
    for element_id, fragment in fragments:
        assert live_regions(fragment) == 1, (element_id, fragment[:80])
        swapped = into_container(containers[element_id], element_id, fragment)
        assert live_regions_within(swapped, element_id) == 1, element_id
        assert live_regions(swapped) == 1, element_id


def test_the_gate_fragment_of_the_real_route_is_the_one_live_region(client):
    """A failing gate check (unknown run) goes through the real route and its alert is the only live region."""
    page = _containers()["gate-result"]
    fragment = client.post("/story/gate-check", data={"run_id": "0123456789ab"}).text
    assert live_regions(fragment) == 1
    assert live_regions(into_container(page, "gate-result", fragment)) == 1


# ------------------------------------------------------------------ home page: Recent Runs table at 375 px


def _make_run_folders(base, count):
    """Run folders with the files the home page lists (a status and a time). Layout test only: the
    page shows these values but this test asserts none of them."""
    import json

    for index in range(count):
        run_dir = base / "runs" / f"{index:012x}"
        run_dir.mkdir(parents=True)
        (run_dir / "verdict.json").write_text(json.dumps({"status": "ZOMBIE" if index % 2 else "ALIVE"}))
        (run_dir / "inputs.json").write_text(json.dumps({"timestamp": f"2026-11-21T09:{index:02d}:00+00:00"}))


def test_recent_runs_table_sits_in_a_scrollable_labelled_region(client, tmp_path):
    """The table was 385 px wide at 375 px and scrolled the whole page sideways (R-141)."""
    _make_run_folders(tmp_path, 3)
    page = client.get("/").text
    wrapper = re.search(r'<div class="table-scroll"([^>]*)>\s*<table', page)
    assert wrapper, "the Recent Runs table is not directly inside a .table-scroll wrapper"
    attrs = {name: value for name, value in re.findall(r'([a-z-]+)="([^"]*)"', wrapper.group(1))}
    assert attrs["role"] == "region"
    assert attrs["tabindex"] == "0"
    heading_id = attrs["aria-labelledby"]
    assert [a for t, a in tags(page, "h2") if a.get("id") == heading_id]
    assert "Recent Runs" in visible_text(page)
    # The table has a caption that tells a visitor it can scroll.
    assert re.search(r"<caption[^>]*>[^<]*[Ss]croll[^<]*</caption>", page)


def test_recent_runs_wrapper_scrolls_inside_its_box_and_shows_a_focus_outline(client, tmp_path):
    _make_run_folders(tmp_path, 1)
    css = _story_style(client.get("/").text)
    rule = re.search(r"\.table-scroll\s*\{([^}]*)\}", css)
    assert rule, ".table-scroll has no rule in the stylesheet of the home page"
    assert "overflow-x: auto" in rule.group(1) and "max-width: 100%" in rule.group(1)
    # The wrapper has tabindex 0, and the shared focus rule draws an outline for it.
    focus = re.search(r'\[tabindex="0"\]:focus-visible\s*\{([^}]*)\}', css)
    assert focus and "outline:" in focus.group(1)


def test_without_runs_the_home_page_has_no_table_wrapper(client):
    page = client.get("/").text
    assert '<div class="table-scroll"' not in page
    assert "No runs found" in visible_text(page)
