"""Tests for the video tools: scripts/make_srt.py and scripts/record_demo.py.

The parsing tests read the real docs/video-plan.md. The plan is also parsed here
with a separate regular expression, so a parser bug cannot hide itself.
"""
import importlib
import os
import re
import shutil
import subprocess
import sys
import urllib.request
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
SCRIPTS = REPO / "scripts"
PLAN = REPO / "docs" / "video-plan.md"
STACK_URL = "http://127.0.0.1:8000"

sys.path.insert(0, str(SCRIPTS))
make_srt = importlib.import_module("make_srt")
record_demo = importlib.import_module("record_demo")

ROW = re.compile(
    r"^\| (\d+) \| (\d+):(\d\d) \| (\d+):(\d\d) \| (\d+) s \| (Text card|Live page|Still image)(.*?) \| (.*?) \| (.*?) \| (.*) \|$"
)
SHEET_ROW = re.compile(r"^\| (\d+) \| \d+:\d\d to \d+:\d\d \| (.*) \| (\d+) \| (\d+\.\d\d) \|$")


def plan_rows():
    """Rows of the section 3 table, parsed independently of the scripts."""
    rows = []
    for line in PLAN.read_text(encoding="utf-8").splitlines():
        match = ROW.match(line)
        if match:
            n, m1, s1, m2, s2, dur, kind, rest, subtitle, voice, _ = match.groups()
            rows.append({
                "n": int(n), "start": int(m1) * 60 + int(s1), "end": int(m2) * 60 + int(s2),
                "duration": int(dur), "kind": kind, "source": kind + rest, "subtitle": subtitle, "voiceover": voice,
            })
    return rows


def run_script(name, *args):
    return subprocess.run([sys.executable, str(SCRIPTS / name), *map(str, args)], capture_output=True, text=True)


def parse_srt(text):
    """Cues of an SRT file as (start_ms, end_ms, [lines])."""
    cues = []
    for block in text.strip().split("\n\n"):
        lines = block.split("\n")
        match = re.fullmatch(r"(\d+):(\d\d):(\d\d),(\d{3}) --> (\d+):(\d\d):(\d\d),(\d{3})", lines[1])
        assert match, f"bad time line: {lines[1]!r}"
        h1, m1, s1, ms1, h2, m2, s2, ms2 = map(int, match.groups())
        cues.append(((h1 * 3600 + m1 * 60 + s1) * 1000 + ms1, (h2 * 3600 + m2 * 60 + s2) * 1000 + ms2, lines[2:]))
    return cues


def ffmpeg_duration(ffmpeg, path):
    result = subprocess.run([ffmpeg, "-hide_banner", "-i", str(path)], capture_output=True, text=True)
    match = re.search(r"Duration: (\d+):(\d+):(\d+\.\d+)", result.stderr)
    assert match, result.stderr[-300:]
    return int(match.group(1)) * 3600 + int(match.group(2)) * 60 + float(match.group(3))


# ---------------------------------------------------------------------------
# The plan
# ---------------------------------------------------------------------------

def test_plan_has_18_shots_ending_at_2_55():
    rows = plan_rows()
    assert [r["n"] for r in rows] == list(range(1, 19))
    assert rows[0]["start"] == 0
    assert rows[-1]["end"] == 175
    for previous, current in zip(rows, rows[1:]):
        assert current["start"] == previous["end"]
    assert all(r["duration"] == r["end"] - r["start"] for r in rows)


def test_plan_has_no_dash_and_no_measured_marker():
    content = PLAN.read_text(encoding="utf-8")
    assert "\u2014" not in content, "em dash found in video-plan.md"
    assert "\u2013" not in content, "en dash found in video-plan.md"
    assert "<!-- MEASURED:" not in content


def test_voiceover_has_no_amount_with_more_than_4_digits():
    """The owner reads the voice-over aloud: no long amount in the spoken text."""
    number = re.compile(r"(?<!\w)\d+(?:\.\d+)?(?!\w)")
    for row in plan_rows():
        for token in number.findall(row["voiceover"]):
            assert len(token.replace(".", "")) <= 4, f"shot {row['n']}: '{token}' in the voice-over"


