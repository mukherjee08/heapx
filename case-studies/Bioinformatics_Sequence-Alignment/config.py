"""
Configuration constants for Case Study 2: Bioinformatics Sequence Alignment.

All tunable parameters are centralized here for reproducibility.
Reviewers can adjust these values without modifying simulation logic.
"""

# ---------------------------------------------------------------------------
# Substitution matrix (BLOSUM62-derived subset for 20 standard amino acids)
# ---------------------------------------------------------------------------
AMINO_ACIDS: str = "ACDEFGHIKLMNPQRSTVWY"

# Simplified BLOSUM62 match/mismatch scores used in the SW beam search.
# Full BLOSUM62 is 20x20; we use match=+3, mismatch=-1 for tractability
# while preserving the statistical separation between homologous and
# random alignments (Altschul et al., 1990).
SW_MATCH: int = 3
SW_MISMATCH: int = -1
SW_GAP_OPEN: int = -5
SW_GAP_EXTEND: int = -2

# ---------------------------------------------------------------------------
# Beam-search alignment parameters
# ---------------------------------------------------------------------------
# Beam width controls the priority-queue size during alignment.
# Larger beams improve alignment quality at the cost of more heap operations.
BEAM_WIDTH: int = 200

# Number of top alignments to extract per sequence pair (bulk pop).
TOP_K: int = 100

# ---------------------------------------------------------------------------
# Sequence generation
# ---------------------------------------------------------------------------
# Deterministic seed for reproducibility (Knuth's birthday: 1938-01-10).
RNG_SEED: int = 19380110

# Protein sequence parameters (modeled after UniProt/Swiss-Prot statistics).
SEQ_LENGTH_MEAN: int = 350
SEQ_LENGTH_STD: int = 120
SEQ_LENGTH_MIN: int = 80
SEQ_LENGTH_MAX: int = 1200

# Number of sequence pairs to align in the benchmark.
N_PAIRS: int = 2000

# ---------------------------------------------------------------------------
# Threading benchmark
# ---------------------------------------------------------------------------
THREAD_COUNTS: list[int] = [1, 2, 4, 8]

# ---------------------------------------------------------------------------
# Neighbor-joining parameters
# ---------------------------------------------------------------------------
NJ_N_TAXA: int = 500  # Number of taxa for phylogenetic tree construction

# ---------------------------------------------------------------------------
# Heap arity comparison
# ---------------------------------------------------------------------------
ARITY_VALUES: list[int] = [2, 3, 4, 8]

# ---------------------------------------------------------------------------
# Visualization
# ---------------------------------------------------------------------------
FIG_DPI: int = 600
FIG_FORMAT: str = "png"
FIG_DIR: str = "figures"
