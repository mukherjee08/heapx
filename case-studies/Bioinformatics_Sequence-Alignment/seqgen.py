"""
Deterministic synthetic protein sequence generator.

Generates realistic protein sequences with amino-acid frequency
distributions modeled after the UniProt/Swiss-Prot database.
All randomness is seeded for full reproducibility (Section 7,
SPE submission guidelines on reproducible experiments).

References:
  - Needleman & Wunsch (1970): global alignment formulation.
  - Smith & Waterman (1981): local alignment with zero-floor.
  - Altschul et al. (1990): BLAST statistical framework.
"""

from __future__ import annotations

import random
from typing import List, Tuple

from config import (
  AMINO_ACIDS,
  RNG_SEED,
  SEQ_LENGTH_MEAN,
  SEQ_LENGTH_STD,
  SEQ_LENGTH_MIN,
  SEQ_LENGTH_MAX,
)

# Empirical amino-acid frequencies from Swiss-Prot (2024 release).
# Order matches AMINO_ACIDS = "ACDEFGHIKLMNPQRSTVWY".
_AA_FREQS: list[float] = [
  0.0826, 0.0136, 0.0546, 0.0675, 0.0386,  # A C D E F
  0.0708, 0.0227, 0.0593, 0.0584, 0.0966,   # G H I K L
  0.0241, 0.0406, 0.0470, 0.0393, 0.0553,    # M N P Q R
  0.0656, 0.0534, 0.0687, 0.0108, 0.0292,    # S T V W Y
]


def _make_cumulative(freqs: list[float]) -> list[float]:
  """Convert frequency list to cumulative distribution."""
  cum: list[float] = []
  total = 0.0
  for f in freqs:
    total += f
    cum.append(total)
  # Normalize to exactly 1.0 to avoid floating-point edge cases.
  cum[-1] = 1.0
  return cum


_AA_CUM = _make_cumulative(_AA_FREQS)


def _sample_aa(rng: random.Random) -> str:
  """Sample a single amino acid from the empirical distribution."""
  r = rng.random()
  for i, c in enumerate(_AA_CUM):
    if r <= c:
      return AMINO_ACIDS[i]
  return AMINO_ACIDS[-1]  # pragma: no cover


def generate_sequence(rng: random.Random, length: int | None = None) -> str:
  """Generate a single protein sequence.

  Args:
    rng: Seeded Random instance.
    length: Exact length.  If None, sampled from a truncated normal
            distribution matching Swiss-Prot statistics.

  Returns:
    Protein sequence string over the 20 standard amino acids.
  """
  if length is None:
    length = int(rng.gauss(SEQ_LENGTH_MEAN, SEQ_LENGTH_STD))
    length = max(SEQ_LENGTH_MIN, min(SEQ_LENGTH_MAX, length))
  return "".join(_sample_aa(rng) for _ in range(length))


def mutate_sequence(rng: random.Random, seq: str, mutation_rate: float = 0.15) -> str:
  """Introduce point mutations to simulate evolutionary divergence.

  Args:
    rng: Seeded Random instance.
    seq: Original protein sequence.
    mutation_rate: Fraction of residues to mutate (default 15 %).

  Returns:
    Mutated sequence of the same length.
  """
  chars = list(seq)
  for i in range(len(chars)):
    if rng.random() < mutation_rate:
      chars[i] = _sample_aa(rng)
  return "".join(chars)


def generate_pair(rng: random.Random) -> Tuple[str, str]:
  """Generate a homologous sequence pair (query, subject).

  The subject is derived from the query via point mutation,
  simulating divergent evolution — the standard model for
  benchmarking local alignment algorithms (Altschul et al., 1990).
  """
  query = generate_sequence(rng)
  subject = mutate_sequence(rng, query, mutation_rate=0.20)
  return query, subject


def generate_dataset(n_pairs: int, seed: int = RNG_SEED) -> List[Tuple[str, str]]:
  """Generate a reproducible dataset of sequence pairs.

  Args:
    n_pairs: Number of (query, subject) pairs.
    seed: RNG seed for determinism.

  Returns:
    List of (query, subject) tuples.
  """
  rng = random.Random(seed)
  return [generate_pair(rng) for _ in range(n_pairs)]
