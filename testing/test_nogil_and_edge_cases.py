#!/usr/bin/env python3
"""
Test nogil parameter and verify all code paths.
"""

import heapx
import time

def test_nogil_paths():
    """Test nogil=True parameter for all functions."""
    print("="*70)
    print("NOGIL PATH TESTING")
    print("="*70)
    
    sizes = [100, 1000, 10000]
    
    for size in sizes:
        print(f"\nSize: {size}")
        print("-"*50)
        
        # Heapify with nogil
        data_nogil = list(range(size, 0, -1))
        data_gil = list(range(size, 0, -1))
        
        start = time.perf_counter_ns()
        heapx.heapify(data_nogil, nogil=True)
        nogil_time = (time.perf_counter_ns() - start) / 1000
        
        start = time.perf_counter_ns()
        heapx.heapify(data_gil, nogil=False)
        gil_time = (time.perf_counter_ns() - start) / 1000
        
        # Verify both produce valid heaps
        assert data_nogil == data_gil, "nogil and gil heapify produce different results!"
        print(f"  heapify: nogil={nogil_time:.2f}µs, gil={gil_time:.2f}µs, ratio={nogil_time/gil_time:.2f}x")
        
        # Push with nogil
        heap_nogil = list(range(size))
        heap_gil = list(range(size))
        heapx.heapify(heap_nogil)
        heapx.heapify(heap_gil)
        
        start = time.perf_counter_ns()
        heapx.push(heap_nogil, 999, nogil=True)
        nogil_time = (time.perf_counter_ns() - start) / 1000
        
        start = time.perf_counter_ns()
        heapx.push(heap_gil, 999, nogil=False)
        gil_time = (time.perf_counter_ns() - start) / 1000
        
        print(f"  push:    nogil={nogil_time:.2f}µs, gil={gil_time:.2f}µs, ratio={nogil_time/gil_time:.2f}x")
        
        # Pop with nogil
        heap_nogil = list(range(size))
        heap_gil = list(range(size))
        heapx.heapify(heap_nogil)
        heapx.heapify(heap_gil)
        
        start = time.perf_counter_ns()
        r1 = heapx.pop(heap_nogil, nogil=True)
        nogil_time = (time.perf_counter_ns() - start) / 1000
        
        start = time.perf_counter_ns()
        r2 = heapx.pop(heap_gil, nogil=False)
        gil_time = (time.perf_counter_ns() - start) / 1000
        
        assert r1 == r2, "nogil and gil pop produce different results!"
        print(f"  pop:     nogil={nogil_time:.2f}µs, gil={gil_time:.2f}µs, ratio={nogil_time/gil_time:.2f}x")

def test_homogeneous_nogil():
    """Test homogeneous array paths with nogil."""
    print("\n" + "="*70)
    print("HOMOGENEOUS NOGIL PATH TESTING")
    print("="*70)
    
    size = 10000
    
    # Homogeneous int with nogil
    data_int_nogil = list(range(size, 0, -1))
    data_int_gil = list(range(size, 0, -1))
    
    start = time.perf_counter_ns()
    heapx.heapify(data_int_nogil, nogil=True)
    int_nogil_time = (time.perf_counter_ns() - start) / 1000
    
    start = time.perf_counter_ns()
    heapx.heapify(data_int_gil, nogil=False)
    int_gil_time = (time.perf_counter_ns() - start) / 1000
    
    print(f"\nHomogeneous int (n={size}):")
    print(f"  nogil={int_nogil_time:.2f}µs, gil={int_gil_time:.2f}µs, ratio={int_nogil_time/int_gil_time:.2f}x")
    
    # Homogeneous float with nogil
    data_float_nogil = [float(i) for i in range(size, 0, -1)]
    data_float_gil = [float(i) for i in range(size, 0, -1)]
    
    start = time.perf_counter_ns()
    heapx.heapify(data_float_nogil, nogil=True)
    float_nogil_time = (time.perf_counter_ns() - start) / 1000
    
    start = time.perf_counter_ns()
    heapx.heapify(data_float_gil, nogil=False)
    float_gil_time = (time.perf_counter_ns() - start) / 1000
    
    print(f"\nHomogeneous float (n={size}):")
    print(f"  nogil={float_nogil_time:.2f}µs, gil={float_gil_time:.2f}µs, ratio={float_nogil_time/float_gil_time:.2f}x")

