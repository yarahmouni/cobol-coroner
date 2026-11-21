#!/usr/bin/env python3
"""Record the first cut of the demo video from docs/video-plan.md.

The shot list is parsed from the plan (section 3 table and section 3.1 cards), so
this script and the plan cannot drift. Text cards are rendered as HTML pages, live
pages are recorded from the running stack with Playwright, the still image is
turned into a clip by ffmpeg. All outputs go to --out-dir, outside the repository.

Frame layout (1280x720): live pages are recorded at 1280x600 and sit at the top, a black band of
120 px at the bottom holds the burned subtitles. Text cards use the whole frame but leave the same
band free and get no burned subtitle (the card is the text). During recording only, the page's
Light/Dark toggle button is hidden by an injected CSS rule; templates are unchanged.
"""
import argparse
import html
import json
import os
import re
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import make_srt  # noqa: E402

REPO_ROOT = make_srt.REPO_ROOT
DEFAULT_URL = "http://127.0.0.1:8000"
WIDTH, HEIGHT, FPS = 1280, 720, 30
# Frame layout: live pages and the still image sit at the top (PAGE_HEIGHT), a black band of
# BAND_HEIGHT at the bottom holds the burned subtitles. Text cards keep the whole frame but
# leave the same band free.
BAND_HEIGHT = 120
PAGE_HEIGHT = HEIGHT - BAND_HEIGHT
# Page chrome that overlaps content at 1280x600. Injected during recording only, templates unchanged.
HIDE_CHROME_CSS = ".theme-toggle { display: none !important; }"
# libass converts an SRT to a script of height SRT_PLAY_RES_Y, so sizes below are in those units.
SRT_PLAY_RES_Y = 288
SUBTITLE_FONT_SIZE = 13
SUBTITLE_MARGIN_V = 12
SUBTITLE_LINE_HEIGHT = 1.25
SUBTITLE_STYLE = (f"FontSize={SUBTITLE_FONT_SIZE},PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,"
                  f"BorderStyle=1,Outline=1,Shadow=0,Alignment=2,MarginV={SUBTITLE_MARGIN_V}")
PRE_ROLL_S = 2.0
HOLD_MARGIN_S = 1.0
REPLAY_TIMEOUT_MS = 150_000
POST_COOLDOWN_S = 11.0
LIVE_DEFAULT_TIMEOUT_MS = 30_000


class RecordError(Exception):
    """A recording or assembly step failed."""


# ---------------------------------------------------------------------------
# Plan parsing
# ---------------------------------------------------------------------------

@dataclass
class PlanShot:
    shot: make_srt.Shot
    kind: str  # card, live, still
    card: int = 0
    card_lines: list = field(default_factory=list)
    path: str = ""
    image: str = ""

    def describe(self, base_url):
        if self.kind == "card":
            return f"card {self.card}: " + " | ".join(self.card_lines)
        if self.kind == "live":
            return base_url.rstrip("/") + self.path
        return self.image


def parse_cards(plan_text):
    """Card number -> list of text lines, from section 3.1."""
    section = make_srt.section_between(plan_text, "### 3.1", "\n## 4.")
    cards = {}
    for match in re.finditer(r"\*\*Card (\d+) \([^)]*\):\*\*\n((?:- .*(?:\n|$))+)", section):
        cards[int(match.group(1))] = [line[2:].strip() for line in match.group(2).splitlines() if line.startswith("- ")]
    return cards


def parse_plan(plan_text):
    """All shots of the plan with their kind and the data needed to record them."""
    cards = parse_cards(plan_text)
    result = []
    for shot in make_srt.parse_shots(plan_text):
        source = shot.source
        kind = shot.kind
        if kind == "card":
            match = re.search(r"section 3\.1, card (\d+)", source)
            if not match or int(match.group(1)) not in cards:
                raise make_srt.PlanError(f"shot {shot.number}: card not found in section 3.1")
            number = int(match.group(1))
            result.append(PlanShot(shot, "card", card=number, card_lines=cards[number]))
        elif kind == "live":
            match = re.match(r"Live page: https?://[^/\s]+(/\S*?)\.\s", source)
            if not match:
                raise make_srt.PlanError(f"shot {shot.number}: no URL in the source cell")
            result.append(PlanShot(shot, "live", path=match.group(1)))
        else:
            match = re.match(r"Still image: (\S+\.(?:png|jpg|jpeg))", source)
            if not match:
                raise make_srt.PlanError(f"shot {shot.number}: no image path in the source cell")
            result.append(PlanShot(shot, "still", image=match.group(1)))
    return result


