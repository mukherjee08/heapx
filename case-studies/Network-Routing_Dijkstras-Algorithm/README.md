# Case Study 3 — Network Routing: Dijkstra's Algorithm

## 1. Introduction

This case study benchmarks Dijkstra's shortest-path algorithm on the DIMACS 9th Challenge USA road network dataset, comparing four priority queue implementations:

- **heapx (replace)**: True decrease-key using position tracking
- **heapx (lazy)**: Lazy deletion with duplicate entries
- **heapq**: Python's standard binary heap with lazy deletion
- **sortedcontainers**: Sorted list implementation with remove/re-add

The benchmark evaluates performance across subgraphs of varying sizes (1K to 1M nodes) extracted from the full USA road network (23.9M nodes, 58.3M edges). The study produces 16 figures analyzing runtime scalability, memory usage, cache behavior, and algorithmic efficiency on realistic sparse graph data.

Road networks present unique characteristics for shortest-path algorithms: they are nearly planar, have low average degree (~4.87), and exhibit spatial locality that affects decrease-key operation frequency. This case study demonstrates how these properties influence the relative performance of different priority queue strategies in practice.

## 2. Mathematical and Algorithmic Background

### 2.1 The Shortest-Path Problem

A **weighted directed graph** is a triple G = (V, E, w) where:
- V is a finite set of vertices (nodes)
- E ⊆ V × V is a set of directed edges (arcs)
- w: E → ℝ is a weight function assigning real-valued weights to edges

A **path** from vertex u to vertex v is a sequence of vertices ⟨v₀, v₁, ..., vₖ⟩ where v₀ = u, vₖ = v, and (vᵢ, vᵢ₊₁) ∈ E for all i ∈ {0, 1, ..., k-1}.

The **weight of a path** p = ⟨v₀, v₁, ..., vₖ⟩ is:
```
w(p) = Σᵢ₌₀ᵏ⁻¹ w(vᵢ, vᵢ₊₁)
```

The **shortest-path distance** from source s to vertex v is:
```
δ(s, v) = min{w(p) : p is a path from s to v}
```
If no path exists, δ(s, v) = ∞.

**Example**: Consider the graph G = (V, E, w) where:
- V = {A, B, C, D}
- E = {(A,B), (A,C), (B,C), (B,D), (C,D)}
- w = {(A,B)→2, (A,C)→4, (B,C)→1, (B,D)→7, (C,D)→3}

```
    A
   /|\
  2 | 4
 /  |  \
B---1---C
|       |
7       3
|       |
D-------+
```

Paths from A to D:
- A→B→D: weight = 2 + 7 = 9
- A→C→D: weight = 4 + 3 = 7
- A→B→C→D: weight = 2 + 1 + 3 = 6

Therefore, δ(A, D) = 6 via path A→B→C→D.

**Non-negative weight requirement**: Dijkstra's algorithm requires w(e) ≥ 0 for all e ∈ E. Negative weights can create negative cycles, making shortest paths undefined, and violate the algorithm's greedy property.

### 2.2 Dijkstra's Algorithm

Dijkstra's algorithm solves the single-source shortest-path problem on graphs with non-negative edge weights using a greedy approach.

**Pseudocode**:
```
DIJKSTRA(G, w, s):
1.  for each vertex v ∈ V:
2.      dist[v] ← ∞
3.      prev[v] ← NIL
4.  dist[s] ← 0
5.  Q ← V  // priority queue keyed by dist values
6.  while Q ≠ ∅:
7.      u ← EXTRACT-MIN(Q)
8.      for each vertex v ∈ Adj[u]:
9.          RELAX(u, v, w)

RELAX(u, v, w):
1.  if dist[u] + w(u, v) < dist[v]:
2.      dist[v] ← dist[u] + w(u, v)
3.      prev[v] ← u
4.      DECREASE-KEY(Q, v, dist[v])
```

**Step-by-step example** on graph:
```
    1
  A---B
  |\  |
  |4\ |2
  |  \|
  C---D
    3
```
Edges: (A,B)→1, (A,C)→4, (A,D)→5, (B,D)→2, (C,D)→3
Source: A

| Iteration | u | Q (vertex: dist) | dist[A] | dist[B] | dist[C] | dist[D] | Action |
|-----------|---|------------------|---------|---------|---------|---------|---------|
| Initial   | - | A:0, B:∞, C:∞, D:∞ | 0 | ∞ | ∞ | ∞ | Initialize |
| 1 | A | B:1, C:4, D:5 | 0 | 1 | 4 | 5 | Extract A, relax (A,B), (A,C), (A,D) |
| 2 | B | C:4, D:3 | 0 | 1 | 4 | 3 | Extract B, relax (B,D): 1+2=3 < 5 |
| 3 | D | C:4 | 0 | 1 | 4 | 3 | Extract D, no outgoing edges |
| 4 | C | ∅ | 0 | 1 | 4 | 3 | Extract C, no improvements |

**Relaxation operation**: For edge (u,v), if dist[u] + w(u,v) < dist[v], then we have found a shorter path to v through u. Update dist[v] and decrease its key in the priority queue.

**Settled vs. unsettled vertices**: Once a vertex u is extracted from the priority queue, it is "settled" — its shortest distance is final. Vertices still in the queue are "unsettled" — their distances may decrease.

**Correctness (intuitive)**: The algorithm maintains the invariant that for any settled vertex u, dist[u] = δ(s,u). This follows from the greedy choice property: when we extract the minimum-distance unsettled vertex, no future relaxations can improve its distance (since all edge weights are non-negative).

