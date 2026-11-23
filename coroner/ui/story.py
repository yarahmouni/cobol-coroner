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
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Iterable, Optional
from urllib.parse import urlencode

from markupsafe import Markup

from coroner.cases import TRAPS_ROOT, case_label, load_cases_registry  # noqa: F401  (registry reader used by the story)
from coroner.ui.pages import RUN_ID_PATTERN, parse_card
from coroner.ui.sentences import generate_zombie_sentence

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
    """One trap of runs/trap_catalog.json. An entry of an older catalog may have no run ids."""
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


# ---------------------------------------------------------------- story shell and steps 1 to 3

STEP_COUNT = 8
STORY_TRAP_ID = "T1"
POSITIONING_SENTENCE = (
    "Coroner does not translate COBOL. AWS Transform, Kiro, an LLM or a human migrates COBOL "
    "to Java. Coroner independently verifies the result."
)
STEP_TITLES = {
    1: "Bank process",
    2: "COBOL result",
    3: "Java migration",
    4: "Coroner compares",
    5: "Where and why",
    6: "Apply the fix",
    7: "ALIVE certificate",
    8: "Try to cheat",
}


def step_url(step: int, view: Optional[str]) -> str:
    """URL of a step. The view is always written, so every link carries it."""
    return f"/story/step/{step}?view={normalize_view(view)}"


def parse_step(value) -> Optional[int]:
    """The step number of a URL segment when it is a whole number from 1 to STEP_COUNT, else None."""
    if isinstance(value, str) and re.fullmatch(r"[0-9]{1,3}", value):
        number = int(value)
        if 1 <= number <= STEP_COUNT:
            return number
    return None


def trap_folder(trap_id: str) -> Path:
    """The samples/traps folder of a trap (T1 gives T1-ebcdic-match-merge)."""
    folders = sorted(p for p in TRAPS_ROOT.glob(f"{trap_id}-*") if p.is_dir())
    if len(folders) != 1:
        raise StoryDataError(f"There is no single trap folder for {trap_id}")
    return folders[0]


def load_trap(trap_id: str) -> dict:
    """trap.json of a trap."""
    trap = _read_json(trap_folder(trap_id) / "trap.json")
    if trap is None:
        raise StoryDataError(f"{trap_id} has no trap.json")
    return trap


def trap_cobol_path(trap_id: str) -> Path:
    """The COBOL program of a trap folder. Used where no run is needed (step 1)."""
    programs = sorted(trap_folder(trap_id).glob("*.cob"))
    if len(programs) != 1:
        raise StoryDataError(f"There is no single COBOL program in the folder of {trap_id}")
    return programs[0]


def _need(value):
    """A file or value the page cannot be shown without: absent means the bundled runs are missing."""
    if value is None:
        raise StoryDataError(MISSING_RUNS_MESSAGE)
    return value


def story_run(base_dir, correct: bool = False) -> Run:
    """The bundled run of the story trap (faulty by default), found through runs/trap_catalog.json."""
    entry = load_catalog(base_dir).get(STORY_TRAP_ID)
    run_id = _need(entry).correct_run_id if correct else _need(entry).faulty_run_id
    return load_run(base_dir, _need(run_id))


def same_amount(first: str, second: str) -> bool:
    """True when two amounts written as text are the same number (compared as decimals)."""
    try:
        return Decimal(first) == Decimal(second)
    except InvalidOperation:
        return first == second


def audit_result(base_dir, run_id: str) -> dict:
    """The verdict and the counts of a run, read from its verdict.json (a missing key is None)."""
    verdict = _need(load_run(base_dir, run_id).verdict)
    return {
        "run_id": run_id,
        "status": verdict.get("status"),
        "cases_divergent": verdict.get("cases_divergent"),
        "cases_total": verdict.get("cases_total"),
    }


def _step_1(base_dir, view: str, bounds=None) -> dict:
    folder = trap_folder(STORY_TRAP_ID)
    cobol = trap_cobol_path(STORY_TRAP_ID)
    blocks = listing(folder, cobol, ["table"])
    schema = _need(_read_json(folder / "schema.json"))
    table = blocks[0]
    return {
        "content": "story_step_1.html",
        "listing_html": render_listing(blocks, view),
        "engineer": {
            "schema_file": "schema.json",
            "input_columns": [column["name"] for column in schema["input"]["columns"]],
            "cobol_file": cobol.name,
            "table_first_line": table.first_line,
            "table_last_line": table.last_line,
        },
    }