# ---------------------------------------------------------------------------
# Per-shot actions (cannot be parsed from prose). Locators by role or text only.
# ---------------------------------------------------------------------------

class Rec:
    """What an action tells the recorder: when the final state became visible."""

    last_post = {}

    def __init__(self, page):
        self.page = page
        self.t0 = time.monotonic()
        self.loaded = None
        self.answer_at = None  # set by actions that wait for a long answer

    def now(self):
        return time.monotonic() - self.t0

    def mark_answer(self):
        self.answer_at = self.now()

    def cooldown(self, key):
        """Wait so that two posts of the same kind are at least POST_COOLDOWN_S apart (rate limit)."""
        wait = POST_COOLDOWN_S - (time.monotonic() - Rec.last_post.get(key, -1e9))
        if wait > 0:
            self.page.wait_for_timeout(int(wait * 1000))
        Rec.last_post[key] = time.monotonic()


def scroll_to_top(page, locator):
    target = locator.first
    target.wait_for(state="visible")
    target.evaluate("el => el.scrollIntoView({block: 'start', behavior: 'smooth'})")
    page.wait_for_timeout(1200)


def warn_if_outside_viewport(page, locator, what):
    inside = locator.first.evaluate("el => { const r = el.getBoundingClientRect(); return r.top >= 0 && r.bottom <= window.innerHeight; }")
    if not inside:
        print(f"  WARNING: {what} is not fully inside the {WIDTH}x{PAGE_HEIGHT} page area", file=sys.stderr)


def act_open_step(page, rec):
    page.get_by_role("heading", level=2).first.wait_for(state="visible")


SUBTOTALS_MARGIN_PX = 16


def box_of(locator):
    return locator.first.evaluate(
        "el => { const r = el.getBoundingClientRect(); return {top: r.top, bottom: r.bottom}; }")


def act_scroll_subtotals(page, rec):
    caption = page.get_by_text("Subtotals posted by the COBOL program", exact=True)
    grand_total = page.get_by_role("row", name=re.compile(r"^Grand total")).first
    scroll_to_top(page, caption)
    # Bring the Grand total row into view with a small margin below it.
    delta = box_of(grand_total)["bottom"] - (PAGE_HEIGHT - SUBTOTALS_MARGIN_PX)
    if delta > 0:
        page.evaluate("d => window.scrollBy({top: d, behavior: 'smooth'})", delta)
        page.wait_for_timeout(1200)
    caption_box = box_of(caption)
    total_box = box_of(grand_total)
    print(f"  shot 4 measured: caption top {caption_box['top']:.1f}, "
          f"Grand total row bottom {total_box['bottom']:.1f}, page area {PAGE_HEIGHT} px")
    if total_box["bottom"] > PAGE_HEIGHT:
        raise RecordError("the Grand total row is cut at the bottom of the page area")
    if caption_box["top"] < 0:
        # The table is taller than the page area: the Grand total row wins, the 001 and 9ZZ rows must show.
        for code in ("001", "9ZZ"):
            row = page.get_by_role("row", name=re.compile(rf"^{code}\b")).first
            row_box = box_of(row)
            print(f"  shot 4 measured: row {code} top {row_box['top']:.1f}, bottom {row_box['bottom']:.1f}")
            if row_box["top"] < 0 or row_box["bottom"] > PAGE_HEIGHT:
                raise RecordError(f"the table is taller than the page area and row {code} is not inside it")


def act_zombie_page(page, rec):
    page.get_by_text("MIGRATION REJECTED", exact=True).first.wait_for(state="visible")
    page.get_by_text("This Java migration is not safe to promote", exact=False).first.wait_for(state="visible")


def act_exposure_figures(page, rec):
    scroll_to_top(page, page.get_by_text("Exposure", exact=True))
    warn_if_outside_viewport(page, page.get_by_role("heading", name="Branch Reconciliation"), "heading Branch Reconciliation")


