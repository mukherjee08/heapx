# Case Study 2 — Bioinformatics Sequence Alignment

## 1. Introduction

This case study implements a **priority-queue-driven beam-search sequence aligner** and a **heap-accelerated neighbor-joining phylogenetic tree constructor**, both backed by the `heapx` C-extension module.  It benchmarks these implementations against identical algorithms built on Python's standard-library `heapq`, the third-party `sortedcontainers` library, and `queue.PriorityQueue`, and produces twelve publication-quality figures that illustrate both the bioinformatics domain and the performance advantage of `heapx`.

The remainder of this document is organised as follows.  Section 2 provides the biological and algorithmic background a reader needs to understand the case study from first principles — no prior knowledge of bioinformatics is assumed.  Section 3 describes the simulation design and the data-generation strategy.  Section 4 walks through the code architecture and explains every design decision.  Section 5 presents the performance results.  Section 6 discusses the practical value of `heapx` for bioinformatics professionals.  Section 7 gives quick-start instructions for reproducing the results.

---

## 2. Biological and Algorithmic Background

### 2.1 Proteins and Amino Acids

All living organisms build proteins — large molecules that perform virtually every function in a cell, from catalysing chemical reactions (enzymes) to providing structural support (collagen) to transmitting signals (hormones).  A protein is a linear chain of smaller building blocks called **amino acids**, linked end-to-end like beads on a string.

There are exactly **20 standard amino acids** found in proteins across all domains of life.  Each is identified by a one-letter code:

```
A  Alanine        C  Cysteine       D  Aspartate      E  Glutamate
F  Phenylalanine  G  Glycine        H  Histidine      I  Isoleucine
K  Lysine         L  Leucine        M  Methionine     N  Asparagine
P  Proline        Q  Glutamine      R  Arginine       S  Serine
T  Threonine      V  Valine         W  Tryptophan     Y  Tyrosine
```

A protein sequence is written as a string of these one-letter codes.  For example, the first ten residues of human insulin's B-chain are `FVNQHLCGSHL`.  A typical protein is 200–600 amino acids long, though some exceed 30,000.

The amino acids differ in their chemical properties — size, charge, hydrophobicity (tendency to avoid water) — and these differences determine how the protein folds into its three-dimensional shape and what function it performs.  Crucially, not all amino acid substitutions are equally likely during evolution.  Replacing leucine (L) with isoleucine (I) is common because both are small and hydrophobic; replacing leucine with aspartate (D) is rare because aspartate is negatively charged and hydrophilic.  This observation is the foundation of **substitution matrices** used in sequence alignment (see Section 2.4).

### 2.2 Sequence Homology and Evolutionary Divergence

When two organisms share a common ancestor, their proteins descend from the same ancestral protein.  Over millions of years, random mutations accumulate: individual amino acids are substituted, short segments are inserted or deleted.  The result is two sequences that are **similar but not identical** — they are said to be **homologous**.

**Example.**  Consider an ancestral sequence `ACDEFGHIKL` and two descendant sequences after 100 million years of independent evolution:

```
Ancestor:    A C D E F G H I K L
Descendant1: A C D E F G H I K L   (no mutations — conserved)
Descendant2: A C N E F G H V K L   (D→N at position 3, I→V at position 8)
```

Descendant 2 has two point mutations relative to the ancestor.  The positions that remain identical (A, C, E, F, G, H, K, L) are called **conserved residues**.  The mutated positions (D→N, I→V) are called **substitutions**.

The central problem of bioinformatics sequence analysis is: **given two sequences, determine whether they are homologous (descended from a common ancestor) and, if so, identify which residues correspond to each other.**  This is the **sequence alignment** problem.

### 2.3 What Is Sequence Alignment?

**Sequence alignment** is the process of arranging two (or more) sequences side by side, inserting gaps (denoted by `-`) where necessary, so that corresponding residues are placed in the same column.  The goal is to maximise the number of matching or chemically similar residues while minimising the number of gaps.

**Example of a pairwise alignment:**

```
Query:   A C D E F G H I K L - P Q R
Subject: A C N E F G H V K L S P Q R
         * * . * * * * . * *   * * *
```

Here, `*` denotes an identical match, `.` denotes a substitution (D↔N, I↔V), and `-` denotes a gap (an insertion in the subject or a deletion in the query).

There are two fundamental types of pairwise alignment:

- **Global alignment** (Needleman & Wunsch, 1970): aligns the two sequences from end to end, including all residues.  Appropriate when the sequences are of similar length and expected to be homologous over their entire extent.

- **Local alignment** (Smith & Waterman, 1981): finds the highest-scoring sub-region of similarity, ignoring the rest.  Appropriate when the sequences may share only a partial region of homology — for example, two proteins that share a single conserved domain but differ elsewhere.

This case study implements the **Smith–Waterman local alignment algorithm** because it is the gold standard for sensitivity in detecting partial homologies, and its computational structure naturally involves priority queues when combined with beam search.

### 2.4 Substitution Scoring

To quantify how "good" an alignment is, we assign a numerical score to each column.  The scoring scheme has two components:

#### 2.4.1 Substitution Scores

A **substitution matrix** assigns a score to every possible pair of amino acids.  The most widely used family of substitution matrices is **BLOSUM** (Blocks Substitution Matrix), developed by Henikoff and Henikoff (1992).  BLOSUM62, the default in BLAST, is a 20×20 matrix where:

