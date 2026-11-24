#!/usr/bin/env python3
"""Build the static fallback page (D-48) from the files of real runs.

Every figure on the page is read from a run file. The replay line comes from a
real `python -m coroner verify <certificate>` run made during the build.
"""

import argparse
import datetime
import hashlib
import html
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
LIVE_URL = "https://coroner.iqoba.com"
REPO_URL = "https://github.com/yarahmouni/cobol-coroner"
POSITIONING_START = "Coroner does not translate COBOL."

CSS = """
:root{--bg:#0f1115;--fg:#e6e6e6;--muted:#b4bac4;--panel:#181b22;--line:#3a404c;--link:#8ab4ff;--bad:#ff8a80;--good:#7bd88f}
@media (prefers-color-scheme:light){:root{--bg:#fff;--fg:#111;--muted:#4b5563;--panel:#f3f4f6;--line:#c4c8d0;--link:#0b57d0;--bad:#b00020;--good:#1b6e3a}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--fg);font:16px/1.5 system-ui,sans-serif}
header,main,footer{max-width:62rem;margin:0 auto;padding:1rem}
h1,h2,h3{font-family:Georgia,'Times New Roman',serif;line-height:1.25}
a{color:var(--link)}
a:focus-visible,.scroll:focus-visible{outline:3px solid var(--link);outline-offset:2px}
p,li{overflow-wrap:anywhere}
.muted{color:var(--muted)}
.scroll{overflow-x:auto;border:1px solid var(--line);margin:1rem 0}
table{border-collapse:collapse;width:100%}
caption{text-align:left;padding:.5rem;font-weight:bold}
th,td{border-top:1px solid var(--line);padding:.4rem .6rem;text-align:left;vertical-align:top}
th{white-space:nowrap}
pre{background:var(--panel);border:1px solid var(--line);padding:.75rem;margin:1rem 0;white-space:pre-wrap;overflow-wrap:anywhere;font:14px/1.45 ui-monospace,Menlo,Consolas,monospace}
.zombie{color:var(--bad);font-weight:bold}
.alive{color:var(--good);font-weight:bold}
"""


def esc(value) -> str:
    return html.escape(str(value), quote=True)


def read_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        sys.exit(f"ERROR: cannot read {path}: {exc}")


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError as exc:
        sys.exit(f"ERROR: cannot read {path}: {exc}")


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def image_reference() -> str:
    text = read_text(REPO_ROOT / "docker-compose.yml")
    match = re.search(r"^x-coroner-image:\s*&\S+\s+(\S+)\s*$", text, re.MULTILINE)
    if not match:
        sys.exit("ERROR: x-coroner-image not found in docker-compose.yml")
    return match.group(1)


def positioning_line() -> str:
    for line in read_text(REPO_ROOT / "README.md").splitlines():
        if line.startswith(POSITIONING_START):
            return line.strip()
    sys.exit("ERROR: positioning line not found in README.md")


def replay(certificate: Path, base: Path) -> dict:
    """Replay a certificate offline with the local CLI and keep its real output."""
    proc = subprocess.run(
        [sys.executable, "-m", "coroner", "verify", str(certificate)],
        cwd=REPO_ROOT, capture_output=True, text=True, timeout=300,
        env={**os.environ, "CORONER_BASE_DIR": str(base)},
    )
    out = proc.stdout
    for private in (str(base), str(REPO_ROOT)):
        out = out.replace(private, "<local folder>")
    lines = out.splitlines()
    if not lines or lines[0] != "Certificate: VALID":
        sys.exit(f"ERROR: replay of {certificate.name} is not VALID (exit {proc.returncode}): {out or proc.stderr}")
    return {"lines": lines, "exit": proc.returncode}


def table(caption: str, head: list, rows: list) -> str:
    out = [f'<div class="scroll" role="region" aria-label="{esc(caption)}" tabindex="0"><table><caption>{esc(caption)}</caption><thead><tr>']
    out += [f'<th scope="col">{esc(h)}</th>' for h in head]
    out.append("</tr></thead><tbody>")
    for row in rows:
        out.append("<tr>" + "".join(f"<td>{cell}</td>" for cell in row) + "</tr>")
    out.append("</tbody></table></div>")
    return "".join(out)


def status_cell(status: str) -> str:
    shape = "&#9632;" if status == "ZOMBIE" else "&#9679;"
    cls = "zombie" if status == "ZOMBIE" else "alive"
    return f'<span class="{cls}"><span aria-hidden="true">{shape} </span>{esc(status)}</span>'


def yes_no(value) -> str:
    return "yes" if value else "no"


