#!/usr/bin/env python3
"""Test homogeneous array optimizations (SIMD paths)."""

import heapx
import time
import random

def benchmark(func, setup, iterations=100):
    """Run benchmark and return min time in microseconds."""
    times = []
    for _ in range(iterations):
        data = setup()
        start = time.perf_counter_ns()
        func(data)
        end = time.perf_counter_ns()
        times.append((end - start) / 1000)
    return min(times)

def test_homogeneous_types():
    """Test performance with homogeneous vs heterogeneous data."""
    sizes = [1000, 10000, 100000]
    
    print("Homogeneous Type Detection & SIMD Path Testing")
    print("=" * 70)
    
    for size in sizes:
        print(f"\nSize: {size}")
        print("-" * 50)
        
        # Homogeneous integers
        def setup_int():
            return list(range(size, 0, -1))
        min_int = benchmark(lambda d: heapx.heapify(d), setup_int, 50)
        
        # Homogeneous floats
        def setup_float():
            return [float(i) for i in range(size, 0, -1)]
        min_float = benchmark(lambda d: heapx.heapify(d), setup_float, 50)
        
        # Homogeneous strings
        def setup_str():
            return [str(i) for i in range(size, 0, -1)]
        min_str = benchmark(lambda d: heapx.heapify(d), setup_str, 50)
        
        # Mixed types (int + float)
        def setup_mixed():
            data = []
            for i in range(size, 0, -1):
                if i % 2 == 0:
                    data.append(i)
                else:
                    data.append(float(i))
            return data
        min_mixed = benchmark(lambda d: heapx.heapify(d), setup_mixed, 50)
        
        print(f"  Homogeneous int:   {min_int:8.2f} µs")
        print(f"  Homogeneous float: {min_float:8.2f} µs")
        print(f"  Homogeneous str:   {min_str:8.2f} µs")
        print(f"  Mixed int/float:   {min_mixed:8.2f} µs")
        print(f"  Float vs Int:      {min_float/min_int:.2f}x")
        print(f"  Mixed vs Int:      {min_mixed/min_int:.2f}x")

def test_arity_comparison():
    """Compare arity performance for large datasets."""
    size = 100000
    
    print("\n\nArity Comparison for Large Dataset (n=100,000)")
    print("=" * 70)
    
    for dtype, setup in [
        ("int", lambda: list(range(size, 0, -1))),
        ("float", lambda: [float(i) for i in range(size, 0, -1)]),
    ]:
        print(f"\nData type: {dtype}")
        print("-" * 50)
        
        for arity in [2, 3, 4, 8]:
            min_time = benchmark(
                lambda d, a=arity: heapx.heapify(d, arity=a),
                setup,
                30
            )
            print(f"  Arity {arity}: {min_time:8.2f} µs")

def test_max_heap_symmetry():
    """Verify max_heap has same performance as min_heap."""
    size = 10000
    
    print("\n\nMax-Heap vs Min-Heap Symmetry")
    print("=" * 70)
    
    def setup():
        return list(range(size, 0, -1))
    
    for arity in [2, 3, 4]:
        min_min = benchmark(
            lambda d, a=arity: heapx.heapify(d, max_heap=False, arity=a),
            setup, 50
        )
        min_max = benchmark(
            lambda d, a=arity: heapx.heapify(d, max_heap=True, arity=a),
            setup, 50
        )
        print(f"Arity {arity}: min-heap={min_min:.2f}µs, max-heap={min_max:.2f}µs, ratio={min_max/min_min:.2f}x")

def test_small_heap_optimization():
    """Test small heap (n≤16) insertion sort optimization."""
    print("\n\nSmall Heap Optimization (n≤16)")
    print("=" * 70)
    
    for size in [4, 8, 12, 16, 20, 32, 64]:
        def setup(s=size):
            return list(range(s, 0, -1))
        
        min_time = benchmark(lambda d: heapx.heapify(d), setup, 200)
        print(f"  n={size:3d}: {min_time:.3f} µs")

if __name__ == "__main__":
    test_homogeneous_types()
    test_arity_comparison()
    test_max_heap_symmetry()
    test_small_heap_optimization()