def test_voiceover_sheet_matches_the_table_and_the_pace():
    voice = {r["n"]: r for r in plan_rows()}
    sheet = {}
    for line in PLAN.read_text(encoding="utf-8").splitlines():
        match = SHEET_ROW.match(line)
        if match:
            sheet[int(match.group(1))] = match.groups()[1:]
    assert sorted(sheet) == sorted(voice)
    for number, (text, words, per_second) in sheet.items():
        assert text == voice[number]["voiceover"], f"shot {number}: section 6 text differs from section 3"
        assert int(words) == len(text.split()), f"shot {number}: word count"
        assert per_second == f"{len(text.split()) / voice[number]['duration']:.2f}", f"shot {number}: words per second"
        assert float(per_second) < 2.6, f"shot {number}: {per_second} words per second"


# ---------------------------------------------------------------------------
# make_srt
# ---------------------------------------------------------------------------

def test_make_srt_help_exits_zero():
    result = run_script("make_srt.py", "--help")
    assert result.returncode == 0, result.stderr
    assert "--column" in result.stdout and "--output" in result.stdout


@pytest.mark.parametrize("column", ["subtitle", "voiceover"])
def test_make_srt_covers_every_shot(tmp_path, column):
    out = tmp_path / f"{column}.srt"
    result = run_script("make_srt.py", "--column", column, "--output", out)
    assert result.returncode == 0, result.stderr
    cues = parse_srt(out.read_text(encoding="utf-8"))
    rows = plan_rows()
    assert len(rows) == 18

    assert cues[0][0] == 0
    assert cues[-1][1] == rows[-1]["end"] * 1000
    for (_, previous_end, _), (start, _, _) in zip(cues, cues[1:]):
        assert start == previous_end, "cues must follow each other without overlap"

    for row in rows:
        window = (row["start"] * 1000, row["end"] * 1000)
        inside = [c for c in cues if window[0] <= c[0] < window[1]]
        assert inside, f"shot {row['n']} has no cue"
        assert inside[0][0] == window[0] and inside[-1][1] == window[1], f"shot {row['n']}: cues do not fill the window"
        assert all(c[1] <= window[1] for c in inside), f"shot {row['n']}: a cue ends after the shot"
        spoken = " ".join(" ".join(c[2]) for c in inside)
        assert spoken == " ".join(row[column].split()), f"shot {row['n']}: text differs from the plan"

    for _, _, lines in cues:
        assert 1 <= len(lines) <= 2
        assert all(len(line) <= 42 for line in lines), lines


def test_make_srt_splits_long_text_in_proportion_to_length():
    row = plan_rows()[1]  # shot 2: 15 s of long text
    cues = make_srt.split_into_cues(row["subtitle"], row["start"] * 1000, row["end"] * 1000)
    assert len(cues) >= 3
    sizes = [len(" ".join(lines)) for _, _, lines in cues]
    for (start, end, _), size in zip(cues, sizes):
        assert abs((end - start) - 15000 * size / sum(sizes)) <= 2


def test_make_srt_refuses_output_inside_the_repository():
    target = REPO / "docs" / "never-written.srt"
    result = run_script("make_srt.py", "--output", target)
    assert result.returncode == 2, result.stderr
    assert "inside the repository" in result.stderr
    assert not target.exists()


def card_windows():
    return [(r["n"], r["start"] * 1000, r["end"] * 1000) for r in plan_rows() if r["kind"] == "Text card"]


