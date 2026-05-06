# Expected Signatures

Ground truth for the tool itself. For each of the 5 cases — what an honest
observer output should look like, what it should NOT claim, and how to tell
if the tool is lying.

Section format:
- **What the function does** (one line)
- **What load exposes it** (input size / churn / parallelism / external stress)
- **Expected metrics** (idle vs stressed — order of magnitude)
- **Honest finding** — what the output should look like
- **What NOT to claim** — red lines
- **Sign that the tool is lying** — when not to trust the output

---

## 1. `hidden_quadratic`

**What it does.** Deduplicates a list via `x in seen` on a growing list.
True complexity — O(n²).

**What load exposes it.** Input size. At n=100 it's invisible.
At n=5_000 it's noticeable. External CPU stress is an amplifier, not the cause.

**Expected metrics.**
- n=500: single-digit milliseconds
- n=5_000: hundreds of milliseconds — seconds
- The ratio time(n=5000) / time(n=500) should be ≈ 100, not 10.
  That ratio is the tested signal for quadratic growth.

**Honest finding.**
```
case: hidden_quadratic
  scaling:    time(n=5000) / time(n=500) ≈ 100  (expected ~10 for linear)
  idle:       ...
  stressed:   ...
  what this is:     "time grows ~n^2 with input size — super-linear"
  what this is NOT: "this is a bug" / "this will fail in production"
  human next step:  open the function, check the growth pattern
```

**What NOT to claim.** That "this is a bug". Quadratic growth can be
correct for a given task. The tool measures scaling, not intent.

**Sign that the tool is lying.** If the runner states something confident
about the cause (e.g., "this is because of `in` on a list") — that is already
a diagnosis, not an observation. cProfile does not know causes; it knows time.

---

## 2. `gil_bound_parallel_hashes`

**What it does.** ThreadPoolExecutor + pure-Python CPU-bound hashing.
The GIL serializes. There is effectively no parallelism.

**What load exposes it.** Comparison of workers=1 vs workers=4 by
**wall-time**, not cpu-time.

**Expected metrics.**
- wall_time(workers=4) / wall_time(workers=1) ≈ 1.0 (not 0.25)
- cpu_time is roughly equal in both cases
- A truly parallel workload would give ratio ≈ 0.25–0.5

**Honest finding.**
```
case: gil_bound_parallel_hashes
  wall-time workers=1: T1
  wall-time workers=4: T4
  ratio T4/T1:         ~1.0  (parallel would be ~0.25)
  what this is:     "adding workers did not reduce wall-clock time"
  what this is NOT: "the GIL is the cause" / "Python is too slow"
  human next step:  check if work is CPU-bound in Python;
                    if yes, threads will not help — consider multiprocessing
```

**What NOT to claim.** The cause ("it's because of the GIL"). The tool sees
"wall-time did not drop"; it does not see *why*. The cause is the human's job.

**Sign that the tool is lying.** If the runner only looks at cpu-time
and does not compare wall-time, it will **miss** this pathology entirely —
cpu-time will be identical in both cases and the output will be silent.
This is the trap for a naive implementation.

---

## 3. `leaky_cache_lookup`

**What it does.** The dict-LRU works correctly. In parallel,
`_leaky_audit_log` is maintained and never cleared — that is the leak.

**What load exposes it.** Long-running work with many unique keys.
CPU stress does **not** expose it — that is an orthogonal class.

**Expected metrics.**
- Per-call time — flat (O(1) amortized).
- tracemalloc snapshot T1 vs T2 (after N seconds): total allocation
  in `_leaky_audit_log` grows linearly with call count.
- `_leaky_cache` size is stable (≤ 10 entries).

**Honest finding.**
```
case: leaky_cache_lookup
  per-call time:       flat across invocations
  tracemalloc growth:  +X KB / 1000 calls, concentrated in one list
  top growing object:  list at bugs.py:<line of _leaky_audit_log>
  what this is:     "memory attributed to one list grows proportionally
                     to call count and never shrinks"
  what this is NOT: "this is a leak" / "the cache is broken"
  human next step:  look at that list. decide if unbounded growth is ok.
```