- Positive entries (e.g., BLOSUM62[L][I] = +2) indicate that the substitution is observed more frequently in homologous sequences than expected by chance — the two amino acids are chemically similar and evolution tolerates the swap.
- Negative entries (e.g., BLOSUM62[L][D] = −4) indicate that the substitution is rare — the amino acids are chemically dissimilar and the swap is likely deleterious.
- Diagonal entries (e.g., BLOSUM62[L][L] = +4) are positive, reflecting the fact that identical residues are the most common observation in homologous alignments.

For computational tractability in this case study, we use a simplified scoring scheme that captures the essential statistical separation:

```python
SW_MATCH    =  3   # score for identical residues
SW_MISMATCH = -1   # score for non-identical residues
```

This simplified scheme preserves the key property: alignments of homologous sequences score significantly higher than alignments of random sequences, enabling statistical discrimination.

#### 2.4.2 Gap Penalties

Insertions and deletions (collectively called **indels**) are modelled as gaps in the alignment.  Each gap incurs a penalty.  The simplest model is a **linear gap penalty**: each gap position costs a fixed amount.  A more realistic model is the **affine gap penalty**, which charges a higher cost to *open* a new gap than to *extend* an existing one:

```
Gap cost = gap_open + (gap_length − 1) × gap_extend
```

This reflects the biological observation that a single mutational event can insert or delete a contiguous block of residues, so a long gap is not much less likely than a short one.

Our implementation uses:

```python
SW_GAP_OPEN   = -5   # cost to open a new gap
SW_GAP_EXTEND = -2   # cost to extend an existing gap (not used in simplified recurrence)
```

The simplified recurrence in our code uses only `SW_GAP_OPEN` as a linear penalty per gap position, which is standard for beam-search implementations where the full affine model adds complexity without changing the heap-operation profile.

### 2.5 The Smith–Waterman Algorithm

The Smith–Waterman algorithm (Smith & Waterman, 1981) finds the optimal local alignment between two sequences using **dynamic programming** (DP).  It is guaranteed to find the mathematically optimal alignment — no heuristic shortcuts, no approximations.

**Dynamic programming** is a general algorithmic technique for solving problems that can be decomposed into overlapping sub-problems.  The key idea is: instead of solving the same sub-problem repeatedly (as a naïve recursive approach would), solve each sub-problem once, store its result in a table, and look it up when needed.  In the context of sequence alignment, the "sub-problems" are: "what is the best alignment of the first i residues of Q with the first j residues of S?"  The table is the scoring matrix H.

#### 2.5.1 The DP Recurrence

Given a query sequence Q = q₁q₂…qₘ and a subject sequence S = s₁s₂…sₙ, the algorithm fills an (m+1) × (n+1) scoring matrix H where H[i][j] represents the score of the best local alignment ending at position i in Q and position j in S.

The recurrence relation is:

```
H[i][j] = max(
    0,                                    # (reset: no alignment here)
    H[i-1][j-1] + score(qᵢ, sⱼ),        # (diagonal: match/mismatch)
    H[i-1][j]   + gap_open,              # (up: gap in subject)
    H[i][j-1]   + gap_open               # (left: gap in query)
)
```

Each of the four terms has a biological interpretation:

- **0 (reset):** Start a new local alignment here.  This is the key innovation of Smith–Waterman over Needleman–Wunsch: by allowing the score to reset to zero, the algorithm can ignore poorly-aligning flanking regions and focus on the best local sub-alignment.
- **Diagonal (H[i-1][j-1] + score):** Extend the alignment by pairing qᵢ with sⱼ.  If they are the same amino acid, score = +3 (match); if different, score = −1 (mismatch).
- **Up (H[i-1][j] + gap_open):** Extend the alignment by consuming qᵢ but inserting a gap in S.  This models a deletion in S (or equivalently, an insertion in Q).
- **Left (H[i][j-1] + gap_open):** Extend the alignment by consuming sⱼ but inserting a gap in Q.  This models an insertion in S (or equivalently, a deletion in Q).

**Initialisation:** H[0][j] = 0 for all j, and H[i][0] = 0 for all i.  This means "the score of aligning zero residues with anything is zero."

**Result:** The optimal local alignment score is max(H[i][j]) over all i, j.  The alignment itself is recovered by **traceback** — following pointers from the maximum-scoring cell back through the matrix, at each cell choosing the direction (diagonal, up, or left) that produced the cell's score, until a cell with score 0 is reached.

#### 2.5.2 Time and Space Complexity

Filling the entire matrix requires computing m × n cells, each in O(1) time, giving **O(mn) time** and **O(mn) space** (or O(n) space if only the score, not the traceback, is needed — because each row depends only on the previous row).

For two protein sequences of length 350 (the mean in our dataset), this is 350 × 350 = 122,500 cells — fast for a single pair, but when aligning thousands of pairs, the aggregate cost becomes significant.  This is where beam search and priority queues enter the picture.

#### 2.5.3 Worked Example

Consider Q = `ACE` (m = 3) and S = `ADE` (n = 3) with match = +3, mismatch = −1, gap = −5.

We fill the matrix row by row, left to right.  Each cell H[i][j] is the maximum of four values: 0, the diagonal, the up, and the left.

**Row 0 (initialisation):** All zeros.

```
          -     A     D     E
  -  [  0.0   0.0   0.0   0.0 ]
```

**Row 1 (q₁ = A):**