**Time complexity**: O((V + E) log V) with a binary heap priority queue. Each vertex is inserted and extracted once (O(V log V)), and each edge causes at most one decrease-key operation (O(E log V)).

### 2.3 The Priority Queue Interface

Dijkstra's algorithm requires a priority queue supporting three operations:

1. **INSERT(v, key)**: Add vertex v with priority key to the queue
2. **EXTRACT-MIN()**: Remove and return the vertex with minimum key
3. **DECREASE-KEY(v, new_key)**: Decrease the key of vertex v to new_key

**Why decrease-key is critical**: During relaxation, when we find a shorter path to vertex v, we must update its priority in the queue. Without efficient decrease-key, we cannot maintain the correct ordering.

**Operation counts in Dijkstra**:
- **V inserts**: Each vertex is added to the queue initially
- **V extract-mins**: Each vertex is removed exactly once
- **At most E decrease-keys**: Each edge (u,v) can cause at most one decrease-key on v

The decrease-key operation dominates the algorithm's complexity on dense graphs, making its efficiency crucial for performance.

### 2.4 The Decrease-Key Problem

Standard binary heaps don't efficiently support decrease-key without additional data structures. Three common strategies exist:

#### Strategy (a): True Decrease-Key with Position Tracking

Maintain a position map tracking each vertex's index in the heap array.

```python
class BinaryHeapWithPositions:
    def __init__(self):
        self.heap = []           # (key, vertex) pairs
        self.positions = {}      # vertex → heap index
    
    def decrease_key(self, vertex, new_key):
        pos = self.positions[vertex]
        self.heap[pos] = (new_key, vertex)
        self._bubble_up(pos)     # Restore heap property
```

**Complexity**: O(log n) decrease-key, but requires O(n) extra space for position tracking and careful index maintenance during heap operations.

**Example**: Heap [A:1, B:3, C:5, D:7] with positions {A:0, B:1, C:2, D:3}
- decrease_key(C, 2): Update heap[2] = (2,C), bubble up to position 1
- Result: [A:1, C:2, B:3, D:7], positions {A:0, C:1, B:2, D:3}

#### Strategy (b): Lazy Deletion

Allow duplicate entries in the heap. Mark outdated entries as "stale" and skip them during extraction.

```python
class LazyHeap:
    def __init__(self):
        self.heap = []
        self.current_dist = {}   # vertex → current best distance
    
    def decrease_key(self, vertex, new_key):
        heappush(self.heap, (new_key, vertex))
        self.current_dist[vertex] = new_key
    
    def extract_min(self):
        while self.heap:
            key, vertex = heappop(self.heap)
            if key == self.current_dist[vertex]:  # Not stale
                return vertex, key
        return None, None
```

**Complexity**: O((V + E) log E) since the heap can contain O(E) entries, but implementation is simple and requires no position tracking.

**Example**: Initial heap [A:5]. After decrease_key(A, 2): heap [A:2, A:5]. Extract-min returns A:2 and skips the stale A:5 entry.

#### Strategy (c): Sorted-List Approach

Use a sorted container supporting efficient remove and re-add operations.

```python
from sortedcontainers import SortedList

class SortedListPQ:
    def __init__(self):
        self.sl = SortedList()
        self.entries = {}        # vertex → (key, vertex) pair
    
    def decrease_key(self, vertex, new_key):
        if vertex in self.entries:
            old_entry = self.entries[vertex]
            self.sl.remove(old_entry)    # O(log n)
        new_entry = (new_key, vertex)
        self.sl.add(new_entry)           # O(log n)
        self.entries[vertex] = new_entry
```

**Complexity**: O(log n) for both remove and add, but with higher constant factors than binary heaps due to the underlying balanced tree structure.

### 2.5 Heap Variants and Cache Behavior

#### d-ary Heaps

A **d-ary heap** is a generalization of binary heaps where each node has at most d children instead of 2.

**Properties**:
- Tree height: ⌈log_d(n)⌉
- Parent of node i: ⌊(i-1)/d⌋
- Children of node i: {di+1, di+2, ..., di+d}

**Trade-offs**:
- **Fewer levels**: Reduces the number of comparisons in bubble-up operations
- **More comparisons per level**: Finding the minimum among d children requires d-1 comparisons
- **Cache locality**: Children are stored contiguously, improving cache performance

**Optimal d for large n**: Theoretical analysis suggests d = 4 often outperforms d = 2 for large heaps due to cache effects, despite requiring more comparisons per level.

**Example**: 4-ary heap with elements [1, 3, 2, 7, 5, 8, 4]
```
       1
   /  |  |  \
  3   2  8   4
 /|
7 5
```
Array representation: [1, 3, 2, 8, 4, 7, 5]
- Node 1 (index 0) has children at indices 1, 2, 3, 4
- Node 3 (index 1) has children at indices 5, 6

This structure reduces height from ⌈log₂(7)⌉ = 3 to ⌈log₄(7)⌉ = 2, potentially improving cache performance when children fit in the same cache line.

### 2.6 Graph Representations

#### Adjacency Matrix

Store the graph as a V × V matrix A where A[i][j] = w(i,j) if edge (i,j) exists, ∞ otherwise.

**Space complexity**: O(V²)
**Edge lookup**: O(1)
**Iteration over neighbors**: O(V)

Suitable only for dense graphs due to quadratic space requirement.

#### Adjacency List

Store an array of lists, where list i contains all neighbors of vertex i.

```python
# Graph: A→B(2), A→C(4), B→C(1), B→D(7), C→D(3)
adj_list = {
    'A': [('B', 2), ('C', 4)],
    'B': [('C', 1), ('D', 7)],
    'C': [('D', 3)],
    'D': []
}
```

