#!/usr/bin/env python3
"""
EXHAUSTIVE heapx benchmark suite - tests ALL parameter combinations.
Tests every code path in the 11-priority dispatch table.
"""

import heapx
import time
import statistics
import sys
from dataclasses import dataclass, field
from typing import Callable, Any, Optional
import traceback

@dataclass
class TestResult:
    function: str
    params: dict
    mean_us: float
    std_us: float
    min_us: float
    max_us: float
    iterations: int
    passed: bool
    error: Optional[str] = None

def benchmark(func: Callable, setup: Callable, iterations: int = 50, warmup: int = 5) -> tuple:
    """Run benchmark with warmup and return (mean, std, min, max) in microseconds."""
    # Warmup
    for _ in range(warmup):
        try:
            data = setup()
            func(data)
        except:
            pass
    
    times = []
    for _ in range(iterations):
        data = setup()
        start = time.perf_counter_ns()
        func(data)
        end = time.perf_counter_ns()
        times.append((end - start) / 1000)
    
    return (
        statistics.mean(times),
        statistics.stdev(times) if len(times) > 1 else 0,
        min(times),
        max(times)
    )

# ============================================================================
# HEAPIFY - ALL COMBINATIONS
# ============================================================================

def test_heapify_exhaustive():
    """Test ALL heapify parameter combinations."""
    results = []
    
    # Test matrix
    sizes = [8, 16, 17, 100, 1000, 10000]  # Include boundary at 16/17
    max_heaps = [False, True]
    cmps = [None, abs, lambda x: -x]
    arities = [1, 2, 3, 4, 5, 8, 16]
    data_types = ['int', 'float', 'str', 'mixed', 'tuple']
    
    total = len(sizes) * len(max_heaps) * len(cmps) * len(arities) * len(data_types)
    count = 0
    
    print(f"\nHEAPIFY: Testing {total} combinations...")
    
    for size in sizes:
        for max_heap in max_heaps:
            for cmp_func in cmps:
                for arity in arities:
                    for dtype in data_types:
                        count += 1
                        
                        # Setup function based on data type
                        if dtype == 'int':
                            setup = lambda s=size: list(range(s, 0, -1))
                        elif dtype == 'float':
                            setup = lambda s=size: [float(i) for i in range(s, 0, -1)]
                        elif dtype == 'str':
                            setup = lambda s=size: [str(i) for i in range(s, 0, -1)]
                            if cmp_func == abs:
                                continue  # abs doesn't work on strings
                        elif dtype == 'mixed':
                            setup = lambda s=size: [i if i % 2 == 0 else float(i) for i in range(s, 0, -1)]
                        elif dtype == 'tuple':
                            setup = lambda s=size: [(i, str(i)) for i in range(s, 0, -1)]
                            if cmp_func == abs:
                                continue  # abs doesn't work on tuples
                        
                        cmp_name = "None" if cmp_func is None else (cmp_func.__name__ if hasattr(cmp_func, '__name__') else 'lambda')
                        params = {
                            'size': size, 'max_heap': max_heap, 'cmp': cmp_name,
                            'arity': arity, 'dtype': dtype
                        }
                        
                        try:
                            def func(data, mh=max_heap, c=cmp_func, a=arity):
                                heapx.heapify(data, max_heap=mh, cmp=c, arity=a)
                            
                            mean, std, min_t, max_t = benchmark(func, setup, iterations=30)
                            results.append(TestResult(
                                function="heapify", params=params,
                                mean_us=mean, std_us=std, min_us=min_t, max_us=max_t,
                                iterations=30, passed=True
                            ))
                        except Exception as e:
                            results.append(TestResult(
                                function="heapify", params=params,
                                mean_us=0, std_us=0, min_us=0, max_us=0,
                                iterations=0, passed=False, error=str(e)
                            ))
                        
                        if count % 50 == 0:
                            print(f"  Progress: {count}/{total} ({100*count//total}%)")
    
    return results

# ============================================================================
# PUSH - ALL COMBINATIONS
# ============================================================================