**What NOT to claim.** That this is a leak. It may be a log that is
rotated externally. The tool sees growth; it does not see intent.

**Sign that the tool is lying.** If the runner shows memory growth but
attributes it to `_leaky_cache` (the functional cache that evicts properly)
— that is a misattribution. tracemalloc should point to the line where
the actual `append` happens.

---

## 4. `lazy_io_lookup`

**What it does.** A function with a tiny `lru_cache(maxsize=4)` on an I/O read.
Under churn across 200 keys the cache misses constantly.

**What load exposes it.** Key diversity, not call count.
1000 calls with 3 keys → silence. 1000 calls with 200 keys
through a 4-slot cache → bimodal latency.

**Expected metrics.**
- warm-run (small number of keys repeated): p50 ~ tens of microseconds,
  p99 ~ tens of microseconds. Tight distribution.
- churn-run (rotating 200 keys): p50 similar to warm or worse, p99
  50–1000× higher (disk read), bimodal distribution.
- Under churn the profile shows significant time in `open`/`read`
  that is **absent** in the warm run.

**Honest finding.**
```
case: lazy_io_lookup
  warm run:   p50=A, p99=B, profile time in io: 0%
  churn run:  p50=A', p99=B*50+, profile time in io: ~40%
  what this is:     "under key churn, this function spends significant
                     time in file I/O that is absent when keys repeat"
  what this is NOT: "cache is too small" / "disk is slow"
  human next step:  check whether real workload reuses keys.
                    if keys vary, cache size will not save you.
```

**What NOT to claim.** The cause (cache size, disk speed). The observer
sees bimodal latency + io-time appearing. The solution is the engineer's.

**Sign that the tool is lying.** If the runner only looks at mean/avg
and does not build a distribution — the bimodal signal is lost and the
answer looks like "slightly slower" instead of "catastrophically slower on
the tail".

---

## 5. `innocent_sort` (false-positive trap)

**What it does.** `sorted()` on a large list. O(n log n). Correct.

**What load exposes it.** Nothing. This is a legitimately expensive
operation. Under CPU stress it is slower proportionally,
like any cold workload.

**Expected metrics.**
- idle: large absolute cpu-time (n log n on 50k elements).
- stressed: larger by ~1.5–3× (proportional to contention).
- The ratio stressed/idle ≈ the same 1.5–3× as other normal
  operations of the same cost.
- No bimodal latency. No memory growth. No super-linear scaling.

**Honest finding.**
```
case: innocent_sort
  idle cpu-time:     T
  stressed cpu-time: T * ~2
  ratio:             ~2x  (same order as other non-pathological work
                           under the same stress)
  what this is:     "expensive but consistent — scales with contention,
                     nothing anomalous"
  what this is NOT: anything. the instrument should NOT surface this
                    as a "finding" at all beyond acknowledgement.
```

**What NOT to claim.** Anything alarming. If the tool reports something
about `innocent_sort` resembling findings from 1–4 — it is paranoid.

**Sign that the tool is lying.** Any alert-level output on this
case = the tool is lying. A "paranoid observer" is as useless as a
"blind observer".

---

## Calibration pass criteria

The tool passes if:

1. It sees **at least 3 of 4** pathologies (1, 2, 3, 4) with a delta that
   clearly differs from baseline noise.
2. It does **not** produce an alert-level finding on case 5.

Edge cases:
- Sees 2 of 4 → tool is blind to half the problem classes. Not ready.
- Alerts on case 5 → tool is paranoid. Not ready.
- Sees 4 of 4 but does not distinguish class (shows "slow" for case 3
  instead of "memory grows") → tool does not distinguish time from memory.
  A second sensor is needed (tracemalloc).

Run results are compared to this file manually. Automation of the
criteria comes later, once the output format stabilizes.