def act_check_gate(page, rec):
    scroll_to_top(page, page.get_by_role("heading", name="The gate", exact=True))
    rec.cooldown("gate")
    page.get_by_role("button", name="Check the gate", exact=True).click()
    page.get_by_text(re.compile(r"Exit code \d+")).first.wait_for(state="visible", timeout=REPLAY_TIMEOUT_MS)
    rec.mark_answer()


def act_cause_of_death(page, rec):
    scroll_to_top(page, page.get_by_role("heading", name="Cause of death", exact=True))


def act_alive_page(page, rec):
    page.get_by_text("MIGRATION CERTIFIED", exact=True).first.wait_for(state="visible")


def act_tamper(page, rec):
    status = page.get_by_label("Status", exact=True)
    status.wait_for(state="visible")
    if status.input_value() != "ZOMBIE":
        raise RecordError(f"the tamper form is prefilled with '{status.input_value()}', expected ZOMBIE")
    status.fill("ALIVE")
    page.get_by_label("Cases Divergent", exact=True).fill("0")
    page.wait_for_timeout(500)
    rec.cooldown("tamper")
    page.get_by_role("button", name="Verify Tampered Certificate", exact=True).click()
    page.get_by_text("Certificate: INVALID", exact=False).first.wait_for(state="visible", timeout=REPLAY_TIMEOUT_MS)
    rec.mark_answer()
    # The result is the last element of the page: add room below it (recording only) so it can
    # be scrolled to the middle of the screen, above the subtitles.
    page.add_style_tag(content="body { padding-bottom: 400px; }")
    page.get_by_text("Certificate: INVALID", exact=False).first.evaluate(
        "el => el.scrollIntoView({block: 'center', behavior: 'smooth'})")
    page.wait_for_timeout(1200)


def act_matrix(page, rec):
    scroll_to_top(page, page.get_by_role("table"))
    for trap in ("T1", "T6"):
        warn_if_outside_viewport(page, page.get_by_role("cell", name=trap, exact=True), f"row {trap}")


# Shot number -> (path of the live page, action). The path must equal the plan's.
ACTIONS = {
    3: ("/story/step/1?view=business", act_open_step),
    4: ("/story/step/2?view=business", act_scroll_subtotals),
    5: ("/story/step/3?view=business", act_open_step),
    6: ("/run/f584d5f35228", act_zombie_page),
    7: ("/run/f584d5f35228", act_exposure_figures),
    8: ("/story/step/4?view=business", act_check_gate),
    9: ("/story/step/5?view=business", act_cause_of_death),
    10: ("/story/step/6?view=business", act_open_step),
    12: ("/run/29c15f04407b", act_alive_page),
    13: ("/story/step/7?view=business", act_check_gate),
    14: ("/tamper?run_id=f584d5f35228", act_tamper),
    17: ("/matrix", act_matrix),
}


def check_actions(plan_shots, actions=None):
    """Problems between the action table and the plan; empty when they agree."""
    actions = ACTIONS if actions is None else actions
    problems = []
    live = {p.shot.number: p for p in plan_shots if p.kind == "live"}
    for number, plan_shot in sorted(live.items()):
        if number not in actions:
            problems.append(f"shot {number}: live page {plan_shot.path} has no action entry")
        elif actions[number][0] != plan_shot.path:
            problems.append(f"shot {number}: action URL path '{actions[number][0]}' differs from the plan's '{plan_shot.path}'")
    for number in sorted(actions):
        if number not in live:
            problems.append(f"shot {number}: action entry exists but the plan has no live page for this shot")
    return problems


# ---------------------------------------------------------------------------
# Disk, paths, ffmpeg
# ---------------------------------------------------------------------------

def check_disk_space(out_dir, threshold_gb):
    probe = Path(out_dir)
    while not probe.exists():
        probe = probe.parent
    free_gb = shutil.disk_usage(probe).free / (1024 ** 3)
    if free_gb < threshold_gb:
        print(f"ERROR: Only {free_gb:.2f} GB free disk space available", file=sys.stderr)
        print(f"Need at least {threshold_gb:.0f} GB free to record safely", file=sys.stderr)
        sys.exit(2)


def run_ffmpeg(ffmpeg, args, cwd=None):
    command = [ffmpeg, "-y", "-hide_banner", "-loglevel", "error"] + args
    result = subprocess.run(command, capture_output=True, text=True, cwd=cwd)
    if result.returncode != 0:
        raise RecordError(f"ffmpeg failed ({result.returncode}): {result.stderr.strip()[-800:]}")


