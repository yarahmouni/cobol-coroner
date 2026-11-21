# CardDemo CBACT04C: Kiro-made Java port, evidence

The Java port in samples/carddemo-cbact04c/java/Cbact04c.java was written by a Kiro agent (kiro-cli 3.5.0, agent coroner-builder, model claude-sonnet-5.5) in one fresh session on 2026-11-21. It is committed exactly as the agent wrote it (SHA-256 e16d5d6ce285efb81eafb532a8803a9fda6c43214e1d1ecfc26178c39eda08ea).

Isolation: the session ran in a separate Git worktree from which every tracked file had been deleted, including .kiro/ (specs, steering, skills, project agents), docs/, README.md and samples/. Its only inputs were copies in port-input/: the adapted COBOL programs, the upstream copybooks, schema.json and one example row with the output the COBOL harness produced for it. inputs.sha256 lists their hashes; they were checked unchanged after the session. The files that describe the audit findings (PROBE.md, CHANGES.md, the spec, generator.py) were not available. sandbox-files-after-port.txt lists every file in the sandbox after the session.

Files:
- prompt.txt: the exact prompt.
- transcript.txt: the full session output (colour codes removed, nothing else changed).
- inputs.sha256: hashes of the inputs.
- audit-200-seed42-image.txt: the operator's audit of the unchanged port in the project image (coroner verify, 200 cases, seed 42): ALIVE, 0 of 200 cases divergent, certificate replayed VALID.

ALIVE means no behavioral difference across the tested scenarios; it is not a certification for all inputs.
