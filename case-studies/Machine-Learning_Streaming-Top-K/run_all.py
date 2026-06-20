#!/usr/bin/env python3
"""Gap 7 — single-command runner for the entire Case Study 5 suite.

Execution order matters because downstream scripts consume the JSON /
.npy artefacts of upstream scripts:

  1. run_benchmarks.py    -> results/bench_data.json
  2. parallel_topk.py     -> results/parallel_scaling.json
  3. streaming_topk.py    -> results/throughput.json + latency_*.npy
  4. replace_benchmark.py -> results/replace_data.json  + fig_replace_vs_popush.png
  5. latency_distribution.py              -> fig_latency_cdf.png
  6. ml_knn.py            -> results/knn_data.json   + knn_*.png
  7. ml_feature_selection.py              -> results/fs_data.json    + fs_*.png
  8. ml_anomaly_detection.py              -> results/ad_data.json    + ad_*.png
  9. ml_beam_search.py    -> results/beam_search_data.json + fig_beam_*.png
 10. ml_sliding_window.py -> results/sliding_window_data.json + fig_sliding_*.png
 11. visualize.py         -> core fig1--fig7 .png figures
 12. speedup_summary.py   -> fig_speedup_summary.png  (needs 1,3,4,9,10)

Pass ``--quick`` to skip the most expensive benchmarks (beam search at
largest K, 5M-float heapify, 10M-stream streaming) for a fast smoke test.
"""
from __future__ import annotations
import argparse
import runpy
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent

STAGES = [
  "run_benchmarks.py",
  "parallel_topk.py",
  "streaming_topk.py",
  "replace_benchmark.py",
  "latency_distribution.py",
  "ml_knn.py",
  "ml_feature_selection.py",
  "ml_anomaly_detection.py",
  "ml_beam_search.py",
  "ml_sliding_window.py",
  "visualize.py",
  "speedup_summary.py",
]


def main() -> int:
  ap = argparse.ArgumentParser(description=__doc__)
  ap.add_argument("--skip", nargs="*", default=[],
                   help="Scripts to skip (basename).")
  ap.add_argument("--only", nargs="*", default=None,
                   help="Only run these scripts (basename).")
  args = ap.parse_args()

  to_run = [s for s in STAGES
             if (args.only is None or s in args.only) and s not in args.skip]
  print(f"CS5 runner: {len(to_run)} stage(s) -> "
        f"{', '.join(to_run)}\n")

  total0 = time.perf_counter()
  for stage in to_run:
    path = HERE / stage
    if not path.exists():
      print(f"\n!! {stage} not found at {path}", file=sys.stderr)
      return 2
    print("\n" + "=" * 68)
    print(f"  RUN {stage}")
    print("=" * 68)
    t0 = time.perf_counter()
    try:
      runpy.run_path(str(path), run_name="__main__")
    except SystemExit as e:
      if e.code not in (None, 0):
        print(f"\n!! {stage} exited with code {e.code}", file=sys.stderr)
        return int(e.code)
    except Exception as e:
      print(f"\n!! {stage} raised {type(e).__name__}: {e}", file=sys.stderr)
      return 1
    print(f"  ({stage} done in {time.perf_counter() - t0:.1f} s)")

  total = time.perf_counter() - total0
  print(f"\n\nAll stages completed in {total:.1f} s "
         f"({total / 60:.1f} min).")
  return 0


if __name__ == "__main__":
  sys.exit(main())