def _step_2(base_dir, view: str, bounds=None) -> dict:
    run = story_run(base_dir)
    verdict = _need(run.verdict)
    reconciliation = _need(run.reconciliation)
    inputs = _need(run.inputs)
    trap = load_trap(STORY_TRAP_ID)
    cobol = resolve_cobol_path(inputs)
    rows = sorted(
        ({"branch": b["branch"], "amount": b["cobol_subtotal"]} for b in reconciliation["branches"]),
        key=lambda row: row["branch"],
    )
    blocks = listing(trap_folder(STORY_TRAP_ID), cobol, ["collation", "sort"])
    return {
        "content": "story_step_2.html",
        "transactions": _need(transaction_count(run)),
        "cases": verdict["cases_total"],
        "rows": rows,
        "suspense": {
            "label": trap["suspense_label"],
            "code": trap["suspense_code"],
            "amount": reconciliation["suspense"]["cobol"],
        },
        "grand_total": reconciliation["grand_total"]["cobol"],
        "listing_html": render_listing(blocks, view),
        "engineer": {"run_id": run.run_id, "seed": inputs["random_seed"], "cobol_file": cobol.name},
    }


def _step_3(base_dir, view: str, bounds=None) -> dict:
    run = story_run(base_dir)
    totals = _need(run.reconciliation)["grand_total"]
    certificate = run.certificate
    java_file = Path(certificate["java_file"]).name if certificate and certificate.get("java_file") else None
    return {
        "content": "story_step_3.html",
        "cobol_total": totals["cobol"],
        "java_total": totals["java"],
        "totals_match": same_amount(totals["cobol"], totals["java"]),
        "engineer": {"run_id": run.run_id, "java_file": java_file},
    }


# ---------------------------------------------------------------- steps 4 to 8

# Default of the "Number of test batches" field of Run it yourself. It is a form default, not a
# measurement; the bounds of both fields come from the model of POST /api/run (run_form_bounds).
RUN_FORM_DEFAULT_CASES = 200

BADGE_LINES = {"ZOMBIE": "MIGRATION REJECTED", "ALIVE": "MIGRATION CERTIFIED"}
TAMPER_STATUS_CHOICES = ("ALIVE", "ZOMBIE")
# Keys of a real certificate.json that the Tamper endpoint edits (all four exist in every certificate).
TAMPER_FIELDS = ("status", "cases_total", "cases_divergent", "random_seed")
CERTIFICATE_FILE = "certificate.json"


def run_form_bounds(model) -> dict:
    """Minimum and maximum of seed and cases, read from the pydantic model of POST /api/run."""
    bounds = {}
    for name in ("seed", "cases"):
        low = high = None
        for item in model.model_fields[name].metadata:
            low = getattr(item, "ge", low)
            high = getattr(item, "le", high)
        bounds[name] = {"min": low, "max": high}
    return bounds


def _run_form(port: str, inputs: dict, bounds: Optional[dict]) -> dict:
    """Values of the Run it yourself form: the seed of the bundled run, a default case count."""
    cases = RUN_FORM_DEFAULT_CASES
    if bounds:
        cases = min(max(cases, bounds["cases"]["min"]), bounds["cases"]["max"])
    return {"port": port, "seed": inputs["random_seed"], "cases": cases, "bounds": bounds}


def format_duration(timing: Optional[dict]) -> Optional[str]:
    """The duration of timing.json written as the run page writes it, or None when not recorded."""
    seconds = (timing or {}).get("duration_seconds")
    return f"{seconds} s" if seconds not in (None, "") else None


def _yes_no(value) -> Optional[str]:
    return None if value is None else ("yes" if value else "no")


def _abs_amount(value: str) -> str:
    """An amount written as text, without its sign, with two decimals (as the run page shows the suspense line)."""
    return f"{abs(Decimal(value)):.2f}"


def _money(value) -> Optional[str]:
    """An amount of verdict.json written with two decimals, as the run page writes it; None stays None."""
    return None if value is None else f"{Decimal(str(value)):.2f}"