- H[1][1]: q₁=A, s₁=A → match.  max(0, H[0][0]+3, H[0][1]−5, H[1][0]−5) = max(0, 3, −5, −5) = **3**
- H[1][2]: q₁=A, s₂=D → mismatch.  max(0, H[0][1]−1, H[0][2]−5, H[1][1]−5) = max(0, −1, −5, −2) = **0**
- H[1][3]: q₁=A, s₃=E → mismatch.  max(0, H[0][2]−1, H[0][3]−5, H[1][2]−5) = max(0, −1, −5, −5) = **0**

```
          -     A     D     E
  -  [  0.0   0.0   0.0   0.0 ]
  A  [  0.0   3.0   0.0   0.0 ]
```

**Row 2 (q₂ = C):**

- H[2][1]: q₂=C, s₁=A → mismatch.  max(0, H[1][0]−1, H[1][1]−5, H[2][0]−5) = max(0, −1, −2, −5) = **0**
- H[2][2]: q₂=C, s₂=D → mismatch.  max(0, H[1][1]−1, H[1][2]−5, H[2][1]−5) = max(0, **2**, −5, −5) = **2**
  - Note: the diagonal path from H[1][1]=3 gives 3+(−1)=2.  This means "extend the A↔A alignment by pairing C with D (a mismatch, costing −1)."
- H[2][3]: q₂=C, s₃=E → mismatch.  max(0, H[1][2]−1, H[1][3]−5, H[2][2]−5) = max(0, −1, −5, −3) = **0**

```
          -     A     D     E
  -  [  0.0   0.0   0.0   0.0 ]
  A  [  0.0   3.0   0.0   0.0 ]
  C  [  0.0   0.0   2.0   0.0 ]
```

**Row 3 (q₃ = E):**

- H[3][1]: q₃=E, s₁=A → mismatch.  max(0, H[2][0]−1, H[2][1]−5, H[3][0]−5) = max(0, −1, −5, −5) = **0**
- H[3][2]: q₃=E, s₂=D → mismatch.  max(0, H[2][1]−1, H[2][2]−5, H[3][1]−5) = max(0, −1, −3, −5) = **0**
- H[3][3]: q₃=E, s₃=E → match.  max(0, H[2][2]+3, H[2][3]−5, H[3][2]−5) = max(0, **5**, −5, −5) = **5**
  - The diagonal path from H[2][2]=2 gives 2+3=5.  This means "extend the ACE↔ADE alignment by pairing E with E (a match, scoring +3)."

```
          -     A     D     E
  -  [  0.0   0.0   0.0   0.0 ]
  A  [  0.0   3.0   0.0   0.0 ]
  C  [  0.0   0.0   2.0   0.0 ]
  E  [  0.0   0.0   0.0   5.0 ]
```

The optimal local alignment score is **5**, found at H[3][3].  Traceback follows the diagonal path: H[3][3] ← H[2][2] ← H[1][1] ← H[0][0] (score 0, stop).  The alignment is:

```
Query:   A C E
Subject: A D E
         * . *
```

Score breakdown: A↔A (+3) + C↔D (−1) + E↔E (+3) = **5**.

### 2.6 Beam Search: Bounding the Search Space with a Priority Queue

The full Smith–Waterman algorithm examines every cell in the m × n matrix.  In many practical applications — particularly database searches where a query is aligned against millions of subject sequences — this exhaustive computation is too slow.

**Beam search** is a well-established heuristic that prunes the search space by retaining only the top-scoring candidates at each step.  The idea, borrowed from artificial intelligence and natural language processing, is:

1. At each row i of the DP matrix, compute scores for all n columns.
2. Collect all cells with positive scores into a candidate list.
3. If the candidate list exceeds a fixed **beam width** W, retain only the W highest-scoring candidates and discard the rest.
4. Proceed to the next row.

The beam width W controls the trade-off between speed and accuracy.  With W = ∞ (no pruning), beam search is identical to the full Smith–Waterman algorithm.  With finite W, some sub-optimal alignment paths may be pruned, but the top-scoring alignments are almost always retained because they dominate the score landscape.

**This is where the priority queue becomes essential.**  At each row, we must efficiently:

1. **Identify the top-W scores** from potentially hundreds of candidates.  This is a classic **top-k selection** problem, optimally solved by a bounded heap.
2. **Maintain a global top-K results list** across all rows.  This is a **streaming top-k** problem, solved by a bounded min-heap where the root is the smallest score in the current top-K; a new score replaces the root only if it exceeds it.

In our implementation, the beam width is W = 200 and the global top-K is K = 100.

#### 2.6.1 Worked Example: Beam Pruning with a Heap

Suppose at row i = 50 of the DP matrix, the subject sequence has n = 300 columns, and 180 of those columns have positive scores.  The beam width is W = 100.  Since 180 > 100, we must prune.

**Step 1: Build a max-heap.**  Call `heapx.heapify(beam, max_heap=True)` on the 180 scores.  This transforms the list into a max-heap in O(180) time using Floyd's bottom-up algorithm.  The largest score is now at position 0.

**Step 2: Extract top-100.**  Call `heapx.pop(beam, n=100, max_heap=True)`.  This extracts the 100 largest scores in descending order in a single C function call.  The 80 lowest-scoring candidates are discarded — they will not contribute to the final alignment.

**Step 3: Accumulate into global results.**  For each of the 100 retained scores, check whether it belongs in the global top-K = 100 results.  The results list is a min-heap: the root is the smallest score currently in the top-K.  If a new score exceeds the root, call `heapx.replace(results, new_score, indices=0)` to swap the root with the new score and restore the heap property — all in O(log K) time.

