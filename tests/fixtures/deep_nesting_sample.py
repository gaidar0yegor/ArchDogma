"""Fixture — Python functions with known nesting depths.

Used by end-to-end tests for the deep-nesting detector.
Comments below mark the depth of each body-statement position so test
expectations match the AST reality.
"""


def shallow(x):
    # max depth = 1 (body of single `if`)
    if x:
        return x
    return 0


def three_deep(x, y, z):
    # max depth = 3. Below default threshold of 4 — should NOT be flagged.
    if x:
        if y:
            if z:
                return 1
    return 0


def five_deep_mixed(order, user, config):
    # max depth = 5 with mixed control flow. ABOVE threshold — should flag.
    if order is not None:               # depth 0
        for item in order.items:        # depth 1 (body of outer if)
            if user is not None:        # depth 2 (body of for)
                while user.is_active:   # depth 3 (body of if)
                    try:                # depth 4 (body of while)
                        item.apply(config)  # depth 5 (body of try)
                        break
                    except ValueError:
                        break
    return True


def elif_chain_not_deep(x):
    # elif should NOT stack depth. Max depth stays at 1.
    if x == 1:
        return "one"
    elif x == 2:
        return "two"
    elif x == 3:
        return "three"
    elif x == 4:
        return "four"
    else:
        return "other"
