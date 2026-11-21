"""Case generator for the CardDemo CBACT04C sample (generator_script of schema.json).

Called by the engine as generate_cases(schema, rng, num_cases). Every draw
comes from rng.random() through draw_int (no other source of randomness), so
the same seed gives the same cases file byte for byte.

The generator only builds inputs. It never computes what the COBOL program
will do: expected results come only from running the harness.

What the cases cover (each case is one row of the harness input contract):

- 1 to 5 accounts with distinct ids in no particular slot order. CBACT04C
  reads the category balances in key order (account id, type, category), not
  in slot order, so the processing order differs from the slot order.
- Category balances that are negative, zero and positive, 1 to 10 per case,
  several of them on the same account.
- Rates that are zero and non-zero.
- Account groups that have their own rate for the needed type and category,
  groups that fall back to the DEFAULT group, and (in about one case out of
  twelve) a needed type and category with neither: CBACT04C abends, exit 231.
- Accounts without a card cross-reference record. In 1110-GET-XREF-DATA the
  INVALID KEY branch only displays "ACCOUNT NOT FOUND"; the status check that
  follows then treats the non-"00" status as an error and calls the abend
  routine, so the run ends with exit 231 as well.
- A category balance that points at an unused account slot (account 0, no
  record in the account file): the account read fails and the run abends.
- The last account of a run: CBACT04C never adds its interest to its balance
  (see PROBE.md). Every case with at least one category balance exercises
  that; cases with a single account update no balance at all.

Amounts stay inside their PIC limits (balances up to 9 integer digits, rates
up to 99.99), so no case overflows a field: overflow is not what this sample
audits.
"""

from coroner.gen import draw_int, generate_case_id

ACCOUNT_SLOTS = 5
CATBAL_SLOTS = 10
RATE_SLOTS = 20

GROUPS = ["GROUP01", "GROUP02", "GROUP03", "SILVER", "GOLD", "DEFAULT"]
GROUP_WEIGHTS = [20, 20, 15, 15, 10, 16]
TYPES = ["01", "02", "03", "04"]
CATEGORIES = [1, 2, 3, 4, 5, 6]

# Integer digits of a drawn amount, 1 to 9: mostly small, a few very large.
DIGIT_WEIGHTS = [15, 20, 20, 20, 12, 8, 3, 1.5, 0.5]


def weighted(rng, weights):
    """Index drawn with the given weights."""
    point = rng.random() * sum(weights)
    for index, weight in enumerate(weights):
        point -= weight
        if point < 0:
            return index
    return len(weights) - 1


def pick(rng, items):
    return items[draw_int(rng, 0, len(items) - 1)]


def number_with_digits(rng, digits):
    value = draw_int(rng, 1, 9)
    for _ in range(digits - 1):
        value = value * 10 + draw_int(rng, 0, 9)
    return value


def money(cents):
    sign = "-" if cents < 0 else ""
    return f"{sign}{abs(cents) // 100}.{abs(cents) % 100:02d}"


def amount(rng, weights):
    """Amount text; weights are for (negative, zero, positive)."""
    kind = weighted(rng, weights)
    if kind == 1:
        return "0.00"
    digits = weighted(rng, DIGIT_WEIGHTS) + 1
    cents = number_with_digits(rng, digits) * 100 + draw_int(rng, 0, 99)
    return money(-cents if kind == 0 else cents)


def rate(rng):
    """Annual rate text: zero, usual (0.01 to 36.00) or high (36.01 to 99.99)."""
    kind = weighted(rng, [25, 70, 5])
    if kind == 0:
        return "0.00"
    if kind == 1:
        return money(draw_int(rng, 1, 3600))
    return money(draw_int(rng, 3601, 9999))


def shuffled(rng, items):
    items = list(items)
    for i in range(len(items) - 1, 0, -1):
        j = draw_int(rng, 0, i)
        items[i], items[j] = items[j], items[i]
    return items


def empty_case(case_id):
    row = {"CASE-ID": case_id}
    for i in range(1, ACCOUNT_SLOTS + 1):
        row[f"ACCT-ID-{i}"] = 0
        row[f"ACCT-GROUP-ID-{i}"] = ""
        row[f"ACCT-CURR-BAL-{i}"] = "0.00"
        row[f"ACCT-CURR-CYC-CREDIT-{i}"] = "0.00"
        row[f"ACCT-CURR-CYC-DEBIT-{i}"] = "0.00"
        row[f"XREF-CARD-NUM-{i}"] = ""
        row[f"XREF-EXISTS-{i}"] = ""
    for i in range(1, CATBAL_SLOTS + 1):
        row[f"CATBAL-ACCT-INDEX-{i}"] = 0
        row[f"CATBAL-TYPE-{i}"] = ""
        row[f"CATBAL-CAT-{i}"] = 0
        row[f"CATBAL-BAL-{i}"] = "0.00"
    for i in range(1, RATE_SLOTS + 1):
        row[f"RATE-GROUP-{i}"] = ""
        row[f"RATE-TYPE-{i}"] = ""
        row[f"RATE-CAT-{i}"] = 0
        row[f"RATE-VALUE-{i}"] = "0.00"
    return row