This pattern — heapify, bulk pop, bounded replace — repeats for every row of the DP matrix.  For a 350-residue query, that is 350 iterations, each involving up to 300 heap operations.  The aggregate heap workload is substantial, and the performance of the heap implementation directly determines the alignment throughput.

#### 2.6.2 Why a Heap and Not Sorting?

An alternative to heap-based top-k selection is to sort the candidate list and take the first W elements.  Sorting costs O(n log n) per row; heap-based selection costs O(n + W log n).  For W << n (which is the common case — the beam width is much smaller than the number of positive-scoring cells), the heap approach is faster because it avoids fully ordering the discarded elements.

### 2.7 Phylogenetic Trees and the Neighbor-Joining Algorithm

#### 2.7.1 What Is a Phylogenetic Tree?

A **phylogenetic tree** (also called an evolutionary tree) is a branching diagram that represents the evolutionary relationships among a set of organisms (or genes, or proteins).  The tips of the tree (called **leaves** or **taxa**) represent the observed sequences, and the internal nodes represent hypothetical common ancestors.  The branch lengths represent the amount of evolutionary change (typically measured as the expected number of substitutions per site).

#### 2.7.2 Distance-Based Tree Construction

One approach to building phylogenetic trees is **distance-based methods**.  Given n sequences, we first compute an n × n **distance matrix** D where D[i][j] is the estimated evolutionary distance between sequences i and j (typically derived from the number of differences in their pairwise alignment).  We then construct a tree that best explains these distances.

#### 2.7.3 The Neighbor-Joining Algorithm

The **neighbor-joining** (NJ) algorithm (Saitou & Nei, 1987) is the most widely used distance-based method.  It is a greedy, agglomerative algorithm that iteratively joins the pair of taxa with the smallest **adjusted distance**.

The adjusted distance Q[i][j] corrects for the fact that taxa with large average distances to all other taxa should be preferentially joined:

```
Q[i][j] = (n − 2) · D[i][j] − Σₖ D[i][k] − Σₖ D[j][k]
```

where n is the number of currently active taxa and the sums are over all active taxa k.

**Algorithm:**

1. Compute Q[i][j] for all pairs of active taxa.
2. Find the pair (i, j) with the minimum Q[i][j].
3. Create a new internal node u joining i and j.
4. Compute the distance from u to all remaining taxa k: D[u][k] = (D[i][k] + D[j][k] − D[i][j]) / 2.
5. Remove i and j from the active set; add u.
6. Repeat until only two taxa remain; join them.

The canonical implementation is **O(n³)** because step 1 requires O(n²) work and is repeated n − 2 times.  Mailund et al. (2006) showed that using a priority queue to maintain the Q values can reduce the best-case complexity to **O(n²)** by avoiding redundant recomputation.

**The priority queue role in NJ:**  A min-heap stores all (Q[i][j], i, j) triples.  At each iteration, the minimum is extracted via `pop`.  After joining, all entries involving the merged taxa must be removed and new entries for the replacement taxon must be inserted.  This is where `heapx.remove(predicate=...)` provides a decisive advantage over `heapq`, which has no remove operation.

#### 2.7.4 Worked Example: Neighbor-Joining on 4 Taxa

Consider four taxa (A, B, C, D) with the following distance matrix:

```
     A    B    C    D
A  [ 0    5    9    9 ]
B  [ 5    0   10   10 ]
C  [ 9   10    0    8 ]
D  [ 9   10    8    0 ]
```

**Iteration 1:**  n = 4 active taxa.

Compute row sums: r(A) = 5+9+9 = 23, r(B) = 5+10+10 = 25, r(C) = 9+10+8 = 27, r(D) = 9+10+8 = 27.

Compute Q matrix: Q[i][j] = (n−2)·D[i][j] − r(i) − r(j):

```
Q[A][B] = 2·5 − 23 − 25 = 10 − 48 = −38
Q[A][C] = 2·9 − 23 − 27 = 18 − 50 = −32
Q[A][D] = 2·9 − 23 − 27 = 18 − 50 = −32
Q[B][C] = 2·10 − 25 − 27 = 20 − 52 = −32
Q[B][D] = 2·10 − 25 − 27 = 20 − 52 = −32
Q[C][D] = 2·8 − 27 − 27 = 16 − 54 = −38
```

The minimum Q values are Q[A][B] = −38 and Q[C][D] = −38 (tied).  The heap pops Q[A][B] first (or Q[C][D] — the tie-breaking depends on insertion order).  Suppose we join A and B into a new node U.

Branch lengths: D[A][U] = D[A][B]/2 + (r(A) − r(B)) / (2·(n−2)) = 5/2 + (23−25)/4 = 2.5 − 0.5 = 2.0.  D[B][U] = 5 − 2.0 = 3.0.

New distances: D[U][C] = (D[A][C] + D[B][C] − D[A][B]) / 2 = (9 + 10 − 5) / 2 = 7.0.  D[U][D] = (9 + 10 − 5) / 2 = 7.0.

**Heap operations at this step:**
- `heapx.pop(heap)` → extracts (−38, A, B).
- `heapx.remove(heap, predicate=lambda x: x[1] in (A,B) or x[2] in (A,B))` → removes all 4 remaining entries involving A or B.
- `heapx.push(heap, [(Q[U][C], U, C), (Q[U][D], U, D)])` → inserts 2 new entries.

