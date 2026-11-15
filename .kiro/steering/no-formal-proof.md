---
inclusion: always
---

# Honest claims

- Never write "proven equivalent", "formal proof" or "guaranteed".
- ALIVE wording: "PASS: business behavior preserved on N cases" (detail line may also show "0 divergence found on N cases").
- ZOMBIE wording: "FAIL: business behavior diverged on M cases".
- Coverage wording: "Paragraph coverage X/Y" and "Branch coverage (Coroner definition) X/Y". Coroner definition: a branch is covered when its first statement appears in the trace of at least one case.
- Always show: "Validated under GnuCOBOL 3.x".
- AI explanations are labeled "AI explanation (advisory, does not affect verdict)". A cached explanation is labeled "Cached AI explanation, generated with Bedrock on [date]".
- Never claim a feature is "first", "unique" or "novel". Present the Coroner Certificate, the minimal failing case with its JUnit regression test (ZombieRegressionTest.java) and the suggested fix as a combination for auditing Java 17 migrations (D-23).
- The Coroner Certificate is a reproducible run record, never a guarantee: it states the verdict sub-label, N cases, the seed, tool versions and input hashes (D-24). A suggested fix is labeled "Suggested fix (deterministic, from the fault catalog)" and is never applied by Coroner (D-26).
