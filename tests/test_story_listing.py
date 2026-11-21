"""Tests for the legacy listing extractor (coroner/ui/story.py listing and render_listing)."""
import json
import re
from pathlib import Path

import pytest

from coroner.ui.story import (
    StoryDataError,
    executed_lines_from_card,
    listing,
    load_catalog,
    load_run,
    render_listing,
    resolve_cobol_path,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
T1_DIR = REPO_ROOT / "samples" / "traps" / "T1-ebcdic-match-merge"
COBOL = T1_DIR / "MATCH-MERGE.cob"
ANCHOR_IDS = ["collation", "table", "sort", "match"]


def _anchors() -> dict:
    return {a["id"]: a for a in json.loads((T1_DIR / "trap.json").read_text())["listing"]}


def _scan(lines: list[str], anchor: dict) -> tuple[int, int]:
    """Independent range finder: first and last line number (1-based) of an anchor."""
    start = next(i for i, text in enumerate(lines) if re.search(anchor["start_pattern"], text))
    until = next(i for i in range(start + 1, len(lines)) if re.search(anchor["until_pattern"], lines[i]))
    end = until
    while not lines[end - 1].strip():
        end -= 1
    return start + 1, end


def _file_lines(path: Path) -> list[str]:
    return path.read_text(encoding="utf-8").splitlines()


def _ranges(blocks) -> dict:
    return {b.anchor_id: (b.first_line, b.last_line) for b in blocks}


def _trap_copy(tmp_path: Path, mutate=None) -> Path:
    trap = json.loads((T1_DIR / "trap.json").read_text())
    if mutate:
        mutate(trap)
    folder = tmp_path / "trap-copy"
    folder.mkdir(exist_ok=True)
    (folder / "trap.json").write_text(json.dumps(trap))
    return folder


def test_anchors_equal_an_independent_scan_of_the_real_file():
    lines = _file_lines(COBOL)
    anchors = _anchors()
    blocks = listing(T1_DIR, COBOL, ANCHOR_IDS)
    assert [b.anchor_id for b in blocks] == ANCHOR_IDS
    for block in blocks:
        assert block.error is None
        first, last = _scan(lines, anchors[block.anchor_id])
        assert (block.first_line, block.last_line) == (first, last)
        assert [line.number for line in block.lines] == list(range(first, last + 1))
        assert [line.text for line in block.lines] == lines[first - 1:last]
        assert block.file_name == "MATCH-MERGE.cob"
        assert not any(line.executed for line in block.lines)


def test_sentinel_line_numbers_of_the_spec():
    """Only a sentinel that the spec text (Req 12) is current; the scan above is the real check."""
    assert _ranges(listing(T1_DIR, COBOL, ANCHOR_IDS)) == {
        "collation": (10, 13),
        "table": (79, 87),
        "sort": (90, 95),
        "match": (201, 223),
    }


def test_three_inserted_lines_shift_every_number_by_three(tmp_path):
    lines = _file_lines(COBOL)
    shifted = tmp_path / "MATCH-MERGE.cob"
    shifted.write_text("\n".join(lines[:2] + ["      *> inserted 1", "      *> inserted 2", "      *> inserted 3"] + lines[2:]) + "\n")
    before = _ranges(listing(T1_DIR, COBOL, ANCHOR_IDS))
    after = _ranges(listing(T1_DIR, shifted, ANCHOR_IDS))
    for anchor_id in ANCHOR_IDS:
        assert after[anchor_id] == (before[anchor_id][0] + 3, before[anchor_id][1] + 3)
    blocks = listing(T1_DIR, shifted, ["match"])
    assert blocks[0].lines[0].number == before["match"][0] + 3
    # the displayed number changed in the rendered panel too
    assert f'<span class="listing-number">{before["match"][0] + 3}</span>' in render_listing(blocks, "engineer")


def test_crlf_file_gives_the_same_numbers_and_clean_text(tmp_path):
    crlf = tmp_path / "MATCH-MERGE.cob"
    crlf.write_bytes(COBOL.read_text().replace("\n", "\r\n").encode())
    assert _ranges(listing(T1_DIR, crlf, ANCHOR_IDS)) == _ranges(listing(T1_DIR, COBOL, ANCHOR_IDS))
    assert not any("\r" in line.text for b in listing(T1_DIR, crlf, ANCHOR_IDS) for line in b.lines)


def test_pattern_matching_nothing_gives_an_explicit_error_not_an_empty_panel(tmp_path):
    def break_patterns(trap):
        for anchor in trap["listing"]:
            if anchor["id"] == "table":
                anchor["start_pattern"] = "THIS TEXT IS NOT IN THE PROGRAM"
            if anchor["id"] == "sort":
                anchor["until_pattern"] = "NOR IS THIS ONE"
            if anchor["id"] == "match":
                anchor["start_pattern"] = "([unclosed"

    trap_dir = _trap_copy(tmp_path, break_patterns)
    blocks = {b.anchor_id: b for b in listing(trap_dir, COBOL, ANCHOR_IDS + ["nope"])}
    assert blocks["collation"].error is None and blocks["collation"].lines
    for broken in ("table", "sort", "match", "nope"):
        assert blocks[broken].error, f"{broken} should be an error"
        assert blocks[broken].lines == ()
    assert "THIS TEXT IS NOT IN THE PROGRAM" in blocks["table"].error
    assert "MATCH-MERGE.cob" in blocks["table"].error
    assert "invalid pattern" in blocks["match"].error
    assert "not defined" in blocks["nope"].error

    rendered = str(render_listing(list(blocks.values()), "business"))
    assert rendered.count('role="alert"') == 4
    assert rendered.count('role="region"') == 1  # only the anchor that resolved has a region


def test_anchor_without_patterns_is_an_error(tmp_path):
    def drop_until(trap):
        del trap["listing"][0]["until_pattern"]

    blocks = listing(_trap_copy(tmp_path, drop_until), COBOL, ["collation"])
    assert blocks[0].error and blocks[0].lines == ()


def test_missing_trap_json_is_the_typed_error(tmp_path):
    with pytest.raises(StoryDataError):
        listing(tmp_path, COBOL, ["match"])


def test_special_characters_in_a_source_line_are_escaped(tmp_path):
    lines = _file_lines(COBOL)
    start, _ = _scan(lines, _anchors()["sort"])
    hostile = '      *> a < b & c "quoted" <script>alert(1)</script>'
    mutated = tmp_path / "MATCH-MERGE.cob"
    mutated.write_text("\n".join(lines[:start] + [hostile] + lines[start:]) + "\n")
    blocks = listing(T1_DIR, mutated, ["sort"])
    assert hostile in [line.text for line in blocks[0].lines]
    page = str(render_listing(blocks, "engineer"))
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in page
    assert "a &lt; b &amp; c &quot;quoted&quot;" in page
    assert "<script>" not in page
    assert 'c "quoted"' not in page


def test_render_views_region_attributes_and_executed_word():
    blocks = listing(T1_DIR, COBOL, ["collation", "match"], executed_lines={201, 207, 999})
    business = str(render_listing(blocks, "business"))
    engineer = str(render_listing(blocks, "engineer"))
    assert business.startswith('<details class="story-listing"><summary>Show the COBOL lines</summary>')
    assert engineer.startswith('<details class="story-listing" open><summary>Show the COBOL lines</summary>')
    assert str(render_listing(blocks, "anything else")).startswith('<details class="story-listing">')
    for page in (business, engineer):
        assert page.count('role="region" tabindex="0"') == 2
        assert 'aria-label="MATCH-MERGE.cob lines 10 to 13"' in page
        assert 'aria-label="MATCH-MERGE.cob lines 201 to 223"' in page
        # the word "executed" marks exactly the lines given, and only those inside the block
        assert page.count(">executed<") == 2
    marked = [b for b in blocks if b.anchor_id == "match"][0]
    assert {line.number for line in marked.lines if line.executed} == {201, 207}


def test_empty_block_list_renders_nothing():
    assert str(render_listing([], "business")) == ""


def test_resolve_cobol_path_keeps_only_the_part_under_samples_traps():
    recorded = "/some/other/machine/dev/cobol-coroner/samples/traps/T1-ebcdic-match-merge/MATCH-MERGE.cob"
    assert resolve_cobol_path({"cobol_file": recorded}) == COBOL.resolve()
    assert resolve_cobol_path({"cobol_file": "samples/traps/T1-ebcdic-match-merge/MATCH-MERGE.cob"}) == COBOL.resolve()


@pytest.mark.parametrize("recorded", [
    None,
    "",
    "/etc/passwd",
    "samples/credit-fees/CREDIT-FEES.cob",
    "samples/traps/../../Makefile",
    "samples/traps/T1-ebcdic-match-merge/missing.cob",
    "samples/traps",
])
def test_resolve_cobol_path_refuses_other_files(recorded):
    with pytest.raises(StoryDataError):
        resolve_cobol_path({"cobol_file": recorded})


def test_resolve_cobol_path_refuses_a_missing_inputs_file():
    with pytest.raises(StoryDataError):
        resolve_cobol_path({})


def test_no_cobol_source_line_is_copied_into_templates_or_trap_json():
    """Req 12: the lines are read from the COBOL file, never copied into a template or trap.json."""
    copies = [p.read_text() for p in (REPO_ROOT / "coroner" / "ui" / "templates").glob("*.html")]
    copies += [p.read_text() for p in (REPO_ROOT / "samples" / "traps").glob("T*/trap.json")]
    haystack = "\n".join(copies)
    for text in _file_lines(COBOL):
        source_line = text.strip()
        if len(source_line) >= 12:
            assert source_line not in haystack, f"COBOL line copied: {source_line}"
    assert " ".join(["PROGRAM", "COLLATING", "SEQUENCE"]) not in haystack


def test_executed_lines_from_card_text_keeps_only_the_named_file():
    card = (
        "Given the following input rows:\n  CASE-ID=X\n"
        "When the COBOL reference and the Java port process this case\n"
        "Then something\n"
        "COBOL lines involved: a/b/FIRST.cob:5 MOVE 1 TO X; a/b/FIRST.cob:9 ADD 1 TO Y; a/b/COPYBOOK.cpy:7 05 FIELD"
    )
    assert executed_lines_from_card(card, "FIRST.cob") == {5, 9}
    assert executed_lines_from_card(card, "COPYBOOK.cpy") == {7}
    assert executed_lines_from_card(card, "OTHER.cob") == set()
    assert executed_lines_from_card(None, "FIRST.cob") == set()
    assert executed_lines_from_card("", "FIRST.cob") == set()


@pytest.mark.slow
def test_executed_lines_on_match_equal_the_card_lines_of_the_t1_faulty_run(story_runs):
    catalog = load_catalog(story_runs.base)
    run = load_run(story_runs.base, catalog["T1"].faulty_run_id)
    assert run.verdict["status"] == "ZOMBIE"

    # independent reading of card.txt: every number after "MATCH-MERGE.cob:" on the involved-lines row
    involved = run.card_text.split("COBOL lines involved:")[1]
    card_numbers = {int(n) for n in re.findall(r"MATCH-MERGE\.cob:(\d+)\b", involved)}
    assert card_numbers, "the T1 faulty run has no COBOL lines involved"

    cobol_path = resolve_cobol_path(run.inputs)
    assert cobol_path == COBOL.resolve()
    executed = executed_lines_from_card(run.card_text, cobol_path.name)
    assert executed == card_numbers

    match = listing(T1_DIR, cobol_path, ["match"], executed)[0]
    assert {line.number for line in match.lines if line.executed} == card_numbers
    rendered = str(render_listing([match], "engineer"))
    assert rendered.count(">executed<") == len(card_numbers)
