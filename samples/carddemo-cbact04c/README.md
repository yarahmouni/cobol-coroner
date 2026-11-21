# CardDemo CBACT04C Interest Calculation

Coroner audits a Kiro-generated Java port of one bounded interest-calculation path in AWS's open-source CardDemo sample.

**Uses AWS's open-source CardDemo sample (Apache 2.0). Not affiliated with or endorsed by AWS.**

Source: https://github.com/aws-samples/aws-mainframe-modernization-carddemo commit 59cc6c2fd7ebd7ef7925cad552a01a4b8b6e4d5e

See LICENSE and NOTICE for copyright and license information.

## Bounded path

Interest calculation loop (paragraphs 1000, 1050, 1100, 1110, 1200, 1200-A, 1300, 1300-B, 1400).

Formula: Interest = (Transaction Category Balance * Interest Rate) / 1200

## Adaptation

The upstream program is adapted for GnuCOBOL and deterministic testing:
- Timestamp generation made deterministic (parameter date + fixed time 12:00:00)
- CEE3ABD replaced with a stub that sets RETURN-CODE from the abend code
- VSAM indexed files loaded from text fixtures for each test

**This preserves the business logic under audit; it does not emulate z/OS VSAM.**

Every change is documented in CHANGES.md.

## Verdict interpretation

ALIVE: no behavioral difference across the tested scenarios; not a certification for all inputs.

ZOMBIE: Java diverged from COBOL on at least one test case.