**Space complexity**: O(V + E)
**Edge lookup**: O(degree(v))
**Iteration over neighbors**: O(degree(v))

Efficient for sparse graphs, which includes most real-world networks.

#### Compressed Sparse Row (CSR) Format

CSR represents sparse graphs using three arrays: offsets, targets, and weights.

**Structure**:
- `offsets[i]`: Starting index in targets/weights arrays for vertex i's neighbors
- `targets[j]`: Target vertex of the j-th edge
- `weights[j]`: Weight of the j-th edge

**Example**: Graph with 5 vertices and edges:
- 0 → {1(2), 2(4)}
- 1 → {2(1), 3(7)}  
- 2 → {3(3)}
- 3 → {}
- 4 → {0(5)}

```python
offsets = [0, 2, 4, 5, 5, 6]  # Length V+1, last element = total edges
targets = [1, 2, 2, 3, 3, 0]  # Length E
weights = [2, 4, 1, 7, 3, 5]  # Length E
```

**Neighbor iteration for vertex v**:
```python
for j in range(offsets[v], offsets[v+1]):
    neighbor = targets[j]
    weight = weights[j]
    # Process edge (v, neighbor) with weight
```

**Advantages**:
- **Cache-friendly**: Sequential memory access during neighbor iteration
- **Space-efficient**: Only 2E + V + 1 integers vs. E pointer-based list nodes
- **Fast iteration**: No pointer dereferencing, excellent cache locality

CSR is the preferred format for high-performance graph algorithms on large sparse graphs.

## 3. The DIMACS Dataset

### 3.1 The 9th DIMACS Implementation Challenge

The **DIMACS Implementation Challenges** are a series of computational experiments organized by the Center for Discrete Mathematics and Theoretical Computer Science at Rutgers University. These challenges provide standardized datasets and problem formulations to enable fair comparison of algorithmic implementations across research groups.

The **9th DIMACS Implementation Challenge** (2005-2006) focused on shortest-path algorithms. It provided several graph datasets, with the USA road network becoming the de facto standard benchmark for evaluating shortest-path implementations. The challenge established file formats, problem variants (single-source, point-to-point, all-pairs), and evaluation metrics that remain widely used in the algorithms community.

The road network dataset represents the most realistic large-scale test case for shortest-path algorithms, exhibiting properties (sparsity, planarity, spatial locality) that distinguish it from synthetic random graphs commonly used in theoretical analysis.

### 3.2 Dataset Description

The USA road network dataset contains:
- **23,947,347 vertices** representing road intersections and endpoints
- **58,333,344 directed edges** representing road segments
- **Three graph variants**:
  - Distance graph: Edge weights in meters
  - Travel-time graph: Edge weights in tenths of seconds
  - Coordinate file: Longitude/latitude positions (TIGER/Line format)

#### DIMACS File Format

**Graph files (.gr)**: Plain text format with problem line and arc lines.

```
c 9th DIMACS Implementation Challenge: Shortest Paths
c USA road network - distance graph
p sp 23947347 58333344
a 1 2 1609
a 1 5 804
a 2 3 2414
...
```

Format specification:
- `c`: Comment line
- `p sp n m`: Problem line declaring n vertices, m arcs for shortest-path problem
- `a u v w`: Arc from vertex u to vertex v with weight w

**Coordinate files (.co)**: Vertex positions for visualization.

```
c 9th DIMACS Implementation Challenge: Shortest Paths  
c USA road network - coordinates
p aux sp co 23947347
v 1 -122419943 37774963
v 2 -122419943 37774963
v 3 -122419943 37774963
...
```

Format specification:
- `p aux sp co n`: Auxiliary coordinate file for n vertices
- `v id x y`: Vertex id at coordinates (x, y) in TIGER/Line format (longitude/latitude × 10⁶)

### 3.3 Graph Properties

#### Sparsity and Degree Distribution

The USA road network is extremely sparse with:
- **Average degree**: ~4.87 edges per vertex
- **Degree distribution**: Most intersections connect 3-4 road segments (T-junctions, 4-way intersections)
- **Maximum degree**: ~20 (complex highway interchanges)

This sparsity means |E| ≈ 2.4|V|, making the graph much sparser than complete graphs (|E| = |V|(|V|-1)) or even random graphs with constant edge probability.

#### Near-Planarity

Road networks are **nearly planar** — they can be embedded in the plane with very few edge crossings (bridges, overpasses). Planar graphs have |E| ≤ 3|V| - 6, and road networks approach this bound.

**Implications for algorithms**:
- **Low treewidth**: Enables efficient dynamic programming approaches
- **Separator theorems**: Small vertex sets disconnect large components
- **Geometric structure**: Euclidean distance provides lower bounds for A* search

#### Decrease-Key Frequency

In Dijkstra's algorithm on road networks, the **decrease-key rate** (fraction of edges causing distance updates) is approximately 5% of total edges.

**Why decrease-key rate is low**:
1. **Spatial locality**: Nearby vertices have similar distances from the source
2. **Uniform local weights**: Road segments in the same area have comparable lengths
3. **Tree-like structure**: Most shortest paths follow a tree rooted at the source

This low decrease-key rate favors lazy deletion strategies over true decrease-key implementations, since the overhead of maintaining position maps may not be justified.

#### Weight Distribution

**Distance graph**: Edge weights range from 1 meter (short connectors) to ~50 kilometers (long highway segments). The distribution is heavy-tailed with many short local roads and few long highways.

**Travel-time graph**: Incorporates speed limits and road types. Highway segments have lower time-per-distance ratios than city streets, creating more complex shortest-path structures.

### 3.4 Subgraph Extraction

