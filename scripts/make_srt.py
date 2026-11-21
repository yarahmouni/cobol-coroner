#!/usr/bin/env python3
"""Build an .srt subtitle file from the shot table of docs/video-plan.md.

One cue per shot, from its Start to its End, with the text of the chosen column
(subtitle or voiceover). Long text is wrapped to lines of at most 42 characters,
at most 2 lines per cue. A text that needs more lines is split into consecutive
cues inside the shot window, sharing its duration in proportion to their length.
"""
import argparse
import re
import sys
import textwrap
from dataclasses import dataclass, replace
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_PLAN = REPO_ROOT / "docs" / "video-plan.md"
MAX_LINE = 42
MAX_LINES = 2
COLUMNS = {"subtitle": "Subtitle", "voiceover": "Voice-over"}


class PlanError(Exception):
    """The plan does not have the expected shape."""


@dataclass(frozen=True)
class Shot:
    number: int
    start: int
    end: int
    source: str
    subtitle: str
    voiceover: str

    @property
    def duration(self):
        return self.end - self.start

    @property
    def kind(self):
        return shot_kind(self.source, self.number)


KINDS = ("card", "live", "still")


def shot_kind(source, number=0):
    """card, live or still, from the 'Source of the picture' cell of a shot."""
    if source.startswith("Text card"):
        return "card"
    if source.startswith("Live page"):
        return "live"
    if source.startswith("Still image"):
        return "still"
    raise PlanError(f"shot {number}: unknown source '{source[:30]}'")


def parse_clock(text):
    """Parse M:SS (or H:MM:SS) into seconds."""
    match = re.fullmatch(r"(?:(\d+):)?(\d+):(\d\d)", text.strip())
    if not match:
        raise PlanError(f"bad time '{text}'")
    hours, minutes, seconds = match.groups()
    return int(hours or 0) * 3600 + int(minutes) * 60 + int(seconds)


def section_between(text, start_marker, end_marker):
    start = text.find(start_marker)
    if start < 0:
        raise PlanError(f"section '{start_marker}' not found")
    end = text.find(end_marker, start + len(start_marker))
    return text[start:end] if end >= 0 else text[start:]


def parse_shots(plan_text):
    """Parse the table of section 3 into a list of Shot, in plan order."""
    section = section_between(plan_text, "## 3. Shot list", "### 3.1")
    rows = [line for line in section.splitlines() if line.startswith("|")]
    header = next((r for r in rows if r.startswith("| Shot |")), None)
    if header is None:
        raise PlanError("shot table header not found in section 3")
    names = [c.strip() for c in header.strip().strip("|").split("|")]
    index = {}
    for key, name in (("source", "Source of the picture"), ("subtitle", "Subtitle"), ("voiceover", "Voice-over")):
        found = [i for i, n in enumerate(names) if n.startswith(name)]
        if len(found) != 1:
            raise PlanError(f"column '{name}' not found exactly once in the shot table")
        index[key] = found[0]
    duration_col = [i for i, n in enumerate(names) if n == "Duration"]
    if len(duration_col) != 1:
        raise PlanError("column 'Duration' not found in the shot table")

    shots = []
    for row in rows:
        cells = [c.strip() for c in row.strip().strip("|").split("|")]
        if not cells[0].isdigit():
            continue
        if len(cells) != len(names):
            raise PlanError(f"shot {cells[0]}: {len(cells)} cells, expected {len(names)}")
        start, end = parse_clock(cells[1]), parse_clock(cells[2])
        stated = re.fullmatch(r"(\d+) s", cells[duration_col[0]])
        if not stated or int(stated.group(1)) != end - start:
            raise PlanError(f"shot {cells[0]}: Duration '{cells[duration_col[0]]}' does not equal End minus Start")
        shots.append(Shot(int(cells[0]), start, end, cells[index["source"]], cells[index["subtitle"]], cells[index["voiceover"]]))

    if not shots:
        raise PlanError("no shot rows found in section 3")
    for position, shot in enumerate(shots):
        if shot.number != position + 1:
            raise PlanError(f"shot numbers are not 1, 2, 3, ...: found {shot.number} at position {position + 1}")
        if position and shot.start != shots[position - 1].end:
            raise PlanError(f"shot {shot.number} starts at {shot.start} s, previous shot ends at {shots[position - 1].end} s")
    return shots


