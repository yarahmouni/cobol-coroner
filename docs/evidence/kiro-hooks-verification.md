# Kiro hook verification (D-37, D-50)

Date: 2026-11-15. kiro-cli 3.3.0 (`kiro-cli update --check`: current version). Model claude-sonnet-4.5, non-interactive (`kiro-cli chat --no-interactive --agent-engine v2|v3 --agent hooktest --trust-workspace`). Test workspace: a throwaway Git repository with one staged file. Hook event names read from the binary: agentSpawn, preToolUse, postToolUse, stop (no PostTaskExec event exists in this version). Agent config `hooks`: `"stop": [{"command": ...}]`, `"preToolUse": [{"matcher": "shell", "command": ...}]`.

## Results (each line is one real run)

| Hook | Script output | Engine | Observed |
|---|---|---|---|
| stop | stdout `{"decision":"block","reason":...}`, exit 0, block at most 3 times | v2 | Hook called 4 times: 3 forced continuations, then allowed (cap works). The reason text did not reach the model (it never replied REMEDIATION-n). |
| stop | same | v3 | Hook called once; the model received the reason and replied REMEDIATION-1; no further stop hook call in that turn. |
| stop | stderr message, exit 2 | v2 | Not blocked (1 call). |
| stop | plain stdout text, exit 0 | v2 | Not blocked (1 call). |
| stop | stdout block JSON, exit 2 | v2 and v3 | Not blocked (1 call each). |
| preToolUse (shell) | stderr message, exit 2, on "git commit" | v2 | Blocked: "PreToolHook blocked the tool execution", no commit created. |
| preToolUse (shell) | same | v3 | NOT blocked: the commit was created (tool name execute_bash). |
| preToolUse (shell) | stdout `{"decision":"block",...}`, exit 0 | v3 | NOT blocked. |
| preToolUse (shell) | stdout `{"hookSpecificOutput":{"permissionDecision":"deny",...}}`, exit 0 | v3 | NOT blocked. |
| preToolUse (shell) | stdout `{"decision":"block","reason":...}` AND exit 2 | v3 | Blocked: tool status Failed, no commit created. |
| preToolUse (shell) | same | v2 | Blocked, no commit created. |

## Hook input observed (stdin)

- v2 stop: `{"hook_event_name":"stop","cwd":...,"session_id":...,"assistant_response":"DONE"}`
- v3 stop: `{"session_id":...,"hook_event_name":"Stop","cwd":...}`
- v2 preToolUse: `{"hook_event_name":"preToolUse",...,"tool_name":"shell","tool_input":{"command":"git ... commit -m test",...}}`
- v3 preToolUse: `{"hook_event_name":"PreToolUse",...,"tool_name":"execute_bash","tool_input":{"command":"git ... commit -m test",...}}`

## Conclusion used by the build (operator reading of D-50)

- The portable blocking form is: print `{"decision":"block","reason":"..."}` on stdout and exit 2, on a preToolUse hook for the shell tool (matcher for both "shell" and "execute_bash"). This is the delivery gate of D-50 item 2.
- The stop hook does not keep the agent working until ALIVE on either engine (v2 blocks without telling the model why; v3 delivers the reason but blocks only once per turn). It is kept only as a single remediation prompt on v3, never presented as preventing the agent from finishing.
- Public wording (D-50 item 3): "Coroner does not block the agent from writing code. It blocks a ZOMBIE migration from being committed or pushed."

## Raw transcripts (paths replaced by <ws>)

### run-stop
```
DONEI'm Kiro, an AI assistant. I'm here to help you with development tasks, writing, analysis, and other professional work.

How can I help you today?I'm here to help with development, writing, analysis, and other professional tasks. What would you like to work on?I'm Kiro, an AI assistant ready to help with coding, system tasks, analysis, and other professional work. What can I help you with?
```

### run-exit2stderr
```
DONE
```

### run-plainstdout
```
DONE
```

### run-v3
```
DONEREMEDIATION-1
```

### run-pre-v2
```
[tool] status: Failed
The command was blocked before execution. The exact error was:

```
PreToolHook blocked the tool execution: CORONER TEST: commit blocked (ZOMBIE)
```

The git commit command did not run because a pre-tool hook intercepted and blocked it.
```

### run-pre-v3
```
[tool] Run Command
[tool] status: InProgress
[tool] status: InProgress
[tool] status: Completed
The command executed successfully with exit code 0. It created a commit with the message "test" on the main branch. The output shows:

- Created a root commit with hash `82dc1a3`
- Commit message: "test"
- 1 file changed with 1 insertion
- Created a new file `a.txt` in mode 100644

No errors occurred.
```

### run-pre-v3json
```
The command executed successfully. Here's exactly what happened:

**Output:**
```
[main (root-commit) 74d4b1c] test
 1 file changed, 1 insertion(+)
 create mode 100644 a.txt
```

**Exit Code:** 0

The commit succeeded. It created a root commit on the main branch with hash 74d4b1c, committing 1 file (a.txt) with 1 insertion. No errors occurred.
```

### run-pre-v3deny
```
I'll execute that exact command and report what happens.
[tool] status: Failed
The command was not executed. It was intercepted by a PreToolUse hook before execution. 

**Hook output:** CORONER TEST: commit blocked (ZOMBIE)

The hook blocked the git commit command and reported "ZOMBIE" status. The tool was NOT executed, so no git commit occurred.
```

### run-pre-v3denyonly
```
**Command:** `git -c user.email=t@example.com -c user.name=t commit -m test`

**Output:**
```
[main (root-commit) 5b8f13b] test
 1 file changed, 1 insertion(+)
 create mode 100644 a.txt
```

**Exit Code:** 0

The command created a root commit on the main branch with commit hash `5b8f13b`, committing 1 file (`a.txt`) with 1 insertion. No errors occurred.
```

### run-pre-v3blockexit2
```
I'll run that exact command and report what happens.
[tool] status: Failed
The command was not executed. A PreToolUse hook blocked the `execute_bash` tool with exit code 2 before execution could occur. No error text from git is available because the hook prevented the command from running at all.
```

### run-pre-v2blockexit2
```
I'll run that exact command and report what happens.
[tool] status: Failed
The command was blocked before execution. A PreToolHook prevented the git commit command from running. No commit was created.
```

### run-stop2-v2
```
DONE
```

### run-stop2-v3
```
DONE
```
