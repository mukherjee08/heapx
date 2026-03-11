#!/usr/bin/env python
"""
Case Study 1 — Financial Order Book Simulation
===============================================

Master entry point that runs the full pipeline:
  1. Simulation  → snapshot time-series  (parquet)
  2. Benchmark   → heapx vs heapq timing (JSON)
  3. Plotting    → 10 publication-quality PNG figures

Usage:
  python run_all.py [--events N] [--bench-events M] [--repeats R]

Requirements:
  pip install heapx numpy pandas matplotlib pyarrow
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
  ap = argparse.ArgumentParser(
    description="Run the full Case Study 1 pipeline")
  ap.add_argument("--events", type=int, default=200_000,
                  help="Events for simulation (default: 200000)")
  ap.add_argument("--bench-events", type=int, default=500_000,
                  help="Events for benchmark (default: 500000)")
  ap.add_argument("--repeats", type=int, default=5,
                  help="Benchmark repetitions (default: 5)")
  ap.add_argument("--seed", type=int, default=42)
  args = ap.parse_args()

  py = sys.executable
  src = Path(__file__).parent

  # Step 1: Simulation
  _run([py, str(src / "simulation.py"),
        "--events", str(args.events),
        "--seed", str(args.seed),
        "--output", "simulation.parquet"])

  # Step 2: Benchmark
  _run([py, str(src / "benchmark.py"),
        "--events", str(args.bench_events),
        "--repeats", str(args.repeats),
        "--seed", str(args.seed),
        "--output", "results.json"])

  # Step 3: Figures
  _run([py, str(src / "plot_results.py"),
        "--sim", "simulation.parquet",
        "--bench", "results.json",
        "--outdir", "figures"])

  print("\nPipeline complete.  Figures are in ./figures/")


if __name__ == "__main__":
  main()