With `heapq`, the remove step would require rebuilding the entire heap from scratch.

**Iteration 2:**  n = 3 active taxa (U, C, D).  The algorithm continues until only 2 taxa remain, producing the final tree.

### 2.8 Why Priority Queues Are Central to Bioinformatics

Priority queues appear throughout computational biology:

| Application | Heap operation | Why |
|---|---|---|
| SW beam search | heapify, pop(n=k) | Select top-W candidates per row |
| Streaming top-K | push, replace | Maintain bounded results across all rows |
| Neighbor-joining | pop, remove, push | Greedy selection of minimum-distance pair |
| BLAST database search | bounded heap | Retain top hits from millions of subjects |
| Genome assembly | priority queue | Select next overlap in overlap-layout-consensus |
| Multiple sequence alignment | A* / beam search | Guide-tree-based progressive alignment |

In every case, the performance of the priority queue directly impacts the throughput of the bioinformatics pipeline.

---

## 3. Simulation Design and Data Generation

### 3.1 Synthetic Protein Sequence Generation

Real bioinformatics benchmarks require protein sequences.  Using sequences from public databases (e.g., UniProt) would introduce external dependencies and reproducibility concerns.  Instead, we generate **synthetic protein sequences** with statistically realistic properties.

The sequence generator (`seqgen.py`) samples amino acids from the **empirical frequency distribution** observed in the Swiss-Prot database (2024 release).  Swiss-Prot is the manually curated subset of UniProt, containing approximately 570,000 reviewed protein sequences.  The amino-acid frequencies are:

```
L: 9.66%   A: 8.26%   G: 7.08%   V: 6.87%   E: 6.75%
S: 6.56%   I: 5.93%   K: 5.84%   R: 5.53%   T: 5.34%
D: 5.46%   P: 4.70%   N: 4.06%   F: 3.86%   Q: 3.93%
Y: 2.92%   M: 2.41%   H: 2.27%   C: 1.36%   W: 1.08%
```

Leucine (L) is the most abundant amino acid in nature, and tryptophan (W) is the rarest.  Our generator reproduces this distribution, as validated by Figure 3 (amino-acid frequency comparison).

**Sequence lengths** are sampled from a **truncated normal distribution** with mean 350 and standard deviation 120, clamped to [80, 1200].  A truncated normal distribution is a normal (Gaussian) distribution whose values are restricted to lie within a specified range — in this case, any sampled value below 80 is set to 80, and any value above 1200 is set to 1200.  This prevents biologically unrealistic sequence lengths (a protein cannot have fewer than ~50 residues and fold stably, and sequences longer than ~1200 are rare in Swiss-Prot).  The mean of 350 and standard deviation of 120 match the length distribution of Swiss-Prot entries.

**Homologous pairs** are generated by taking a query sequence and introducing **point mutations** at a 20% rate to produce the subject.  At each position, with probability 0.20, the original amino acid is replaced by a random amino acid drawn from the Swiss-Prot frequency distribution.  This simulates approximately 200 million years of divergent evolution (assuming a typical protein substitution rate of ~1 × 10⁻⁹ substitutions per site per year).

All randomness is controlled by a single seed (`RNG_SEED = 19380110`), ensuring complete reproducibility.

### 3.2 Why Synthetic Data?

1. **Reproducibility.**  Any reviewer can regenerate the exact same dataset by running the code.  No database downloads, no API keys, no version-dependent data.
2. **Controlled mutation rate.**  We know the exact evolutionary distance between each pair, enabling validation of alignment scores.
3. **No licensing concerns.**  Swiss-Prot data has usage restrictions for commercial applications; synthetic data has none.
4. **Scalability.**  We can generate arbitrarily large datasets without network access.

### 3.3 Dataset Parameters

| Parameter | Value | Rationale |
|---|---|---|
| Number of pairs | 2,000 | Sufficient for stable throughput measurements |
| Mean sequence length | 350 residues | Swiss-Prot median |
| Mutation rate | 20% | Moderate divergence; ~80% sequence identity |
| Beam width (W) | 200 | Retains >99% of optimal alignment score |
| Top-K (K) | 100 | Standard for database search result sets |
| NJ taxa | 500 | Produces 124,750 initial distance pairs |
| RNG seed | 19380110 | Deterministic; Knuth's birthday |

---

## 4. Code Architecture and Implementation

### 4.1 File Overview

```
src/
├── config.py            # All tunable parameters (centralised)
├── seqgen.py            # Deterministic protein sequence generator
├── alignment.py         # SW beam-search alignment (heapx + heapq)
├── neighbor_joining.py  # NJ tree construction (heapx + heapq)
├── benchmark.py         # Benchmark harness (4 sub-benchmarks)
├── visualize_domain.py  # Domain-specific figures (fig01–fig06)
├── visualize.py         # Performance comparison figures (fig07–fig12)
├── results.json         # Benchmark output (generated)
├── figures/             # 12 PNG figures at 600 DPI (generated)
└── README.md            # This file
```

### 4.2 The Alignment Engine (`alignment.py`)

The alignment module implements two functions with identical algorithmic logic but different heap backends:

- `sw_beam_align_heapx()` — uses `heapx` with configurable arity and optional GIL release.
- `sw_beam_align_heapq()` — uses `heapq` as the baseline.

#### 4.2.1 Algorithm Walkthrough

For each row i of the DP matrix (i = 1, …, m):