def audit_block(run: Run) -> dict:
    """The verdict of a run and the figures of steps 4 and 7, each read from verdict.json (absent is None)."""
    verdict = _need(run.verdict)
    status = verdict.get("status")
    return {
        "run_id": run.run_id,
        "status": status,
        "kind": {"ALIVE": "alive", "ZOMBIE": "zombie"}.get(status, "error"),
        "badge_line": BADGE_LINES.get(status),
        "sentence": generate_zombie_sentence(STORY_TRAP_ID, run.run_dir) if status == "ZOMBIE" else None,
        "cases_total": verdict.get("cases_total"),
        "cases_divergent": verdict.get("cases_divergent"),
        "exposure_sum": _money(verdict.get("exposure_sum")),
        "exposure_max": _money(verdict.get("exposure_max")),
        "affected_branches": verdict.get("affected_branches"),
        "grand_total_balances": _yes_no(verdict.get("grand_total_matches")),
        "suspense_difference": _money(verdict.get("suspense_difference")),
        "return_codes": verdict.get("run_return_codes"),
    }


def divergence_summary(entry: dict) -> dict:
    """Kind, output key and field names of one entry of failure_report.json divergent_fields."""
    if entry.get("field_name") is not None:
        names = [entry["field_name"]]
    else:
        names = list(dict.fromkeys([*entry.get("cobol_values", {}), *entry.get("java_values", {})]))
    key = entry.get("output_key") or {}
    return {
        "kind": entry.get("kind"),
        "output_key": ", ".join(f"{name}={str(value).strip()}" for name, value in key.items()),
        "fields": ", ".join(names),
    }


def card_example(card_text: Optional[str]) -> Optional[str]:
    """The Given and Then lines of card.txt as one text block, or None when the run has no card."""
    card = parse_card(card_text) if card_text else None
    if not card:
        return None
    return "\n".join(part for part in (card["given"], card["then"]) if part)


def _certificate_exhibits(run: Run) -> list[Exhibit]:
    return [e for e in exhibits(run) if e.file_name == CERTIFICATE_FILE]


def _certificate_prefix(run: Run) -> Optional[str]:
    """First 12 characters of certificate_sha256 (Engineer view)."""
    digest = (run.certificate or {}).get("certificate_sha256")
    return digest[:12] if isinstance(digest, str) else None


def _step_4(base_dir, view: str, bounds=None) -> dict:
    run = story_run(base_dir)
    inputs = _need(run.inputs)
    block = audit_block(run)
    return {
        "content": "story_step_4.html",
        "audit": block,
        "run_form": _run_form("faulty", inputs, bounds),
        "engineer": {
            "run_id": run.run_id,
            "seed": inputs["random_seed"],
            "duration": format_duration(run.timing),
            "exposure_max": block["exposure_max"],
            "suspense_difference": block["suspense_difference"],
            "return_codes": block["return_codes"],
        },
    }


def _step_5(base_dir, view: str, bounds=None) -> dict:
    run = story_run(base_dir)
    reconciliation = _need(run.reconciliation)
    inputs = _need(run.inputs)
    trap = load_trap(STORY_TRAP_ID)
    cobol = resolve_cobol_path(inputs)
    branches = reconciliation["branches"]
    mismatches = sorted(
        (b for b in branches if b["status"] == "MISMATCH"),
        key=lambda b: Decimal(b["absolute_difference"]),
        reverse=True,
    )
    executed = executed_lines_from_card(run.card_text, cobol.name)
    blocks = {b.anchor_id: b for b in listing(trap_folder(STORY_TRAP_ID), cobol, ["collation", "match"], executed)}
    divergent_fields = (run.failure_report or {}).get("divergent_fields")
    return {
        "content": "story_step_5.html",
        "run_id": run.run_id,
        "mismatches": mismatches,
        "match_count": len(branches) - len(mismatches),
        "suspense_difference": _abs_amount(reconciliation["suspense"]["difference"]),
        "business_cause": trap["business_cause"],
        "first_case": first_divergent_case(run),
        "example": card_example(run.card_text),
        "exhibit_list": exhibits(run),
        "listing_html": render_listing([blocks["match"]], view),
        "engineer": {
            "divergences": [divergence_summary(e) for e in divergent_fields[:2]] if divergent_fields else None,
            "technical_cause": trap["technical_cause"],
            "cobol_rule": trap["cobol_rule"],
            "cobol_file": cobol.name,
            "anchors": [blocks["collation"], blocks["match"]],
        },
    }