def probe_duration(ffmpeg, path):
    """Duration in seconds, read from the output of `ffmpeg -i`."""
    result = subprocess.run([ffmpeg, "-hide_banner", "-i", str(path)], capture_output=True, text=True)
    match = re.search(r"Duration: (\d+):(\d+):(\d+\.\d+)", result.stderr)
    if not match:
        raise RecordError(f"cannot read the duration of {path}")
    hours, minutes, seconds = match.groups()
    return int(hours) * 3600 + int(minutes) * 60 + float(seconds)


NORMALIZE_FULL = (f"scale={WIDTH}:{HEIGHT}:force_original_aspect_ratio=decrease,"
                  f"pad={WIDTH}:{HEIGHT}:(ow-iw)/2:(oh-ih)/2:black,setsar=1,fps={FPS}")
# Page at the top of the frame, black band at the bottom.
NORMALIZE_TOP = (f"scale={WIDTH}:{PAGE_HEIGHT}:force_original_aspect_ratio=decrease,"
                 f"pad={WIDTH}:{HEIGHT}:(ow-iw)/2:0:black,setsar=1,fps={FPS}")
ENCODE = ["-c:v", "libx264", "-preset", "fast", "-crf", "18", "-pix_fmt", "yuv420p", "-an"]


def viewport_for(kind):
    """Browser viewport and raw video size of a shot kind: cards use the whole frame, live pages the page area."""
    return {"width": WIDTH, "height": HEIGHT if kind == "card" else PAGE_HEIGHT}


def normalize_for(kind):
    return NORMALIZE_FULL if kind == "card" else NORMALIZE_TOP


def subtitle_top_px(lines=2):
    """Top of the subtitle text block in output pixels, assuming the given number of lines."""
    scale = HEIGHT / SRT_PLAY_RES_Y
    return HEIGHT - SUBTITLE_MARGIN_V * scale - lines * SUBTITLE_FONT_SIZE * scale * SUBTITLE_LINE_HEIGHT


def clip_from_video(ffmpeg, raw, keep_from, duration, out, normalize=NORMALIZE_TOP):
    """Trim a raw recording to [keep_from, keep_from + duration]; pad with the last frame if it is short."""
    run_ffmpeg(ffmpeg, ["-ss", f"{keep_from:.3f}", "-i", str(raw),
                        "-vf", normalize + ",tpad=stop_mode=clone:stop_duration=3,format=yuv420p",
                        "-frames:v", str(round(duration * FPS))] + ENCODE + [str(out)])


def clip_from_image(ffmpeg, image, duration, out):
    run_ffmpeg(ffmpeg, ["-loop", "1", "-framerate", str(FPS), "-i", str(image),
                        "-vf", NORMALIZE_TOP + ",format=yuv420p", "-frames:v", str(round(duration * FPS))] + ENCODE + [str(out)])


# ---------------------------------------------------------------------------
# Cards
# ---------------------------------------------------------------------------

