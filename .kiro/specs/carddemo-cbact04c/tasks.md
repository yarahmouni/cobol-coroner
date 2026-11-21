# CardDemo CBACT04C Tasks

Status marks: [x] done, [ ] open. Every done task names the file that proves it.

## [x] Task 1: Check the harness contract against the probes

**Requirements**: the harness contract (one row with accounts, category balances, rates) can reproduce the recorded probe results.

**Proof**: samples/carddemo-cbact04c/harness-check/probe-nonzero.csv and missing-default.csv (one row each, made by tools/dataset_to_row.py from datasets/); PROBE.md section "Sign convention" (the harness compiled with and without `-fsign=EBCDIC` on probe-nonzero).

---

## [x] Task 2: Write adapted/HARNESS-CBACT04C.cob

**Requirements**: wrap CBACT04C for differential testing; INPUT_FILE and OUTPUT_FILE; one process per step and case; work directory under TMPDIR; no path built from CASE-ID.

**Proof**: samples/carddemo-cbact04c/adapted/HARNESS-CBACT04C.cob (header comment states the 157-column input and 98-column output contract); `make -C samples/carddemo-cbact04c harness` builds it with `cobc -fsign=EBCDIC -x -Wall`; the engine compiles it in tests/test_carddemo_audit.py::test_stand_in_gives_zombie_end_to_end; CHANGES.md item 6.

---

## [x] Task 3: Check the harness against the probe outputs

**Requirements**: probe-nonzero and missing-default run through the harness give the recorded results.

**Proof**: harness-check/*.csv through the compiled harness: probe-nonzero gives EXIT-CODE 0, the five balances of probe/probe-nonzero/acctdata-after.txt (258.58, 151.75, 181.50, 40.00, 345.00) and 6 transactions (the first amounts 12.50, 52.08, -6.25 as in the probe; the probe's transact.txt also has 6 records); missing-default gives EXIT-CODE 231 and 0 transactions, as probe/missing-default/exit-code.txt (231). The upstream-sample dataset (50 transactions) is not run through the harness because it exceeds the 10 transaction slots; its probe stays in tests/test_carddemo_probe.py.

---

## [x] Task 4: Write schema.json

**Requirements**: input and output columns exactly as the harness reads and writes them; `cobc_flags` `["-fsign=EBCDIC"]`; `generator_script` `generator.py`.

**Proof**: samples/carddemo-cbact04c/schema.json (157 input and 98 output columns); tests/test_carddemo_audit.py::test_same_seed_gives_byte_identical_cases_file (header of the generated file equals the schema's input columns); the 20-case run reads the schema's output columns from the real harness output without a missing-column error.

---

## [x] Task 5: Write generator.py

**Requirements**: draws only from the given rng; covers negative, zero and positive balances, zero and non-zero rates, own-rate groups, DEFAULT fallback, no DEFAULT (abend 231), accounts without cross-reference, several balances on one account, the last-account behavior; computes no expected outcome.

**Proof**: samples/carddemo-cbact04c/generator.py; tests/test_carddemo_audit.py::test_generator_covers_the_cases_that_matter (2,000 cases, inputs only) and ::test_generator_draws_only_from_the_given_rng (only import is coroner.gen, no randint, choice, shuffle and similar).

---

## [x] Task 6: Extend the engine for generator_script

**Requirements**: requirements.md section "Case Generation": containment inside the schema folder before any import, ERROR exit 2, validation of the result, determinism, hash in inputs.json and the certificate, replay refuses a changed script, gate and pre-commit lookup match it; existing run ids unchanged.

**Proof**: coroner/parse/schema.py (`resolve_generator_script`, `GeneratorScriptError`), coroner/gen/__init__.py (`generate_cases_from_script`), coroner/store.py, coroner/certificate.py, coroner/gate.py, coroner/hooks.py, coroner/cli.py; tests in task 7.

---

## [x] Task 7: Tests for the extension and an end-to-end run with a stand-in

**Requirements**: real runs, no mocks. (a) generator_script outside the schema folder (absolute, `../`, symlink) gives ERROR before import; (b) same seed twice, byte-identical cases file; (c) the bundled T1 correct audit at 2,000 cases, seed 42 keeps run id 29c15f04407b; (d) a stand-in Java written by the test, which ports nothing, gives ZOMBIE on CardDemo at 20 cases. CardDemo tests above 10 s carry the slow marker.

**Proof**: tests/test_carddemo_audit.py (13 tests: the three outside-folder cases, inside accepted, missing, byte-identical cases, rng-only source, coverage of the generated inputs, T1 run id, ZOMBIE end to end, certificate hash, replay refusal on a changed script, gate match); tests/test_schema.py (generator_script parsing); tests/test_gen.py (script result validation).

---

## [ ] Task 8: Decide the run time budget

**Requirements**: the harness must finish inside the engine's run timeout (60 s per run, reference and instrumented) at the case count of the audit.

**Finding** (requirements.md, "Measured run time"): 20 cases verify in 30.8 s; at 200 cases the reference run took 50.66 s and the instrumented run exceeded 60 s, so `coroner verify` ended with exit 2. The engine timeout is unchanged.

**Done when**: the owner chooses one of: a lower case count for the CardDemo audit (the cost looks like about 7 s fixed plus 0.22 s per case, so about 100 cases leave room for the instrumented run), a larger timeout for this sample, or a cheaper harness (fewer processes per case). Then `coroner verify` at the chosen count with the stand-in ends in a verdict, not exit 2.

---

## [ ] Task 9: Kiro agent generates the Java port, in isolation

**Requirements**: requirements.md section "Isolation of the porting agent". A fresh session in a worktree that holds only adapted/CBACT04C.cob, upstream/cpy/*.cpy and schema.json; prompt states Java 17, BigDecimal for money, explicit RoundingMode and scale, the input file name environment variables and the output header; no hint about the formula, rounding, ordering, the last account or abends. The agent does not run the audit.

**Done when**: the unedited port is in samples/carddemo-cbact04c/java/ (class name chosen by the agent); prompt, the list of files read and the transcript are in docs/evidence/; it compiles with `javac`.

---

## [ ] Task 10: Audit the port

**Requirements**: `coroner verify` with the harness, the port and schema.json at the case count of task 8, seed 42; the verdict is reported as it comes out (ALIVE or ZOMBIE).

**Done when**: runs/<run_id>/verdict.json exists with the chosen case count; for a ZOMBIE, failure_report.json and the Given/When/Then card name the divergent columns; the certificate replays VALID.

---

## [ ] Task 11: Documentation

**Requirements**: CHANGES.md lists every added file; the sample README carries the public wording verbatim; nothing claims "audits CardDemo" or "all programs"; the main README line is added only after task 10.

**Progress**: CHANGES.md items 10 and 11 (schema.json, generator.py) added with the engine extension; README of the sample unchanged; main README, SECURITY.md and docs/ not touched by this spec's code tasks.

---

## [ ] Task 12: Audit test for the real port

**Requirements**: extend tests/test_carddemo_audit.py with one test that audits the port of task 9 at the case count of task 8 and asserts a verdict (not ERROR) and the certificate replay; slow marker.

**Done when**: `pytest tests/test_carddemo_audit.py -m "slow or not slow"` passes with that test.
