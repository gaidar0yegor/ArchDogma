"""Fixture — functions with known parameter counts.

Used by end-to-end tests for the too-many-params detector.
Default threshold: 5. `self`/`cls` are excluded. `*args` and `**kwargs`
each count as one parameter.
"""


def lean(a, b, c):
    # 3 params — below threshold. Should NOT flag.
    return a + b + c


def on_the_line(a, b, c, d, e):
    # 5 params — at default threshold. SHOULD flag.
    return a + b + c + d + e


def varargs_counts_as_one(a, b, c, *rest):
    # 3 named + *rest → 4 params. Below threshold. Should NOT flag.
    return (a, b, c, rest)


def kitchen_sink(user_id, tenant_id, order, *items, discount=0, notify=True, **extras):
    # user_id, tenant_id, order + *items + discount, notify + **extras
    # = 3 + 1 + 2 + 1 = 7 params. SHOULD flag.
    _ = (user_id, tenant_id, order, items, discount, notify, extras)
    return None
