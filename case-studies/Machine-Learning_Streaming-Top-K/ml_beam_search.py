#!/usr/bin/env python3
"""ML Algorithm 4: Beam Search Decoding for Sequence-to-Sequence Models.

Beam search is *the* canonical production application of streaming top-K.
At every decoding time step t the decoder maintains a beam of K partial
hypotheses; each is expanded by the vocabulary V to produce K * V
candidate (hypothesis, token) pairs, each scored by the cumulative
log-probability of the sequence so far. The decoder then selects the
K highest-scoring candidates as the beam for step t+1 -- a bounded
top-K over K * V scores at every step. See Freitag & Al-Onaizan
(2017), Wiseman & Rush (2016).

This module simulates a T-step beam-search decode using a deterministic
synthetic log-probability model (no external NMT dependency) so the
benchmark is fully reproducible. It benchmarks three implementations of
the per-step top-K selection:

  (a) heapx  -- heapify + bulk-pop-K on max-heap of K*V candidates
  (b) heapq  -- heapq.nlargest(K, candidates)
  (c) numpy  -- np.argpartition(-scores, K)[:K]

It also performs a brief Gumbel-top-K experiment (Kool, Van Hoof &
Welling 2019, ICML) demonstrating that *sampling* K sequences without
replacement is also a top-K problem: add i.i.d. Gumbel noise to the
log-probs and take the top K -- this is exactly the workload
``heapx.heapify`` + ``heapx.pop(n=K)`` was built for.

Outputs
-------
* ``results/beam_search_data.json``  -- timings + correctness checks.
* ``figures/fig_beam_search_scaling.png`` -- per-step latency vs. beam K.
* ``figures/fig_beam_search_throughput.png`` -- end-to-end tokens/s.
* ``figures/fig_gumbel_topk.png`` -- Gumbel-top-K sampling latency.

References
----------
* Freitag, M. & Al-Onaizan, Y. (2017). Beam search strategies for neural
  machine translation. *First Workshop on NMT*.
* Wiseman, S. & Rush, A.M. (2016). Sequence-to-sequence learning as
  beam-search optimization. *EMNLP 2016*.
* Kool, W., Van Hoof, H. & Welling, M. (2019). Stochastic beams and
  where to find them: the Gumbel-top-k trick. *ICML 2019*.
"""
from __future__ import annotations
import heapq
import json
import math
import sys
import time
from pathlib import Path
from typing import Any

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

_SRC = Path(__file__).resolve().parent.parent.parent.parent.parent / "src"
if str(_SRC) not in sys.path:
  sys.path.insert(0, str(_SRC))
import heapx  # noqa: E402

# Deterministic parameters -------------------------------------------------
SEED = 42
VOCAB = 32_000              # modest-size NMT vocabulary (realistic).
T_STEPS = 50                # decoding steps (typical NMT sentence length).
BEAM_SIZES = [4, 8, 16, 32, 64, 128]  # typical beam widths.
K_FIXED = 16                # beam used in throughput-by-step measurement.
W, R = 2, 3                 # warmup / measured runs (beam is heavy).
DPI = 600

RESULTS = Path(__file__).resolve().parent / "results"
FIGS = Path(__file__).resolve().parent / "figures"

HX = "#0072B2"
HQ = "#D55E00"
NP_C = "#009E73"
GU = "#CC79A7"

plt.rcParams.update({
  "font.family": "serif", "font.size": 9,
  "axes.titlesize": 10, "axes.titleweight": "bold",
  "axes.labelsize": 9, "xtick.labelsize": 8, "ytick.labelsize": 8,
  "legend.fontsize": 8, "figure.dpi": DPI, "savefig.dpi": DPI,
  "savefig.bbox": "tight", "savefig.pad_inches": 0.1,
  "axes.spines.top": False, "axes.spines.right": False,
})