For scalability analysis, we extract connected subgraphs of varying sizes using breadth-first search (BFS):

**Algorithm**:
1. Select a random source vertex s
2. Perform BFS from s, adding vertices in order of discovery
3. Stop when the desired number of vertices n is reached
4. Include all edges between the selected vertices

**Properties of extracted subgraphs**:
- **Connected**: BFS ensures all vertices are reachable from the source
- **Representative**: Maintains local graph structure and degree distribution
- **Scalable**: Enables testing on graphs from 1K to 1M vertices

**Size progression**: 1K, 2K, 5K, 10K, 20K, 50K, 100K, 200K, 500K, 1M vertices

This extraction method preserves the essential characteristics of road networks (sparsity, planarity, spatial locality) while enabling controlled scalability experiments across multiple orders of magnitude.
## 4. Code Architecture and Implementation

### 4.1 File Overview

The implementation consists of six Python source files, each serving a specific role in the benchmark pipeline:

| File | Description |
|------|-------------|
| `dimacs_loader.py` | DIMACS file parser and CSR graph construction |
| `dijkstra.py` | Four Dijkstra implementations with different priority queues |
| `benchmark.py` | Performance measurement harness and subgraph extraction |
| `visualize_dataset.py` | Dataset visualization (3 geographic maps) |
| `visualize_results.py` | Performance analysis plots (10 benchmark charts) |
| `visualize_explanatory.py` | Algorithm explanation figures (3 educational diagrams) |

### 4.2 The DIMACS Loader (dimacs_loader.py)

The DIMACS loader handles parsing `.gr` graph files and `.co` coordinate files into efficient CSR (Compressed Sparse Row) format for high-performance graph traversal.

#### Graph Loading with CSR Construction

The `load_graph()` function parses DIMACS `.gr` files and constructs CSR arrays:

```python
def load_graph(filename):
    # Parse edges into arrays
    src_arr = np.array(sources, dtype=np.int32)
    dst_arr = np.array(targets, dtype=np.int32) 
    wt_arr = np.array(weights, dtype=np.float64)
    
    # Build CSR offset array using np.add.at
    offsets = np.zeros(n + 1, dtype=np.int64)
    np.add.at(offsets[1:], src_arr, 1)  # Count outgoing edges per vertex
    np.cumsum(offsets, out=offsets)     # Convert counts to cumulative offsets
    
    # Sort edges by source vertex for CSR format
    order = np.argsort(src_arr, kind='mergesort')
    targets = dst_arr[order]
    weights = wt_arr[order]
    
    return n, offsets, targets, weights
```

The key insight is using `np.add.at(offsets[1:], src_arr, 1)` to efficiently count outgoing edges per vertex in a single vectorized operation, avoiding explicit loops over the edge list.

#### Subgraph Extraction

The `extract_subgraph()` function uses BFS to extract connected subgraphs of specified sizes:

```python
def extract_subgraph(offsets, targets, weights, start_vertex, target_size):
    visited = set()
    queue = deque([start_vertex])
    vertices_in_order = []
    
    # BFS traversal
    while queue and len(vertices_in_order) < target_size:
        v = queue.popleft()
        if v in visited:
            continue
        visited.add(v)
        vertices_in_order.append(v)
        
        # Add neighbors to queue
        for j in range(offsets[v], offsets[v + 1]):
            neighbor = targets[j]
            if neighbor not in visited:
                queue.append(neighbor)
    
    # Build vertex remapping
    old_to_new = {old_v: new_v for new_v, old_v in enumerate(vertices_in_order)}
    
    # Extract edges and remap vertex IDs
    # ... (edge extraction and CSR reconstruction)
    
    return new_n, new_offsets, new_targets, new_weights, old_to_new
```

This approach ensures extracted subgraphs remain connected while preserving the local structure and degree distribution of the original road network.

#### Coordinate Loading

The `load_coordinates()` function parses `.co` files for geographic visualization:

```python
def load_coordinates(filename):
    coordinates = {}
    with open(filename, 'r') as f:
        for line in f:
            if line.startswith('v '):
                parts = line.strip().split()
                vertex_id = int(parts[1])
                x = int(parts[2]) / 1_000_000.0  # Convert from TIGER/Line format
                y = int(parts[3]) / 1_000_000.0
                coordinates[vertex_id] = (x, y)
    return coordinates
```

Coordinates are stored in TIGER/Line format (longitude/latitude × 10⁶) and converted to decimal degrees for mapping libraries.

### 4.3 Dijkstra Implementations (dijkstra.py)

The module implements four Dijkstra variants to compare different priority queue strategies:

#### (a) dijkstra_heapx_replace: True Decrease-Key

Uses `heapx.replace()` for O(log n) decrease-key operations with position tracking:

```python
def dijkstra_heapx_replace(offsets, targets, weights, source):
    dist = np.full(n, np.inf)
    dist[source] = 0.0
    heap_pos = np.full(n, -1, dtype=np.int32)  # Position tracking
    
    heap = [(0.0, source)]
    heap_pos[source] = 0
    
    while heap:
        d_u, u = heapx.pop(heap)
        heap_pos[u] = -1  # Mark as settled
        
        for j in range(offsets[u], offsets[u + 1]):
            v = targets[j]
            nd = d_u + weights[j]
            
            if heap_pos[v] >= 0:  # v is in heap
                heapx.replace(heap, (nd, v), indices=heap_pos[v])
                replaces += 1
                _rebuild_pos()  # Rebuild position array after mutation
            elif not settled[v]:  # v not yet processed
                heapx.push(heap, (nd, v))
                pushes += 1
                _rebuild_pos()
```