def _step_6(base_dir, view: str, bounds=None) -> dict:
    trap = load_trap(STORY_TRAP_ID)
    cobol = trap_cobol_path(STORY_TRAP_ID)
    blocks = listing(trap_folder(STORY_TRAP_ID), cobol, ["match"])
    return {
        "content": "story_step_6.html",
        "fix": trap["fix_sentence"] if view == "engineer" else trap["business_fix"],
        "listing_html": render_listing(blocks, view),
    }


def _step_7(base_dir, view: str, bounds=None) -> dict:
    run = story_run(base_dir, correct=True)
    inputs = _need(run.inputs)
    return {
        "content": "story_step_7.html",
        "audit": audit_block(run),
        "run_form": _run_form("correct", inputs, bounds),
        "exhibit_list": _certificate_exhibits(run),
        "engineer": {
            "run_id": run.run_id,
            "seed": inputs["random_seed"],
            "certificate_prefix": _certificate_prefix(run),
        },
    }


def _step_8(base_dir, view: str, bounds=None) -> dict:
    run = story_run(base_dir)
    certificate = _need(run.certificate)
    fields = {name: certificate[name] for name in TAMPER_FIELDS}
    choices = list(TAMPER_STATUS_CHOICES)
    if fields["status"] not in choices:
        choices.append(fields["status"])
    return {
        "content": "story_step_8.html",
        "tamper": {"run_id": run.run_id, "fields": fields, "status_choices": choices},
        "engineer": {"run_id": run.run_id, "certificate_prefix": _certificate_prefix(run)},
    }


_STEP_BUILDERS = {1: _step_1, 2: _step_2, 3: _step_3, 4: _step_4, 5: _step_5, 6: _step_6, 7: _step_7, 8: _step_8}


def build_step(base_dir, step: int, view: Optional[str], run_bounds: Optional[dict] = None) -> dict:
    """
    Everything the story page template needs for one step.

    run_bounds are the limits of the Run it yourself fields (see run_form_bounds). A missing or
    unreadable file gives `error` (the typed message) and no step content, so no default number
    is ever shown.
    """
    view = normalize_view(view)
    context = {
        "step": step,
        "step_count": STEP_COUNT,
        "title": STEP_TITLES[step],
        "view": view,
        "error": None,
        "content": None,
        "noscript_notes": [],
        "back_url": step_url(step - 1, view) if step > 1 else None,
        "next_url": step_url(step + 1, view) if step < STEP_COUNT else "/",
        "next_label": "Next" if step < STEP_COUNT else "Finish",
        "business_url": step_url(step, "business"),
        "engineer_url": step_url(step, "engineer"),
        "positioning": POSITIONING_SENTENCE,
        "case_label": case_label(STORY_TRAP_ID),
    }
    builder = _STEP_BUILDERS.get(step)
    if builder is not None:
        try:
            context.update(builder(base_dir, view, run_bounds))
        except StoryDataError as e:
            context["error"] = str(e)
        except (KeyError, TypeError, InvalidOperation) as e:
            context["error"] = f"A bundled run file does not have the expected content ({e})."
    return context


# ---------------------------------------------------------------- "Can you fool Coroner?"

FOOL_PATH = "/fool"
CREDIT_FEES_COBOL_TAIL = ("samples", "credit-fees", "CREDIT-FEES.cob")
CREDIT_FEES_CORRECT_JAVA_TAIL = ("samples", "credit-fees", "java", "CreditFees.java")
# Where scripts/init_demo_runs.sh and the engine worker put the HALF_EVEN variant of the credit-fees port.
HALF_EVEN_VARIANT_JAVA_TAIL = ("build", "variants", "CreditFees.java")
T4_INPUT_COLUMN = "ZONED-VALUE"
FOOL_NOT_RECORDED = "not recorded"
FOOL_MISSING = "Bundled run missing"


