"""
Orchestrator — runs the full benchmark suite then generates all figures.

Usage:
  python run_all.py
"""

from benchmark import main as run_benchmark
from plot_results import main as run_plots


if __name__ == "__main__":
  run_benchmark()
  print()
  run_plots()