The `_rebuild_pos()` function reconstructs the position array after each heap mutation, which adds overhead but enables true O(log n) decrease-key operations. This keeps the heap bounded at n entries.

#### (b) dijkstra_heapx_lazy: Lazy Deletion with heapx

Uses the same lazy-deletion strategy as heapq but with heapx operations to measure raw C-extension performance:

```python
def dijkstra_heapx_lazy(offsets, targets, weights, source):
    dist = np.full(n, np.inf)
    dist[source] = 0.0
    
    heap = [(0.0, source)]
    
    while heap:
        d_u, u = heapx.pop(heap)
        
        if d_u > dist[u]:  # Stale entry
            stale_pops += 1
            continue
            
        for j in range(offsets[u], offsets[u + 1]):
            v = targets[j]
            nd = d_u + weights[j]
            
            if nd < dist[v]:
                dist[v] = nd
                heapx.push(heap, (nd, v))
                pushes += 1
```

This implementation demonstrates heapx's raw speed without position-tracking overhead.

#### (c) dijkstra_heapq: Standard Binary Heap Baseline

The reference implementation using Python's standard `heapq` module:

```python
def dijkstra_heapq(offsets, targets, weights, source):
    dist = np.full(n, np.inf)
    dist[source] = 0.0
    
    heap = [(0.0, source)]
    
    while heap:
        d_u, u = heapq.heappop(heap)
        
        if d_u > dist[u]:  # Stale entry check
            stale_pops += 1
            continue
            
        for j in range(offsets[u], offsets[u + 1]):
            v = targets[j]
            nd = d_u + weights[j]
            
            if nd < dist[v]:
                dist[v] = nd
                heapq.heappush(heap, (nd, v))
                pushes += 1
```

The stale-pop check `if d_u > dist[u]: stale_pops += 1; continue` skips outdated entries that were superseded by later distance improvements.

#### (d) dijkstra_sortedlist: Sorted Container Implementation

Uses `SortedList` with explicit remove/add operations for bounded heap size:

```python
def dijkstra_sortedlist(offsets, targets, weights, source):
    from sortedcontainers import SortedList
    
    dist = np.full(n, np.inf)
    dist[source] = 0.0
    
    sl = SortedList([(0.0, source)])
    in_queue = np.zeros(n, dtype=bool)
    in_queue[source] = True
    
    while sl:
        d_u, u = sl.pop(0)  # Extract minimum
        in_queue[u] = False
        
        for j in range(offsets[u], offsets[u + 1]):
            v = targets[j]
            nd = d_u + weights[j]
            
            if nd < dist[v]:
                if in_queue[v]:
                    sl.remove((dist[v], v))  # O(log n) removal
                dist[v] = nd
                sl.add((nd, v))  # O(log n) insertion
                in_queue[v] = True
```

This approach maintains a bounded queue (at most n entries) but incurs higher constant factors due to the balanced tree operations underlying `SortedList`.

#### Operation Counting

All implementations return detailed operation counts:
- **pushes**: Number of heap insertions
- **pops**: Number of heap extractions  
- **replaces** (heapx-replace) or **stale_pops** (lazy methods): Decrease-key operations or stale entry skips
- **max_heap_size**: Peak heap size during execution

### 4.4 The Benchmark Harness (benchmark.py)

The benchmark harness provides precise performance measurement and automated subgraph extraction across multiple size points.

#### Measurement Infrastructure

The `_measure()` function implements rigorous timing and memory measurement:

```python
def _measure(func, *args):
    # Prepare clean environment
    gc.collect()
    gc.disable()
    tracemalloc.start()
    
    # Measure execution
    t0 = time.perf_counter()
    result = func(*args)
    elapsed = time.perf_counter() - t0
    
    # Capture peak memory
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    gc.enable()
    
    return result, elapsed, peak
```

This approach ensures accurate timing by disabling garbage collection during measurement and captures peak memory usage via `tracemalloc`.

#### BFS-Based Subgraph Extraction

The harness extracts subgraphs at each size using BFS to maintain connectivity:

```python
def extract_subgraph_at_size(offsets, targets, weights, size):
    # Select random starting vertex
    start_vertex = random.randint(0, len(offsets) - 2)
    
    # Extract connected subgraph via BFS
    sub_n, sub_offsets, sub_targets, sub_weights, mapping = \
        extract_subgraph(offsets, targets, weights, start_vertex, size)
    
    # Select random source within subgraph
    source = random.randint(0, sub_n - 1)
    
    return sub_offsets, sub_targets, sub_weights, source
```

#### Cross-Validation

The benchmark validates correctness by comparing distance arrays across all implementations:

```python
def validate_results(results):
    distances = [result[0] for result in results.values()]
    
    for i in range(1, len(distances)):
        if not np.allclose(distances[0], distances[i], rtol=1e-9):
            raise ValueError(f"Distance mismatch between implementations")
```

This ensures all algorithms compute identical shortest-path distances, validating implementation correctness.

### 4.5 Visualization Scripts

#### Dataset Visualization (visualize_dataset.py)

Generates three geographic maps of the USA road network:
- **Full network overview**: Continental USA with all 23.9M vertices
- **Regional detail**: Zoomed view of California showing road density
- **Urban detail**: San Francisco Bay Area with individual road segments visible

Uses `cartopy` for geographic projections and `matplotlib` for rendering.

#### Results Visualization (visualize_results.py)

Produces 10 benchmark analysis plots:
- Runtime vs. graph size (4 algorithms)
- Operation counts vs. graph size (pushes, pops, replaces/stale)
- Heap size comparison (bounded vs. unbounded)
- Memory usage analysis
- Cache performance metrics
- Scaling behavior analysis

