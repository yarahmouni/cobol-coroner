# CardDemo CBACT04C Design

## Files

### Upstream and adapted (read-only for this spec)

- samples/carddemo-cbact04c/upstream/: original program, copybooks (CVTRA01Y, CVACT03Y, CVTRA02Y, CVACT01Y, CVTRA05Y), data files; LICENSE and NOTICE one level up
- samples/carddemo-cbact04c/adapted/CBACT04C.cob: lines 614 to 621 changed (run date parameter instead of FUNCTION CURRENT-DATE), rest unchanged
- samples/carddemo-cbact04c/adapted/RUN-CBACT04C.cob (driver), CEE3ABD.cob (abend stub, exit 231), LOAD-FILES.cob (text files to indexed files), DUMP-ACCT.cob (account balances)
- samples/carddemo-cbact04c/adapted/HARNESS-CBACT04C.cob: the program Coroner compiles and runs
- samples/carddemo-cbact04c/Makefile: builds the helpers (target harness-helpers) with `cobc -fsign=EBCDIC`
- samples/carddemo-cbact04c/probe/, PROBE.md: recorded probe runs and findings

### Added by this spec

- samples/carddemo-cbact04c/schema.json: input and output columns exactly as the harness reads and writes them, `cobc_flags` `["-fsign=EBCDIC"]`, `generator_script` `generator.py`
- samples/carddemo-cbact04c/generator.py: case generator
- coroner/parse/schema.py, coroner/gen/__init__.py, coroner/store.py, coroner/certificate.py, coroner/gate.py, coroner/hooks.py, coroner/cli.py: the generator_script extension
- tests/test_carddemo_audit.py, plus tests in tests/test_schema.py and tests/test_gen.py

## Pipeline

```
schema.json --(generator_script)--> generated_cases.csv (157 columns, one row per case)
                                         |
       harness (cobc -x -Wall -I upstream/cpy -fsign=EBCDIC) ---> COBOL output (98 columns)
       Java port (javac, java -cp, same INPUT_FILE/OUTPUT_FILE) -> Java output (98 columns)
                                         |
                        engine comparison (exact, per column, keyed by CASE-ID)
```

Nothing in the pipeline is specific to CardDemo except the schema and the generator. The harness runs each case in its own processes, so a case that abends (exit 231) ends only that case; its row carries EXIT-CODE 231 and whatever balances and transactions were produced before the abend.

## Schema