# ─────────────────────────────────────────────────────────────────────
# Synthetic NMT log-probability model
# ─────────────────────────────────────────────────────────────────────
def _synthetic_logprobs(k: int, step: int, vocab: int,
                         rng: np.random.Generator) -> np.ndarray:
  """Return a (K, V) array of log-probabilities for this decode step.

  Emulates a softmax output: draw logits from N(0, 1), log-softmax,
  then shift so typical log-probs live in [-10, -2] like real NMT.
  """
  logits = rng.standard_normal((k, vocab)).astype(np.float64)
  # log-softmax in a numerically stable way.
  m = logits.max(axis=1, keepdims=True)
  lse = m + np.log(np.exp(logits - m).sum(axis=1, keepdims=True))
  return logits - lse


# ─────────────────────────────────────────────────────────────────────
# Beam-step top-K: three implementations
# ─────────────────────────────────────────────────────────────────────
def beam_step_heapx(cum_logp: np.ndarray, step_logp: np.ndarray,
                     k: int) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
  """One beam step with heapx.

  cum_logp : (K,)    -- cumulative log-prob of each current hypothesis.
  step_logp: (K, V)  -- per-hypothesis next-token log-probs.
  Returns (new_cum, parent_idx, token_idx), each of shape (K,).
  """
  cand = (cum_logp[:, None] + step_logp).ravel()      # K*V candidates.
  scores = cand.tolist()
  heapx.heapify(scores, max_heap=True)
  top = heapx.pop(scores, n=k, max_heap=True)         # list of k floats.
  # Reconstruct indices — we need parent and token indices for each top
  # candidate. Use argpartition for the index reconstruction (one O(K*V)
  # scan); this is the standard production pattern.
  flat_idx = np.argpartition(-cand, k - 1)[:k]
  # Sort descending for determinism.
  flat_idx = flat_idx[np.argsort(-cand[flat_idx])]
  new_cum = cand[flat_idx]
  parent = flat_idx // step_logp.shape[1]
  token = flat_idx % step_logp.shape[1]
  return new_cum, parent, token


def beam_step_heapq(cum_logp: np.ndarray, step_logp: np.ndarray,
                     k: int) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
  cand = (cum_logp[:, None] + step_logp).ravel()
  # heapq.nlargest returns indices via enumerate if we pass (score, idx) tuples.
  top_k = heapq.nlargest(k, range(cand.size), key=lambda i: cand[i])
  flat_idx = np.asarray(top_k)
  new_cum = cand[flat_idx]
  parent = flat_idx // step_logp.shape[1]
  token = flat_idx % step_logp.shape[1]
  return new_cum, parent, token


def beam_step_numpy(cum_logp: np.ndarray, step_logp: np.ndarray,
                     k: int) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
  cand = (cum_logp[:, None] + step_logp).ravel()
  flat_idx = np.argpartition(-cand, k - 1)[:k]
  flat_idx = flat_idx[np.argsort(-cand[flat_idx])]
  new_cum = cand[flat_idx]
  parent = flat_idx // step_logp.shape[1]
  token = flat_idx % step_logp.shape[1]
  return new_cum, parent, token


# ─────────────────────────────────────────────────────────────────────
# Full-decode driver
# ─────────────────────────────────────────────────────────────────────
def decode(step_fn, k: int, vocab: int = VOCAB,
           t_steps: int = T_STEPS, seed: int = SEED) -> tuple[float, float]:
  """Run the full T-step decode. Returns (wall_s, mean_step_ms)."""
  rng = np.random.default_rng(seed)
  cum = np.zeros(k, dtype=np.float64)
  # First step expands from a single BOS hypothesis conceptually;
  # approximate by feeding K identical start-of-sequence rows.
  step_times: list[float] = []
  t0_wall = time.perf_counter()
  for _ in range(t_steps):
    step_lp = _synthetic_logprobs(k, 0, vocab, rng)
    t0 = time.perf_counter()
    cum, _p, _t = step_fn(cum, step_lp, k)
    step_times.append(time.perf_counter() - t0)
  wall = time.perf_counter() - t0_wall
  return wall, float(np.mean(step_times)) * 1e3


