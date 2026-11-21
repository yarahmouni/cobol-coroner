"""Data layer of the guided story and the fool page.

Every value returned here is read at call time from a run file, runs/trap_catalog.json,
a trap.json or the COBOL file. Nothing measured is typed in this module, and an absent
optional file gives None, never a default number.
"""
import csv
import html
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional

from markupsafe import Markup

from coroner.cases import TRAPS_ROOT, load_cases_registry  # noqa: F401  (registry reader used by the story)
from coroner.ui.pages import RUN_ID_PATTERN, parse_card

MISSING_RUNS_MESSAGE = "Bundled demo runs missing. Run docker compose up to generate them."

# Evidence files of a run, in the fixed order of the "Exhibits" list: (label, file name).
EXHIBIT_FILES = (
    ("Certificate", "certificate.json"),
    ("Failure report", "failure_report.json"),
    ("Minimal case", "minimal_case_input.csv"),
    ("JUnit test", "ZombieRegressionTest.java"),
)


class StoryDataError(Exception):
    """A catalog, a run or a trap file the story needs is missing or unreadable."""


@dataclass(frozen=True)
class CatalogEntry:
    """One trap of runs/trap_catalog.json. T6 has no run ids."""
    trap_id: str
    faulty_run_id: Optional[str]
    correct_run_id: Optional[str]
    entry: dict


@dataclass(frozen=True)
class Run:
    """The parsed files of one run folder. A file the run does not have is None."""
    run_id: str
    run_dir: Path
    verdict: Optional[dict]
    inputs: Optional[dict]
    certificate: Optional[dict]
    timing: Optional[dict]
    reconciliation: Optional[dict]
    failure_report: Optional[dict]
    card_text: Optional[str]


@dataclass(frozen=True)
class FirstDivergentCase:
    """The first divergent case in the order of comparison_results.json (not the minimal case)."""
    case_id: str
    position: int
    cases_total: Optional[int]


@dataclass(frozen=True)
class Exhibit:
    label: str
    file_name: str


@dataclass(frozen=True)
class ListingLine:
    number: int
    text: str
    executed: bool


@dataclass(frozen=True)
class ListingBlock:
    """The COBOL lines of one anchor, or an explicit error when the anchor cannot be resolved."""
    anchor_id: str
    label: str
    file_name: str
    first_line: Optional[int]
    last_line: Optional[int]
    lines: tuple
    error: Optional[str]


def normalize_view(value: Optional[str]) -> str:
    """"engineer" stays engineer; anything else, including None, is business."""
    return "engineer" if value == "engineer" else "business"


def _read_json(path: Path) -> Optional[dict]:
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        raise StoryDataError(f"{path.name} in {path.parent.name} is not readable: {e}") from e


def load_catalog(base_dir) -> dict[str, CatalogEntry]:
    """Read runs/trap_catalog.json. Raises StoryDataError when it is missing or unreadable."""
    catalog_file = Path(base_dir) / "runs" / "trap_catalog.json"
    if not catalog_file.is_file():
        raise StoryDataError(MISSING_RUNS_MESSAGE)
    catalog = _read_json(catalog_file)
    traps = catalog.get("traps") if isinstance(catalog, dict) else None
    if not isinstance(traps, list):
        raise StoryDataError("trap_catalog.json has no traps list")
    entries = {}
    for entry in traps:
        trap_id = entry.get("id") if isinstance(entry, dict) else None
        if not trap_id:
            raise StoryDataError("trap_catalog.json has an entry without an id")
        run_ids = []
        for key in ("faulty_run_id", "correct_run_id"):
            run_id = entry.get(key)
            if run_id is not None and not RUN_ID_PATTERN.match(str(run_id)):
                raise StoryDataError(f"trap_catalog.json: {trap_id} has an invalid {key}")
            run_ids.append(run_id)
        entries[trap_id] = CatalogEntry(trap_id, run_ids[0], run_ids[1], entry)
    return entries