All 157 input and 98 output columns are listed one per line in schema.json (the file is under the engine's 100 KB schema limit).

- Input: `string` for ids, groups, card numbers, types and flags; `integer` for ACCT-ID, CATBAL-ACCT-INDEX, CATBAL-CAT, RATE-CAT; `decimal` (PIC S9(10)V99, S9(9)V99, S9(4)V99) for amounts and rates.
- Output: CASE-ID string, EXIT-CODE integer, every other column `string`. Amounts and counts are empty when absent, and the engine's decimal comparison treats an empty value as a divergence, so they are compared as exact text (trailing spaces trimmed). The format is part of the contract and is stated in each column's description: plain signed decimal at scale 2, no plus sign, no leading zeros.
- The program name in the schema is HARNESS-CBACT04C: the program the engine compiles and runs. Coverage is measured on the harness (the instrumented harness binary), not on CBACT04C, which runs in subprocesses.

## Engine extension: generator_script

### Where each rule lives

| Rule | Code |
|---|---|
| Read the key, resolve against the schema folder, refuse outside or missing | `resolve_generator_script` in coroner/parse/schema.py, called by `load_schema` |
| Error type | `GeneratorScriptError(ValueError)` in coroner/parse/schema.py |
| Run the script, validate its result, write the CSV | `generate_cases_from_script` in coroner/gen/__init__.py, called first thing by `generate_cases` when the schema has a script |
| Print `ERROR: ...`, exit 2 | `verify_command` in coroner/cli.py |
| Hash into inputs.json and the run id | `generator_script_info` and `collect_inputs`, `compute_run_id` in coroner/store.py |
| Certificate keys and replay checks | `generate_certificate`, `replay_certificate` in coroner/certificate.py |
| Gate and pre-commit lookup | `certificate_matches_files` in coroner/gate.py, the certificate search in coroner/hooks.py |

### Containment check

```
schema_dir = Path(schema_path).parent.resolve()
candidate  = declared if absolute else schema_dir / declared
resolved   = candidate.resolve()          # follows symlinks
refuse unless resolved is inside schema_dir and is a regular file
```

It runs inside `load_schema`, so every path that loads the schema (CLI run, replay, gate, UI) is covered, and it runs before the COBOL structure parse, the compile and any execution. An absolute path, a `../` path and a symlink that points out of the folder are all refused; the declared string (not the resolved host path) is printed.

### Execution

The script is read once, its bytes are compiled and executed in a new namespace (`__name__` `coroner_generator_script`). This is not an import: no module cache entry, no __pycache__ written beside the script (the Docker image's /app is read-only), and the bytes that run are the bytes that were read. The script can import `coroner.gen` helpers (`draw_int`, `generate_case_id`); the sample generator does.

### Result validation

A list of exactly `num_cases` dicts; the key set of each equals the schema's input columns; values are str, int or Decimal (Decimal through `format_decimal` at the column's scale); no float, bool or None; no CR or LF inside a value. The CSV is written with `csv.DictWriter`, UTF-8, LF, columns in schema order, to `<base>/runs/temp/generated_cases.csv` like the built-in generators.

### Determinism

`generate_cases` creates `random.Random(seed)` and hands it to the script. The script draws only through `draw_int` and `rng.random()`. Same seed, same bytes (tests/test_carddemo_audit.py). The generator version guard of tests/test_gen_regression.py is unchanged: the built-in generators did not change.

### Hash and certificate

`generator_script_info(schema_path)` reads only the `generator_script` key of the schema JSON (so it works for the minimal schema files some tests write), resolves it with `resolve_generator_script` and returns `(declared path, SHA-256 of the file)`, or None. `collect_inputs` stores both under `generator_script` and `generator_script_sha256` only when it returns a value; `compute_run_id` and `generate_certificate` add the hash only when it is present. Certificates and run ids of every schema without a script are therefore byte for byte what they were (run id 29c15f04407b, tests/test_carddemo_audit.py).

Replay (`replay_certificate`), after the schema hash check: schema has no script and the certificate has no hash is fine; exactly one of the two is `generator script differs between certificate and schema`; both present and the hash of the file on disk differs is `generator script hash mismatch`. Replay does not re-run the script (the stored cases file is authoritative, D-30); the hash records which script produced it.

`certificate_matches_files` (gate) and the certificate search (pre-commit lookup) compare `cert.get("generator_script_sha256")` with the hash of the script the scope's schema declares (None when it declares none), so a changed script no longer matches an old certificate.

### Known limit

The pre-commit hook exports only the four scope files from the Git index (COBOL, Java, schema, copybook folder). A scope whose schema declares a generator script would find no script in that export and be blocked with `generator script not found`. CardDemo is not the pre-commit scope; extending the export is out of this spec.

## Generator (samples/carddemo-cbact04c/generator.py)

One function builds each case in four steps, all from the given rng:

1. `make_accounts`: 1 to 5 accounts (weights 15, 30, 25, 15, 15), distinct ids of 1 to 11 digits drawn in no particular order, a group from GROUP01, GROUP02, GROUP03, SILVER, GOLD, DEFAULT (4 percent blank), balances (30 percent negative, 10 percent zero), cycle credit and debit (never negative), a unique card number, cross-reference present with probability 0.97.
2. `make_catbals`: 1 to 10 category balances on distinct (account slot, type, category) keys, so several land on the same account; balances 25 percent negative, 10 percent zero; with probability 0.03 (when a slot is free) the first one names an unused account slot.
3. `make_rates`: for each needed (group, type, category) one of: own rate (50), DEFAULT only (35), both (15); with probability 0.08 one needed type and category gets neither; up to 3 unrelated rates (other group, type or category). Rate values: zero 25 percent, 0.01 to 36.00 70 percent, 36.01 to 99.99 5 percent. Rate slots are shuffled.
4. Unused slots hold the values `dataset_to_row.py` uses (id 0, empty text, 0.00).

Integer digits of an amount are drawn with weights favoring 1 to 4 digits; a few reach 9. The largest possible product (999,999,999.99 times 99.99 divided by 1200) and sum of ten of them stay inside S9(09)V99, so no case overflows a field.

The generator draws no expected value. Coverage claims (negative, zero and positive balances, zero and non-zero rates, own rate, DEFAULT fallback, no rate, no cross-reference, unused slot, several balances on one account, slot order different from key order, single account) are checked from the generated inputs alone by tests/test_carddemo_audit.py; the abend outcomes were checked against real harness runs (requirements, Findings).

## Java port

Made later by an isolated Kiro session (see Isolation in requirements.md). The class reads INPUT_FILE, writes OUTPUT_FILE with the 98 header columns of schema.json and exits 0 when the run completes. Its source is saved unedited.

## Stand-in Java (tests only)

tests/test_carddemo_audit.py writes, in a temporary directory, a Java class `StandIn` that writes only the output header from schema.json and reads no input. It is not a port. It exists to prove that the pipeline (generate, compile, run the harness twice, run Java, compare, report, certificate, replay, gate match) runs end to end on CardDemo: the verdict is ZOMBIE on every case.

## Public Documentation

samples/carddemo-cbact04c/README.md carries the required public wording verbatim. The verdict lines are the engine's standard ones; the scope sentence "no behavioral difference across the tested scenarios; not a certification for all inputs" is added by the documentation task.
