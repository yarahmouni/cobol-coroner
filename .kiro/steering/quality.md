---
inclusion: always
---

# Quality

- Shortest readable code. No abstraction without a second real use. Few dependencies, all compatible with Apache-2.0.
- Business logic lives in `lazarus/` modules, never in API routes, MCP handlers or the UI.
- Fixed random seed everywhere; same inputs give the same verdict.
- Every module has unit tests. Property-based tests for the normalizer and comparator.
- End-to-end tests: correct Java must be VIVANT, HALF_EVEN Java must be ZOMBIE.
- CI on GitHub blocks merges when a test fails. A step is done only with green tests.
- Validate every input server-side; size and time limits on every run.
- No secrets in code. Secret scan in CI.
- Makefile targets: `demo`, `test`, `zombie`, `serve`.