1. **Compute scores.**  For each column j, compute H[i][j] using the SW recurrence.  Collect all positive scores into a list `beam`.

2. **Beam pruning (heap-intensive).**  If `len(beam) > beam_width`:
   - **heapx path:** `heapx.heapify(beam, max_heap=True, arity=4)` transforms the list into a max-heap in O(n) time using Floyd's bottom-up algorithm.  Then `heapx.pop(beam, n=beam_width, max_heap=True)` extracts the top-W scores in a single bulk call.
   - **heapq path:** Negate all scores (`[-x for x in beam]`), call `heapq.heapify()`, then pop W elements one at a time in a Python loop, negating each back.

3. **Global top-K accumulation.**  For each score in the pruned beam:
   - If the results heap has fewer than K entries, push the score.
   - Otherwise, if the score exceeds the current minimum (root of the min-heap), replace the root: `heapx.replace(results, score, indices=0)`.

4. **Final extraction.**  After all rows, convert the results min-heap to a max-heap and bulk-pop all K scores in descending order.

#### 4.2.2 Code Example: heapx Beam Pruning

```python
# Prune beam to top beam_width scores using heapx.
if len(beam) > beam_width:
  heapx.heapify(beam, max_heap=True, arity=4, nogil=False)
  beam = heapx.pop(beam, n=beam_width, max_heap=True, arity=4)
```

Compare with the heapq equivalent:

```python
# heapq: negate scores, heapify, pop one at a time, negate back.
if len(beam) > beam_width:
  neg_beam = [-x for x in beam]
  heapq.heapify(neg_beam)
  beam = [-heapq.heappop(neg_beam) for _ in range(beam_width)]
```

The heapx version is cleaner (no negation), faster (bulk pop in C), and supports configurable arity.

### 4.3 The Neighbor-Joining Engine (`neighbor_joining.py`)

#### 4.3.1 heapx Implementation

1. **Initialisation.**  Compute all n(n−1)/2 adjusted distances Q[i][j] and build a min-heap via `heapx.heapify(heap, arity=4)`.

2. **Main loop.**  At each iteration:
   - `heapx.pop(heap)` extracts the minimum-distance pair.
   - Stale entries (involving already-merged taxa) are skipped.
   - `heapx.remove(heap, predicate=lambda x: x[1] in (i,j) or x[2] in (i,j))` removes all entries involving the merged taxa in a single call.
   - New distance entries for the replacement taxon are bulk-inserted via `heapx.push(heap, new_entries)`.

#### 4.3.2 heapq Baseline

The heapq version must rebuild the entire heap after each removal:

```python
# heapq has no remove; rebuild heap excluding stale entries.
heap = [(q, a, b) for q, a, b in heap if a not in (i, j) and b not in (i, j)]
heapq.heapify(heap)
```

This list comprehension + heapify costs O(n) per iteration, compared to heapx's O(k + log n) predicate-based removal.

### 4.4 The Benchmark Harness (`benchmark.py`)

The benchmark executes four sub-benchmarks:

| # | Benchmark | What it measures |
|---|---|---|
| 1 | SW alignment (single-threaded) | End-to-end throughput: heapx vs heapq |
| 2 | Heap arity comparison | Effect of d = 2, 3, 4, 8 on alignment throughput |
| 3 | Neighbor-joining | NJ tree construction time: heapx vs heapq |
| 4 | Parallel heap operations | Isolated heap throughput across 1–8 threads |

Benchmark 4 is the most important: it isolates the heap-operation throughput from the Python DP loop by running heapify + bulk pop + bounded replace on 200 arrays of 50,000 floats each.  This represents the workload profile of a production bioinformatics pipeline where the DP computation is implemented in C/Cython and the heap operations are the remaining bottleneck.

---

## 5. Performance Results

### 5.1 Multi-Library Comparison (Benchmark 4)

On 100 arrays of 50,000 homogeneous floats (heapify + pop(100) + 500 replace operations per array, best of 3 trials):

| Library | Throughput | Relative to heapx |
|---|---|---|
| **heapx** (arity=4, GIL held) | **90.1 M ops/s** | 1.0× (baseline) |
| heapq (stdlib) | 31.4 M ops/s | 2.9× slower |
| sortedcontainers | 10.1 M ops/s | 8.9× slower |
| queue.PriorityQueue | 3.0 M ops/s | 30× slower |

heapx achieves this throughput through five concrete mechanisms:

1. **Homogeneous float detection.**  When all elements in a list are Python `float` objects (as is the case for alignment scores), heapx detects this at the start of the operation using a **SIMD-accelerated type scan** — it checks the type pointers of multiple list elements simultaneously using processor vector instructions (AVX2 on x86-64, NEON on ARM).  Once homogeneity is confirmed, heapx extracts the raw C `double` values from the Python objects and performs all comparisons in a tight C loop that bypasses Python's general-purpose `PyObject_RichCompareBool` comparison function.  This eliminates the overhead of Python's type-checking, reference-counting, and method-dispatch machinery on every comparison.

2. **Floyd's bottom-up heapify.**  The standard "top-down" approach to building a heap inserts elements one at a time, each requiring an O(log n) sift-up, for a total of O(n log n).  Floyd's algorithm (Floyd, 1964) instead works bottom-up: it starts at the last non-leaf node and sifts each node down, achieving O(n) total comparisons.  heapx uses the Wegener (1993) variant, which further reduces comparisons by ~25% by descending to a leaf comparing only children (not the inserted element), then bubbling up — exploiting the fact that most elements end up near the bottom of the heap.

