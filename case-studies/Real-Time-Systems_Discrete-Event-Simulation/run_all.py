#!/usr/bin/env python3
"""
Case Study 4 — Real-Time Event Simulation
==========================================

Master pipeline: benchmark (parallelized) → 10 publication-quality figures.

Usage::

    python run_all.py                    # Full run: 10M events, 250K queue
    python run_all.py -q                 # Quick debug (~2-5 min)
    python plot_results.py               # Figures only from cached data

Requirements::

    pip install heapx numpy matplotlib sortedcontainers heapdict pqdict
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


def _run(cmd: list[str]) -> None:
    print(f"\n{'=' * 70}")
    print(f"  Running: {' '.join(cmd)}")
    print(f"{'=' * 70}\n")
    subprocess.check_call(cmd)


def main() -> None:
    ap = argparse.ArgumentParser(description="Run the full CS4 pipeline")
    ap.add_argument("--repeats", type=int, default=5)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--workers", type=int, default=0,
                    help="Worker processes (0 = all cores)")
    ap.add_argument("-q", "--quick", action="store_true",
                    help="Quick mode for debugging")
    args = ap.parse_args()

    py = sys.executable
    src = Path(__file__).parent

    bench_cmd = [
        py, str(src / "benchmark.py"),
        "--repeats", str(args.repeats),
        "--seed", str(args.seed),
        "--workers", str(args.workers),
        "--output", "bench_results.json",
    ]
    if args.quick:
        bench_cmd.append("--quick")
    _run(bench_cmd)

    _run([
        py, str(src / "plot_results.py"),
        "--bench", "bench_results.json",
        "--outdir", "figures",
    ])

    print("\nPipeline complete.  Figures are in ./figures/")


if __name__ == "__main__":
    main()
