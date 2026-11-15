# Kiro hooks requirements

## Context

D-37 and D-50 define the Kiro hook strategy based on measured hook behavior in docs/evidence/kiro-hooks-verification.md. The delivery gate (preToolUse hook) blocks git commit, git push and git merge when the certificate of the migration in scope is ZOMBIE, missing or invalid. The stop hook re-prompts the agent once per turn (v3) or up to 3 times per session (v2) but does not prevent it from finishing.

## Requirements

### 1. Scope definition
1.1. A scope file `.kiro/coroner-scope.json` records the migration in scope: `{"cobol": "path", "copybooks": "path", "java": "path", "schema": "path"}`.
1.2. The initial scope is the credit-fees sample.

### 2. Delivery gate hook
2.1. A preToolUse hook (matcher "shell" and "execute_bash") blocks git commit, git push and git merge commands when the certificate of the migration in scope is ZOMBIE, missing or invalid.
2.2. The hook parses the command words (not a substring search) to detect git commit, git push or git merge.
2.3. The hook finds the certificate: the newest `runs/*/certificate.json` whose recorded COBOL, Java, schema and copybook hashes equal the current files on disk.
2.4. The hook replays the certificate with the certificate module.
2.5. Block when ZOMBIE or invalid (replay exit 1 or 3).
2.6. Block when missing only if the audited COBOL or Java files are staged (detected by running `git diff --cached --name-only` from the hook code).
2.7. Do not block file writes, compilation, tests, certificate generation or other git commands (git status, git diff, git log, etc.).
2.8. Blocking form (portable across v2 and v3): stdout `{"decision":"block","reason":"<message>"}` and exit 2.
2.9. Block message: verdict line, divergences, "Unreconciled branch exposure: not applicable (no group key in the schema)" unless the schema declares a group key (then the measured value when that metric exists), and the fix instruction "Run get_failure_report and export_junit_test, fix the Java port, then run run_differential_check again."
2.10. Non-blocking commands exit 0 silently (no stdout, no stderr).

### 3. Stop hook
3.1. A stop hook blocks at most 3 times per session_id (v2 behavior, counted in `build/hooks/<session_id>.count`).
3.2. On each block: same certificate lookup and replay as the delivery gate; print `{"decision":"block","reason":"<message>"}` on stdout and exit 0.
3.3. After 3 blocks: write `build/hooks/<session_id>-failure.json` (verdict, reasons, attempts) and allow (exit 0, no stdout).
3.4. Block when ZOMBIE, missing or invalid (same missing condition as the gate: only if the audited files are staged).
3.5. Allow when ALIVE and valid (exit 0, no stdout).

### 4. Hook input
4.1. Both hooks read JSON from stdin.
4.2. v2 stop: `{"hook_event_name":"stop","cwd":...,"session_id":...}`
4.3. v3 stop: `{"session_id":...,"hook_event_name":"Stop","cwd":...}`
4.4. v2 preToolUse: `{"hook_event_name":"preToolUse",...,"tool_name":"shell","tool_input":{"command":"..."}}`
4.5. v3 preToolUse: `{"hook_event_name":"PreToolUse",...,"tool_name":"execute_bash","tool_input":{"command":"..."}}`

### 5. Agent configuration
5.1. The agent `.kiro/agents/coroner-auditor.json` defines two preToolUse hooks (matcher "shell" and "execute_bash"), command `.venv/bin/python -m coroner.hooks gate`.
5.2. The agent defines one stop hook, command `.venv/bin/python -m coroner.hooks stop`.
5.3. The agent tools include "shell" so the agent can attempt git commands (the gate governs them).
5.4. Validate with `kiro-cli agent validate --agent coroner-auditor`.

### 6. Documentation
6.1. README: the exact wording "Coroner does not block the agent from writing code. It blocks a ZOMBIE migration from being committed or pushed."
6.2. README: one honest line that the stop hook only re-prompts the agent once per turn (v3) and does not prevent it from finishing.
6.3. .kiro/steering/product.md: the same wording.

### 7. Testing
7.1. Feed both stdin shapes (v2 and v3) to each hook.
7.2. Gate ignores `ls`, `git status`, `echo git commit` (not a real git commit) and file writes.
7.3. Gate blocks `git commit -m x` when the scope certificate is ZOMBIE (create one with the legacy variant in a temporary copy of the scope).
7.4. Gate allows `git commit -m x` when the scope certificate is ALIVE and valid.
7.5. Gate blocks a missing certificate only when the audited files are staged (use a temporary git repository in the test).
7.6. Stop hook blocks 3 times per session_id, then writes the failure file and allows.
7.7. All tests in tests/test_hooks.py, run with `.venv/bin/pytest -q tests/test_hooks.py`.

## Coverage
| Criterion | Requirements |
|---|---|
| Scope | 1.1, 1.2 |
| Delivery gate | 2.1 to 2.10 |
| Stop hook | 3.1 to 3.5 |
| Hook input | 4.1 to 4.5 |
| Agent config | 5.1 to 5.4 |
| Documentation | 6.1 to 6.3 |
| Testing | 7.1 to 7.7 |

## Done when
- `.kiro/coroner-scope.json` exists with the credit-fees sample paths.
- `coroner/hooks.py` implements gate and stop commands.
- `.kiro/agents/coroner-auditor.json` passes `kiro-cli agent validate`.
- README and product.md have the exact wording.
- Tests pass with `.venv/bin/pytest -q tests/test_hooks.py`.
