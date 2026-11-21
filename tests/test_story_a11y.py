"""Accessibility tests of the guided story and the fool page (guided-story Task 14, Req 2 and 16).

Tests that need no run use an empty base directory (the shell and the forms do not depend on the
runs). Tests marked slow use the real runs of the story_runs and fool_runs fixtures
(tests/conftest.py) and read nothing from the repository runs/ folder.
"""
import re
from html.parser import HTMLParser

import pytest
from fastapi.testclient import TestClient

from coroner.ui.app import app, templates

from story_html import anchors, has_live_region_root, listing_lines, live_regions, live_regions_within, tags, visible_text

POSITIONING = (
    "Coroner does not translate COBOL. AWS Transform, Kiro, an LLM or a human migrates COBOL "
    "to Java. Coroner independently verifies the result."
)
VIEWS = ("business", "engineer")
STEPS = range(1, 9)


@pytest.fixture
def empty_client(tmp_path, monkeypatch):
    """A client with an empty base directory: no catalog, no runs."""
    monkeypatch.setenv("CORONER_BASE_DIR", str(tmp_path))
    return TestClient(app)


def _story_paths():
    paths = ["/story"]
    paths += [f"/story/step/{step}?view={view}" for step in STEPS for view in VIEWS]
    return paths


FOOL_PATHS = [
    "/fool",
    "/fool?view=engineer",
    "/fool?case1=on&case2=on&case4=on",
    "/fool?case1=on&view=engineer",
]


# ------------------------------------------------------------------ the positioning sentence (Req 16)


@pytest.mark.parametrize("path", _story_paths() + FOOL_PATHS)
def test_positioning_sentence_is_on_every_page_type(empty_client, path):
    response = empty_client.get(path)
    assert response.status_code == 200
    assert POSITIONING in visible_text(response.text)


@pytest.mark.slow
@pytest.mark.parametrize("view", VIEWS)
@pytest.mark.parametrize("step", STEPS)
def test_positioning_sentence_is_on_every_story_page_with_real_runs(story_client, step, view):
    page = story_client.get(f"/story/step/{step}?view={view}").text
    assert POSITIONING in visible_text(page)


@pytest.mark.slow
@pytest.mark.parametrize("path", FOOL_PATHS)
def test_positioning_sentence_is_on_the_fool_page_with_real_runs(fool_client, path):
    assert POSITIONING in visible_text(fool_client.get(path).text)


def test_the_fragment_does_not_repeat_the_positioning_sentence(empty_client):
    """The sentence sits in the shell, outside the swapped fragment."""
    for step in STEPS:
        fragment = empty_client.get(f"/story/step/{step}", headers={"HX-Request": "true"}).text
        assert POSITIONING not in visible_text(fragment)
    fool_fragment = empty_client.get("/fool", headers={"HX-Request": "true"}).text
    assert POSITIONING not in visible_text(fool_fragment)


# ------------------------------------------------------------------ Next and Back are links (Req 1, 2)


@pytest.mark.parametrize("headers", [{}, {"HX-Request": "true"}])
@pytest.mark.parametrize("step", STEPS)
def test_next_and_back_are_links_with_an_href(empty_client, step, headers):
    page = empty_client.get(f"/story/step/{step}", headers=headers).text
    links = {a["class"]: a for a in anchors(page) if a.get("class") in ("story-back", "story-next")}
    assert "story-next" in links, "Next is not an <a href>"
    assert links["story-next"]["href"]
    if step == 1:
        assert "story-back" not in links
    else:
        assert links["story-back"]["href"]
    # Nothing that moves between steps is a button: it would not work without JavaScript.
    for tag, attrs in tags(page):
        if tag == "button":
            assert "story-next" not in attrs.get("class", "") and "story-back" not in attrs.get("class", "")
    # htmx attributes only enhance anchors.
    for tag, attrs in tags(page):
        if "hx-get" in attrs and attrs["hx-get"].startswith("/story/step/"):
            assert tag == "a"


@pytest.mark.parametrize("step", STEPS)
def test_following_next_and_back_without_javascript_gives_the_neighbouring_step(empty_client, step):
    page = empty_client.get(f"/story/step/{step}").text
    links = {a["class"]: a["href"] for a in anchors(page) if a.get("class") in ("story-back", "story-next")}
    followed = empty_client.get(links["story-next"])
    assert followed.status_code == 200
    if step < 8:
        assert f"Step {step + 1} of 8" in visible_text(followed.text)
    else:
        assert links["story-next"] == "/"
        assert "Run Audit" in visible_text(followed.text)
    if step > 1:
        assert f"Step {step - 1} of 8" in visible_text(empty_client.get(links["story-back"]).text)


# ------------------------------------------------------------------ async targets are live regions (Req 2)