def load_run(base_dir, run_id: str) -> Run:
    """Read the files of runs/<run_id>. Raises StoryDataError when the run folder is missing."""
    if not isinstance(run_id, str) or not RUN_ID_PATTERN.match(run_id):
        raise StoryDataError("Invalid run id")
    run_dir = Path(base_dir) / "runs" / run_id
    if not run_dir.is_dir():
        raise StoryDataError(MISSING_RUNS_MESSAGE)
    card_file = run_dir / "card.txt"
    return Run(
        run_id=run_id,
        run_dir=run_dir,
        verdict=_read_json(run_dir / "verdict.json"),
        inputs=_read_json(run_dir / "inputs.json"),
        certificate=_read_json(run_dir / "certificate.json"),
        timing=_read_json(run_dir / "timing.json"),
        reconciliation=_read_json(run_dir / "branch_reconciliation.json"),
        failure_report=_read_json(run_dir / "failure_report.json"),
        card_text=card_file.read_text(encoding="utf-8") if card_file.is_file() else None,
    )


def first_divergent_case(run: Run) -> Optional[FirstDivergentCase]:
    """First case of comparison_results.json with divergent true, its 1-based position and cases_total."""
    comparison = _read_json(run.run_dir / "comparison_results.json")
    if comparison is None:
        return None
    for position, case in enumerate(comparison.get("cases", []), start=1):
        if case.get("divergent"):
            cases_total = run.verdict.get("cases_total") if run.verdict else None
            return FirstDivergentCase(case["case_id"], position, cases_total)
    return None


def exhibits(run: Run) -> list[Exhibit]:
    """The evidence files that exist in the run folder, in the fixed order of EXHIBIT_FILES."""
    return [
        Exhibit(label, file_name)
        for label, file_name in EXHIBIT_FILES
        if (run.run_dir / file_name).is_file()
    ]


def transaction_count(run: Run) -> Optional[int]:
    """Number of data rows of generated_cases.csv (a case is a batch of one or more rows)."""
    cases_file = run.run_dir / "generated_cases.csv"
    if not cases_file.is_file():
        return None
    with cases_file.open(newline="", encoding="utf-8") as f:
        return max(sum(1 for _ in csv.reader(f)) - 1, 0)


def t2_column_counts(run: Run) -> Optional[dict[str, int]]:
    """Divergent values per output column (FEE1, FEE2 for T2), from comparison_results.json."""
    comparison = _read_json(run.run_dir / "comparison_results.json")
    if comparison is None:
        return None
    counts: dict[str, int] = {}
    for case in comparison.get("cases", []):
        for divergence in case.get("divergent_fields", []):
            name = divergence.get("field_name")
            if name is not None:
                counts[name] = counts.get(name, 0) + 1
    return dict(sorted(counts.items()))


def executed_lines_from_card(card_text: Optional[str], cobol_file_name: str) -> set[int]:
    """Line numbers of the COBOL file named in the "COBOL lines involved" of card.txt."""
    card = parse_card(card_text) if card_text else None
    executed = set()
    for entry in (card or {}).get("cobol_lines", []):
        match = re.match(r"^([^:]+):(\d+)\b", entry)
        if match and match.group(1) == cobol_file_name:
            executed.add(int(match.group(2)))
    return executed


def resolve_cobol_path(inputs: dict, traps_root: Optional[Path] = None) -> Path:
    """
    COBOL file of a run, resolved under the repository's samples/traps folder.

    inputs.json records the path as it was on the machine that ran the audit; only the part
    after samples/traps is kept, so no path from the request or from another machine is read.
    """
    root = Path(traps_root) if traps_root else TRAPS_ROOT
    recorded = (inputs or {}).get("cobol_file")
    if not recorded:
        raise StoryDataError("inputs.json has no cobol_file")
    parts = Path(recorded).parts
    anchor = [i for i in range(len(parts) - 1) if parts[i] == "samples" and parts[i + 1] == "traps"]
    if not anchor:
        raise StoryDataError("The COBOL file of this run is not under samples/traps")
    relative = parts[anchor[-1] + 2:]
    if not relative or ".." in relative:
        raise StoryDataError("The COBOL file path of this run is not valid")
    resolved = root.joinpath(*relative).resolve()
    if root.resolve() not in resolved.parents or not resolved.is_file():
        raise StoryDataError("The COBOL file of this run is not in samples/traps")
    return resolved


def _source_lines(cobol_path: Path) -> list[str]:
    """Lines of the file numbered as an editor numbers them (line 1 is the first line)."""
    text = cobol_path.read_text(encoding="utf-8", errors="replace")
    lines = [line.rstrip("\r") for line in text.split("\n")]
    if lines and lines[-1] == "":
        lines.pop()
    return lines