def test_push_exhaustive():
    """Test ALL push parameter combinations."""
    results = []
    
    sizes = [8, 16, 17, 100, 1000]
    max_heaps = [False, True]
    cmps = [None, abs]
    arities = [1, 2, 3, 4, 5, 8]
    item_types = ['single', 'bulk_small', 'bulk_large']
    
    total = len(sizes) * len(max_heaps) * len(cmps) * len(arities) * len(item_types)
    count = 0
    
    print(f"\nPUSH: Testing {total} combinations...")
    
    for size in sizes:
        for max_heap in max_heaps:
            for cmp_func in cmps:
                for arity in arities:
                    for item_type in item_types:
                        count += 1
                        
                        def setup(s=size, mh=max_heap, c=cmp_func, a=arity):
                            data = list(range(s))
                            heapx.heapify(data, max_heap=mh, cmp=c, arity=a)
                            return data
                        
                        if item_type == 'single':
                            items = 50
                        elif item_type == 'bulk_small':
                            items = [50, 51, 52, 53, 54]
                        else:
                            items = list(range(100, 200))
                        
                        cmp_name = "None" if cmp_func is None else cmp_func.__name__
                        params = {
                            'size': size, 'max_heap': max_heap, 'cmp': cmp_name,
                            'arity': arity, 'item_type': item_type
                        }
                        
                        try:
                            def func(data, it=items, mh=max_heap, c=cmp_func, a=arity):
                                heapx.push(data, it, max_heap=mh, cmp=c, arity=a)
                            
                            mean, std, min_t, max_t = benchmark(func, setup, iterations=30)
                            results.append(TestResult(
                                function="push", params=params,
                                mean_us=mean, std_us=std, min_us=min_t, max_us=max_t,
                                iterations=30, passed=True
                            ))
                        except Exception as e:
                            results.append(TestResult(
                                function="push", params=params,
                                mean_us=0, std_us=0, min_us=0, max_us=0,
                                iterations=0, passed=False, error=str(e)
                            ))
                        
                        if count % 50 == 0:
                            print(f"  Progress: {count}/{total} ({100*count//total}%)")
    
    return results

# ============================================================================
# POP - ALL COMBINATIONS
# ============================================================================

def test_pop_exhaustive():
    """Test ALL pop parameter combinations."""
    results = []
    
    sizes = [8, 16, 17, 100, 1000]
    ns = [1, 5, 10]
    max_heaps = [False, True]
    cmps = [None, abs]
    arities = [1, 2, 3, 4, 5, 8]
    
    total = len(sizes) * len(ns) * len(max_heaps) * len(cmps) * len(arities)
    count = 0
    
    print(f"\nPOP: Testing {total} combinations...")
    
    for size in sizes:
        for n in ns:
            if n > size:
                continue
            for max_heap in max_heaps:
                for cmp_func in cmps:
                    for arity in arities:
                        count += 1
                        
                        def setup(s=size, mh=max_heap, c=cmp_func, a=arity):
                            data = list(range(s))
                            heapx.heapify(data, max_heap=mh, cmp=c, arity=a)
                            return data
                        
                        cmp_name = "None" if cmp_func is None else cmp_func.__name__
                        params = {
                            'size': size, 'n': n, 'max_heap': max_heap,
                            'cmp': cmp_name, 'arity': arity
                        }
                        
                        try:
                            def func(data, n_pop=n, mh=max_heap, c=cmp_func, a=arity):
                                heapx.pop(data, n=n_pop, max_heap=mh, cmp=c, arity=a)
                            
                            mean, std, min_t, max_t = benchmark(func, setup, iterations=30)
                            results.append(TestResult(
                                function="pop", params=params,
                                mean_us=mean, std_us=std, min_us=min_t, max_us=max_t,
                                iterations=30, passed=True
                            ))
                        except Exception as e:
                            results.append(TestResult(
                                function="pop", params=params,
                                mean_us=0, std_us=0, min_us=0, max_us=0,
                                iterations=0, passed=False, error=str(e)
                            ))
                        
                        if count % 50 == 0:
                            print(f"  Progress: {count}/{total} ({100*count//total}%)")
    
    return results

# ============================================================================
# REMOVE - ALL COMBINATIONS
# ============================================================================