def test_first_cut_srt_has_no_cue_inside_a_card_shot(tmp_path):
    out = tmp_path / "first-cut.srt"
    result = run_script("make_srt.py", "--column", "subtitle", "--skip-kind", "card", "--output", out)
    assert result.returncode == 0, result.stderr
    cues = parse_srt(out.read_text(encoding="utf-8"))
    windows = card_windows()
    assert [n for n, _, _ in windows] == [1, 2, 11, 16, 18]
    for number, start, end in windows:
        overlapping = [c for c in cues if c[0] < end and c[1] > start]
        assert overlapping == [], f"card shot {number} has a burned-in cue"
    # every other shot keeps its cues
    for row in plan_rows():
        if row["kind"] != "Text card":
            assert any(row["start"] * 1000 <= c[0] < row["end"] * 1000 for c in cues), f"shot {row['n']} lost its cues"


def test_first_cut_srt_of_the_recorder_skips_cards_and_keeps_the_timeline():
    plan_shots = record_demo.parse_plan(PLAN.read_text(encoding="utf-8"))
    timeline = make_srt.retimed([p.shot for p in plan_shots])
    cues = parse_srt(make_srt.build_srt(timeline, "subtitle", skip_kinds=("card",)))
    for number, start, end in card_windows():
        assert not [c for c in cues if c[0] < end and c[1] > start], f"card shot {number}"
    assert make_srt.build_srt(timeline, "subtitle", skip_kinds=("card", "live", "still")) == ""


def test_voiceover_srt_covers_all_18_shots_including_cards(tmp_path):
    out = tmp_path / "voiceover.srt"
    result = run_script("make_srt.py", "--column", "voiceover", "--output", out)
    assert result.returncode == 0, result.stderr
    cues = parse_srt(out.read_text(encoding="utf-8"))
    rows = plan_rows()
    assert len(rows) == 18
    for row in rows:
        assert any(row["start"] * 1000 <= c[0] < row["end"] * 1000 for c in cues), f"shot {row['n']} has no voice-over cue"
    assert cues[-1][1] == 175000


def test_make_srt_rejects_an_unknown_skip_kind(tmp_path):
    result = run_script("make_srt.py", "--skip-kind", "banner", "--output", tmp_path / "x.srt")
    assert result.returncode == 2
    assert "invalid choice" in result.stderr


def test_shot_kind_matches_the_recorder_kind():
    plan_shots = record_demo.parse_plan(PLAN.read_text(encoding="utf-8"))
    assert [p.kind for p in plan_shots] == [p.shot.kind for p in plan_shots]
    assert [p.kind for p in plan_shots].count("card") == 5


# ---------------------------------------------------------------------------
# record_demo
# ---------------------------------------------------------------------------

def test_band_geometry_is_what_the_script_uses():
    assert (record_demo.WIDTH, record_demo.HEIGHT, record_demo.BAND_HEIGHT) == (1280, 720, 120)
    assert record_demo.PAGE_HEIGHT == 600
    assert record_demo.viewport_for("live") == {"width": 1280, "height": 600}
    assert record_demo.viewport_for("card") == {"width": 1280, "height": 720}
    # live pages and the still image: page at the top (y offset 0) of a 1280x720 frame
    top = record_demo.normalize_for("live")
    assert top == record_demo.normalize_for("still") == record_demo.NORMALIZE_TOP
    assert "scale=1280:600" in top and "pad=1280:720:(ow-iw)/2:0:black" in top
    # cards keep the whole frame
    assert "scale=1280:720" in record_demo.normalize_for("card")


def test_shot_4_action_brings_the_grand_total_row_into_the_page_area():
    import inspect
    path, action = record_demo.ACTIONS[4]
    assert action is record_demo.act_scroll_subtotals
    source = inspect.getsource(action)
    assert "Grand total" in source
    assert "PAGE_HEIGHT" in source and "RecordError" in source
    # the row the action looks for exists in the step 2 template
    template = (REPO / "coroner" / "ui" / "templates" / "story_step_2.html").read_text(encoding="utf-8")
    assert '<th scope="row">Grand total</th>' in template


def test_card_page_leaves_the_band_free(tmp_path):
    page = tmp_path / "card.html"
    record_demo.render_card(["Line one", "Line two"], page)
    css = page.read_text(encoding="utf-8")
    assert "height: 720px" in css
    assert "padding: 0 90px 120px" in css