def _find_line(lines: list[str], pattern: str, first_index: int) -> Optional[int]:
    regex = re.compile(pattern)
    for index in range(first_index, len(lines)):
        if regex.search(lines[index]):
            return index
    return None


def _resolve_anchor(anchor: dict, lines: list[str], file_name: str, executed: frozenset) -> ListingBlock:
    anchor_id = anchor.get("id", "")
    label = anchor.get("label", anchor_id)

    def error(message: str) -> ListingBlock:
        return ListingBlock(anchor_id, label, file_name, None, None, (), message)

    start_pattern = anchor.get("start_pattern")
    until_pattern = anchor.get("until_pattern")
    if not start_pattern or not until_pattern:
        return error(f'Listing anchor "{anchor_id}" needs a start_pattern and an until_pattern')
    try:
        start = _find_line(lines, start_pattern, 0)
        if start is None:
            return error(f'Listing anchor "{anchor_id}": no line of {file_name} matches {start_pattern}')
        until = _find_line(lines, until_pattern, start + 1)
    except re.error as e:
        return error(f'Listing anchor "{anchor_id}": invalid pattern ({e})')
    if until is None:
        return error(f'Listing anchor "{anchor_id}": no line of {file_name} after line {start + 1} matches {until_pattern}')
    last = until - 1
    while last > start and not lines[last].strip():
        last -= 1
    block_lines = tuple(
        ListingLine(index + 1, lines[index], (index + 1) in executed)
        for index in range(start, last + 1)
    )
    return ListingBlock(anchor_id, label, file_name, start + 1, last + 1, block_lines, None)


def listing(
    trap_dir: Path,
    cobol_path: Path,
    anchor_ids: Iterable[str],
    executed_lines: Iterable[int] = (),
) -> list[ListingBlock]:
    """
    The COBOL lines of each anchor named in anchor_ids, found by the patterns of trap.json.

    Line numbers are found at call time, so a change in the COBOL file moves the numbers.
    An anchor whose pattern matches nothing gives a block with an error and no lines.
    """
    trap = _read_json(Path(trap_dir) / "trap.json")
    if trap is None:
        raise StoryDataError(f"{Path(trap_dir).name} has no trap.json")
    anchors = {a.get("id"): a for a in trap.get("listing", [])}
    cobol_path = Path(cobol_path)
    lines = _source_lines(cobol_path)
    executed = frozenset(executed_lines)
    blocks = []
    for anchor_id in anchor_ids:
        anchor = anchors.get(anchor_id)
        if anchor is None:
            blocks.append(ListingBlock(
                anchor_id, anchor_id, cobol_path.name, None, None, (),
                f'Listing anchor "{anchor_id}" is not defined in trap.json',
            ))
        else:
            blocks.append(_resolve_anchor(anchor, lines, cobol_path.name, executed))
    return blocks


def render_listing(blocks: list[ListingBlock], view: Optional[str]) -> Markup:
    """
    HTML of the listing panel: a details element, closed in the Business view and open in
    the Engineer view, with one scrollable labelled region per anchor.
    """
    if not blocks:
        return Markup("")
    esc = html.escape
    open_attr = " open" if normalize_view(view) == "engineer" else ""
    parts = [f'<details class="story-listing"{open_attr}><summary>Show the COBOL lines</summary>']
    for block in blocks:
        parts.append(f'<h4 class="story-listing-title">{esc(block.label)}</h4>')
        if block.error:
            parts.append(f'<p class="story-listing-error" role="alert">{esc(block.error)}</p>')
            continue
        aria_label = f"{block.file_name} lines {block.first_line} to {block.last_line}"
        parts.append(
            f'<div class="story-listing-region" role="region" tabindex="0" '
            f'aria-label="{esc(aria_label)}" style="overflow-x: auto;"><pre>'
        )
        for line in block.lines:
            marker = ' <span class="listing-executed">executed</span>' if line.executed else ""
            parts.append(
                f'<span class="listing-line"><span class="listing-number">{line.number}</span> '
                f'{esc(line.text)}{marker}</span>\n'
            )
        parts.append("</pre></div>")
    parts.append("</details>")
    return Markup("".join(parts))
