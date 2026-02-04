"""Profile where time is spent in optimized_pop."""
import heapq
import time
import random

# Test raw comparison overhead
def test_comparison_overhead():
    n = 100000
    ints = [random.randint(0, n) for _ in range(n)]
    floats = [random.random() for _ in range(n)]
    
    # Test Python native comparison
    start = time.perf_counter()
    for i in range(n-1):
        _ = ints[i] < ints[i+1]
    native_int = time.perf_counter() - start
    
    start = time.perf_counter()
    for i in range(n-1):
        _ = floats[i] < floats[i+1]
    native_float = time.perf_counter() - start
    
    print(f"Native int comparison: {native_int*1e6/n:.3f}µs per comparison")
    print(f"Native float comparison: {native_float*1e6/n:.3f}µs per comparison")
    
    # Test heapq pop timing breakdown
    sizes = [100, 1000, 10000]
    for size in sizes:
        data = list(range(size, 0, -1))
        heapq.heapify(data)
        
        times = []
        for _ in range(1000):
            d = data.copy()
            start = time.perf_counter()
            heapq.heappop(d)
            times.append(time.perf_counter() - start)
        
        avg = sum(times) / len(times) * 1e6
        comparisons = size.bit_length()  # ~log2(size) comparisons
        per_cmp = avg / comparisons
        print(f"heapq pop size={size}: {avg:.3f}µs total, ~{comparisons} comparisons, {per_cmp:.3f}µs/cmp")

test_comparison_overhead()
