# CBACT04C Feasibility Probe

Probe runs of the adapted CBACT04C program on three test datasets. Every program of the sample is compiled with `cobc -fsign=EBCDIC` (Makefile variable `COBFLAGS`, see "Sign convention" below). The probe outputs under `probe/` are recorded by `make probe-upstream probe-nonzero probe-missing-default probe-sign` and are never edited by hand. The tests in `tests/test_carddemo_probe.py` rebuild them and compare byte for byte.

## Results

**upstream-sample**: 50 TRANSACT records, 0 "DISCLOSURE GROUP RECORD MISSING". Every upstream balance is zero, so every posted amount is 0.00. The 50 account balances after the run are the 50 balances before it (account 1 is +194.00 before and after).

**probe-nonzero**: 7 category balances read, 6 TRANSACT records, 1 "DISCLOSURE GROUP RECORD MISSING" followed by the DEFAULT group fallback (account 5), and one zero-rate category (account 4) that posts nothing.

| Account | Posted interest | Balance before | Balance after |
|---|---|---|---|
| 1 | 12.50 (1000.00 x 15.00 / 1200) and 52.08 (2500.00 x 25.00 / 1200) | 194.00 | 258.58 |
| 2 | -6.25 (-500.00 x 15.00 / 1200) | 158.00 | 151.75 |
| 3 | 22.50 (1500.00 x 18.00 / 1200) and 12.00 (800.00 x 18.00 / 1200) | 147.00 | 181.50 |
| 4 | none (rate 0.00) | 40.00 | 40.00 |
| 5 | 25.00 (2000.00 x 15.00 / 1200, DEFAULT group) | 345.00 | 345.00 (see "Last account of a run") |

**missing-default**: abends with exit code 231, 0 records.

### Same probe before and after the compiler option

probe-nonzero, recorded without `-fsign=EBCDIC` (earlier commit) and with it:

| | Without the option | With `-fsign=EBCDIC` |
|---|---|---|
| Interest, account 1 | 12.59 and 52.31 | 12.50 and 52.08 |
| Interest, account 2 (reversal) | +6.29 | -6.25 |
| Interest, account 3 | 22.63 and 12.07 | 22.50 and 12.00 |
| Interest, account 4 (rate 0.00) | 0.11 (a record was posted although the rate in the data is 0.00) | none |
| Interest, account 5 | 25.18 | 25.00 |
| TRANSACT records | 7 | 6 |
| Balances after, accounts 1 to 4 | -129.21, -151.82, -112.41, -40.00 | +258.58, +151.75, +181.50, +40.00 |

upstream-sample: the 49 first balances after the run were -194.11, -158.11, ... without the option and are +194.00, +158.00, ... with it (the balances before are +194.00, +158.00, ...); the posted amounts were 0 in both runs but written with a different sign character ("0" without the option, "{" with it).

## Sign convention

Upstream stores signed amounts with an EBCDIC zoned overpunch in the last character: `{` is +0 and `}` is -0 (A to I are +1 to +9, J to R are -1 to -9). GnuCOBOL 3.2 reads these characters in two different ways under its default (ASCII) convention, and consistently under `-fsign=EBCDIC`.

Evidence: `probe/sign-convention/SIGN-PROBE.cob`, compiled twice by `make probe-sign` (outputs `probe/sign-convention/ascii.txt` and `ebcdic.txt`). The program restores the raw text before every test, because reading a field can rewrite its last byte (in a first draft that displayed a field before using it, the ADD gave +1000.00 under the default convention; the order of reads changed the result).

| Test on the upstream text | Default `cobc` (ASCII) | `cobc -fsign=EBCDIC` |
|---|---|---|
| DISPLAY `0000010000{` | +1000.00 | +1000.00 |
| DISPLAY `0000005000}` | +500.00 | -500.00 |
| ADD `0000010000{` to 0 | -1000.11 | +1000.00 |
| ADD `0000005000}` to 0 | -500.13 | -500.00 |
| interest `0000010000{` x `00150{` / 1200 | 12.59 | 12.50 |
| interest `0000005000}` x `00150{` / 1200 | +6.29 | -6.25 |

Under the default convention DISPLAY shows `{` as +0 while arithmetic uses a different value (digit 11, negative), so the same data gives different answers depending on the statement. The upstream data is not valid under that convention. With `-fsign=EBCDIC` DISPLAY and arithmetic agree and the results match the meaning of the data (1000.00 x 15.00 / 1200 = 12.50 by hand). This is a compiler option; no source line changed.

The option must be given to every program that reads or writes these records, including the harness. Measured: the harness compiled with the engine's default flags (no `-fsign=EBCDIC`) on `harness-check/probe-nonzero.csv` gave 164.25 for the balance of account 2 (probe: 151.75), 52.00 for transaction 2 (probe: 52.08) and 6.20 for transaction 3 (probe: -6.25), 3 differences; compiled with the option it matches the probe on every field. The engine takes the option from `cobc_flags` in the schema.

## Last account of a run

The last account of a run never gets its interest added to ACCT-CURR-BAL. The loop in `adapted/CBACT04C.cob`, lines 188 to 222 (unchanged from upstream; lines 192 to 217 abridged):

```
188           PERFORM UNTIL END-OF-FILE = 'Y'
189               IF  END-OF-FILE = 'N'
190                   PERFORM 1000-TCATBALF-GET-NEXT
191                   IF  END-OF-FILE = 'N'
...                     (lines 192 to 217: count the record, on a new account line 196
                         PERFORM 1050-UPDATE-ACCOUNT for the previous one, then 1200 to 1400)
218                   END-IF
219               ELSE
220                    PERFORM 1050-UPDATE-ACCOUNT
221               END-IF
222           END-PERFORM.
```

1050-UPDATE-ACCOUNT (line 350: ADD WS-TOTAL-INT TO ACCT-CURR-BAL at line 352, REWRITE at line 356) runs for an account only when the first category balance of the next account is read (line 196), or in the ELSE at line 220. Line 189 is evaluated only while END-OF-FILE is not 'Y' (line 188), and END-OF-FILE is only ever set to 'Y' by 1000-TCATBALF-GET-NEXT (line 340), which is performed at line 190. In the iteration that reads the end of the file, line 191 is false and the loop then ends, so the ELSE at line 220 is never reached. The last account's interest is computed, added to WS-TOTAL-INT (line 467) and written as a TRANSACT record (line 500), but 1050-UPDATE-ACCOUNT does not run for that account and its balance is not rewritten.

In the probe-nonzero output: account 5 has the TRANSACT record `Int. for a/c 00000000005` with amount 25.00 (`probe/probe-nonzero/transact.txt`, record 6), and its balance is 345.00 before and after (`acctdata-before.txt`, `acctdata-after.txt`). Accounts 1 to 3 got their interest added.

This is upstream behavior and the audit preserves it: a Java port that "fixes" it (adds the last account's interest to its balance) behaves differently from the COBOL reference and is a behavioral difference.