def parm_date(rng):
    return f"{draw_int(rng, 2020, 2030)}-{draw_int(rng, 1, 12):02d}-{draw_int(rng, 1, 28):02d}"


def make_accounts(rng):
    """1 to 5 accounts: id, group, balances, card number, cross-reference flag."""
    count = 1 + weighted(rng, [15, 30, 25, 15, 15])
    ids, cards, accounts = set(), set(), []
    for _ in range(count):
        acct_id = 0
        while acct_id == 0 or acct_id in ids:
            acct_id = number_with_digits(rng, draw_int(rng, 1, 11))
        ids.add(acct_id)
        card = ""
        while card == "" or card in cards:
            card = "4" + str(number_with_digits(rng, 15))
        cards.add(card)
        group = "" if rng.random() < 0.04 else GROUPS[weighted(rng, GROUP_WEIGHTS)]
        accounts.append({
            "id": acct_id,
            "group": group,
            "bal": amount(rng, [30, 10, 60]),
            "credit": amount(rng, [0, 20, 80]),
            "debit": amount(rng, [0, 20, 80]),
            "card": card,
            "xref": rng.random() >= 0.03,
        })
    return accounts


def make_catbals(rng, account_count):
    """Distinct (account slot, type, category) keys with signed balances."""
    count = 1 + weighted(rng, [5, 8, 10, 12, 14, 14, 14, 10, 8, 5])
    point_at_empty_slot = account_count < ACCOUNT_SLOTS and rng.random() < 0.03
    catbals, keys = [], set()
    for n in range(count):
        for _ in range(20):
            slot = draw_int(rng, 1, account_count)
            if point_at_empty_slot and n == 0:
                slot = draw_int(rng, account_count + 1, ACCOUNT_SLOTS)
            key = (slot, pick(rng, TYPES), pick(rng, CATEGORIES))
            if key not in keys:
                keys.add(key)
                catbals.append({"key": key, "bal": amount(rng, [25, 10, 65])})
                break
    return catbals


def make_rates(rng, accounts, catbals):
    """Rate rows for the needed (group, type, category) keys, as {key: value}."""
    needed = []
    for catbal in catbals:
        slot, type_cd, cat = catbal["key"]
        if slot <= len(accounts):
            key = (accounts[slot - 1]["group"], type_cd, cat)
            if key not in needed:
                needed.append(key)
    # About one case in twelve has one needed type and category with no rate at all.
    no_rate = pick(rng, needed) if needed and rng.random() < 0.08 else None
    rates = {}
    for group, type_cd, cat in needed:
        if no_rate is not None and (type_cd, cat) == no_rate[1:]:
            continue
        mode = weighted(rng, [50, 35, 15])  # own rate, DEFAULT only, both
        if mode != 1 and group != "":
            rates[(group, type_cd, cat)] = rate(rng)
        if mode != 0 or group == "":
            rates[("DEFAULT", type_cd, cat)] = rate(rng)
    # Rates of other groups, types or categories that must not be picked up.
    for _ in range(draw_int(rng, 0, 3) if rng.random() < 0.4 else 0):
        key = (pick(rng, GROUPS), pick(rng, TYPES), pick(rng, CATEGORIES))
        if len(rates) < RATE_SLOTS and key not in rates and (no_rate is None or key[1:] != no_rate[1:]):
            rates[key] = rate(rng)
    return rates


def generate_cases(schema, rng, num_cases):
    cases = []
    for index in range(1, num_cases + 1):
        row = empty_case(generate_case_id(index, 10))
        row["PARM-DATE"] = parm_date(rng)
        accounts = make_accounts(rng)
        for slot, acct in enumerate(accounts, start=1):
            row[f"ACCT-ID-{slot}"] = acct["id"]
            row[f"ACCT-GROUP-ID-{slot}"] = acct["group"]
            row[f"ACCT-CURR-BAL-{slot}"] = acct["bal"]
            row[f"ACCT-CURR-CYC-CREDIT-{slot}"] = acct["credit"]
            row[f"ACCT-CURR-CYC-DEBIT-{slot}"] = acct["debit"]
            row[f"XREF-CARD-NUM-{slot}"] = acct["card"] if acct["xref"] else ""
            row[f"XREF-EXISTS-{slot}"] = "Y" if acct["xref"] else "N"
        catbals = make_catbals(rng, len(accounts))
        for slot, catbal in enumerate(catbals, start=1):
            row[f"CATBAL-ACCT-INDEX-{slot}"] = catbal["key"][0]
            row[f"CATBAL-TYPE-{slot}"] = catbal["key"][1]
            row[f"CATBAL-CAT-{slot}"] = catbal["key"][2]
            row[f"CATBAL-BAL-{slot}"] = catbal["bal"]
        rates = make_rates(rng, accounts, catbals)
        for slot, (key, value) in enumerate(shuffled(rng, rates.items()), start=1):
            row[f"RATE-GROUP-{slot}"] = key[0]
            row[f"RATE-TYPE-{slot}"] = key[1]
            row[f"RATE-CAT-{slot}"] = key[2]
            row[f"RATE-VALUE-{slot}"] = value
        cases.append(row)
    return cases