# Every result target of the story, with a request of the real route that fails cheaply (no replay,
# no audit): the fragment that comes back must be the one live region of the target.
RESULT_ROUTES = {
    "gate-result": ("/story/gate-check", {"run_id": "0123456789ab"}),
    "run-result": ("/story/run", {"port": "faulty", "seed": "abc", "cases": "10"}),
    "tamper-result": ("/story/tamper", {"run_id": "0123456789ab", "status": "ALIVE", "cases_total": "x",
                                         "cases_divergent": "0", "random_seed": "42"}),
}


def _hx_targets(page):
    return {attrs["hx-target"] for _, attrs in tags(page) if "hx-target" in attrs}


def _element_count(page, element_id):
    return sum(1 for _, attrs in tags(page) if attrs.get("id") == element_id)


@pytest.mark.slow
def test_every_async_target_of_the_story_is_a_container_whose_swapped_result_is_a_live_region(story_client):
    found = set()
    for step in (4, 7, 8):
        page = story_client.get(f"/story/step/{step}").text
        for target in _hx_targets(page) - {"#story-content"}:
            found.add(target)
            element_id = target.lstrip("#")
            assert _element_count(page, element_id) == 1, f"{target} is not in the step {step} page exactly once"
            assert element_id in RESULT_ROUTES, f"{target} has no route in this test: add it"
            # The container is a plain element; the fragment swapped into it is the live region.
            assert live_regions_within(page, element_id) == 0
    assert found == {f"#{name}" for name in RESULT_ROUTES}
    for element_id, (route, data) in RESULT_ROUTES.items():
        fragment = story_client.post(route, data=data).text
        assert has_live_region_root(fragment), element_id
        assert live_regions(fragment) == 1, element_id


@pytest.mark.slow
def test_the_fool_result_region_is_the_one_live_region_and_its_fragment_has_none(fool_client):
    page = fool_client.get("/fool").text
    assert _hx_targets(page) == {"#fool-result"}
    assert live_regions_within(page, "fool-result") == 1
    fragment = fool_client.get("/fool?case1=on", headers={"HX-Request": "true"}).text
    assert live_regions(fragment) == 0
    # With the fragment swapped in, the page still has the one live region.
    assert live_regions(page) == 1


def test_a_failing_action_gives_an_alert_the_visitor_hears(empty_client):
    """The three cheap failures of the real routes are role=alert fragments (no catalog needed)."""
    for element_id, (route, data) in RESULT_ROUTES.items():
        fragment = empty_client.post(route, data=data)
        assert fragment.status_code == 200, element_id
        assert has_live_region_root(fragment.text), element_id
        assert 'role="alert"' in fragment.text, element_id


# ------------------------------------------------------------------ the listing region (Req 2, 12)


def _regions(page):
    return [attrs for tag, attrs in tags(page, "div") if attrs.get("role") == "region"]


@pytest.mark.parametrize("view", VIEWS)
@pytest.mark.parametrize("step", [1, 6])
def test_every_listing_region_has_tabindex_and_an_aria_label_naming_file_and_lines(empty_client, step, view):
    """Steps 1 and 6 show the listing without any run (the lines come from the COBOL file)."""
    page = empty_client.get(f"/story/step/{step}?view={view}").text
    regions = _regions(page)
    assert regions, f"step {step} shows no listing region"
    numbers = {number for number, _ in listing_lines(page)}
    assert numbers
    for attrs in regions:
        assert attrs.get("tabindex") == "0"
        label = re.fullmatch(r"(\S+\.cob) lines (\d+) to (\d+)", attrs.get("aria-label", ""))
        assert label, attrs.get("aria-label")
        # The label names lines that are in the listing.
        assert int(label.group(2)) in numbers and int(label.group(3)) in numbers
    # The listing is inside the details element of the panel.
    assert 'class="story-listing"' in page


# ------------------------------------------------------------------ labels on every control (Req 2)

_NO_LABEL_TYPES = {"hidden", "submit", "button", "reset", "image"}


def unlabelled_controls(page):
    """Ids (or the tag when there is no id) of the form controls that have no <label for> and no aria-label."""
    labelled = set()
    controls = []

    class Reader(HTMLParser):
        def handle_starttag(self, tag, attrs):
            attrs = dict(attrs)
            if tag == "label" and "for" in attrs:
                labelled.add(attrs["for"])
            if tag == "input" and attrs.get("type", "text") not in _NO_LABEL_TYPES:
                controls.append((tag, attrs))
            elif tag in ("select", "textarea"):
                controls.append((tag, attrs))

    Reader().feed(page)
    return [
        attrs.get("id") or tag
        for tag, attrs in controls
        if attrs.get("id") not in labelled and not attrs.get("aria-label") and not attrs.get("aria-labelledby")
    ]


