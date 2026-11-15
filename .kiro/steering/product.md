---
inclusion: always
---

# Product

COBOL Coroner is the independent regression auditor for COBOL-to-Java migrations. It does not translate. It checks whether a migration kept the business behavior on N generated cases, and shows exactly where it broke.

- Coroner verifies a migration provided by the user. It never converts code.
- Rule: "AI accelerates. Coroner certifies." The ALIVE/ZOMBIE verdict is always deterministic and never depends on an AI model.
- Audience: banks and teams modernizing COBOL batch programs.
- Hackathon: Kiroween 2026, category Resurrection.
- Agent: coroner-auditor uses 7 MCP tools (run_differential_check, get_verdict, get_failure_report, get_detection_matrix, export_junit_test, generate_certificate, verify_certificate) and 3 skills (banking-trap-recognition, cobol-semantics-safety, coroner-audit-workflow).
- Hooks: Coroner does not block the agent from writing code. It blocks a ZOMBIE migration from being committed or pushed. The stop hook re-prompts the agent up to 3 times (v2 engine) or once per turn (v3 engine); it does not prevent the agent from finishing.
- All user-facing text, code comments and docs are in English.
- Never use the em dash character in any file.
- Every decision is logged in `docs/decisions.md` after a simulated vote, then validated by the owner.
- Other hackathon projects (competitors) are never named in the public repository (see public-repo.md). A competitor feature is never copied: a feature judged valuable gets a differentiated version or is skipped, after a simulated vote logged in docs/decisions.md.