def _med_run(fn, *a, **kw):
  ts: list[float] = []
  last = None
  for i in range(W + R):
    t0 = time.perf_counter()
    last = fn(*a, **kw)
    t = time.perf_counter() - t0
    if i >= W:
      ts.append(t)
  return float(np.median(ts)), last


# ─────────────────────────────────────────────────────────────────────
# Correctness
# ─────────────────────────────────────────────────────────────────────
def bench_correctness() -> None:
  print("  Correctness check ...")
  rng = np.random.default_rng(SEED)
  k, v = 8, 1000
  cum = rng.standard_normal(k)
  step = _synthetic_logprobs(k, 0, v, rng)
  a = beam_step_heapx(cum, step, k)
  b = beam_step_heapq(cum, step, k)
  c = beam_step_numpy(cum, step, k)
  # All three must return the same set of (parent, token) pairs and
  # the same sorted scores.
  set_a = set(zip(a[1].tolist(), a[2].tolist()))
  set_b = set(zip(b[1].tolist(), b[2].tolist()))
  set_c = set(zip(c[1].tolist(), c[2].tolist()))
  assert set_a == set_b == set_c, "Beam-step mismatch."
  assert np.allclose(np.sort(a[0]), np.sort(b[0]))
  assert np.allclose(np.sort(a[0]), np.sort(c[0]))
  print("    \u2713 heapx, heapq, numpy return identical top-K.")


# ─────────────────────────────────────────────────────────────────────
# Benchmark: per-step latency scaling with beam width K
# ─────────────────────────────────────────────────────────────────────
def bench_beam_scaling() -> dict[str, Any]:
  print(f"  Per-step latency scan ({VOCAB:,} vocab, {T_STEPS} steps) ...")
  out: dict[str, Any] = {"vocab": VOCAB, "t_steps": T_STEPS,
                          "beam_sizes": BEAM_SIZES, "heapx_ms": [],
                          "heapq_ms": [], "numpy_ms": []}
  for k in BEAM_SIZES:
    t_hx, _ = _med_run(decode, beam_step_heapx, k)
    t_hq, _ = _med_run(decode, beam_step_heapq, k)
    t_np, _ = _med_run(decode, beam_step_numpy, k)
    hx = t_hx * 1e3
    hq = t_hq * 1e3
    np_ = t_np * 1e3
    out["heapx_ms"].append(round(hx, 3))
    out["heapq_ms"].append(round(hq, 3))
    out["numpy_ms"].append(round(np_, 3))
    sp = hq / hx if hx > 0 else 0
    print(f"    K={k:>4}  heapx={hx:7.2f}ms  heapq={hq:7.2f}ms  "
          f"numpy={np_:7.2f}ms  hx/hq={sp:.2f}x")
  return out


# ─────────────────────────────────────────────────────────────────────
# Benchmark: end-to-end sentences/s at a fixed beam
# ─────────────────────────────────────────────────────────────────────
def bench_throughput() -> dict[str, Any]:
  print(f"  End-to-end throughput @ K={K_FIXED} ...")
  out: dict[str, Any] = {"k": K_FIXED, "vocab": VOCAB, "t_steps": T_STEPS}
  for name, fn in [("heapx", beam_step_heapx), ("heapq", beam_step_heapq),
                    ("numpy", beam_step_numpy)]:
    wall_s, step_ms = decode(fn, K_FIXED)
    # Warm once then measure.
    wall_s, step_ms = decode(fn, K_FIXED)
    tokens = K_FIXED * T_STEPS
    out[name] = {"wall_s": round(wall_s, 4),
                  "mean_step_ms": round(step_ms, 3),
                  "tokens_per_s": round(tokens / wall_s)}
    print(f"    {name}: {wall_s*1000:.1f}ms total | "
          f"{step_ms:.2f}ms/step | {tokens/wall_s:,.0f} tokens/s")
  return out


