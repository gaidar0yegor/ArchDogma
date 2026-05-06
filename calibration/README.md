# Calibration sandbox

Experimental subdirectory. **Not part of v0.1 ArchDogma.**
Does not break Function Probe, does not break Catalog, pulls no dependencies
into the main codebase.

## Why

Before building any runtime observation tool (working name: Orchestra),
we need **ground truth for the tool itself**. Otherwise the tool will
produce pretty numbers and we'll never know if it's seeing real gaps
between idle and loaded runs, or hallucinating.

The calibration repo is 5 known-in-advance cases:
- 4 cases with **planted pathologies** (quadratic, GIL, leak, lazy I/O)
- 1 case that **looks pathological but is correct** (false-positive trap)

The tool passes calibration if:
1. It sees 3–4 of the first four cases (produces a non-trivial delta)
2. It **stays silent** or produces a small delta on the fifth

If it fails in either direction — the tool is not ready for real repos.

## Structure

- `bugs.py` — 5 pre-planned functions with docstrings (what they do, what load exposes)
- `expected_signatures.md` — for each function, what an honest finding should look like
- `runner.py` — minimal runner: idle vs stressed via cProfile, prints delta

## Acknowledged blind spots (do not delete)

- **Sampling and short functions.** cProfile counts all calls but is not ideal for
  nanosecond-scale functions. py-spy (sampling) is even worse. This is a
  limitation of the approach.
- **Baseline non-determinism.** Two idle runs give different results due to GC,
  OS scheduling, and warm-up. Use 3+ repetitions; watch delta stability,
  not a single number.
- **External-process stress ≠ GIL stress.** A background busy-loop in a separate
  process pressures OS CPU. Intra-process contention for the GIL is a different
  class of load. For case #2 (GIL) this matters: the runner compares wall-time
  and CPU-time rather than relying solely on an external stressor.
- **Pattern-specific bugs.** If a bug only manifests on a specific input shape
  rather than general load — this tool will not catch it. This is a
  limitation of the approach, not the implementation.

## How to run

```
cd /path/to/ArchDogma
python calibration/runner.py
```

Dependencies: stdlib only (`cProfile`, `pstats`, `multiprocessing`,
`tracemalloc`). No py-spy, no numpy, no third-party packages.

## What the runner does **not** do

- Does not diagnose. Prints only observable numbers.
- Does not say "this is a bug". Says "delta = N×".
- Does not decide whether the tool passes calibration or not.
  That is the human's job, reading the table and comparing with `expected_signatures.md`.