def matrix_section(catalog: dict) -> str:
    rows = []
    for trap in catalog["traps"]:
        case = f"Case {trap['case_number']}: {trap['case_name']}"
        if trap.get("status") == "measured":
            rows.append([
                esc(case), esc(trap["id"]), esc(trap["title"]),
                esc(f"{trap['cases_detected']} of {trap['cases_generated']}"),
                esc(trap["detection_rate"]), status_cell(trap["correct_verdict"]),
                esc(trap["faulty_run_id"]), esc(trap["correct_run_id"]),
            ])
        else:
            rows.append([esc(case), esc(trap["id"]), esc(trap["title"]),
                         "not measured", "not measured", "not measured", "none", "none"])
    head = ["Case", "Trap", "Title", "Detected of generated", "Rate", "Correct port", "Faulty run", "Correct run"]
    return (
        '<section aria-labelledby="matrix"><h2 id="matrix">Detection Matrix</h2>'
        "<p>Each measured case has a faulty Java port and a correct one. Detected is the number of generated "
        "cases on which the faulty port diverged from COBOL. Rates depend on the generator settings of each "
        "case and are not real-world statistics. There is no global rate.</p>"
        + table("Detection Matrix from trap_catalog.json", head, rows)
        + "</section>"
    )


def case1_section(faulty: dict, correct: dict, faulty_id: str, correct_id: str, recon: dict, card: str, seed) -> str:
    def row(label, key, fmt=esc):
        return [esc(label), fmt(faulty[key]), fmt(correct[key])]

    verdict_rows = [
        ["Run", esc(faulty_id), esc(correct_id)],
        row("Status", "status", status_cell),
        row("Sub-label", "sub_label"),
        row("Cases", "cases_total"),
        row("Divergent cases", "cases_divergent"),
        row("Unreconciled branch exposure, sum", "exposure_sum"),
        row("Unreconciled branch exposure, max", "exposure_max"),
        row("Branches affected", "affected_branches"),
        row("Suspense difference", "suspense_difference"),
        row("Grand total matches", "grand_total_matches", yes_no),
        row("Notice", "validation_notice"),
    ]
    branch_rows = [
        [esc(b["branch"]), esc(b["cobol_subtotal"]), esc(b["java_subtotal"]), esc(b["difference"]), esc(b["status"])]
        for b in recon["branches"]
    ]
    s = recon["suspense"]
    g = recon["grand_total"]
    branch_rows.append(["Suspense", esc(s["cobol"]), esc(s["java"]), esc(s["difference"]), "separate line"])
    equal = g["cobol"] == g["java"]
    branch_rows.append(["Grand total", esc(g["cobol"]), esc(g["java"]),
                        "equal" if equal else "differs", "balanced" if equal else "not balanced"])
    return (
        '<section aria-labelledby="case1"><h2 id="case1">Case 1: The Missing Branch</h2>'
        "<p>The COBOL program fills its branch table in EBCDIC order. The faulty Java port matches branch codes in "
        "ASCII order, so some amounts are posted to suspense. The grand total still balances, which is why a "
        f"total-only check does not see it. Both runs used the generated cases of seed {esc(seed)}.</p>"
        + table("Case 1 verdicts from verdict.json", ["", "Faulty port", "Correct port"], verdict_rows)
        + table("Branch reconciliation of the faulty run from branch_reconciliation.json",
                ["Branch", "COBOL subtotal", "Java subtotal", "Difference", "Status"], branch_rows)
        + "<h3>Minimal failing case</h3>"
        + f"<pre>{esc(card)}</pre></section>"
    )


def replay_section(certs: list, image: str) -> str:
    """certs: list of dicts with run_id, file, cases_file, cases_name, replay."""
    first = certs[0]
    commands = []
    for c in certs:
        commands.append(
            f"mkdir -p replay/runs/{c['run_id']}\n"
            f"cp {c['file']} replay/\n"
            f"cp {c['cases_name']} replay/runs/{c['run_id']}/generated_cases.csv\n"
            f"docker run --rm --init -v \"$PWD/replay:/replay:ro\" -e CORONER_BASE_DIR=/replay \\\n"
            f"  {image} \\\n"
            f"  python3 -m coroner verify /replay/{c['file']}"
        )
    links = "".join(
        f'<li><a href="{esc(c["file"])}" download>{esc(c["file"])}</a> ({esc(c["label"])})</li>' for c in certs
    )
    cases_names = sorted({c["cases_name"] for c in certs})
    links += "".join(f'<li><a href="{esc(n)}" download>{esc(n)}</a> (generated cases the certificates refer to)</li>' for n in cases_names)
    replays = ""
    for c in certs:
        replays += (
            f"<h3>{esc(c['label'])}: replay run during the build</h3>"
            f"<pre>{esc(chr(10).join(c['replay']['lines']))}\nexit code: {esc(c['replay']['exit'])}</pre>"
        )
    return (
        '<section aria-labelledby="replay"><h2 id="replay">Replay a certificate</h2>'
        "<p>A certificate is a reproducible run record. Replaying it offline recomputes every file hash, "
        "regenerates the cases from the seed and runs COBOL and Java again. It is not a formal proof of equivalence.</p>"
        f"<h3>Downloads</h3><ul>{links}</ul>"
        "<h3>Command, with the published image</h3>"
        "<p>The image is pinned by digest. The command needs Docker and the downloaded files in the current folder. "
        "It was not run during this build.</p>"
        f"<pre>{esc(chr(10).join(commands))}</pre>"
        "<p>Expected first line of the output: <code>Certificate: VALID</code>. The exit code is 0 for an ALIVE "
        "certificate and 1 for a ZOMBIE certificate.</p>"
        + replays
        + "<p class=\"muted\">The replays above were run during the build with the local command "
        "<code>python -m coroner verify &lt;certificate&gt;</code>, not through the image.</p>"
        + f'<h3>First certificate in full: {esc(first["label"])}</h3>'
        f'<pre id="certificate">{esc(first["pretty"])}</pre></section>'
    )