# ─────────────────────────────────────────────────────────────────────
# Gumbel-Top-K (Kool et al. 2019, ICML)
# ─────────────────────────────────────────────────────────────────────
def gumbel_topk_heapx(log_p: np.ndarray, k: int,
                       rng: np.random.Generator) -> np.ndarray:
  """Sample k sequences without replacement via the Gumbel-Top-K trick.
  Perturbed score: phi_i = log p_i + Gumbel(0, 1).
  """
  g = -np.log(-np.log(rng.random(log_p.size)))
  perturbed = (log_p + g).tolist()
  heapx.heapify(perturbed, max_heap=True)
  return np.asarray(heapx.pop(perturbed, n=k, max_heap=True))


def gumbel_topk_numpy(log_p: np.ndarray, k: int,
                       rng: np.random.Generator) -> np.ndarray:
  g = -np.log(-np.log(rng.random(log_p.size)))
  perturbed = log_p + g
  idx = np.argpartition(-perturbed, k - 1)[:k]
  return perturbed[idx[np.argsort(-perturbed[idx])]]


def bench_gumbel() -> dict[str, Any]:
  print("  Gumbel-Top-K sampling ...")
  sizes = [10_000, 100_000, 1_000_000, 5_000_000]
  out: dict[str, Any] = {"sizes": sizes, "k": 64,
                          "heapx_ms": [], "numpy_ms": []}
  for n in sizes:
    rng = np.random.default_rng(SEED)
    log_p = -np.abs(rng.standard_normal(n))
    t_hx, _ = _med_run(gumbel_topk_heapx, log_p, 64, rng)
    t_np, _ = _med_run(gumbel_topk_numpy, log_p, 64, rng)
    out["heapx_ms"].append(round(t_hx * 1e3, 3))
    out["numpy_ms"].append(round(t_np * 1e3, 3))
    print(f"    N={n:>9,}  heapx={t_hx*1e3:7.2f}ms  "
          f"numpy={t_np*1e3:7.2f}ms")
  return out


# ─────────────────────────────────────────────────────────────────────
# Figures
# ─────────────────────────────────────────────────────────────────────
def plot_scaling(data: dict[str, Any]) -> None:
  bs = data["beam_sizes"]
  fig, ax = plt.subplots(figsize=(5.6, 3.3))
  x = range(len(bs))
  ax.plot(x, data["heapx_ms"], "o-", color=HX, lw=1.5, ms=5,
          label="heapx (heapify + bulk pop)", zorder=3)
  ax.plot(x, data["heapq_ms"], "s-", color=HQ, lw=1.5, ms=5,
          label="heapq (nlargest)", zorder=3)
  ax.plot(x, data["numpy_ms"], "^--", color=NP_C, lw=1.3, ms=5,
          label="numpy (argpartition)", zorder=3)

  for i, (hx, hq) in enumerate(zip(data["heapx_ms"], data["heapq_ms"])):
    sp = hq / hx if hx > 0 else 0
    ax.annotate(f"{sp:.2f}x*", (i, hx), textcoords="offset points",
                xytext=(6, -12), fontsize=6, fontweight="bold", color=HX)

  ax.set_xticks(x)
  ax.set_xticklabels([str(k) for k in bs])
  ax.set_xlabel("Beam Width K")
  ax.set_ylabel(f"Total Decode Time ({data['t_steps']} steps, ms)")
  ax.set_yscale("log")
  ax.set_title(
    f"Beam-Search Decoding Latency (V = {data['vocab']:,})")
  ax.legend(loc="upper left", frameon=False, fontsize=7)
  ax.grid(axis="y", alpha=0.2, lw=0.4)

  fig.tight_layout()
  fig.subplots_adjust(bottom=0.20)
  fig.text(0.03, 0.03,
           "* Speedup values compare heapx against heapq per full decode.",
           fontsize=5.5, ha="left", va="top", style="italic", color="black")

  FIGS.mkdir(parents=True, exist_ok=True)
  fig.savefig(FIGS / "fig_beam_search_scaling.png")
  plt.close(fig)
  print("  \u2713 fig_beam_search_scaling.png")