@dataclass(frozen=True)
class FoolToggle:
    """
    One defect of the fool page: the form parameter, what names it and its source of runs.

    A catalog toggle is named after its trap's case (cases.json). The credit-fees toggle has no trap:
    it is named by its run (`label`), never by a case, because it is not the T2 port (Q7).
    """
    param: str
    trap_id: Optional[str]
    caption: str
    # "catalog": the faulty and correct runs of the trap in runs/trap_catalog.json.
    # "credit-fees": the HALF_EVEN variant run and the correct run of the credit-fees sample (R-134).
    source: str
    sample_note: Optional[str] = None
    label: Optional[str] = None


# The form parameter "case2" is kept so that existing links work; it is never shown as text.
HALF_EVEN_LABEL = "HALF_EVEN rounding, credit-fees sample (HALF_EVEN variant run)"

FOOL_TOGGLES = (
    FoolToggle("case1", "T1", "Branch codes are compared in ASCII order instead of EBCDIC order.", "catalog"),
    FoolToggle(
        "case2", None,
        "Fees are rounded half to even (HALF_EVEN) instead of half away from zero (HALF_UP).",
        "credit-fees",
        "Shown on the credit-fees sample program: one real rounding defect.",
        HALF_EVEN_LABEL,
    ),
    FoolToggle("case4", "T4", "The zero overpunch characters { and } are not decoded.", "catalog"),
)
FOOL_PARAMS = tuple(toggle.param for toggle in FOOL_TOGGLES)


def fool_url(selected: Iterable[str], view: Optional[str]) -> str:
    """URL of the fool page for a set of switched-on toggles. The view is always written."""
    chosen = set(selected)
    pairs = [(param, "on") for param in FOOL_PARAMS if param in chosen]
    pairs.append(("view", normalize_view(view)))
    return f"{FOOL_PATH}?{urlencode(pairs)}"


def _has_tail(path, tail: tuple) -> bool:
    parts = Path(path or "").parts
    return len(parts) >= len(tail) and tuple(parts[-len(tail):]) == tail


def _run_dirs(base_dir) -> list[Path]:
    runs = Path(base_dir) / "runs"
    if not runs.is_dir():
        return []
    return sorted(p for p in runs.iterdir() if p.is_dir() and RUN_ID_PATTERN.match(p.name))


def reference_parameters(base_dir, catalog: dict[str, CatalogEntry]) -> tuple[Optional[int], Optional[int]]:
    """
    Case count and seed of the bundled runs, read from the inputs.json of the first catalog run.

    The credit-fees runs are looked up with these two values, so a visitor's own audit of the
    credit-fees sample with another seed or case count is never mistaken for the bundled run.
    """
    for trap_id in sorted(catalog):
        run_id = catalog[trap_id].faulty_run_id
        if not run_id:
            continue
        run_dir = Path(base_dir) / "runs" / run_id
        inputs = _read_json(run_dir / "inputs.json") if run_dir.is_dir() else None
        if isinstance(inputs, dict):
            return inputs.get("case_count"), inputs.get("random_seed")
    return None, None


def credit_fees_run_ids(base_dir, case_count: Optional[int], seed: Optional[int]) -> tuple[Optional[str], Optional[str]]:
    """
    (HALF_EVEN variant run, correct run) of the credit-fees sample, found from the inputs.json files.

    A run is the variant run when its inputs.json names the credit-fees COBOL program and a Java file
    ending in build/variants/CreditFees.java (the file scripts/init_demo_runs.sh audits); it is the
    correct run when the Java file is samples/credit-fees/java/CreditFees.java. Both must have the
    given case count and seed. No run id is typed anywhere.
    """
    if case_count is None or seed is None:
        return None, None
    faulty = correct = None
    for run_dir in _run_dirs(base_dir):
        try:
            inputs = _read_json(run_dir / "inputs.json")
        except StoryDataError:
            continue  # an unreadable run of another sample is not a problem of this page
        if not isinstance(inputs, dict) or not _has_tail(inputs.get("cobol_file"), CREDIT_FEES_COBOL_TAIL):
            continue
        if inputs.get("case_count") != case_count or inputs.get("random_seed") != seed:
            continue
        if _has_tail(inputs.get("java_file"), HALF_EVEN_VARIANT_JAVA_TAIL):
            faulty = run_dir.name
        elif _has_tail(inputs.get("java_file"), CREDIT_FEES_CORRECT_JAVA_TAIL):
            correct = run_dir.name
    return faulty, correct