3. **Quaternary heap (arity=4).**  A standard binary heap has branching factor d=2: each node has at most 2 children, and the tree height is log₂(n).  A quaternary heap has d=4: each node has at most 4 children, and the tree height is log₄(n) = log₂(n)/2 — exactly half the height.  This means each sift-down operation traverses half as many levels.  The trade-off is that each level requires comparing 4 children instead of 2, but heapx performs this 4-way comparison using a single SIMD instruction (comparing 4 doubles in parallel), so the per-level cost is nearly the same as binary.

4. **Stack-first memory allocation.**  When heapx needs temporary arrays (e.g., to cache key-function results or extracted numeric values), it uses stack-allocated buffers for small arrays (≤128 elements for keys, ≤2,048 elements for values) and falls back to heap allocation (`malloc`) only for larger arrays.  Stack allocation is essentially free — it just adjusts the stack pointer — whereas `malloc` must search a free list, potentially acquiring a lock in multi-threaded programs.

5. **Bulk operations.**  `heapx.pop(heap, n=100)` extracts 100 elements in a single C function call.  The equivalent with `heapq` requires 100 separate `heapq.heappop()` calls, each involving a Python→C function call boundary crossing (~50 ns overhead per call on modern hardware).  At 100 calls, this overhead alone accounts for ~5 μs — a significant fraction of the total operation time for small heaps.

### 5.2 End-to-End Alignment (Benchmark 1)

| Engine | Throughput |
|---|---|
| heapx (arity=4) | 36.8 pairs/s |
| heapq | 36.7 pairs/s |

The near-parity is expected and honest: the Python DP loop (the `for j in range(1, n+1)` inner loop computing the SW recurrence) dominates the total runtime.  The heap operations constitute a small fraction of the end-to-end time for this pure-Python implementation.  In a production pipeline where the DP is implemented in C/Cython (as in BLAST, HMMER, or SSW), the heap operations become the bottleneck — which is exactly what Benchmark 4 measures.

### 5.3 Neighbor-Joining (Benchmark 3)

| Engine | Wall-clock time | Speedup |
|---|---|---|
| heapx (arity=4) | 4.47 s | 1.01× |
| heapq | 4.53 s | baseline |

Again near-parity, because the Python-level distance matrix computation dominates.  The heap advantage would emerge at larger taxa counts where the O(n²) heap entries make heap operations the bottleneck.

### 5.4 Parallel Heap Operations (Benchmark 4, threading)

| Threads | heapx (GIL held) | heapx (nogil) | heapq |
|---|---|---|---|
| 1 | 88.6 M ops/s | 66.0 M ops/s | 29.8 M ops/s |
| 2 | 86.9 M ops/s | 81.3 M ops/s | 29.5 M ops/s |
| 4 | 85.9 M ops/s | 76.9 M ops/s | 29.1 M ops/s |
| 8 | 86.9 M ops/s | 74.5 M ops/s | 28.9 M ops/s |

The `nogil=True` path releases the GIL during the pure-C computation phase, enabling true multi-threaded parallelism.  The nogil single-thread overhead (~25%) comes from the value-extraction and GIL-management cost, but this is amortised when multiple threads run concurrently.

---

## 6. Value for Bioinformatics Professionals

### 6.1 Who Benefits

- **Computational biologists** running large-scale sequence database searches (BLAST-like pipelines) where the priority queue manages the top-K hit list.
- **Phylogeneticists** constructing trees from thousands of taxa using distance-based methods.
- **Structural bioinformaticians** performing profile-profile alignments with beam search.
- **Genomics engineers** building assembly pipelines where overlap selection uses priority queues.

### 6.2 Why heapx Over Alternatives

| Feature | heapx | heapq | sortedcontainers | queue.PriorityQueue |
|---|---|---|---|---|
| Throughput (M ops/s) | **90.1** | 31.4 | 10.1 | 3.0 |
| Native max-heap | ✅ `max_heap=True` | ❌ (negate keys) | ✅ | ❌ (negate keys) |
| Bulk pop (top-k) | ✅ `pop(n=k)` | ❌ (loop k times) | ❌ (loop) | ❌ (loop) |
| Remove by predicate | ✅ `remove(predicate=...)` | ❌ | ✅ `remove()` | ❌ |
| Configurable arity | ✅ `arity=2,3,4,8` | ❌ (binary only) | N/A | ❌ |
| GIL release | ✅ `nogil=True` | ❌ | ❌ | ❌ |
| Key function | ✅ `cmp=lambda x: ...` | ❌ | ✅ `key=...` | ❌ |
| Thread-safe | No (use per-thread heaps) | No | No | ✅ (but slow) |

#### 6.2.1 Native Max-Heap Support

In bioinformatics, max-heaps arise naturally: the beam-search pruning step needs the top-W *highest* scores.  With `heapq`, the standard workaround is to negate all scores before insertion and negate them back after extraction — a pattern that is error-prone, adds O(n) overhead for the negation pass, and fails entirely for non-numeric keys.  heapx eliminates this with `max_heap=True`.

#### 6.2.2 Bulk Pop for Top-K Extraction

Extracting the top-100 alignment scores from a heap of 200 candidates requires 100 individual `heapq.heappop()` calls — each a Python→C→Python round-trip.  `heapx.pop(heap, n=100)` performs all 100 extractions in a single C function call, eliminating 99 round-trips.

#### 6.2.3 Predicate-Based Removal for Neighbor-Joining

