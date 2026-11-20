# Independence Track Results

| Port | Source | Verdict | Divergent cases | Run ID | Java SHA-256 | Branch exposure |
|------|--------|---------|-----------------|--------|--------------|-----------------|
| claude | Claude Opus 5.5 (Anthropic), run as a Claude Code subagent; not a Kiro agent. | ALIVE | 0 of 2000 | 0d1e698359fb | be82c6bdcd5d | sum 0.00 |
| hand-written | pending | pending | pending | pending | pending | pending |
| kiro | Kiro agent (kiro-cli, agent coroner-builder, model claude-sonnet-4.5) | ZOMBIE | 682 of 2000 | a4709d638df5 | 3f2b2d38933c | sum 3995184.38, max 2025606.03, 2 branches |