def _found_run(base_dir, run_id: Optional[str]) -> Optional[Run]:
    """The run when its folder and its verdict.json exist, else None (a deleted run is a missing run)."""
    if not run_id or not (Path(base_dir) / "runs" / run_id).is_dir():
        return None
    run = load_run(base_dir, run_id)
    return run if run.verdict else None


def overpunch_counts(run: Run) -> Optional[dict[str, int]]:
    """
    Divergent cases of a T4 run, and how many of their inputs end in "}" and in "{".

    Read from comparison_results.json and generated_cases.csv. Only the count of "}" is
    claimed by the page when the count of "{" is shown next to it.
    """
    comparison = _read_json(run.run_dir / "comparison_results.json")
    cases_file = run.run_dir / "generated_cases.csv"
    if comparison is None or not cases_file.is_file():
        return None
    with cases_file.open(newline="", encoding="utf-8") as f:
        values = {row["CASE-ID"]: row[T4_INPUT_COLUMN] for row in csv.DictReader(f)}
    counts = {"divergent": 0, "closing": 0, "opening": 0}
    for case in comparison.get("cases", []):
        if not case.get("divergent"):
            continue
        counts["divergent"] += 1
        value = values[case["case_id"]]
        counts["closing"] += value.endswith("}")
        counts["opening"] += value.endswith("{")
    return counts


def _short_line_ref(reference: str) -> str:
    """"dir/FILE.cob:201 text" written as "FILE.cob:201 text" (the card already does this)."""
    path_part, separator, rest = reference.partition(":")
    return f"{Path(path_part).name}{separator}{rest}" if separator else reference


def _fool_sentence(toggle: FoolToggle, run: Run) -> Optional[str]:
    """
    The sentence of a run, the one its run page shows: the trap sentence of a catalog ZOMBIE run,
    and for every other run the sub_label of verdict.json (the run page falls back to it too).
    """
    verdict = run.verdict
    if verdict.get("status") == "ZOMBIE" and toggle.source == "catalog":
        try:
            return generate_zombie_sentence(toggle.trap_id, run.run_dir)
        except (KeyError, ValueError, OSError, TypeError, InvalidOperation):
            pass
    return verdict.get("sub_label")


def _fool_engineer(toggle: FoolToggle, entry: Optional[CatalogEntry], run: Run, faulty_shown: bool) -> dict:
    """Engineer details of one toggle row, each read from the files of the shown run or the catalog entry."""
    inputs = run.inputs or {}
    details = {
        "run_id": run.run_id,
        "cases_divergent": run.verdict.get("cases_divergent"),
        "cases_total": run.verdict.get("cases_total"),
        "seed": inputs.get("random_seed"),
        "cobol_lines": None,
        "column_counts": None,
        "overpunch": None,
    }
    if not faulty_shown:
        return details
    if toggle.source == "catalog":
        lines = entry.entry.get("cobol_lines") if entry else None
        details["cobol_lines"] = [_short_line_ref(line) for line in lines] if lines else None
    else:
        card = parse_card(run.card_text) if run.card_text else None
        details["cobol_lines"] = (card or {}).get("cobol_lines") or None
        details["column_counts"] = t2_column_counts(run)
    if toggle.trap_id == "T4":
        details["overpunch"] = overpunch_counts(run)
    return details


def _unavailable_row(toggle: FoolToggle, registry: dict) -> dict:
    """A toggle row without any run: disabled, with the missing message and no number."""
    return {
        "param": toggle.param,
        "input_id": f"toggle-{toggle.param}",
        "case_label": toggle.label or case_label(toggle.trap_id, registry) or FOOL_NOT_RECORDED,
        "caption": toggle.caption,
        "sample_note": toggle.sample_note,
        "available": False,
        "selected": False,
        "shown": None,
        "missing_message": FOOL_MISSING,
        "correct_status": None,
        "faulty_status": None,
        "run_id": None,
        "status": None,
        "kind": "error",
        "badge_line": None,
        "cases_total": None,
        "cases_divergent": None,
        "sentence": None,
        "engineer": None,
    }


