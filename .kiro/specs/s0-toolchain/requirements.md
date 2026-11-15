# Requirements: S0 toolchain and MCP smoke test

## Introduction
Prove, before building the engine, that the three risky foundations work: GnuCOBOL 3.2 tracing, a Docker image with GnuCOBOL and JDK 17, and a local MCP server discovered by Kiro.

### Requirement 1: GnuCOBOL trace
**User Story:** As the developer, I want a parseable execution trace so that coverage can be computed.

#### Acceptance Criteria
1. WHEN a toy COBOL program with one IF/ELSE is compiled with `cobc -x -ftraceall` and run with tracing enabled THE SYSTEM SHALL write a trace that lists the executed statements with their line numbers.
2. WHEN the trace is parsed THE SYSTEM SHALL return the set of executed line numbers.
3. IF the trace does not contain line numbers THEN the fallback in decision D-07 (DISPLAY markers) SHALL be recorded in `docs/decisions.md`.

### Requirement 2: Docker image
**User Story:** As a judge, I want one reproducible image so that I can run the demo anywhere.

#### Acceptance Criteria
1. THE SYSTEM SHALL build one image containing GnuCOBOL 3.2, JDK 17 and Python 3.12, with pinned versions.
2. WHEN `make smoke` runs in the container THE SYSTEM SHALL compile and run the toy COBOL program and a toy Java program.
3. THE SYSTEM SHALL run as a non-root user.

### Requirement 3: MCP smoke test
**User Story:** As a Kiro user, I want Kiro to call Coroner through MCP.

#### Acceptance Criteria
1. THE SYSTEM SHALL expose a local MCP server with one tool, `get_verdict`, returning a fixed JSON verdict.
2. WHEN `.kiro/settings/mcp.json` is configured THE Kiro agent SHALL list `get_verdict` and call it successfully.
3. The working `mcp.json` content SHALL be committed and recorded in `docs/decisions.md`.