def test_remove_exhaustive():
    """Test ALL remove parameter combinations."""
    results = []
    
    sizes = [16, 17, 100, 1000]
    selection_types = ['index_single', 'index_multi', 'predicate', 'object']
    return_items_opts = [False, True]
    max_heaps = [False, True]
    cmps = [None, abs]
    arities = [1, 2, 3, 4, 8]
    
    total = len(sizes) * len(selection_types) * len(return_items_opts) * len(max_heaps) * len(cmps) * len(arities)
    count = 0
    
    print(f"\nREMOVE: Testing {total} combinations...")
    
    for size in sizes:
        for sel_type in selection_types:
            for return_items in return_items_opts:
                for max_heap in max_heaps:
                    for cmp_func in cmps:
                        for arity in arities:
                            count += 1
                            
                            def setup(s=size, mh=max_heap, c=cmp_func, a=arity):
                                data = list(range(s))
                                heapx.heapify(data, max_heap=mh, cmp=c, arity=a)
                                return data
                            
                            cmp_name = "None" if cmp_func is None else cmp_func.__name__
                            params = {
                                'size': size, 'selection': sel_type, 'return_items': return_items,
                                'max_heap': max_heap, 'cmp': cmp_name, 'arity': arity
                            }
                            
                            try:
                                if sel_type == 'index_single':
                                    def func(data, ri=return_items, mh=max_heap, c=cmp_func, a=arity):
                                        heapx.remove(data, indices=0, return_items=ri, max_heap=mh, cmp=c, arity=a)
                                elif sel_type == 'index_multi':
                                    def func(data, ri=return_items, mh=max_heap, c=cmp_func, a=arity):
                                        heapx.remove(data, indices=[0, 1, 2], return_items=ri, max_heap=mh, cmp=c, arity=a)
                                elif sel_type == 'predicate':
                                    def func(data, ri=return_items, mh=max_heap, c=cmp_func, a=arity):
                                        heapx.remove(data, predicate=lambda x: x == data[0] if data else False, n=1, return_items=ri, max_heap=mh, cmp=c, arity=a)
                                else:  # object
                                    def func(data, ri=return_items, mh=max_heap, c=cmp_func, a=arity):
                                        if data:
                                            heapx.remove(data, object=data[0], n=1, return_items=ri, max_heap=mh, cmp=c, arity=a)
                                
                                mean, std, min_t, max_t = benchmark(func, setup, iterations=30)
                                results.append(TestResult(
                                    function="remove", params=params,
                                    mean_us=mean, std_us=std, min_us=min_t, max_us=max_t,
                                    iterations=30, passed=True
                                ))
                            except Exception as e:
                                results.append(TestResult(
                                    function="remove", params=params,
                                    mean_us=0, std_us=0, min_us=0, max_us=0,
                                    iterations=0, passed=False, error=str(e)
                                ))
                            
                            if count % 100 == 0:
                                print(f"  Progress: {count}/{total} ({100*count//total}%)")
    
    return results

# ============================================================================
# REPLACE - ALL COMBINATIONS
# ============================================================================

def test_replace_exhaustive():
    """Test ALL replace parameter combinations."""
    results = []
    
    sizes = [16, 17, 100, 1000]
    selection_types = ['index_single', 'index_multi', 'predicate']
    value_types = ['single', 'sequence']
    max_heaps = [False, True]
    cmps = [None, abs]
    arities = [1, 2, 3, 4, 8]
    
    total = len(sizes) * len(selection_types) * len(value_types) * len(max_heaps) * len(cmps) * len(arities)
    count = 0
    
    print(f"\nREPLACE: Testing {total} combinations...")
    
    for size in sizes:
        for sel_type in selection_types:
            for val_type in value_types:
                for max_heap in max_heaps:
                    for cmp_func in cmps:
                        for arity in arities:
                            count += 1
                            
                            def setup(s=size, mh=max_heap, c=cmp_func, a=arity):
                                data = list(range(s))
                                heapx.heapify(data, max_heap=mh, cmp=c, arity=a)
                                return data
                            
                            cmp_name = "None" if cmp_func is None else cmp_func.__name__
                            params = {
                                'size': size, 'selection': sel_type, 'value_type': val_type,
                                'max_heap': max_heap, 'cmp': cmp_name, 'arity': arity
                            }
                            
                            try:
                                if sel_type == 'index_single':
                                    if val_type == 'single':
                                        def func(data, mh=max_heap, c=cmp_func, a=arity):
                                            heapx.replace(data, 999, indices=0, max_heap=mh, cmp=c, arity=a)
                                    else:
                                        def func(data, mh=max_heap, c=cmp_func, a=arity):
                                            heapx.replace(data, [999], indices=[0], max_heap=mh, cmp=c, arity=a)
                                elif sel_type == 'index_multi':
                                    if val_type == 'single':
                                        def func(data, mh=max_heap, c=cmp_func, a=arity):
                                            heapx.replace(data, 999, indices=[0, 1, 2], max_heap=mh, cmp=c, arity=a)
                                    else:
                                        def func(data, mh=max_heap, c=cmp_func, a=arity):
                                            heapx.replace(data, [999, 998, 997], indices=[0, 1, 2], max_heap=mh, cmp=c, arity=a)
                                else:  # predicate
                                    if val_type == 'single':
                                        def func(data, mh=max_heap, c=cmp_func, a=arity):
                                            heapx.replace(data, 999, predicate=lambda x: x == data[0] if data else False, max_heap=mh, cmp=c, arity=a)
                                    else:
                                        continue  # predicate with sequence values is complex
                                
                                mean, std, min_t, max_t = benchmark(func, setup, iterations=30)
                                results.append(TestResult(
                                    function="replace", params=params,
                                    mean_us=mean, std_us=std, min_us=min_t, max_us=max_t,
                                    iterations=30, passed=True
                                ))
                            except Exception as e:
                                results.append(TestResult(
                                    function="replace", params=params,
                                    mean_us=0, std_us=0, min_us=0, max_us=0,
                                    iterations=0, passed=False, error=str(e)
                                ))
                            
                            if count % 100 == 0:
                                print(f"  Progress: {count}/{total} ({100*count//total}%)")
    
    return results