def shot_18_card_lines():
    plan_shots = record_demo.parse_plan(PLAN.read_text(encoding="utf-8"))
    shot = next(p for p in plan_shots if p.shot.number == 18)
    assert shot.kind == "card"
    return shot.card_lines


def paragraphs(page):
    return re.findall(r"<p class=\"(?:text|note)(?: nowrap)?\">(.*?)</p>", page.read_text(encoding="utf-8"))


def old_card_html(lines, final_card=False):
    """The card HTML as render_card wrote it before the URL rule (copy of that logic)."""
    import html as html_module
    body = [line for line in lines if not line.startswith("Placeholder")]
    chars = sum(len(line) for line in body)
    size = 72 if chars <= 60 else 52 if chars <= 130 else 40 if chars <= 230 else 34
    shown = body if final_card else lines
    paragraphs = "\n".join(
        f'<p class="{"note" if line.startswith("Placeholder") else "text"}">{html_module.escape(line)}</p>' for line in shown)
    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><title>Card</title>
<style>
html, body {{ margin: 0; width: {record_demo.WIDTH}px; height: {record_demo.HEIGHT}px; background: #0a0a0a; color: #e5e5e5; overflow: hidden; }}
body {{ display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 28px;
  padding: 0 90px {record_demo.BAND_HEIGHT}px; box-sizing: border-box; text-align: center; font-family: Georgia, 'Times New Roman', serif; }}
p {{ margin: 0; max-width: 1100px; line-height: 1.3; }}
p.text {{ font-size: {size}px; }}
p.note {{ font-size: 26px; color: #a3a3a3; font-family: -apple-system, 'Segoe UI', Roboto, sans-serif; }}
</style></head><body>
{paragraphs}
</body></html>
"""


def test_final_card_url_lines_never_wrap_and_fit_the_text_width(tmp_path):
    lines = shot_18_card_lines()
    page = tmp_path / "final.html"
    record_demo.render_card(lines, page, final_card=True)
    text = page.read_text(encoding="utf-8")
    url_lines = [line for line in lines if record_demo.URL_LINE.search(line) and not line.startswith("Placeholder")]
    assert any("github.com/yarahmouni/cobol-coroner" in line for line in url_lines)
    for line in url_lines:
        assert f'<p class="text nowrap">{line}</p>' in text
    assert "p.nowrap { white-space: nowrap; }" in text
    size = int(re.search(r"p\.text \{ font-size: (\d+)px; \}", text).group(1))
    longest = max(len(line) for line in url_lines)
    assert longest * 0.5 * size <= 1100
    assert size < 52  # the size of the old rule for this card, which did not fit
    # lines without a URL are not marked nowrap
    assert '<p class="text">AI accelerates. Coroner certifies.</p>' in text


def test_every_card_without_a_url_line_is_byte_identical_to_the_old_html(tmp_path):
    cards = [p for p in record_demo.parse_plan(PLAN.read_text(encoding="utf-8")) if p.kind == "card"]
    assert len(cards) == 5
    unchanged = 0
    for planned in cards:
        lines = planned.card_lines
        if any(record_demo.URL_LINE.search(line) for line in lines if not line.startswith("Placeholder")):
            assert planned.shot.number == 18
            continue
        for final in (False, True):
            page = tmp_path / f"card-{planned.shot.number}-{final}.html"
            record_demo.render_card(lines, page, final_card=final)
            assert page.read_text(encoding="utf-8") == old_card_html(lines, final), planned.shot.number
        unchanged += 1
    assert unchanged == 4


def test_final_card_option_leaves_out_the_placeholder_note_only(tmp_path):
    lines = shot_18_card_lines()
    placeholders = [line for line in lines if line.startswith("Placeholder")]
    others = [line for line in lines if not line.startswith("Placeholder")]
    assert placeholders and others
    default_page, final_page = tmp_path / "default.html", tmp_path / "final.html"
    record_demo.render_card(lines, default_page)
    record_demo.render_card(lines, final_page, final_card=True)
    default_text, final_text = paragraphs(default_page), paragraphs(final_page)
    assert any(text.startswith("Placeholder") for text in default_text)
    assert not any("Placeholder" in text for text in final_text)
    assert [t for t in default_text if not t.startswith("Placeholder")] == final_text
    assert len(final_text) == len(others)


def test_final_card_option_changes_nothing_without_a_placeholder_line(tmp_path):
    plain, final = tmp_path / "plain.html", tmp_path / "final.html"
    record_demo.render_card(["Line one", "Line two"], plain)
    record_demo.render_card(["Line one", "Line two"], final, final_card=True)
    assert plain.read_text(encoding="utf-8") == final.read_text(encoding="utf-8")


def test_record_demo_dry_run_accepts_final_card(tmp_path):
    result = run_script("record_demo.py", "--dry-run", "--shots", "18", "--final-card", "--out-dir", tmp_path / "cut")
    assert result.returncode == 0, result.stderr
    assert "Total: 1 shots, 8 s" in result.stdout


def test_subtitles_sit_inside_the_band_and_are_white_with_at_most_two_lines():
    assert record_demo.subtitle_top_px(lines=2) >= record_demo.PAGE_HEIGHT
    style = record_demo.SUBTITLE_STYLE
    assert "Alignment=2" in style and "PrimaryColour=&H00FFFFFF" in style
    # readable: at least 24 output pixels
    assert record_demo.SUBTITLE_FONT_SIZE * record_demo.HEIGHT / record_demo.SRT_PLAY_RES_Y >= 24


def test_toggle_button_selector_exists_in_the_templates_and_is_hidden_during_recording():
    base = (REPO / "coroner" / "ui" / "templates" / "base.html").read_text(encoding="utf-8")
    assert 'class="theme-toggle"' in base
    assert ".theme-toggle" in record_demo.HIDE_CHROME_CSS and "display: none" in record_demo.HIDE_CHROME_CSS


def test_record_demo_help_exits_zero():
    result = run_script("record_demo.py", "--help")
    assert result.returncode == 0, result.stderr
    for option in ("--out-dir", "--ffmpeg", "--shots", "--dry-run"):
        assert option in result.stdout


def test_record_demo_refuses_out_dir_inside_the_repository():
    target = REPO / "build" / "never-written-cut"
    result = run_script("record_demo.py", "--dry-run", "--out-dir", target)
    assert result.returncode == 2, result.stderr
    assert "inside the repository" in result.stderr
    assert not target.exists()


def test_record_demo_dry_run_lists_every_shot(tmp_path):
    out_dir = tmp_path / "cut"
    result = run_script("record_demo.py", "--dry-run", "--out-dir", out_dir)
    assert result.returncode == 0, result.stderr
    assert not out_dir.exists(), "a dry run must record and create nothing"

    rows = plan_rows()
    listed = re.findall(r"^Shot +(\d+) +\S+ +(\d+) s +(card|live|still) +(.*)$", result.stdout, re.M)
    assert len(listed) == 18
    kind_of = {"Text card": "card", "Live page": "live", "Still image": "still"}
    for (number, seconds, kind, what), row in zip(listed, rows):
        assert int(number) == row["n"]
        assert int(seconds) == row["duration"]
        assert kind == kind_of[row["kind"]], f"shot {row['n']}"
        assert what.strip(), f"shot {row['n']} has nothing to show"
    kinds = [kind for _, _, kind, _ in listed]
    assert (kinds.count("card"), kinds.count("live"), kinds.count("still")) == (5, 12, 1)
    total = sum(r["duration"] for r in rows)
    assert f"Total: 18 shots, {total} s" in result.stdout


def test_record_demo_dry_run_limited_to_some_shots(tmp_path):
    result = run_script("record_demo.py", "--dry-run", "--shots", "6,1", "--out-dir", tmp_path / "cut")
    assert result.returncode == 0, result.stderr
    assert "Total: 2 shots, 14 s" in result.stdout


def test_action_table_covers_every_live_shot_with_the_plan_url():
    live_path = re.compile(r"Live page: https?://[^/\s]+(/\S*?)\.\s")
    expected = {}
    for row in plan_rows():
        if row["kind"] == "Live page":
            match = live_path.match(row["source"])
            assert match, f"shot {row['n']}"
            expected[row["n"]] = match.group(1)
    assert len(expected) == 12
    assert {n: path for n, (path, _) in record_demo.ACTIONS.items()} == expected
    plan_shots = record_demo.parse_plan(PLAN.read_text(encoding="utf-8"))
    assert record_demo.check_actions(plan_shots) == []


def test_action_check_reports_a_wrong_url_a_missing_entry_and_a_stray_entry():
    plan_shots = record_demo.parse_plan(PLAN.read_text(encoding="utf-8"))
    actions = dict(record_demo.ACTIONS)
    actions[6] = ("/run/000000000000", actions[6][1])
    del actions[17]
    actions[1] = ("/", actions[3][1])
    problems = " ".join(record_demo.check_actions(plan_shots, actions))
    assert "shot 6" in problems and "differs" in problems
    assert "shot 17" in problems and "no action entry" in problems
    assert "shot 1:" in problems and "no live page" in problems


def test_record_demo_disk_space_guard(tmp_path):
    free_gb = shutil.disk_usage(tmp_path).free / (1024 ** 3)
    threshold_gb = free_gb + 1000
    result = run_script("record_demo.py", "--out-dir", tmp_path, "--min-free-gb", threshold_gb,
                        "--shots", "6", "--url", "http://127.0.0.1:9999")
    assert result.returncode == 2, f"expected exit 2, got {result.returncode}: {result.stderr}"
    assert "free disk space available" in result.stderr
    assert f"Need at least {threshold_gb:.0f} GB" in result.stderr
    assert list(tmp_path.iterdir()) == [], "files were created despite the disk space error"


# ---------------------------------------------------------------------------
# Recording against the running stack
# ---------------------------------------------------------------------------

@pytest.mark.slow
def test_record_demo_first_cut_of_shots_1_and_6(tmp_path):
    ffmpeg = os.environ.get("CORONER_FFMPEG")
    if not ffmpeg:
        pytest.skip("CORONER_FFMPEG is not set")
    try:
        urllib.request.urlopen(STACK_URL + "/", timeout=5).close()
    except OSError:
        pytest.skip(f"the stack does not answer at {STACK_URL}")

    out_dir = tmp_path / "cut"
    result = subprocess.run(
        [sys.executable, str(SCRIPTS / "record_demo.py"), "--url", STACK_URL, "--out-dir", str(out_dir),
         "--ffmpeg", ffmpeg, "--shots", "1,6"],
        capture_output=True, text=True, timeout=600,
    )
    assert result.returncode == 0, result.stdout[-1500:] + result.stderr[-1500:]

    first_cut = out_dir / "first-cut.mp4"
    assert first_cut.is_file()
    rows = {r["n"]: r for r in plan_rows()}
    expected = rows[1]["duration"] + rows[6]["duration"]
    assert abs(ffmpeg_duration(ffmpeg, first_cut) - expected) <= 0.2
    for name in ("first-cut.srt", "voiceover.srt", "shots.json"):
        assert (out_dir / name).is_file()
    cues = parse_srt((out_dir / "first-cut.srt").read_text(encoding="utf-8"))
    assert cues[-1][1] == expected * 1000, "subtitles must follow the recorded timeline, not the plan's"
    assert cues[0][0] >= rows[1]["duration"] * 1000, "no burned-in cue during the card shot 1"
    voice = parse_srt((out_dir / "voiceover.srt").read_text(encoding="utf-8"))
    assert voice[0][0] == 0, "voiceover.srt keeps the card shot"

    info = subprocess.run([ffmpeg, "-hide_banner", "-i", str(first_cut)], capture_output=True, text=True).stderr
    assert re.search(r"Video: h264.* 1280x720", info), info[-400:]
