# Decisions log

Panels are simulated (business users and architects). Each decision is validated by the project owner.

| ID | Date | Decision | Options considered | Reason |
|---|---|---|---|---|
| D-01 | 2026-11-14 | Build a new project for Kiroween 2026, category Resurrection | Reuse an existing project, new COBOL project | Rules require a new public open source project built with Kiro |
| D-02 | 2026-11-14 | Lazarus verifies a migration, it never converts | Converter, verifier | Lower demo risk; neutral toward AWS Transform, IBM, Claude, humans |
| D-03 | 2026-11-14 | Architecture B: one Docker container (GnuCOBOL 3.2, JDK 17, Python), FastAPI, HTML + htmx, JSON files in `runs/` | A static report, B single container, C Spring + React + PostgreSQL | Only option with a testable app that fits 3 weeks |
| D-04 | 2026-11-14 | Java 17 is the only target; BigDecimal with explicit scale; no double or float | Java, Python | Common banking migration target |
| D-05 | 2026-11-14 | Demo case: synthetic credit file fees and eligibility, with COMP-3 and ROUNDED | Several banking cases | Credible, bounded, shows the rounding trap |
| D-06 | 2026-11-14 | Demo bug: Java HALF_UP replaced by HALF_EVEN; about 100 divergences out of 2,000 expected | Other bugs | COBOL ROUNDED default is nearest away from zero; only ties with an even preceding digit diverge |
| D-07 | 2026-11-14 | Metrics: "Paragraph coverage" and "Branch coverage (Lazarus definition)"; fallback to Paragraphs + Statements if not reliable on 2026-11-23 | Standard branch coverage | Honest, reproducible metric |
| D-08 | 2026-11-14 | Lazarus case generator (PIC clauses, branches, rounding ties) separate from Hypothesis (random cases and properties) | Hypothesis only | Hypothesis does not understand PIC or COMP-3 |
| D-09 | 2026-11-14 | No numeric tolerance in comparison | Tolerance | A tolerance would hide the rounding bug |
| D-10 | 2026-11-14 | Kiro PreToolUse hook blocks agent actions; Git pre-commit hook blocks the real commit (500 cases, under 20 s) | Kiro hook only | A Kiro hook cannot block a Git commit |
| D-11 | 2026-11-14 | Public URL runs bundled samples only; uploads in local mode only; sandboxed container | Public uploads | Executing arbitrary code on a public URL is not acceptable (security, not voted) |
| D-12 | 2026-11-14 | Hosting: Cloudflare Tunnel on personal Ubuntu server; fallback Codespaces, `make demo`, video; available until 2027-01-29 | Cloud hosting | Rules require testing access until end of judging |
| D-13 | 2026-11-14 | AI: "AI accelerates, Lazarus certifies". Optional "Explain this failure" (advisory) via Bedrock + Claude, EU region, two-layer validation (deterministic checks, then Guardrails). Cached explanation on public URL, live call in local mode and video. Built only if the 2026-11-30 review is green | No AI, advisory AI, AI test generation | Verdict stays deterministic; AI test generation rejected (not reproducible) |
| D-14 | 2026-11-14 | Dev machine: macOS with Kiro and Docker; Ubuntu server for hosting | macOS, Windows, Ubuntu | Native Unix toolchain, no WSL friction, same Docker image everywhere |
| D-15 | 2026-11-14 | Plan validated by Claude and Perplexity (technical plan and AI plan) | | Cross review |