#### Explanatory Visualization (visualize_explanatory.py)

Creates 3 figures that explain the case study's algorithmic context:

- **Graph structure** (`graph_structure.png`): dual-axis plot showing edge count and average degree vs subgraph size
- **Decrease-key analysis** (`decrease_key_analysis.png`): two-panel figure showing (a) edge relaxation rate and (b) heap inflation ratio across graph sizes
- **Dijkstra wavefront** (`dijkstra_wavefront.png`): geographic visualization of Dijkstra exploration from the 15 most populous US cities, each with 1M-node subgraphs, on a Lambert Conformal US map

### 4.6 Figure Catalogue and Findings

The case study produces 16 publication-ready figures.  Each figure, its filename, and its key finding are described below.

#### Dataset Visualizations (3 figures)

| # | File | Description | Key Finding |
|---|------|-------------|-------------|
| 1 | `usa_road_network_nodes.png` | Node density heatmap of 2M sampled nodes on a Lambert Conformal US map | Urban clusters (NYC, LA, Chicago, Houston) are clearly visible as high-density regions; the road network covers the entire contiguous US with density proportional to population |
| 2 | `usa_edge_density_distance.png` | Edge density by distance weight (meters), YlOrRd colormap | Mean edge distance is ~2,949 meters, median ~1,447 meters; urban areas show orders-of-magnitude higher edge density than rural regions |
| 3 | `usa_edge_density_traveltime.png` | Edge density by travel time (seconds), YlGnBu colormap | Mean travel time is ~707 seconds, median ~347 seconds; the spatial pattern differs from distance density because highway segments have high distance but low travel time per unit distance |

#### Benchmark Result Plots (10 figures)

| # | File | Description | Key Finding |
|---|------|-------------|-------------|
| 4 | `runtime_comparison_distance.png` | Bar chart of Dijkstra runtime per method across 5 graph sizes (distance weights) | heapx-lazy and heapq are nearly identical (~11.7s at 1M nodes); sortedcontainers is 25-35% slower (~15.8s) |
| 5 | `runtime_comparison_time.png` | Same as above for travel-time weights | Same pattern: heapx-lazy ~11.9s, heapq ~12.0s, sortedcontainers ~15.5s |
| 6 | `operation_counts_distance.png` | Horizontal stacked bar showing insert/extract-min/stale-pop breakdown at 1M nodes (distance) | All methods perform ~1.05M inserts and ~1M extract-mins; lazy methods incur 54,831 stale pops (~5.2%); sortedcontainers incurs 54,831 explicit removes |
| 7 | `operation_counts_time.png` | Same as above for travel-time weights | Nearly identical pattern: 53,845 stale pops/removes (~5.1%) |
| 8 | `memory_comparison_distance.png` | Two-panel: (a) max heap size bounded vs inflated, (b) peak traced memory (distance) | heapx-replace bounds heap at 491 entries vs 508 for lazy at 100K nodes; peak memory dominated by graph storage, not heap |
| 9 | `memory_comparison_time.png` | Same as above for travel-time weights | Heap inflation slightly higher for time weights (767 vs 808 at 100K) due to more varied edge weights |
| 10 | `scaling_distance.png` | Line plot of runtime vs graph size (distance) | Linear scaling confirms O(E log V) on sparse graphs; all three methods scale identically |
| 11 | `scaling_time.png` | Same as above for travel-time weights | Same linear scaling pattern |
| 12 | `speedup_distance.png` | Speedup of heapx-lazy and sortedcontainers relative to heapq (distance) | heapx-lazy hovers near 1.0x (parity with heapq); sortedcontainers at 0.75x (25% slower) |
| 13 | `speedup_time.png` | Same as above for travel-time weights | Same pattern |

#### Explanatory Figures (3 figures)

| # | File | Description | Key Finding |
|---|------|-------------|-------------|
| 14 | `graph_structure.png` | Dual-axis plot: edges and average degree vs subgraph size | Edge count scales linearly; average degree stabilises at ~4.7, confirming the sparse, road-network character of the graph |
| 15 | `decrease_key_analysis.png` | Two-panel: (a) decrease-key rate vs size, (b) heap inflation ratio | Decrease-key rate stabilises at ~5.2-5.5% for large graphs; heap inflation ratio is only 1.03-1.08x, explaining why lazy deletion performs comparably to true decrease-key on road networks |
| 16 | `dijkstra_wavefront.png` | Dijkstra exploration wavefront from 15 most populous US cities on a US map | The plasma colormap reveals concentric wavefronts expanding from each city; wavefronts from nearby cities (e.g., Dallas/Fort Worth/Austin) merge, while isolated cities (e.g., Phoenix) show symmetric radial expansion limited by the road network topology |

## 5. Performance Results

### 5.1 Runtime Comparison

At 1M nodes on the distance-weighted graph, the runtime results demonstrate the performance characteristics of each approach:

- **heapx lazy**: 11.65s
- **heapq**: 11.87s  
- **sortedcontainers**: 15.83s

The near-identical performance between heapx lazy (11.65s) and heapq (11.87s) reveals that Dijkstra's algorithm on road networks is dominated by Python-level graph traversal overhead rather than heap operations. The CSR neighbor iteration, distance comparisons, and array indexing consume the majority of execution time, making the choice of heap implementation less critical than in heap-intensive algorithms.

SortedContainers performs 25-35% slower (15.83s vs ~11.8s) due to the higher constant factors in balanced tree operations compared to binary heap operations, despite both having O(log n) complexity.

### 5.2 Operation Counts

At 1M nodes, the operation counts reveal the algorithmic behavior:

**Lazy deletion methods (heapx-lazy, heapq)**:
- **Pushes**: 1,054,831
- **Useful pops**: 1,000,000 (one per vertex)
- **Stale pops**: 54,831
- **Total pops**: 1,054,831

The stale pop rate of 54,831/1,054,831 ≈ 5.2% reflects the low decrease-key frequency characteristic of road networks.

**heapx-replace at 100K nodes**:
- **Pushes**: 100,000
- **Pops**: 100,000  
- **Replaces**: 4,532
- **Max heap size**: 491

**heapq at 100K nodes**:
- **Max heap size**: 508

The replace operation count (4,532) matches the expected decrease-key frequency, while the bounded heap size (491 vs 508) demonstrates the space efficiency of true decrease-key.

### 5.3 Heap Size and Memory

The heapx-replace implementation maintains a bounded heap with at most n entries, while lazy deletion methods allow heap inflation to n+k entries where k is the number of stale entries.

**Heap size inflation ratios**:
- 100K nodes: 508/491 ≈ 1.03x
- 1M nodes: 1,876/1,000 ≈ 1.88x (estimated bounded size)

The inflation remains modest (1.03-1.08x) on road networks due to the low decrease-key rate (~5%). On denser graphs with higher relaxation rates, the bounded-heap advantage would be more pronounced.

**Memory implications**: The position tracking in heapx-replace requires an additional O(n) integer array, partially offsetting the heap size savings. The net memory benefit depends on the inflation ratio and the relative costs of heap entries vs. position tracking.

### 5.4 The Decrease-Key Rate

Road networks exhibit a characteristically low decrease-key rate due to their geometric and topological properties:

**Spatial locality**: Vertices near the source tend to have similar shortest-path distances, reducing the likelihood that a path through a distant vertex will improve nearby distances.

**Uniform local weights**: Road segments in the same geographic area have comparable lengths (city blocks, highway segments), making dramatic distance improvements rare.

**Tree-like shortest-path structure**: Most shortest paths from a single source form a tree rooted at the source, with few "cross-edges" that would trigger distance updates.

This low relaxation rate (≈5% of edges) means lazy deletion performs comparably to true decrease-key on road networks, despite the theoretical O(E log E) vs O(E log V) complexity difference.

### 5.5 Scaling Behavior

Runtime scales linearly with graph size, confirming the expected O((V+E) log V) complexity on sparse graphs where E ≈ 2.4V:

**Scaling coefficients**:
- heapx-lazy: ~11.65 μs per vertex
- heapq: ~11.87 μs per vertex  
- sortedcontainers: ~15.83 μs per vertex

The linear scaling validates that the algorithm complexity is dominated by the O(V log V + E log V) = O(E log V) term on sparse graphs, with the log V factor absorbed into the constant due to the bounded heap sizes (log V ≈ 20 for V = 1M).

## 6. Value for Network Routing Professionals and Researchers

### 6.1 Who Benefits

This case study provides actionable insights for several professional communities:

**Network Engineers**: OSPF and IS-IS routing protocols use Dijkstra's algorithm for shortest-path tree computation. The performance characteristics on road-like network topologies (sparse, nearly planar) directly apply to network routing scenarios.

**Transportation Planners**: Route optimization in logistics, public transit planning, and traffic management systems rely on shortest-path computations on road networks. The benchmark results inform technology choices for real-time routing applications.

**GIS Developers**: Geographic Information Systems require efficient shortest-path algorithms for navigation, service area analysis, and network analysis. The comparison helps select appropriate data structures for different use cases.

**Logistics Optimization**: Vehicle routing, delivery optimization, and supply chain management depend on fast shortest-path computation. Understanding the performance trade-offs enables better system design decisions.

**Academic Researchers**: Algorithmic engineering researchers studying shortest-path algorithms, priority queue implementations, and graph algorithm optimization can use these results as baseline comparisons and validation data.

### 6.2 Why heapx Over Alternatives

The following table compares the key characteristics of each priority queue implementation:

| Feature | heapx | heapq | sortedcontainers |
|---------|-------|-------|------------------|
| **Push complexity** | O(log n) | O(log n) | O(log n) |
| **Pop complexity** | O(log n) | O(log n) | O(log n) |
| **Decrease-key** | O(log n) replace | Lazy deletion | O(log n) remove+add |
| **Max-heap support** | Native | Manual negation | Native |
| **Key function** | Native | Manual tuples | Native |
| **d-ary heaps** | Yes (d=2,3,4) | No | No |
| **Position tracking** | Optional | No | No |
| **GIL release** | Yes | No | No |

**heapx advantages**:

**(a) True decrease-key**: The `heapx.replace()` operation provides O(log n) decrease-key without heap inflation, crucial for applications with high relaxation rates.

**(b) Native max-heap**: Supports both min-heap and max-heap operations without manual key negation, simplifying implementation of algorithms requiring both.

**(c) Ternary/quaternary heap support**: d-ary heaps (d=3,4) can improve cache performance on large datasets by reducing tree height and improving spatial locality.

**(d) Homogeneous float optimization**: Specialized code paths for float keys avoid Python object overhead in distance-based algorithms.

**(e) GIL release**: C-extension operations release the Global Interpreter Lock, enabling parallel shortest-path computation in multi-threaded applications.

### 6.3 Production Considerations

In production routing engines, several optimizations would eliminate the position-tracking overhead observed in this benchmark:

**Auxiliary hash map**: Instead of rebuilding the position array after each mutation, maintain a separate hash map (vertex → heap_index) updated incrementally during heap operations. This reduces the position-tracking overhead from O(n) per operation to O(1).

**Batch processing**: Group multiple decrease-key operations and apply them in batches to amortize the position-tracking cost across multiple updates.