def wrap_text(text):
    """Wrap into lines of at most MAX_LINE characters."""
    return textwrap.wrap(" ".join(text.split()), width=MAX_LINE, break_long_words=True, break_on_hyphens=False)


def split_into_cues(text, start_ms, end_ms):
    """Return [(start_ms, end_ms, [lines])] covering exactly [start_ms, end_ms]."""
    lines = wrap_text(text)
    if not lines:
        return []
    groups = [lines[i:i + MAX_LINES] for i in range(0, len(lines), MAX_LINES)]
    weights = [len(" ".join(g)) for g in groups]
    total = sum(weights)
    cues = []
    cursor, shared = start_ms, 0
    for position, (group, weight) in enumerate(zip(groups, weights)):
        shared += weight
        stop = end_ms if position == len(groups) - 1 else start_ms + round((end_ms - start_ms) * shared / total)
        cues.append((cursor, stop, group))
        cursor = stop
    return cues


def srt_time(ms):
    hours, rest = divmod(ms, 3600000)
    minutes, rest = divmod(rest, 60000)
    seconds, millis = divmod(rest, 1000)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d},{millis:03d}"


def build_srt(shots, column="subtitle", skip_kinds=()):
    """SRT text for the shots (Shot objects, start and end in seconds).

    Shots whose kind is in skip_kinds get no cue; the other cues keep their own time window.
    """
    if column not in COLUMNS:
        raise PlanError(f"unknown column '{column}'")
    blocks = []
    for shot in shots:
        if skip_kinds and shot.kind in skip_kinds:
            continue
        text = shot.subtitle if column == "subtitle" else shot.voiceover
        for start_ms, end_ms, lines in split_into_cues(text, shot.start * 1000, shot.end * 1000):
            blocks.append((start_ms, end_ms, lines))
    out = []
    for number, (start_ms, end_ms, lines) in enumerate(blocks, start=1):
        out.append(f"{number}\n{srt_time(start_ms)} --> {srt_time(end_ms)}\n" + "\n".join(lines) + "\n")
    return "\n".join(out)


def retimed(shots):
    """The same shots laid end to end from 0 s (used when only some shots are recorded)."""
    out, cursor = [], 0
    for shot in shots:
        out.append(replace(shot, start=cursor, end=cursor + shot.duration))
        cursor += shot.duration
    return out


def is_inside_repo(path):
    """True when path is inside the repository, except under a pytest temporary folder."""
    resolved = Path(path).expanduser().resolve()
    if resolved != REPO_ROOT and REPO_ROOT not in resolved.parents:
        return False
    return not any(part.startswith("pytest-") for part in resolved.parts)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Build an SRT subtitle file from the shot table of docs/video-plan.md")
    parser.add_argument("--plan", default=str(DEFAULT_PLAN), help="video plan (default: docs/video-plan.md)")
    parser.add_argument("--column", choices=sorted(COLUMNS), default="subtitle", help="text column (default: subtitle)")
    parser.add_argument("--skip-kind", action="append", choices=KINDS, default=[],
                        help="write no cue for shots of this kind, for example card (repeatable)")
    parser.add_argument("--output", required=True, help="SRT file to write, outside the repository")
    args = parser.parse_args(argv)

    output = Path(args.output).expanduser()
    if is_inside_repo(output):
        print(f"ERROR: output {output} is inside the repository; write recordings outside it", file=sys.stderr)
        return 2
    try:
        shots = parse_shots(Path(args.plan).read_text(encoding="utf-8"))
    except (OSError, PlanError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 2

    try:
        srt = build_srt(shots, args.column, tuple(args.skip_kind))
    except PlanError as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 2
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(srt, encoding="utf-8")
    skipped = f", no cue for kind {','.join(args.skip_kind)}" if args.skip_kind else ""
    print(f"Wrote {output}: {len(shots)} shots, column {args.column}{skipped}, ends at {shots[-1].end} s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
