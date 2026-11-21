# Probe dataset with non-zero balances

This dataset contains a few accounts with non-zero transaction category balances to verify interest computation.

## Accounts:
- 00000000001: Group A000000000, positive balances
- 00000000002: Group A000000000, negative balance (reversal)
- 00000000003: Group A000000001, different rate
- 00000000004: Group A000000002, zero rate category
- 00000000005: Group B000000000, missing from discgrp (DEFAULT fallback)