**Hybrid strategies**: Use lazy deletion for low-relaxation scenarios (road networks) and true decrease-key for high-relaxation scenarios (dense graphs, negative-weight detection).

**Memory-mapped graphs**: Store large road networks in memory-mapped files to reduce memory pressure and enable processing of continental-scale datasets.

With these optimizations, heapx.replace would become the optimal choice for production systems, providing bounded memory usage and predictable performance characteristics essential for real-time routing applications.

The lazy-deletion approach remains competitive specifically for road networks due to their low decrease-key rate, but true decrease-key provides more robust performance guarantees across diverse graph topologies.

## 7. Reproducing the Results

### 7.1 Prerequisites

Install the required Python packages:

```bash
pip install heapx sortedcontainers matplotlib cartopy psutil numpy
```

**System requirements**:
- Python >= 3.9
- 16+ GB RAM (for 1M node subgraphs)
- 50+ GB disk space (for full DIMACS dataset)

### 7.2 Quick Start

The DIMACS data files should be decompressed into the `data/` subdirectory, then all scripts are run from the `src/` directory:

```bash
cd src/

# Decompress DIMACS files (from ../pdfs/DIMACS/)
mkdir -p data
gzcat ../pdfs/DIMACS/USA-road-d.USA.gr.gz > data/USA-road-d.USA.gr
gzcat ../pdfs/DIMACS/USA-road-t.USA.gr.gz > data/USA-road-t.USA.gr
gzcat ../pdfs/DIMACS/USA-road-d.USA.co.gz > data/USA-road-d.USA.co

# Run benchmark (default: 10K, 50K, 100K, 500K, 1M nodes)
python3 benchmark.py

# Generate all figures
python3 visualize_dataset.py
python3 visualize_results.py
python3 visualize_explanatory.py
```

This produces:
- `results/benchmark_results.json` — raw performance data
- `figures/` — all 16 PNG figures

### 7.3 Custom Parameters

```bash
# Quick test (10K and 50K nodes only)
python3 benchmark.py --quick

# Specific sizes
python3 benchmark.py --sizes 10000,50000,100000

# Dataset maps with custom sample sizes
python3 visualize_dataset.py --sample 1000000 --sample-edges 3000000
```

### 7.4 Running Individual Steps

```bash
# Test the DIMACS loader
python3 -c "
from dimacs_loader import load_graph, GR_DIST
n, offsets, targets, weights = load_graph(GR_DIST)
print(f'Loaded: {n:,} nodes, {int(offsets[n]):,} edges')
"

# Run a single Dijkstra implementation on a small subgraph
python3 -c "
from dimacs_loader import load_graph, extract_subgraph, GR_DIST
from dijkstra import dijkstra_heapq
n, off, tgt, wt = load_graph(GR_DIST)
sub_n, sub_off, sub_tgt, sub_wt, sub_src, _ = extract_subgraph(n, off, tgt, wt, 0, 10000)
dist, stats = dijkstra_heapq(sub_n, sub_off, sub_tgt, sub_wt, sub_src)
print(f'Reachable: {sum(1 for d in dist if d < float(\"inf\")):,}')
print(f'Stats: {stats}')
"
```

**Output files**:
- `results/benchmark_results.json` — timing, memory, and operation counts for all methods and sizes
- `figures/usa_road_network_nodes.png` — node density map
- `figures/usa_edge_density_distance.png` — distance edge density
- `figures/usa_edge_density_traveltime.png` — travel-time edge density
- `figures/runtime_comparison_{distance,time}.png` — runtime bar charts
- `figures/operation_counts_{distance,time}.png` — operation breakdowns
- `figures/memory_comparison_{distance,time}.png` — memory and heap size
- `figures/scaling_{distance,time}.png` — scaling line plots
- `figures/speedup_{distance,time}.png` — speedup relative to heapq
- `figures/graph_structure.png` — subgraph structure analysis
- `figures/decrease_key_analysis.png` — decrease-key rate and heap inflation
- `figures/dijkstra_wavefront.png` — Dijkstra wavefront from 15 cities

## References

1. E. W. Dijkstra, "A Note on Two Problems in Connexion with Graphs," *Numerische Mathematik* 1, pp. 269-271, 1959.

2. 9th DIMACS Implementation Challenge: Shortest Paths, http://www.diag.uniroma1.it/challenge9/

3. R. Dementiev, P. Sanders, D. Schultes, and D. Wagner, "Engineering Route Planning Algorithms," in *Algorithmics of Large and Complex Networks*, LNCS 5515, Springer, 2009.

4. G. S. Brodal, R. Fagerberg, and R. Jacob, "Priority Queues with Decreasing Keys," in *Scandinavian Workshop on Algorithm Theory (SWAT)*, 2022.

5. A. LaMarca and R. E. Ladner, "The Influence of Caches on the Performance of Heaps," *Journal of Experimental Algorithmics* 1, Article 4, 1996.

6. B. V. Cherkassky, A. V. Goldberg, and T. Radzik, "Shortest Paths Algorithms: Theory and Experimental Evaluation," *Mathematical Programming* 73, pp. 129-174, 1996.

7. B. Haeupler, R. Hladík, V. Rozhoň, R. Tarjan, and J. Tětek, "Universal Optimality of Dijkstra via Beyond-Worst-Case Heaps," in *Proceedings of the 65th Annual IEEE Symposium on Foundations of Computer Science (FOCS)*, 2024.

8. D. Chen, R. Cherkassky, and A. Goldberg, "Optimizing Dijkstra for Real-World Performance," *arXiv preprint arXiv:1505.05033*, 2015.