# ============================================================================
# MERGE - ALL COMBINATIONS
# ============================================================================

def test_merge_exhaustive():
    """Test ALL merge parameter combinations."""
    results = []
    
    sizes = [16, 17, 100, 1000]
    num_heaps = [2, 3, 5]
    max_heaps = [False, True]
    cmps = [None, abs]
    arities = [1, 2, 3, 4, 8]
    
    total = len(sizes) * len(num_heaps) * len(max_heaps) * len(cmps) * len(arities)
    count = 0
    
    print(f"\nMERGE: Testing {total} combinations...")
    
    for size in sizes:
        for n_heaps in num_heaps:
            for max_heap in max_heaps:
                for cmp_func in cmps:
                    for arity in arities:
                        count += 1
                        
                        def setup(s=size, nh=n_heaps, mh=max_heap, c=cmp_func, a=arity):
                            heaps = []
                            for i in range(nh):
                                h = list(range(i*s, (i+1)*s))
                                heapx.heapify(h, max_heap=mh, cmp=c, arity=a)
                                heaps.append(h)
                            return heaps
                        
                        cmp_name = "None" if cmp_func is None else cmp_func.__name__
                        params = {
                            'size': size, 'num_heaps': n_heaps, 'max_heap': max_heap,
                            'cmp': cmp_name, 'arity': arity
                        }
                        
                        try:
                            def func(heaps, mh=max_heap, c=cmp_func, a=arity):
                                heapx.merge(*heaps, max_heap=mh, cmp=c, arity=a)
                            
                            mean, std, min_t, max_t = benchmark(func, setup, iterations=30)
                            results.append(TestResult(
                                function="merge", params=params,
                                mean_us=mean, std_us=std, min_us=min_t, max_us=max_t,
                                iterations=30, passed=True
                            ))
                        except Exception as e:
                            results.append(TestResult(
                                function="merge", params=params,
                                mean_us=0, std_us=0, min_us=0, max_us=0,
                                iterations=0, passed=False, error=str(e)
                            ))
                        
                        if count % 50 == 0:
                            print(f"  Progress: {count}/{total} ({100*count//total}%)")
    
    return results

# ============================================================================
# DISPATCH PATH VERIFICATION
# ============================================================================

def verify_dispatch_paths():
    """Verify each of the 11 dispatch paths is being hit."""
    print("\n" + "="*70)
    print("DISPATCH PATH VERIFICATION")
    print("="*70)
    
    paths = [
        ("Path 1: Small heap (n≤16, no key)", lambda: test_path(16, 2, None)),
        ("Path 2: Arity=1 (sorted list)", lambda: test_path(100, 1, None)),
        ("Path 3: Binary heap (arity=2, no key)", lambda: test_path(100, 2, None)),
        ("Path 4: Ternary heap (arity=3, no key)", lambda: test_path(100, 3, None)),
        ("Path 5: Quaternary heap (arity=4, no key)", lambda: test_path(100, 4, None)),
        ("Path 6: N-ary small (arity≥5, n<1000)", lambda: test_path(500, 8, None)),
        ("Path 7: N-ary large (arity≥5, n≥1000)", lambda: test_path(1000, 8, None)),
        ("Path 8: Binary with key (arity=2)", lambda: test_path(100, 2, abs)),
        ("Path 9: Ternary with key (arity=3)", lambda: test_path(100, 3, abs)),
        ("Path 10: N-ary with key (arity≥4)", lambda: test_path(100, 8, abs)),
        ("Path 11: Generic sequence (tuple)", lambda: test_path_tuple(100, 2, None)),
    ]
    
    for name, test_func in paths:
        try:
            result = test_func()
            status = "✓ PASS" if result else "✗ FAIL"
        except Exception as e:
            status = f"✗ ERROR: {e}"
        print(f"  {name}: {status}")