def build(base: Path, out: Path, commit: str) -> None:
    runs = base / "runs"
    catalog = read_json(runs / "trap_catalog.json")
    t1 = next((t for t in catalog["traps"] if t["id"] == "T1" and t.get("status") == "measured"), None)
    if t1 is None:
        sys.exit("ERROR: T1 is not measured in trap_catalog.json")
    faulty_id, correct_id = t1["faulty_run_id"], t1["correct_run_id"]
    faulty_dir, correct_dir = runs / faulty_id, runs / correct_id

    faulty = read_json(faulty_dir / "verdict.json")
    correct = read_json(correct_dir / "verdict.json")
    recon = read_json(faulty_dir / "branch_reconciliation.json")
    card = read_text(faulty_dir / "card.txt")

    out.mkdir(parents=True, exist_ok=True)
    certs = []
    for label, run_id, run_dir in (("T1 correct port", correct_id, correct_dir), ("T1 faulty port", faulty_id, faulty_dir)):
        cert_path = run_dir / "certificate.json"
        cert = read_json(cert_path)
        cases_path = base / cert["cases_file"]
        if sha256_file(cases_path) != cert["cases_file_sha256"]:
            sys.exit(f"ERROR: cases file of run {run_id} does not match its certificate")
        file_name = f"certificate-{run_id}.json"
        cases_name = f"cases-{cert['cases_file_sha256'][:12]}.csv"
        shutil.copyfile(cert_path, out / file_name)
        shutil.copyfile(cases_path, out / cases_name)
        certs.append({
            "label": label, "run_id": run_id, "file": file_name, "cases_name": cases_name,
            "pretty": json.dumps(cert, indent=2, sort_keys=True, ensure_ascii=False),
            "replay": replay(cert_path, base), "seed": cert["random_seed"],
        })

    date = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")
    body = (
        "<header><h1>COBOL Coroner: static copy of real outputs</h1>"
        f"<p>{esc(positioning_line())}</p>"
        "<p>This page is a static copy of real run outputs, for when the live site is unavailable. "
        "It contains no script and loads nothing from another site. "
        f'Live site: <a href="{LIVE_URL}">{LIVE_URL}</a>. '
        f'Repository: <a href="{REPO_URL}">{REPO_URL}</a>.</p></header>'
        "<main>"
        + matrix_section(catalog)
        + case1_section(faulty, correct, faulty_id, correct_id, recon, card, certs[0]["seed"])
        + replay_section(certs, image_reference())
        + "</main>"
        f"<footer><p class=\"muted\">Built from commit {esc(commit)} on {esc(date)}.</p></footer>"
    )
    page = (
        '<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        "<title>COBOL Coroner: static copy of real outputs</title>"
        f"<style>{CSS}</style></head><body>{body}</body></html>\n"
    )
    for private in (str(Path.home()), str(REPO_ROOT)):
        if private in page:
            sys.exit("ERROR: the page contains a local path; refusing to write it")
    (out / "index.html").write_text(page, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the static fallback page from real runs")
    parser.add_argument("--base", required=True, help="base directory holding runs/ and runs/trap_catalog.json")
    parser.add_argument("--out", default="docs/static", help="output folder (default docs/static)")
    parser.add_argument("--commit", required=True, help="commit id shown in the footer")
    args = parser.parse_args()
    out = Path(args.out)
    if not out.is_absolute():
        out = REPO_ROOT / out
    build(Path(args.base).resolve(), out, args.commit)
    print(f"Wrote {out / 'index.html'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