def render_card(lines, path):
    body = [line for line in lines if not line.startswith("Placeholder")]
    chars = sum(len(line) for line in body)
    size = 72 if chars <= 60 else 52 if chars <= 130 else 40 if chars <= 230 else 34
    paragraphs = "\n".join(
        f'<p class="{"note" if line.startswith("Placeholder") else "text"}">{html.escape(line)}</p>' for line in lines)
    path.write_text(f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><title>Card</title>
<style>
html, body {{ margin: 0; width: {WIDTH}px; height: {HEIGHT}px; background: #0a0a0a; color: #e5e5e5; overflow: hidden; }}
body {{ display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 28px;
  padding: 0 90px {BAND_HEIGHT}px; box-sizing: border-box; text-align: center; font-family: Georgia, 'Times New Roman', serif; }}
p {{ margin: 0; max-width: 1100px; line-height: 1.3; }}
p.text {{ font-size: {size}px; }}
p.note {{ font-size: 26px; color: #a3a3a3; font-family: -apple-system, 'Segoe UI', Roboto, sans-serif; }}
</style></head><body>
{paragraphs}
</body></html>
""", encoding="utf-8")


# ---------------------------------------------------------------------------
# Recording
# ---------------------------------------------------------------------------

def launch_browser(playwright):
    """Playwright's Chromium, or the browser named by SCREENSHOT_CHANNEL; installed Chrome as a last resort."""
    channel = os.environ.get("SCREENSHOT_CHANNEL", "")
    if channel:
        return playwright.chromium.launch(headless=True, channel=channel)
    try:
        return playwright.chromium.launch(headless=True)
    except Exception as first:
        try:
            return playwright.chromium.launch(headless=True, channel="chrome")
        except Exception:
            raise RecordError("cannot launch a browser: install Playwright's Chromium or set SCREENSHOT_CHANNEL=chrome "
                              f"({str(first).splitlines()[0]})") from first


def record_page_shot(context, plan_shot, base_url, cards_dir, raw_dir, actions):
    """Record one browser shot to raw/shot-NN.webm and return its trim data."""
    shot = plan_shot.shot
    if plan_shot.kind == "card":
        card_file = cards_dir / f"card-{plan_shot.card}.html"
        render_card(plan_shot.card_lines, card_file)
        target = card_file.resolve().as_uri()
    else:
        target = base_url.rstrip("/") + plan_shot.path

    page = context.new_page()
    page.set_default_timeout(LIVE_DEFAULT_TIMEOUT_MS)
    rec = Rec(page)
    try:
        page.goto(target, wait_until="load")
        if plan_shot.kind == "live":
            page.add_style_tag(content=HIDE_CHROME_CSS)
        page.wait_for_load_state("networkidle")
        rec.loaded = rec.now()
        if plan_shot.kind == "live":
            actions[shot.number][1](page, rec)
        ready = rec.now()
        keep_from = rec.loaded if rec.answer_at is None else max(rec.loaded, rec.answer_at - PRE_ROLL_S)
        wait = keep_from + shot.duration + HOLD_MARGIN_S - rec.now()
        if wait > 0:
            page.wait_for_timeout(int(wait * 1000))
    finally:
        page.close()
    raw = raw_dir / f"shot-{shot.number:02d}.webm"
    page.video.save_as(str(raw))
    page.video.delete()
    if rec.answer_at is None and ready > keep_from + shot.duration:
        print(f"  WARNING: shot {shot.number}: final state reached at {ready - keep_from:.1f} s, after the {shot.duration} s of the shot", file=sys.stderr)
    return {"raw": raw, "loaded_at": round(rec.loaded, 3), "ready_at": round(ready, 3),
            "answer_at": None if rec.answer_at is None else round(rec.answer_at, 3), "keep_from": round(keep_from, 3)}


def playwright_ffmpeg_shim(ffmpeg, out_dir):
    """Let Playwright's video recorder use the given ffmpeg when its own build is not installed.

    Playwright looks for ffmpeg-<revision>/ffmpeg-<platform> in its browser cache. When that file
    is missing, a folder inside out_dir with a link to the given ffmpeg is used as browser cache,
    so no download and nothing outside out_dir is needed (the browser then comes from the
    installed Chrome, see launch_browser).
    """
    import importlib.util

    names = {"darwin": "ffmpeg-mac", "linux": "ffmpeg-linux"}
    name = names.get(sys.platform)
    spec = importlib.util.find_spec("playwright")
    if name is None or spec is None or not spec.submodule_search_locations:
        return
    browsers = json.loads((Path(spec.submodule_search_locations[0]) / "driver" / "package" / "browsers.json").read_text())
    revision = next(b["revision"] for b in browsers["browsers"] if b["name"] == "ffmpeg")
    cache = os.environ.get("PLAYWRIGHT_BROWSERS_PATH")
    cache = Path(cache) if cache else (Path.home() / "Library" / "Caches" / "ms-playwright" if sys.platform == "darwin"
                                       else Path.home() / ".cache" / "ms-playwright")
    if (cache / f"ffmpeg-{revision}" / name).is_file():
        return
    shim = out_dir / "playwright-browsers" / f"ffmpeg-{revision}"
    shim.mkdir(parents=True, exist_ok=True)
    link = shim / name
    if not link.exists():
        link.symlink_to(Path(ffmpeg).resolve())
    os.environ["PLAYWRIGHT_BROWSERS_PATH"] = str(out_dir / "playwright-browsers")
    print("Playwright's own ffmpeg is not installed: its recorder uses the --ffmpeg binary", flush=True)


def record_all(selected, args, out_dir, actions):
    playwright_ffmpeg_shim(args.ffmpeg, out_dir)
    from playwright.sync_api import sync_playwright  # imported late: the disk guard runs first

    raw_dir = out_dir / "raw"
    cards_dir = out_dir / "cards"
    raw_dir.mkdir(parents=True, exist_ok=True)
    cards_dir.mkdir(parents=True, exist_ok=True)
    trims = {}
    with sync_playwright() as playwright:
        browser = launch_browser(playwright)
        try:
            contexts = {}
            for kind in ("card", "live"):
                size = viewport_for(kind)
                contexts[kind] = browser.new_context(viewport=size, device_scale_factor=1,
                                                     record_video_dir=str(raw_dir), record_video_size=size)
            for plan_shot in selected:
                if plan_shot.kind == "still":
                    continue
                print(f"Recording shot {plan_shot.shot.number} ({plan_shot.kind}) ...", flush=True)
                try:
                    trims[plan_shot.shot.number] = record_page_shot(contexts[plan_shot.kind], plan_shot, args.url,
                                                                    cards_dir, raw_dir, actions)
                except RecordError:
                    raise
                except Exception as error:
                    raise RecordError(f"shot {plan_shot.shot.number}: {type(error).__name__}: {str(error).splitlines()[0]}") from error
            for context in contexts.values():
                context.close()
        finally:
            browser.close()
    return trims


def assemble(selected, trims, args, out_dir):
    ffmpeg = args.ffmpeg
    clips_dir = out_dir / "clips"
    clips_dir.mkdir(parents=True, exist_ok=True)
    clips, report = [], {}
    for plan_shot in selected:
        shot = plan_shot.shot
        clip = clips_dir / f"shot-{shot.number:02d}.mp4"
        if plan_shot.kind == "still":
            clip_from_image(ffmpeg, REPO_ROOT / plan_shot.image, shot.duration, clip)
        else:
            trim = trims[shot.number]
            available = probe_duration(ffmpeg, trim["raw"])
            if available < trim["keep_from"] + shot.duration - 0.2:
                print(f"  WARNING: shot {shot.number}: raw video is {available:.1f} s, the last frame is repeated to fill the shot", file=sys.stderr)
            clip_from_video(ffmpeg, trim["raw"], trim["keep_from"], shot.duration, clip, normalize_for(plan_shot.kind))
        clips.append(clip)
        report[shot.number] = probe_duration(ffmpeg, clip)

    (out_dir / "clips.txt").write_text("".join(f"file 'clips/{c.name}'\n" for c in clips), encoding="utf-8")
    timeline = make_srt.retimed([p.shot for p in selected])
    first_cut_srt = make_srt.build_srt(timeline, "subtitle", skip_kinds=("card",))
    (out_dir / "first-cut.srt").write_text(first_cut_srt, encoding="utf-8")
    (out_dir / "voiceover.srt").write_text(make_srt.build_srt(timeline, "voiceover"), encoding="utf-8")

    # An empty subtitle file (only cards selected) would make the filter fail: burn nothing then.
    video_filter = ["-vf", f"subtitles=first-cut.srt:original_size={WIDTH}x{HEIGHT}:force_style='{SUBTITLE_STYLE}'"] \
        if first_cut_srt.strip() else []
    run_ffmpeg(ffmpeg, ["-f", "concat", "-safe", "0", "-i", "clips.txt"] + video_filter
               + ["-r", str(FPS)] + ENCODE + ["first-cut.mp4"], cwd=str(out_dir))
    return report


def write_shots_json(selected, trims, out_dir):
    entries = []
    for plan_shot in selected:
        shot = plan_shot.shot
        entry = {"shot": shot.number, "kind": plan_shot.kind, "duration_s": shot.duration}
        if plan_shot.kind == "still":
            entry["image"] = plan_shot.image
        else:
            trim = trims[shot.number]
            entry.update({k: v for k, v in trim.items() if k != "raw"})
            entry["raw"] = str(Path("raw") / trim["raw"].name)
        entries.append(entry)
    (out_dir / "shots.json").write_text(json.dumps(entries, indent=2) + "\n", encoding="utf-8")


# ---------------------------------------------------------------------------
# Command line
# ---------------------------------------------------------------------------

def clock(seconds):
    return f"{seconds // 60}:{seconds % 60:02d}"


def print_plan(selected, base_url):
    for plan_shot in selected:
        shot = plan_shot.shot
        print(f"Shot {shot.number:2d}  {clock(shot.start)}-{clock(shot.end)}  {shot.duration:3d} s  "
              f"{plan_shot.kind:5s}  {plan_shot.describe(base_url)}")
    total = sum(p.shot.duration for p in selected)
    print(f"Total: {len(selected)} shots, {total} s ({clock(total)})")


def parse_shot_list(text, known):
    try:
        numbers = sorted({int(part) for part in text.split(",") if part.strip()})
    except ValueError:
        raise ValueError(f"--shots must be a comma list of numbers, got '{text}'")
    unknown = [n for n in numbers if n not in known]
    if not numbers or unknown:
        raise ValueError(f"--shots: unknown shot numbers {unknown or text}")
    return numbers


def main(argv=None):
    parser = argparse.ArgumentParser(description="Record the first cut of the demo video from docs/video-plan.md")
    parser.add_argument("--url", default=DEFAULT_URL, help=f"base URL of the running stack (default: {DEFAULT_URL})")
    parser.add_argument("--out-dir", required=True, help="output folder, outside the repository")
    parser.add_argument("--ffmpeg", help="path of the ffmpeg binary (required to assemble)")
    parser.add_argument("--shots", help="record only these shots, for example 3,6,12")
    parser.add_argument("--dry-run", action="store_true", help="parse the plan and print the shots, record nothing")
    parser.add_argument("--min-free-gb", type=float, default=5.0, help="refuse when less than this would stay free (default: 5)")
    parser.add_argument("--plan", default=str(make_srt.DEFAULT_PLAN), help="video plan (default: docs/video-plan.md)")
    args = parser.parse_args(argv)

    out_dir = Path(args.out_dir).expanduser()
    if make_srt.is_inside_repo(out_dir):
        print(f"ERROR: --out-dir {out_dir} is inside the repository; write recordings outside it", file=sys.stderr)
        return 2
    try:
        plan_shots = parse_plan(Path(args.plan).read_text(encoding="utf-8"))
    except (OSError, make_srt.PlanError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 2
    problems = check_actions(plan_shots)
    if problems:
        print("ERROR: the action table of record_demo.py does not match the plan:", file=sys.stderr)
        for problem in problems:
            print(f"  {problem}", file=sys.stderr)
        return 2

    selected = plan_shots
    if args.shots:
        try:
            wanted = parse_shot_list(args.shots, {p.shot.number for p in plan_shots})
        except ValueError as error:
            print(f"ERROR: {error}", file=sys.stderr)
            return 2
        selected = [p for p in plan_shots if p.shot.number in wanted]

    if args.dry_run:
        print_plan(selected, args.url)
        return 0

    check_disk_space(out_dir, args.min_free_gb)
    if not args.ffmpeg or not Path(args.ffmpeg).is_file():
        print("ERROR: --ffmpeg must be the path of an ffmpeg binary", file=sys.stderr)
        return 2
    for plan_shot in selected:
        if plan_shot.kind == "still" and not (REPO_ROOT / plan_shot.image).is_file():
            print(f"ERROR: shot {plan_shot.shot.number}: image {plan_shot.image} not found", file=sys.stderr)
            return 2

    try:
        from playwright.sync_api import sync_playwright  # noqa: F401
    except ImportError:
        print("ERROR: Playwright is not installed (pip install -e '.[screenshots]')", file=sys.stderr)
        return 2

    out_dir.mkdir(parents=True, exist_ok=True)
    try:
        trims = record_all(selected, args, out_dir, ACTIONS)
        write_shots_json(selected, trims, out_dir)
        report = assemble(selected, trims, args, out_dir)
    except RecordError as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1

    for number, seconds in report.items():
        print(f"clip shot {number:2d}: {seconds:6.2f} s")
    print(f"first-cut.mp4: {probe_duration(args.ffmpeg, out_dir / 'first-cut.mp4'):.2f} s")
    print(f"Wrote {out_dir / 'first-cut.mp4'}, first-cut.srt, voiceover.srt and shots.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
