# Kiro hooks tasks

## Task 1: Scope file
_Requirements: 1.1, 1.2_

Create `.kiro/coroner-scope.json` with the credit-fees sample paths:
```json
{
  "cobol": "samples/credit-fees/CREDIT-FEES.cob",
  "copybooks": "samples/credit-fees/copybooks",
  "java": "samples/credit-fees/CreditFees.java",
  "schema": "samples/credit-fees/schema.json"
}
```

**Done when**: file exists and is valid JSON.

## Task 2: Hook module skeleton
_Requirements: 4.1 to 4.5_

Create `coroner/hooks.py` with:
- `parse_hook_input(stdin_text: str) -> dict`: parse JSON from stdin, handle both v2 and v3 shapes.
- `main()`: read stdin, parse args (`sys.argv[1]` is "gate" or "stop"), dispatch.

**Done when**: `python -m coroner.hooks gate` and `python -m coroner.hooks stop` read stdin and print the parsed hook event name.

## Task 3: Scope and certificate lookup
_Requirements: 2.3, 2.4_

Implement:
- `load_scope(scope_path: str = ".kiro/coroner-scope.json") -> dict`: load and parse the scope file.
- `compute_file_hash(path: str) -> str`: SHA-256 hex digest of a file (reuse from coroner/store.py if available).
- `find_certificate(scope: dict) -> Optional[str]`: list all `runs/*/certificate.json`, filter by matching hashes (current files vs recorded), return the newest by mtime.

**Done when**: unit test proves it finds the right certificate when multiple exist.

## Task 4: Certificate replay
_Requirements: 2.4_

Implement:
- `replay_certificate(cert_path: str) -> tuple[int, str, dict]`: run `python -m coroner verify {cert_path}` as a subprocess, capture exit code and stdout (the verdict line), load the certificate JSON, return all three.

**Done when**: unit test replays a real certificate and gets exit code 0 or 1.

## Task 5: Command parsing and staged files
_Requirements: 2.2, 2.6_

Implement:
- `is_git_commit_push_merge(command: str) -> bool`: split into words (shell-like, respect quotes), check if `words[0] == "git"` and `words[1] in ["commit", "push", "merge"]`.
- `get_staged_files() -> list[str]`: run `git diff --cached --name-only`, return the list of paths.
- `is_audited_file_staged(scope: dict, staged: list[str]) -> bool`: check if the COBOL or Java path from the scope is in the staged list.

**Done when**: unit test proves "git commit -m x" matches, "echo git commit" does not, and "ls" does not.

## Task 6: Block message
_Requirements: 2.9_

Implement:
- `build_block_message(cert_data: dict, verdict_data: Optional[dict] = None, replay_line: str = "") -> str`: construct the message from the certificate's `status` and `sub_label` (the divergence count is in the sub label), the exposure line the CLI prints for the run (`coroner.verdict.exposure_text` on the run's `verdict.json`, otherwise "not applicable"), and the fix instruction. Real certificates have no `verdict` or `divergences` key.

**Done when**: unit tests use the certificate and `verdict.json` of real engine runs (never hand-made keys) and show the correct message for a ZOMBIE run with and without a group key.

## Task 7: Gate command
_Requirements: 2.1 to 2.10_

Implement `gate_command(hook_input: dict) -> None`:
1. Extract `tool_input.command`.
2. If not git commit/push/merge: `sys.exit(0)` silently.
3. Load scope, find certificate.
4. If certificate found: replay, check exit code.
   - Exit 0 (ALIVE valid): `sys.exit(0)` silently.
   - Exit 1 or 3 (ZOMBIE or invalid): print `{"decision":"block","reason":"<message>"}` on stdout, `sys.exit(2)`.
5. If certificate missing: check staged files.
   - If audited files staged: block (JSON + exit 2).
   - Otherwise: allow (exit 0 silently).

**Done when**: unit test feeds v2 and v3 JSON, blocks git commit when ZOMBIE, allows when ALIVE, ignores other commands.

## Task 8: Stop command
_Requirements: 3.1 to 3.5_

Implement `stop_command(hook_input: dict) -> None`:
1. Extract `session_id`.
2. Load scope, find certificate.
3. If certificate found: replay, check exit code.
   - Exit 0 (ALIVE valid): `sys.exit(0)` silently.
   - Exit 1 or 3 (ZOMBIE or invalid): increment count in `build/hooks/<session_id>.count`, check limit.
     - Count <= 3: print `{"decision":"block","reason":"<message>"}` on stdout, `sys.exit(0)`.
     - Count > 3: write `build/hooks/<session_id>-failure.json`, `sys.exit(0)` silently.
4. If certificate missing: check staged files, same count logic.

**Done when**: unit test proves 3 blocks then allow, and the failure file exists after the 4th call.

## Task 9: Agent configuration
_Requirements: 5.1 to 5.4_

Update `.kiro/agents/coroner-auditor.json`:
- Add `"hooks"` with two preToolUse hooks (matcher "shell" and "execute_bash"), command `.venv/bin/python -m coroner.hooks gate`.
- Add `"stop"` hook, command `.venv/bin/python -m coroner.hooks stop`.
- Add "shell" to `"tools"` or `"allowedTools"`.
- Run `kiro-cli agent validate --agent coroner-auditor`.

**Done when**: validation passes.

## Task 10: Documentation
_Requirements: 6.1 to 6.3_

Update README and `.kiro/steering/product.md`:
- Add the exact wording "Coroner does not block the agent from writing code. It blocks a ZOMBIE migration from being committed or pushed."
- Add one honest line about the stop hook: "The stop hook re-prompts the agent up to 3 times (v2 engine) or once per turn (v3 engine); it does not prevent the agent from finishing."

**Done when**: both files contain the exact wording.

## Task 11: Tests
_Requirements: 7.1 to 7.7_

Create `tests/test_hooks.py`:
- Test `parse_hook_input` with v2 and v3 shapes.
- Test `is_git_commit_push_merge` with various commands.
- Test gate: ignores `ls`, `git status`, `echo git commit`; blocks `git commit -m x` when ZOMBIE (create a ZOMBIE certificate with the legacy variant in a temp directory); allows when ALIVE; blocks missing certificate only when audited files are staged (use a temp git repo).
- Test stop: blocks 3 times, writes failure file on 4th call.
- Run with `.venv/bin/pytest -q tests/test_hooks.py`.

**Done when**: all tests pass.

## Coverage table

| Criterion | Tasks |
|---|---|
| Scope | 1 |
| Delivery gate | 5, 6, 7, 9, 11 |
| Stop hook | 8, 9, 11 |
| Hook input | 2, 11 |
| Agent config | 9 |
| Documentation | 10 |
| Testing | 11 |
