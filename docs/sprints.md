# Sprints (start 2026-11-14, submission 2026-12-03)

Deadline: 2026-12-04 14:00 PT (23:00 Paris). Kiro credits request: before 2026-12-01 12:00 PT (21:00 Paris).

## S0 Foundations (14 to 17 Nov)
- Toolchain installed: Kiro, Docker, GnuCOBOL 3.2, JDK 17, Python 3.12.
- `-ftraceall` tested on a toy program; trace is parseable.
- Minimal MCP server (`get_verdict` only) discovered and called by Kiro.
- Synthetic COBOL program compiles and writes CSV.

Acceptance: `cobc` compiles the sample, the trace file lists executed lines, Kiro lists and calls `get_verdict`.

## S1 Engine (18 to 23 Nov)
- Java 17 version written with Kiro (specs + steering).
- Copybook parser, case generator, runners (one JVM for all cases), normalizer, comparator, CLI verdict.
- Git pre-commit hook in fast mode (500 cases, fixed seed, under 20 s).

Acceptance: 2,000 cases give VIVANT with the correct Java and ZOMBIE with the HALF_EVEN variant. Coverage decision (D-07) taken on 23 Nov.

## S2 Diagnosis and interface (24 to 30 Nov)
- Coverage report, failure report, four MCP tools, Kiro PreToolUse hook.
- Minimal one-screen UI, Docker image, Cloudflare Tunnel.
- Review on 30 Nov: if green, build the optional AI explanation (D-13).

Acceptance: hook blocks the bugged commit; UI shows VIVANT then ZOMBIE with diagnosis.

## S3 Delivery (1 to 3 Dec)
- Fixes only, README, Kiro write-up, blog post, social post, 60 s video, Devpost submission on 3 Dec.

## Success criteria
- 2,000 cases in under 60 s.
- 0 false ZOMBIE on 10 runs of the correct Java.
- 0 false VIVANT on 10 runs of the bugged Java.
- Git hook under 20 s.
- UI response under 2 s.
- Paragraph coverage at least 90 %.