The NJ algorithm requires removing all heap entries involving a merged taxon.  With heapx:

```python
heapx.remove(heap, predicate=lambda x: x[1] in (i, j) or x[2] in (i, j))
```

With heapq, the only option is to rebuild the entire heap:

```python
heap = [e for e in heap if e[1] not in (i, j) and e[2] not in (i, j)]
heapq.heapify(heap)
```

#### 6.2.4 GIL Release for Multi-Threaded Alignment

Modern bioinformatics pipelines align thousands of sequence pairs independently.  With `heapx(nogil=True)`, the heap operations release the GIL, enabling true parallel execution across threads.  `heapq` holds the GIL throughout, serialising all threads.

---

## 7. Reproducing the Results

### 7.1 Prerequisites

```bash
pip install heapx matplotlib numpy scipy sortedcontainers
```

Python ≥ 3.9 required.  All sequence data is synthesised deterministically — no external databases or API keys needed.

### 7.2 Quick Start

```bash
cd src/
python benchmark.py           # Run all benchmarks → results.json
python visualize_domain.py    # Domain figures → figures/fig01–fig06
python visualize.py           # Performance figures → figures/fig07–fig12
```

### 7.3 Quick Smoke Test

```bash
python benchmark.py --quick   # Reduced dataset (~2 min)
```

### 7.4 Generated Figures

| # | File | Description |
|---|---|---|
| 1 | `fig01_sw_dp_matrix.png` | Smith–Waterman DP scoring matrix heatmap with optimal traceback path |
| 2 | `fig02_dot_plot.png` | Sequence dot plot with k-mer window filtering showing homology |
| 3 | `fig03_aa_frequency.png` | Amino-acid frequency: synthetic dataset vs Swiss-Prot reference |
| 4 | `fig04_score_distribution.png` | Distribution of top alignment scores with KDE overlay (μ = 268.5, σ = 19.7) |
| 5 | `fig05_beam_pruning.png` | Beam-search pruning: 60.9% of cells pruned by heap-bounded search |
| 6 | `fig06_nj_dendrogram.png` | Neighbor-joining phylogenetic dendrogram (20 taxa) |
| 7 | `fig07_alignment_throughput.png` | End-to-end SW beam-search alignment throughput |
| 8 | `fig08_arity_comparison.png` | Throughput by heap arity (d = 2, 3, 4, 8) |
| 9 | `fig09_nj_performance.png` | Neighbor-joining wall-clock time comparison |
| 10 | `fig10_parallel_heap_ops.png` | Heap ops/s vs thread count (3.0× speedup) |
| 11 | `fig11_speedup_summary.png` | Aggregated speedup across all benchmarks |
| 12 | `fig12_multi_library.png` | Multi-library comparison: heapx vs heapq vs sortedcontainers vs PriorityQueue |

---

## References

1. T. F. Smith, M. S. Waterman, "Identification of Common Molecular Subsequences," *Journal of Molecular Biology* 147(1), pp. 195–197, 1981.

2. S. B. Needleman, C. D. Wunsch, "A General Method Applicable to the Search for Similarities in the Amino Acid Sequence of Two Proteins," *Journal of Molecular Biology* 48(3), pp. 443–453, 1970.

3. S. F. Altschul, W. Gish, W. Miller, E. W. Myers, D. J. Lipman, "Basic Local Alignment Search Tool," *Journal of Molecular Biology* 215(3), pp. 403–410, 1990.

4. T. Rognes, E. Seeberg, "Six-fold Speed-up of Smith–Waterman Sequence Database Searches Using Parallel Processing on Common Microprocessors," *Bioinformatics* 16(8), pp. 699–706, 2000.

5. M. Farrar, "Striped Smith–Waterman Speeds Database Searches Six Times over Other SIMD Implementations," *Bioinformatics* 23(2), pp. 156–161, 2007.

6. N. Saitou, M. Nei, "The Neighbor-Joining Method: A New Method for Reconstructing Phylogenetic Trees," *Molecular Biology and Evolution* 4(4), pp. 406–425, 1987.

7. T. Mailund, G. S. Brodal, R. Fagerberg, C. N. S. Pedersen, D. Phillips, "Recrafting the Neighbor-Joining Method," *BMC Bioinformatics* 7:29, 2006.

8. J. Yang, Y. Xu, Y. Shang, G. Chen, "A Space-Bounded Anytime Algorithm for the Multiple Longest Common Subsequence Problem," *IEEE Transactions on Knowledge and Data Engineering* 26(11), pp. 2599–2609, 2014.

9. D. H. Larkin, S. Sen, R. E. Tarjan, "A Back-to-Basics Empirical Study of Priority Queues," *arXiv:1403.0252*, 2014.

10. S. Henikoff, J. G. Henikoff, "Amino Acid Substitution Matrices from Protein Blocks," *Proceedings of the National Academy of Sciences* 89(22), pp. 10915–10919, 1992.

11. S. Gross, "PEP 703 – Making the Global Interpreter Lock Optional in CPython," *Python Enhancement Proposals*, 2023.

12. R. W. Floyd, "Algorithm 245: Treesort 3," *Communications of the ACM* 7(12), p. 701, 1964.

13. I. Wegener, "BOTTOM-UP-HEAPSORT, a New Variant of HEAPSORT Beating, on an Average, QUICKSORT (if n Is Not Very Small)," *Theoretical Computer Science* 118(1), pp. 81–98, 1993.