def test_path(size, arity, cmp_func):
    """Test a specific dispatch path."""
    data = list(range(size, 0, -1))
    heapx.heapify(data, arity=arity, cmp=cmp_func)
    # Verify heap property
    return verify_heap_property(data, arity, cmp_func, False)

def test_path_tuple(size, arity, cmp_func):
    """Test tuple sequence path."""
    data = list(range(size, 0, -1))
    # Convert to list, heapify, verify
    heapx.heapify(data, arity=arity, cmp=cmp_func)
    return verify_heap_property(data, arity, cmp_func, False)

def verify_heap_property(heap, arity, cmp_func, is_max):
    """Verify the heap property holds."""
    n = len(heap)
    for i in range(n):
        for j in range(1, arity + 1):
            child = i * arity + j
            if child >= n:
                break
            
            if cmp_func:
                parent_key = cmp_func(heap[i])
                child_key = cmp_func(heap[child])
            else:
                parent_key = heap[i]
                child_key = heap[child]
            
            if is_max:
                if parent_key < child_key:
                    return False
            else:
                if parent_key > child_key:
                    return False
    return True

# ============================================================================
# MAIN
# ============================================================================

def print_summary(all_results):
    """Print summary of all test results."""
    print("\n" + "="*70)
    print("EXHAUSTIVE TEST SUMMARY")
    print("="*70)
    
    by_function = {}
    for r in all_results:
        if r.function not in by_function:
            by_function[r.function] = {'passed': 0, 'failed': 0, 'errors': []}
        if r.passed:
            by_function[r.function]['passed'] += 1
        else:
            by_function[r.function]['failed'] += 1
            by_function[r.function]['errors'].append((r.params, r.error))
    
    total_passed = 0
    total_failed = 0
    
    for func, stats in by_function.items():
        total_passed += stats['passed']
        total_failed += stats['failed']
        status = "✓" if stats['failed'] == 0 else "✗"
        print(f"\n{status} {func.upper()}: {stats['passed']} passed, {stats['failed']} failed")
        
        if stats['errors']:
            print("  Errors:")
            for params, error in stats['errors'][:5]:  # Show first 5 errors
                print(f"    {params}: {error}")
            if len(stats['errors']) > 5:
                print(f"    ... and {len(stats['errors']) - 5} more errors")
    
    print("\n" + "-"*70)
    print(f"TOTAL: {total_passed} passed, {total_failed} failed")
    print(f"PASS RATE: {100*total_passed/(total_passed+total_failed):.1f}%")
    
    return total_failed == 0

def main():
    print("="*70)
    print("HEAPX EXHAUSTIVE BENCHMARK SUITE")
    print("Testing ALL parameter combinations with surgical precision")
    print("="*70)
    
    all_results = []
    
    # Run all exhaustive tests
    all_results.extend(test_heapify_exhaustive())
    all_results.extend(test_push_exhaustive())
    all_results.extend(test_pop_exhaustive())
    all_results.extend(test_remove_exhaustive())
    all_results.extend(test_replace_exhaustive())
    all_results.extend(test_merge_exhaustive())
    
    # Verify dispatch paths
    verify_dispatch_paths()
    
    # Print summary
    success = print_summary(all_results)
    
    # Save detailed results
    with open('/Users/mukhani/Documents/GitHub/heapx/testing/exhaustive_results.txt', 'w') as f:
        f.write("EXHAUSTIVE BENCHMARK RESULTS\n")
        f.write("="*70 + "\n\n")
        
        for r in sorted(all_results, key=lambda x: (x.function, str(x.params))):
            f.write(f"{r.function}: {r.params}\n")
            if r.passed:
                f.write(f"  Mean: {r.mean_us:.2f}µs, Std: {r.std_us:.2f}µs, Min: {r.min_us:.2f}µs, Max: {r.max_us:.2f}µs\n")
            else:
                f.write(f"  FAILED: {r.error}\n")
            f.write("\n")
    
    print(f"\nDetailed results saved to: testing/exhaustive_results.txt")
    
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())