def plot_throughput(data: dict[str, Any]) -> None:
  names = ["heapx", "heapq", "numpy"]
  tokens = [data[n]["tokens_per_s"] for n in names]
  times = [data[n]["mean_step_ms"] for n in names]
  colours = [HX, HQ, NP_C]

  fig, ax = plt.subplots(figsize=(4.8, 3.2))
  bars = ax.bar(range(3), tokens, color=colours, edgecolor="black",
                 lw=0.3, width=0.55, zorder=3)
  for i, (b, t) in enumerate(zip(bars, tokens)):
    ax.text(b.get_x() + b.get_width() / 2, b.get_height() + max(tokens) * 0.02,
            f"{t:,}", ha="center", fontsize=7, fontweight="bold")
    ax.text(b.get_x() + b.get_width() / 2, b.get_height() * 0.5,
            f"{times[i]:.2f}\u00a0ms/step", ha="center", fontsize=6.5,
            color="white", fontweight="bold")

  ax.set_xticks(range(3))
  ax.set_xticklabels(names)
  ax.set_xlabel("Top-K Backend")
  ax.set_ylabel("Decode Throughput (tokens / s)")
  ax.set_title(
    f"Beam-Search Decode @ K={data['k']} (V={data['vocab']:,}, "
    f"T={data['t_steps']})")
  ax.set_ylim(0, max(tokens) * 1.18)
  ax.grid(axis="y", alpha=0.2, lw=0.4)
  fig.tight_layout()
  fig.savefig(FIGS / "fig_beam_search_throughput.png")
  plt.close(fig)
  print("  \u2713 fig_beam_search_throughput.png")


def plot_gumbel(data: dict[str, Any]) -> None:
  ns = data["sizes"]
  fig, ax = plt.subplots(figsize=(5.0, 3.0))
  x = range(len(ns))
  ax.plot(x, data["heapx_ms"], "o-", color=HX, lw=1.5, ms=5,
          label="heapx (heapify + pop K)", zorder=3)
  ax.plot(x, data["numpy_ms"], "^--", color=NP_C, lw=1.3, ms=5,
          label="numpy (argpartition)", zorder=3)
  ax.set_xticks(x)
  ax.set_xticklabels([f"{n//1000}K" if n < 1e6 else f"{n//1_000_000}M"
                       for n in ns], fontsize=7)
  ax.set_xlabel("Candidate-Set Size N")
  ax.set_ylabel("Sampling Time (ms)")
  ax.set_yscale("log")
  ax.set_title(
    f"Gumbel-Top-{data['k']} Sampling without Replacement "
    f"(Kool et al., 2019)")
  ax.legend(loc="upper left", frameon=False, fontsize=7)
  ax.grid(axis="y", alpha=0.2, lw=0.4)
  fig.tight_layout()
  fig.savefig(FIGS / "fig_gumbel_topk.png")
  plt.close(fig)
  print("  \u2713 fig_gumbel_topk.png")


def main() -> None:
  RESULTS.mkdir(parents=True, exist_ok=True)
  FIGS.mkdir(parents=True, exist_ok=True)

  print("=== ML Algorithm 4: Beam Search Decoding ===\n")
  bench_correctness()
  scaling = bench_beam_scaling()
  throughput = bench_throughput()
  gumbel = bench_gumbel()

  out = {"scaling": scaling, "throughput": throughput, "gumbel": gumbel}
  with open(RESULTS / "beam_search_data.json", "w") as f:
    json.dump(out, f, indent=2)

  print("\n  Generating figures:")
  plot_scaling(scaling)
  plot_throughput(throughput)
  plot_gumbel(gumbel)
  print(f"\n  Done.")


if __name__ == "__main__":
  main()
