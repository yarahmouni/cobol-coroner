# Real Git pre-commit block, then allowed commit (priority 7), 2026-11-15

Scratch clone of the repository with `git config core.hooksPath .githooks`. The hook runs the guard, then `python -m coroner.hooks precommit`: it exports the STAGED version of the scope files (.kiro/coroner-scope.json) and runs the 500-case check (seed 42) on them.

## Blocked: HALF_EVEN port staged while the working tree holds the correct Java
```
$ (stage the HALF_EVEN port; working tree keeps the correct Java)
Generated HALF_EVEN variant: 3 replacements
  MM samples/credit-fees/java/CreditFees.java
$ git commit -m "Port with HALF_EVEN"
Commit blocked by Coroner: ZOMBIE: FAIL: business behavior diverged on 21 cases. See runs/aa7e43333e51/failure_report.json. Fix the Java port, then run run_differential_check again.
exit status: 1

```

## Allowed: corrected port (HALF_UP) with one added comment line staged
```
$ (corrected port with one added comment line, staged)
  M  samples/credit-fees/java/CreditFees.java
$ git commit -m "Port with HALF_UP"
Coroner pre-commit: ALIVE: PASS: business behavior preserved on 500 cases (Duration: 3.3 s)
[main 0bbcfc2] Port with HALF_UP
 1 file changed, 1 insertion(+)
exit status: 0
0bbcfc2 Port with HALF_UP
c4a93b4 demo: hooks in place
```

Note: an intermediate attempt where the corrected file equaled HEAD ended in "nothing to commit" (hook output: no audited file staged); it is omitted from the sequence above.
