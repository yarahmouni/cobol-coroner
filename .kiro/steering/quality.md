---
inclusion: always
---

# Quality

- Shortest readable code. No abstraction without a second real use. Few dependencies, all compatible with Apache-2.0.
- Never leave helper or wrapper scripts. Temporary files go under build/ and are never committed. A new file at the repository root or in scripts/ must first be listed in docs/architecture.md (Repository layout); the pre-commit guard enforces it.
- Business logic lives in `coroner/` modules, never in API routes, MCP handlers or the UI.
- Fixed random seed everywhere; same inputs give the same verdict.
- Every module has unit tests. Property-based tests for the normalizer and comparator.
- End-to-end tests: correct Java must be ALIVE, HALF_EVEN Java must be ZOMBIE.
- CI on GitHub blocks merges when a test fails. A step is done only with green tests.
- Validate every input server-side; size and time limits on every run.
- No secrets in code. Secret scan in CI.
- Makefile targets: `demo`, `test`, `zombie`, `serve`.
