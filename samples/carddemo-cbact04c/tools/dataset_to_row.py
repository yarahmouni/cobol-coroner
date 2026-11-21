#!/usr/bin/env python3
"""Convert a CardDemo dataset folder into rows of the harness input contract.

The folder holds the four fixed-width text files read by LOAD-FILES
(tcatbal.txt, cardxref.txt, acctdata.txt or account.txt, discgrp.txt). The
output is a CSV with the 157 columns of adapted/HARNESS-CBACT04C.cob.

Upstream stores signed amounts with an EBCDIC zoned overpunch in the last
character: "{" is +0, A to I are +1 to +9, "}" is -0 and J to R are -1 to -9
(a plain digit is positive). The sample is compiled with cobc -fsign=EBCDIC
(see the Makefile and PROBE.md), so the programs read these characters with
exactly this meaning and the converter decodes them the same way. Any other
last character is an error.

Usage:
  dataset_to_row.py DATASET_DIR CASE_ID [--parm-date YYYY-MM-DD]
                    [--repeat N]

--repeat N writes N rows whose CASE-IDs are CASE_ID followed by a counter
(at most 10 characters in total).
"""

import argparse
import csv
import sys
from decimal import Decimal
from pathlib import Path

N_ACCOUNTS = 5
N_CATBALS = 10
N_RATES = 20


def decode_amount(text: str, scale: int) -> Decimal:
    """Decode a zoned decimal whose last character is an EBCDIC overpunch."""
    prefix, last = text[:-1], text[-1]
    if last.isdigit():
        digit, negative = int(last), False
    elif last == "{":
        digit, negative = 0, False
    elif last == "}":
        digit, negative = 0, True
    elif "A" <= last <= "I":
        digit, negative = ord(last) - ord("A") + 1, False
    elif "J" <= last <= "R":
        digit, negative = ord(last) - ord("J") + 1, True
    else:
        raise ValueError(f"cannot decode {text!r}")
    value = Decimal(int(prefix or "0") * 10 + digit).scaleb(-scale)
    return -value if negative else value


def money(value: Decimal) -> str:
    return f"{value:.2f}"


def read_records(path: Path) -> list[str]:
    with open(path, "r", newline="") as handle:
        lines = [ln.rstrip("\r\n") for ln in handle.read().split("\n")]
    return [ln for ln in lines if ln.strip()]


def lenient_amount(text: str, what: str, acct_id: int) -> Decimal:
    """Cycle credit and debit are never read by CBACT04C (it only moves
    zero into them), so an undecodable value becomes 0.00 with a warning."""
    try:
        return decode_amount(text, 2)
    except ValueError:
        print(f"warning: account {acct_id} {what} {text!r} is not a valid "
              f"amount, using 0.00", file=sys.stderr)
        return Decimal("0.00")


def build_row(dataset: Path, case_id: str, parm_date: str) -> dict:
    acct_file = dataset / "acctdata.txt"
    if not acct_file.exists():
        acct_file = dataset / "account.txt"
    accounts = []
    for rec in read_records(acct_file):
        acct_id = int(rec[0:11])
        accounts.append({
            "id": acct_id,
            "bal": decode_amount(rec[12:24], 2),
            "credit": lenient_amount(rec[78:90], "cycle credit", acct_id),
            "debit": lenient_amount(rec[90:102], "cycle debit", acct_id),
            "group": rec[102:112].rstrip(),
        })
    cards = {}
    for rec in read_records(dataset / "cardxref.txt"):
        cards[int(rec[25:36])] = rec[0:16]
    catbals = []
    for rec in read_records(dataset / "tcatbal.txt"):
        catbals.append({
            "acct": int(rec[0:11]),
            "type": rec[11:13],
            "cat": int(rec[13:17]),
            "bal": decode_amount(rec[17:28], 2),
        })
    rates = []
    for rec in read_records(dataset / "discgrp.txt"):
        rates.append({
            "group": rec[0:10].rstrip(),
            "type": rec[10:12],
            "cat": int(rec[12:16]),
            "value": decode_amount(rec[16:22], 2),
        })
    if len(accounts) > N_ACCOUNTS or len(catbals) > N_CATBALS \
            or len(rates) > N_RATES:
        raise ValueError("dataset does not fit the harness slots")

    row = {"CASE-ID": case_id, "PARM-DATE": parm_date}
    index_of = {acc["id"]: i + 1 for i, acc in enumerate(accounts)}
    for i in range(1, N_ACCOUNTS + 1):
        acc = accounts[i - 1] if i <= len(accounts) else None
        row[f"ACCT-ID-{i}"] = acc["id"] if acc else 0
        row[f"ACCT-GROUP-ID-{i}"] = acc["group"] if acc else ""
        row[f"ACCT-CURR-BAL-{i}"] = money(acc["bal"]) if acc else "0.00"
        row[f"ACCT-CURR-CYC-CREDIT-{i}"] = \
            money(acc["credit"]) if acc else "0.00"
        row[f"ACCT-CURR-CYC-DEBIT-{i}"] = \
            money(acc["debit"]) if acc else "0.00"
        row[f"XREF-CARD-NUM-{i}"] = cards.get(acc["id"], "") if acc else ""
        row[f"XREF-EXISTS-{i}"] = \
            ("Y" if acc["id"] in cards else "N") if acc else ""
    for i in range(1, N_CATBALS + 1):
        cb = catbals[i - 1] if i <= len(catbals) else None
        if cb and cb["acct"] not in index_of:
            raise ValueError(f"category balance for unknown account "
                             f"{cb['acct']}")
        row[f"CATBAL-ACCT-INDEX-{i}"] = index_of[cb["acct"]] if cb else 0
        row[f"CATBAL-TYPE-{i}"] = cb["type"] if cb else ""
        row[f"CATBAL-CAT-{i}"] = cb["cat"] if cb else 0
        row[f"CATBAL-BAL-{i}"] = money(cb["bal"]) if cb else "0.00"
    for i in range(1, N_RATES + 1):
        rt = rates[i - 1] if i <= len(rates) else None
        row[f"RATE-GROUP-{i}"] = rt["group"] if rt else ""
        row[f"RATE-TYPE-{i}"] = rt["type"] if rt else ""
        row[f"RATE-CAT-{i}"] = rt["cat"] if rt else 0
        row[f"RATE-VALUE-{i}"] = money(rt["value"]) if rt else "0.00"
    return row


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("dataset_dir")
    parser.add_argument("case_id")
    parser.add_argument("--parm-date", default="")
    parser.add_argument("--repeat", type=int, default=1)
    args = parser.parse_args()

    base = build_row(Path(args.dataset_dir), args.case_id, args.parm_date)
    writer = csv.DictWriter(sys.stdout, fieldnames=list(base.keys()),
                            lineterminator="\n")
    writer.writeheader()
    width = len(str(args.repeat))
    for n in range(1, args.repeat + 1):
        row = dict(base)
        if args.repeat > 1:
            row["CASE-ID"] = f"{args.case_id}{n:0{width}d}"
        if len(row["CASE-ID"]) > 10:
            raise ValueError("CASE-ID longer than 10 characters")
        writer.writerow(row)
    return 0


if __name__ == "__main__":
    sys.exit(main())
