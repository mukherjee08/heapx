"""
Time comparison tests for heapx vs heapq on large datasets.

Tests binary min-heap operations with integers for n in range 1M to 10M.
"""

import heapx
import heapq
import time
import random
import pytest

# Test sizes: 1M to 10M
SIZES = [1_000_000, 2_000_000, 5_000_000, 10_000_000]

def generate_integers(n, seed=42):
  """Generate list of random integers."""
  random.seed(seed)
  return [random.randint(-10_000_000, 10_000_000) for _ in range(n)]

def time_func(func, *args, **kwargs):
  """Time a function call and return elapsed time in seconds."""
  start = time.perf_counter()
  result = func(*args, **kwargs)
  elapsed = time.perf_counter() - start
  return elapsed, result

def print_table_header():
  """Print table header."""
  print("\n" + "=" * 90)
  print(f"{'Operation':<20} | {'n':>12} | {'heapq (s)':>12} | {'heapx (s)':>12} | {'Speedup':>10}")
  print("=" * 90)

def print_row(op, n, hq_time, hx_time):
  """Print a table row."""
  speedup = hq_time / hx_time if hx_time > 0 else float('inf')
  print(f"{op:<20} | {n:>12,} | {hq_time:>12.4f} | {hx_time:>12.4f} | {speedup:>9.2f}x")

class TestTimeComparison:
  """Time comparison tests for heapx vs heapq."""

  @pytest.fixture(autouse=True)
  def setup(self, capsys):
    """Setup for capturing output."""
    self.capsys = capsys

  def test_heapify_time(self):
    """Compare heapify time for large datasets."""
    print_table_header()
    
    for n in SIZES:
      # heapq
      data_hq = generate_integers(n)
      hq_time, _ = time_func(heapq.heapify, data_hq)
      
      # heapx
      data_hx = generate_integers(n)
      hx_time, _ = time_func(heapx.heapify, data_hx)
      
      print_row("heapify", n, hq_time, hx_time)
      
      # Verify correctness
      assert data_hq[0] == data_hx[0], "Root elements should match"
    
    print("=" * 90)

  def test_push_time(self):
    """Compare push time for large datasets."""
    print_table_header()
    
    for n in SIZES:
      # Setup heaps
      data_hq = generate_integers(n)
      heapq.heapify(data_hq)
      
      data_hx = generate_integers(n)
      heapx.heapify(data_hx)
      
      items_to_push = list(range(1000))
      
      # heapq - push 1000 items
      hq_time, _ = time_func(lambda: [heapq.heappush(data_hq, x) for x in items_to_push])
      
      # heapx - bulk push 1000 items
      hx_time, _ = time_func(heapx.push, data_hx, items_to_push)
      
      print_row("push (1000 items)", n, hq_time, hx_time)
    
    print("=" * 90)

  def test_pop_time(self):
    """Compare pop time for large datasets."""
    print_table_header()
    
    for n in SIZES:
      # Setup heaps
      data_hq = generate_integers(n)
      heapq.heapify(data_hq)
      
      data_hx = generate_integers(n)
      heapx.heapify(data_hx)
      
      # heapq - pop 1000 items
      hq_time, _ = time_func(lambda: [heapq.heappop(data_hq) for _ in range(1000)])
      
      # heapx - bulk pop 1000 items
      hx_time, _ = time_func(heapx.pop, data_hx, n=1000)
      
      print_row("pop (1000 items)", n, hq_time, hx_time)
    
    print("=" * 90)

  def test_merge_time(self):
    """Compare merge time for large datasets."""
    print_table_header()
    
    for n in SIZES:
      half = n // 2
      
      # heapq - concat + heapify
      data1_hq = generate_integers(half, seed=42)
      data2_hq = generate_integers(half, seed=43)
      heapq.heapify(data1_hq)
      heapq.heapify(data2_hq)
      
      def hq_merge():
        merged = data1_hq + data2_hq
        heapq.heapify(merged)
        return merged
      
      hq_time, _ = time_func(hq_merge)
      
      # heapx - native merge
      data1_hx = generate_integers(half, seed=42)
      data2_hx = generate_integers(half, seed=43)
      heapx.heapify(data1_hx)
      heapx.heapify(data2_hx)
      
      hx_time, _ = time_func(heapx.merge, data1_hx, data2_hx)
      
      print_row(f"merge (2×{half:,})", n, hq_time, hx_time)
    
    print("=" * 90)

  def test_full_comparison(self):
    """Run full comparison and print summary table."""
    print("\n")
    print("=" * 90)
    print(" HEAPX vs HEAPQ TIME COMPARISON - Binary Min-Heap of Integers")
    print("=" * 90)
    
    results = []
    
    for n in SIZES:
      row = {"n": n}
      
      # Heapify
      data_hq = generate_integers(n)
      hq_time, _ = time_func(heapq.heapify, data_hq)
      
      data_hx = generate_integers(n)
      hx_time, _ = time_func(heapx.heapify, data_hx)
      
      row["heapify_hq"] = hq_time
      row["heapify_hx"] = hx_time
      
      # Push (reuse heapified data)
      items = list(range(1000))
      
      data_hq2 = generate_integers(n)
      heapq.heapify(data_hq2)
      hq_time, _ = time_func(lambda: [heapq.heappush(data_hq2, x) for x in items])
      
      data_hx2 = generate_integers(n)
      heapx.heapify(data_hx2)
      hx_time, _ = time_func(heapx.push, data_hx2, items)
      
      row["push_hq"] = hq_time
      row["push_hx"] = hx_time
      
      # Pop
      data_hq3 = generate_integers(n)
      heapq.heapify(data_hq3)
      hq_time, _ = time_func(lambda: [heapq.heappop(data_hq3) for _ in range(1000)])
      
      data_hx3 = generate_integers(n)
      heapx.heapify(data_hx3)
      hx_time, _ = time_func(heapx.pop, data_hx3, n=1000)
      
      row["pop_hq"] = hq_time
      row["pop_hx"] = hx_time
      
      results.append(row)
    
    # Print summary table
    print(f"\n{'n':>12} | {'heapify':^25} | {'push (1000)':^25} | {'pop (1000)':^25}")
    print(f"{'':>12} | {'heapq':>10} {'heapx':>10} {'×':>3} | {'heapq':>10} {'heapx':>10} {'×':>3} | {'heapq':>10} {'heapx':>10} {'×':>3}")
    print("-" * 90)
    
    for r in results:
      heapify_x = r["heapify_hq"] / r["heapify_hx"] if r["heapify_hx"] > 0 else 0
      push_x = r["push_hq"] / r["push_hx"] if r["push_hx"] > 0 else 0
      pop_x = r["pop_hq"] / r["pop_hx"] if r["pop_hx"] > 0 else 0
      
      print(f"{r['n']:>12,} | {r['heapify_hq']:>10.4f} {r['heapify_hx']:>10.4f} {heapify_x:>3.1f} | "
            f"{r['push_hq']:>10.4f} {r['push_hx']:>10.4f} {push_x:>3.1f} | "
            f"{r['pop_hq']:>10.4f} {r['pop_hx']:>10.4f} {pop_x:>3.1f}")
    
    print("=" * 90)


if __name__ == "__main__":
  pytest.main([__file__, "-v", "-s"])
