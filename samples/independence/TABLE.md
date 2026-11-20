# Independence Track Results

Environment: image coroner-local:latest (linux/amd64)

| Port | Source | Verdict | Divergent cases | Run ID | Java SHA-256 | Branch exposure | Same file as a repository Java port? |
|------|--------|---------|-----------------|--------|--------------|-----------------|--------------------------------------|
| Claude Opus 5.5 | Claude Opus 5.5 (Anthropic), run as a Claude Code subagent; not a Kiro agent. | ALIVE | 0 of 2000 | 0d1e698359fb | be82c6bdcd5d | sum 0.00 | no |
| hand-written by the author: pending | pending | pending | pending | pending | pending | pending | pending |
| Kiro agent, session 1 (rules in prompt, full repository readable) | Kiro agent (kiro-cli, agent coroner-builder, model claude-sonnet-4.5) | ZOMBIE | 682 of 2000 | a4709d638df5 | 3f2b2d38933c | sum 3995184.38, max 2025606.03, 2 branches | no |
| Kiro agent, fresh isolated session | Kiro agent (kiro-cli, agent coroner-builder, model claude-sonnet-4.5), fresh session | ALIVE | 0 of 2000 | 7af943198226 | 37fc82b6d5d6 | sum 0.00 | no |