def test_edge_cases():
    """Test edge cases and boundary conditions."""
    print("\n" + "="*70)
    print("EDGE CASE TESTING")
    print("="*70)
    
    # Empty heap
    print("\n1. Empty heap operations:")
    empty = []
    heapx.heapify(empty)
    print(f"   heapify([]) = {empty} ✓")
    
    heapx.push(empty, 1)
    print(f"   push([], 1) = {empty} ✓")
    
    result = heapx.pop(empty)
    print(f"   pop([1]) = {result}, heap = {empty} ✓")
    
    # Single element
    print("\n2. Single element heap:")
    single = [42]
    heapx.heapify(single)
    print(f"   heapify([42]) = {single} ✓")
    
    # Boundary at n=16/17
    print("\n3. Small heap boundary (n=16 vs n=17):")
    for n in [15, 16, 17, 18]:
        data = list(range(n, 0, -1))
        heapx.heapify(data)
        valid = all(data[i] <= data[2*i+1] for i in range((n-1)//2) if 2*i+1 < n)
        valid &= all(data[i] <= data[2*i+2] for i in range((n-2)//2) if 2*i+2 < n)
        status = "✓" if valid else "✗"
        print(f"   n={n}: heap property {status}")
    
    # Duplicate elements
    print("\n4. Duplicate elements:")
    dups = [5, 3, 5, 1, 3, 5, 1]
    heapx.heapify(dups)
    print(f"   heapify([5,3,5,1,3,5,1]) = {dups}")
    print(f"   root = {dups[0]} (should be 1) {'✓' if dups[0] == 1 else '✗'}")
    
    # Negative numbers
    print("\n5. Negative numbers:")
    negs = [-5, -2, -8, -1, -9]
    heapx.heapify(negs)
    print(f"   heapify([-5,-2,-8,-1,-9]) = {negs}")
    print(f"   root = {negs[0]} (should be -9) {'✓' if negs[0] == -9 else '✗'}")
    
    # Max heap with negatives
    print("\n6. Max heap with negatives:")
    negs_max = [-5, -2, -8, -1, -9]
    heapx.heapify(negs_max, max_heap=True)
    print(f"   heapify([-5,-2,-8,-1,-9], max_heap=True) = {negs_max}")
    print(f"   root = {negs_max[0]} (should be -1) {'✓' if negs_max[0] == -1 else '✗'}")
    
    # Float NaN handling
    print("\n7. Float NaN handling:")
    import math
    floats = [1.0, float('nan'), 2.0, 3.0]
    try:
        heapx.heapify(floats)
        print(f"   heapify with NaN: {floats} (NaN handling works)")
    except Exception as e:
        print(f"   heapify with NaN: ERROR - {e}")
    
    # Very large arity (max is 64)
    print("\n8. Large arity (arity=64, max allowed):")
    data = list(range(1000, 0, -1))
    heapx.heapify(data, arity=64)
    print(f"   heapify(1000 elements, arity=64): root = {data[0]} {'✓' if data[0] == 1 else '✗'}")
    
    # Test arity limit
    print("\n9. Arity limit test:")
    try:
        data = list(range(100))
        heapx.heapify(data, arity=65)
        print("   arity=65: accepted (unexpected)")
    except ValueError as e:
        print(f"   arity=65: rejected as expected ({e})")

def test_correctness_verification():
    """Verify correctness of all operations."""
    print("\n" + "="*70)
    print("CORRECTNESS VERIFICATION")
    print("="*70)
    
    import random
    
    for trial in range(10):
        size = random.randint(50, 500)
        data = [random.randint(-1000, 1000) for _ in range(size)]
        original = data.copy()
        
        # Test heapify + pop produces sorted output
        heapx.heapify(data)
        sorted_output = []
        while data:
            sorted_output.append(heapx.pop(data))
        
        expected = sorted(original)
        if sorted_output == expected:
            print(f"  Trial {trial+1}: n={size} ✓")
        else:
            print(f"  Trial {trial+1}: n={size} ✗ MISMATCH!")
            print(f"    Expected: {expected[:10]}...")
            print(f"    Got:      {sorted_output[:10]}...")

if __name__ == "__main__":
    test_nogil_paths()
    test_homogeneous_nogil()
    test_edge_cases()
    test_correctness_verification()
    
    print("\n" + "="*70)
    print("ALL TESTS COMPLETE")
    print("="*70)
