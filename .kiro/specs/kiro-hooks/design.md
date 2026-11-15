# Kiro hooks design

## Architecture

```
stdin (hook JSON) -> parse -> gate or stop command
                                 |
                                 v
                          load scope.json
                                 |
                                 v
                          find certificate (newest runs/*/certificate.json with matching hashes)
                                 |
                                 v
                          replay certificate (coroner.certificate.verify_certificate)
                                 |
                                 +-> ALIVE/valid: allow (exit 0, no output)
                                 +-> ZOMBIE/invalid: block (gate: exit 2 + JSON, stop: exit 0 + JSON, count)
                                 +-> missing: check staged (git diff --cached --name-only), block only if audited files staged
```

## Module structure

`coroner/hooks.py`:
- `parse_hook_input(stdin_text: str) -> dict`: parse v2 or v3 JSON.
- `load_scope(scope_path: str = ".kiro/coroner-scope.json") -> dict`: load the scope file.
- `find_certificate(scope: dict) -> Optional[str]`: find the newest certificate whose recorded hashes match the current files.
- `replay_certificate(cert_path: str) -> tuple[int, str, dict]`: call `python -m coroner verify cert_path`, return (exit_code, verdict_line, cert_data).
- `is_git_commit_push_merge(command: str) -> bool`: parse command words, return True if the command is `git commit`, `git push` or `git merge`.
- `get_staged_files() -> list[str]`: run `git diff --cached --name-only`, return the list.
- `is_audited_file_staged(scope: dict, staged: list[str]) -> bool`: check if COBOL or Java from the scope is staged.
- `build_block_message(cert_data: dict) -> str`: construct the block message with verdict, divergences, exposure and fix instruction.
- `gate_command(hook_input: dict) -> None`: preToolUse hook logic, exit 0 or exit 2 with JSON.
- `stop_command(hook_input: dict) -> None`: stop hook logic, exit 0 with or without JSON.
- `main()`: read stdin, parse args (gate or stop), dispatch.

## Key behaviors

### Gate (preToolUse)
1. Parse hook input (both v2 and v3 shapes).
2. Extract `tool_input.command`.
3. If not a git commit/push/merge: exit 0 silently.
4. Load scope, find certificate.
5. If certificate found: replay, check exit code.
   - Exit 0 (ALIVE valid): allow (exit 0 silently).
   - Exit 1 or 3 (ZOMBIE or invalid): block (stdout JSON + exit 2).
6. If certificate missing: check staged files.
   - If audited files staged: block (stdout JSON + exit 2).
   - Otherwise: allow (exit 0 silently).

### Stop
1. Parse hook input (both v2 and v3 shapes).
2. Extract `session_id`.
3. Load scope, find certificate.
4. If certificate found: replay, check exit code.
   - Exit 0 (ALIVE valid): allow (exit 0 silently).
   - Exit 1 or 3 (ZOMBIE or invalid): increment count, check limit.
     - Count <= 3: block (stdout JSON + exit 0).
     - Count > 3: write failure file, allow (exit 0 silently).
5. If certificate missing: check staged files.
   - If audited files staged: same count logic.
   - Otherwise: allow (exit 0 silently).

## Block message format

```
ZOMBIE: FAIL: business behavior diverged on N cases
Unreconciled branch exposure: not applicable (no group key in the schema)
Run get_failure_report and export_junit_test, fix the Java port, then run run_differential_check again.
```

When a group key is declared in the schema and the exposure metric exists in the certificate: replace "not applicable" with the measured values (sum, max, count, grand total match).

## Command parsing

Split the command string into words (shell-like splitting, respect quotes). Check if:
- words[0] == "git" and words[1] in ["commit", "push", "merge"]

Not a substring search (so "echo git commit" does not match).

## Certificate lookup

1. List all `runs/*/certificate.json`.
2. For each: load, extract recorded COBOL/Java/schema/copybook hashes.
3. Compute current hashes of the files in the scope.
4. Filter certificates where all hashes match.
5. Return the newest (by mtime).

## Count storage

`build/hooks/<session_id>.count`: plain text file with the count (1, 2, 3).
`build/hooks/<session_id>-failure.json`: failure record after 3 blocks.

## Testing strategy

Use temporary directories and git repositories. Mock the certificate module or write real certificates with the legacy variant. Feed both v2 and v3 JSON shapes on stdin. Assert exit codes and stdout.

## Done when
- All functions implemented.
- Agent config has two preToolUse hooks and one stop hook.
- Tests cover all cases (ignore, allow, block, staged, not staged, count limit).
