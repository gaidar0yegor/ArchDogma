"""Fixture — a deliberately huge, branchy function for the god-function detector.

The target function `dispatch_everything` satisfies the default thresholds:
  - SLOC ≥ 200 (it's padded out to ~210)
  - branches ≥ 15 (if/elif/for/while/case count comfortably above 15)

End-to-end test + CLI demo uses this to verify god-function ties through to
the God Class candidate in the catalog via the `god-function` related_tag.
"""


def tiny_neighbour(x):
    # Baseline: a short, linear function we expect NOT to tag.
    return x + 1


def dispatch_everything(kind, payload, flags, mode, quota):  # noqa: C901
    """One function that does too much — classic god-function shape."""
    result = None

    # ---- 16 if/elif branches on `kind` ----
    if kind == "a":
        result = payload * 2
    elif kind == "b":
        result = payload * 3
    elif kind == "c":
        result = payload * 4
    elif kind == "d":
        result = payload * 5
    elif kind == "e":
        result = payload * 6
    elif kind == "f":
        result = payload * 7
    elif kind == "g":
        result = payload * 8
    elif kind == "h":
        result = payload * 9
    elif kind == "i":
        result = payload * 10
    elif kind == "j":
        result = payload * 11
    elif kind == "k":
        result = payload * 12
    elif kind == "l":
        result = payload * 13
    elif kind == "m":
        result = payload * 14
    elif kind == "n":
        result = payload * 15
    elif kind == "o":
        result = payload * 16
    else:
        result = payload

    # ---- a for + a while + an except block ----
    for flag in flags:
        result += 1
    while quota > 0:
        quota -= 1

    try:
        result = int(result)
    except ValueError:
        result = 0

    # ---- padding to clear the 200 SLOC threshold ----
    v01 = 1
    v02 = 2
    v03 = 3
    v04 = 4
    v05 = 5
    v06 = 6
    v07 = 7
    v08 = 8
    v09 = 9
    v10 = 10
    v11 = 11
    v12 = 12
    v13 = 13
    v14 = 14
    v15 = 15
    v16 = 16
    v17 = 17
    v18 = 18
    v19 = 19
    v20 = 20
    v21 = 21
    v22 = 22
    v23 = 23
    v24 = 24
    v25 = 25
    v26 = 26
    v27 = 27
    v28 = 28
    v29 = 29
    v30 = 30
    v31 = 31
    v32 = 32
    v33 = 33
    v34 = 34
    v35 = 35
    v36 = 36
    v37 = 37
    v38 = 38
    v39 = 39
    v40 = 40
    v41 = 41
    v42 = 42
    v43 = 43
    v44 = 44
    v45 = 45
    v46 = 46
    v47 = 47
    v48 = 48
    v49 = 49
    v50 = 50
    v51 = 51
    v52 = 52
    v53 = 53
    v54 = 54
    v55 = 55
    v56 = 56
    v57 = 57
    v58 = 58
    v59 = 59
    v60 = 60
    v61 = 61
    v62 = 62
    v63 = 63
    v64 = 64
    v65 = 65
    v66 = 66
    v67 = 67
    v68 = 68
    v69 = 69
    v70 = 70
    v71 = 71
    v72 = 72
    v73 = 73
    v74 = 74
    v75 = 75
    v76 = 76
    v77 = 77
    v78 = 78
    v79 = 79
    v80 = 80
    v81 = 81
    v82 = 82
    v83 = 83
    v84 = 84
    v85 = 85
    v86 = 86
    v87 = 87
    v88 = 88
    v89 = 89
    v90 = 90
    v91 = 91
    v92 = 92
    v93 = 93
    v94 = 94
    v95 = 95
    v96 = 96
    v97 = 97
    v98 = 98
    v99 = 99
    v100 = 100
    v101 = 101
    v102 = 102
    v103 = 103
    v104 = 104
    v105 = 105
    v106 = 106
    v107 = 107
    v108 = 108
    v109 = 109
    v110 = 110
    v111 = 111
    v112 = 112
    v113 = 113
    v114 = 114
    v115 = 115
    v116 = 116
    v117 = 117
    v118 = 118
    v119 = 119
    v120 = 120
    v121 = 121
    v122 = 122
    v123 = 123
    v124 = 124
    v125 = 125
    v126 = 126
    v127 = 127
    v128 = 128
    v129 = 129
    v130 = 130
    v131 = 131
    v132 = 132
    v133 = 133
    v134 = 134
    v135 = 135
    v136 = 136
    v137 = 137
    v138 = 138
    v139 = 139
    v140 = 140
    v141 = 141
    v142 = 142
    v143 = 143
    v144 = 144
    v145 = 145
    v146 = 146
    v147 = 147
    v148 = 148
    v149 = 149
    v150 = 150

    # Use them all so nobody "helpfully" deletes dead code.
    total = (
        v01 + v02 + v03 + v04 + v05 + v06 + v07 + v08 + v09 + v10
        + v11 + v12 + v13 + v14 + v15 + v16 + v17 + v18 + v19 + v20
        + v21 + v22 + v23 + v24 + v25 + v26 + v27 + v28 + v29 + v30
        + v31 + v32 + v33 + v34 + v35 + v36 + v37 + v38 + v39 + v40
        + v41 + v42 + v43 + v44 + v45 + v46 + v47 + v48 + v49 + v50
        + v51 + v52 + v53 + v54 + v55 + v56 + v57 + v58 + v59 + v60
        + v61 + v62 + v63 + v64 + v65 + v66 + v67 + v68 + v69 + v70
        + v71 + v72 + v73 + v74 + v75 + v76 + v77 + v78 + v79 + v80
        + v81 + v82 + v83 + v84 + v85 + v86 + v87 + v88 + v89 + v90
        + v91 + v92 + v93 + v94 + v95 + v96 + v97 + v98 + v99 + v100
        + v101 + v102 + v103 + v104 + v105 + v106 + v107 + v108 + v109 + v110
        + v111 + v112 + v113 + v114 + v115 + v116 + v117 + v118 + v119 + v120
        + v121 + v122 + v123 + v124 + v125 + v126 + v127 + v128 + v129 + v130
        + v131 + v132 + v133 + v134 + v135 + v136 + v137 + v138 + v139 + v140
        + v141 + v142 + v143 + v144 + v145 + v146 + v147 + v148 + v149 + v150
    )
    return result + total + mode