def _fool_row(base_dir, toggle: FoolToggle, catalog: dict, registry: dict, reference: tuple, selected: set) -> dict:
    """One row of the fool page: the shown run, its verdict and the figures read from its files."""
    entry = catalog.get(toggle.trap_id)
    if toggle.source == "catalog":
        faulty_id = entry.faulty_run_id if entry else None
        correct_id = entry.correct_run_id if entry else None
    else:
        faulty_id, correct_id = credit_fees_run_ids(base_dir, *reference)
    faulty = _found_run(base_dir, faulty_id)
    correct = _found_run(base_dir, correct_id)
    available = faulty is not None
    on = available and toggle.param in selected
    shown = faulty if on else correct
    status = shown.verdict.get("status") if shown else None
    row = _unavailable_row(toggle, registry)
    row.update({
        "available": available,
        "selected": on,
        "shown": ("faulty" if on else "correct") if shown else None,
        "missing_message": FOOL_MISSING if (not available or shown is None) else None,
        "correct_status": correct.verdict.get("status") if correct else None,
        "faulty_status": faulty.verdict.get("status") if faulty else None,
        "run_id": shown.run_id if shown else None,
        "status": status,
        "kind": {"ALIVE": "alive", "ZOMBIE": "zombie"}.get(status, "error"),
        "badge_line": BADGE_LINES.get(status),
        "cases_total": shown.verdict.get("cases_total") if shown else None,
        "cases_divergent": shown.verdict.get("cases_divergent") if shown else None,
        "sentence": _fool_sentence(toggle, shown) if shown else None,
        "engineer": _fool_engineer(toggle, entry, shown, on) if shown else None,
    })
    return row


def fool_state(base_dir, selected: Iterable[str]) -> dict:
    """
    The three toggle rows, the counter and the clean-ports line of the fool page.

    N is the number of switched-on toggles whose faulty run exists and D the number of those whose
    verdict.json status is ZOMBIE; M is the number of correct runs found and C the number of those
    whose status is ALIVE. Nothing is typed: a deleted or edited run changes the numbers.
    """
    catalog = load_catalog(base_dir)
    registry = load_cases_registry()
    reference = reference_parameters(base_dir, catalog)
    chosen = set(selected)
    rows = [_fool_row(base_dir, toggle, catalog, registry, reference, chosen) for toggle in FOOL_TOGGLES]
    on_rows = [row for row in rows if row["selected"]]
    clean_rows = [row for row in rows if row["correct_status"] is not None]
    n = len(on_rows)
    d = sum(1 for row in on_rows if row["status"] == "ZOMBIE")
    m = len(clean_rows)
    c = sum(1 for row in clean_rows if row["correct_status"] == "ALIVE")
    if n:
        counter, clean_line = f"Coroner detected {d} of {n} injected defects", None
    else:
        counter = "No defect injected"
        clean_line = f"Coroner certified {c} of {m} clean ports" if m else "No clean port run is found."
    return {"rows": rows, "counter": counter, "clean_line": clean_line, "n": n, "d": d, "m": m, "c": c}


def build_fool(base_dir, selected: Iterable[str], view: Optional[str]) -> dict:
    """Everything the fool page template needs. A missing or unreadable file gives `error` and no numbers."""
    view = normalize_view(view)
    chosen = [param for param in FOOL_PARAMS if param in set(selected)]
    context = {
        "view": view,
        "error": None,
        "rows": [],
        "counter": None,
        "clean_line": None,
        "selected": chosen,
        "business_url": fool_url(chosen, "business"),
        "engineer_url": fool_url(chosen, "engineer"),
        "story_url": step_url(1, view),
        "positioning": POSITIONING_SENTENCE,
    }
    try:
        context.update(fool_state(base_dir, chosen))
    except StoryDataError as e:
        context["error"] = str(e)
    except (KeyError, TypeError, InvalidOperation) as e:
        context["error"] = f"A bundled run file does not have the expected content ({e})."
    if context["error"]:
        # The toggles are still listed, all disabled and without a number, next to the alert.
        registry = load_cases_registry()
        context["rows"] = [_unavailable_row(toggle, registry) for toggle in FOOL_TOGGLES]
    return context
