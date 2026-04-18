"""Fixture — functions with known SLOC counts.

Used by end-to-end tests and manual CLI demos for the long-function detector.
Comments note the expected SLOC so test expectations stay tethered to AST reality.
"""


def short_and_sweet(x, y):
    # SLOC = 2 (two assignments). Far below threshold.
    result = x + y
    return result


def commented_but_short(x):
    # SLOC = 3 even though this function looks longer on screen —
    # blank lines, comments, and the docstring don't count.
    """Docstring that spans
    two lines but contributes zero SLOC.
    """

    # A comment describing the next step.
    a = x * 2

    # Another comment.
    b = a + 1

    return b


def long_and_deep(order, user, config):
    """Synthetic function that trips BOTH detectors at once.

    Designed as a regression fixture for the Tier 1 registry: exercises
    deep-nesting (depth 6, mixed control flow) AND long-function
    (83 SLOC — above the default 80 threshold). Neither branch is meaningful
    business logic — the shape is the point.
    """
    result = 0
    total = 0
    count = 0

    if order is not None:
        for item in order.items:
            if user is not None:
                while user.is_active:
                    try:
                        item.apply(config)
                        result = result + 1
                        total = total + item.value
                        count = count + 1
                        if count > 100:
                            break
                        if total > 1_000_000:
                            raise ValueError("overflow")
                        break
                    except ValueError:
                        result = -1
                        break

    if user is not None:
        a = user.a
        b = user.b
        c = user.c
        d = user.d
        e = user.e
        f = user.f
        g = user.g
        h = user.h
        i = user.i
        j = user.j
        k = user.k
        l = user.l  # noqa: E741 - fixture variable
        m = user.m
        n = user.n
        o = user.o
        p = user.p
        q = user.q
        r = user.r
        s = user.s
        t = user.t
        u = user.u
        v = user.v
        w = user.w
        x = user.x
        y = user.y
        z = user.z
        aa = user.aa
        bb = user.bb
        cc = user.cc
        dd = user.dd
        ee = user.ee
        ff = user.ff
        gg = user.gg
        hh = user.hh
        ii = user.ii
        jj = user.jj
        kk = user.kk
        ll = user.ll
        mm = user.mm
        nn = user.nn
        oo = user.oo
        pp = user.pp
        qq = user.qq
        rr = user.rr
        ss = user.ss
        tt = user.tt
        uu = user.uu
        vv = user.vv
        ww = user.ww
        xx = user.xx
        yy = user.yy
        zz = user.zz
        a1 = user.a1
        b1 = user.b1
        c1 = user.c1
        d1 = user.d1
        result = result + a + b + c + d + e + f + g + h + i + j + k + l + m
        result = result + n + o + p + q + r + s + t + u + v + w + x + y + z
        result = result + aa + bb + cc + dd + ee + ff + gg + hh + ii + jj
        result = result + kk + ll + mm + nn + oo + pp + qq + rr + ss + tt
        result = result + uu + vv + ww + xx + yy + zz + a1 + b1 + c1 + d1

    return result, total, count