def _buttons_without_text(page):
    return [
        body for body in re.findall(r"<button[^>]*>(.*?)</button>", page, re.S)
        if not re.sub(r"<[^>]+>", "", body).strip()
    ]


def test_the_label_check_itself_finds_a_missing_label():
    assert unlabelled_controls('<input id="a" type="text"><label for="b">B</label><input id="b" type="number">') == ["a"]
    assert unlabelled_controls('<select name="x"></select>') == ["select"]
    assert unlabelled_controls('<input type="hidden" name="h"><input type="checkbox" id="c" aria-label="C">') == []


@pytest.mark.parametrize("path", ["/fool", "/fool?view=engineer"] + [f"/story/step/{n}" for n in (1, 2, 3, 5, 6)])
def test_every_control_has_a_label_without_runs(empty_client, path):
    page = empty_client.get(path).text
    assert unlabelled_controls(page) == []
    assert _buttons_without_text(page) == []


@pytest.mark.slow
@pytest.mark.parametrize("view", VIEWS)
@pytest.mark.parametrize("step", STEPS)
def test_every_control_of_every_story_step_has_a_label(story_client, step, view):
    page = story_client.get(f"/story/step/{step}?view={view}").text
    assert unlabelled_controls(page) == []
    assert _buttons_without_text(page) == []
    if step in (4, 7):
        # The Run it yourself form: both fields have a visible label.
        assert {"run-seed", "run-cases"} <= {a.get("id") for _, a in tags(page, "input")}
    if step == 8:
        assert {"tamper-status", "tamper-cases-total", "tamper-cases-divergent", "tamper-random-seed"} <= {
            a.get("id") for _, a in tags(page) if a.get("id")
        }


@pytest.mark.slow
def test_every_toggle_of_the_fool_page_has_a_label(fool_client):
    page = fool_client.get("/fool?case1=on").text
    checkboxes = [a for _, a in tags(page, "input") if a.get("type") == "checkbox"]
    assert sorted(a["name"] for a in checkboxes) == ["case1", "case2", "case4"]
    assert unlabelled_controls(page) == []


# ------------------------------------------------------------------ badges carry text and shape (Req 2, D-56)

BADGE_SHAPES = {"alive": "<circle", "zombie": "<rect", "invalid": "<polygon", "error": 'transform="rotate(45'}
# Shape elements that must not appear in the badge of a status (the error diamond is a rotated rect).
OTHER_SHAPES = {
    "alive": ["<rect", "<polygon"],
    "zombie": ["<circle", "<polygon", "rotate(45"],
    "invalid": ["<circle", "<rect"],
    "error": ["<circle", "<polygon"],
}


def _shape(kind):
    macros = templates.env.get_template("story_macros.html").module
    return str(macros.status_badge(kind))


@pytest.mark.parametrize("kind, marker", sorted(BADGE_SHAPES.items()))
def test_each_status_has_its_own_shape(kind, marker):
    svg = _shape(kind)
    assert marker in svg
    assert 'aria-hidden="true"' in svg  # the text label carries the meaning
    for other in OTHER_SHAPES[kind]:
        assert other not in svg, (kind, other)


@pytest.mark.parametrize("name, context", [
    ("story_gate_result.html", {"heading": "A label", "exit_code": 1}),
    ("story_tamper_result.html", {"result_html": "<p>A label</p>"}),
])
@pytest.mark.parametrize("kind", sorted(BADGE_SHAPES))
def test_result_badges_have_a_shape_and_a_text_label(name, context, kind):
    html = templates.env.get_template(name).render(kind=kind, **context)
    assert BADGE_SHAPES[kind] in html
    assert "A label" in visible_text(html)


@pytest.mark.slow
def test_the_verdict_badges_of_steps_4_and_7_have_shape_and_word(story_client):
    for step, kind, shape, word in ((4, "zombie", "<rect", "ZOMBIE"), (7, "alive", "<circle", "ALIVE")):
        page = story_client.get(f"/story/step/{step}").text
        badges = re.findall(rf'<div class="verdict-badge {kind}".*?</div>', page, re.S)
        assert badges, f"step {step} has no {kind} badge"
        for badge in badges:
            assert shape in badge
            assert word in visible_text(badge)


@pytest.mark.slow
def test_every_badge_of_the_fool_page_has_shape_and_word(fool_client):
    page = fool_client.get("/fool?case1=on&case2=on&case4=on").text
    assert len(re.findall(r'<div class="verdict-badge ', page)) >= 3
    matches = list(re.finditer(r'<div class="verdict-badge (\w+)".*?</div>', page, re.S))
    assert len(matches) >= 3
    for match in matches:
        kind, badge = match.group(1), match.group(0)
        assert BADGE_SHAPES[kind] in badge
        assert re.search(r"ALIVE|ZOMBIE|INVALID|ERROR|no verdict recorded", visible_text(badge))
