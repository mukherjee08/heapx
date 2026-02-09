#!/usr/bin/env python3
"""Comprehensive benchmark harness for heapx optimization analysis."""

import heapx
import time
import random
import statistics
from dataclasses import dataclass
from typing import Callable, Any

@dataclass
class BenchmarkResult:
    function: str
    params: dict
    mean_us: float
    std_us: float
    min_us: float
    iterations: int

def benchmark(func: Callable, setup: Callable, iterations: int = 100) -> tuple[float, float, float]:
    """Run benchmark and return (mean, std, min) in microseconds."""
    times = []
    for _ in range(iterations):
        data = setup()
        start = time.perf_counter_ns()
        func(data)
        end = time.perf_counter_ns()
        times.append((end - start) / 1000)  # Convert to microseconds
    return statistics.mean(times), statistics.stdev(times) if len(times) > 1 else 0, min(times)

def run_heapify_benchmarks(sizes: list[int] = [100, 1000, 10000]) -> list[BenchmarkResult]:
    """Benchmark heapify with all parameter combinations."""
    results = []
    
    for size in sizes:
        for max_heap in [False, True]:
            for cmp in [None, abs]:
                for arity in [1, 2, 3, 4, 8]:
                    def setup(s=size):
                        return list(range(s, 0, -1))  # Worst case: reverse sorted
                    
                    def func(data, mh=max_heap, c=cmp, a=arity):
                        heapx.heapify(data, max_heap=mh, cmp=c, arity=a)
                    
                    cmp_name = "None" if cmp is None else cmp.__name__
                    try:
                        mean, std, min_t = benchmark(func, setup, iterations=50)
                        results.append(BenchmarkResult(
                            function="heapify",
                            params={"size": size, "max_heap": max_heap, "cmp": cmp_name, "arity": arity},
                            mean_us=mean, std_us=std, min_us=min_t, iterations=50
                        ))
                    except Exception as e:
                        print(f"Error: heapify size={size} max_heap={max_heap} cmp={cmp_name} arity={arity}: {e}")
    
    return results

def run_push_benchmarks(sizes: list[int] = [100, 1000, 10000]) -> list[BenchmarkResult]:
    """Benchmark push with all parameter combinations."""
    results = []
    
    for size in sizes:
        for bulk in [False, True]:
            for max_heap in [False, True]:
                for cmp in [None, abs]:
                    for arity in [1, 2, 3, 4, 8]:
                        def setup(s=size, mh=max_heap, c=cmp, a=arity):
                            data = list(range(s))
                            heapx.heapify(data, max_heap=mh, cmp=c, arity=a)
                            return data
                        
                        items = list(range(100)) if bulk else 50
                        
                        def func(data, it=items, mh=max_heap, c=cmp, a=arity):
                            heapx.push(data, it, max_heap=mh, cmp=c, arity=a)
                        
                        cmp_name = "None" if cmp is None else cmp.__name__
                        try:
                            mean, std, min_t = benchmark(func, setup, iterations=50)
                            results.append(BenchmarkResult(
                                function="push",
                                params={"size": size, "bulk": bulk, "max_heap": max_heap, "cmp": cmp_name, "arity": arity},
                                mean_us=mean, std_us=std, min_us=min_t, iterations=50
                            ))
                        except Exception as e:
                            print(f"Error: push size={size} bulk={bulk} max_heap={max_heap} cmp={cmp_name} arity={arity}: {e}")
    
    return results

def run_pop_benchmarks(sizes: list[int] = [100, 1000, 10000]) -> list[BenchmarkResult]:
    """Benchmark pop with all parameter combinations."""
    results = []
    
    for size in sizes:
        for n in [1, 10]:
            for max_heap in [False, True]:
                for cmp in [None, abs]:
                    for arity in [1, 2, 3, 4, 8]:
                        def setup(s=size, mh=max_heap, c=cmp, a=arity):
                            data = list(range(s))
                            heapx.heapify(data, max_heap=mh, cmp=c, arity=a)
                            return data
                        
                        def func(data, n_pop=n, mh=max_heap, c=cmp, a=arity):
                            heapx.pop(data, n=n_pop, max_heap=mh, cmp=c, arity=a)
                        
                        cmp_name = "None" if cmp is None else cmp.__name__
                        try:
                            mean, std, min_t = benchmark(func, setup, iterations=50)
                            results.append(BenchmarkResult(
                                function="pop",
                                params={"size": size, "n": n, "max_heap": max_heap, "cmp": cmp_name, "arity": arity},
                                mean_us=mean, std_us=std, min_us=min_t, iterations=50
                            ))
                        except Exception as e:
                            print(f"Error: pop size={size} n={n} max_heap={max_heap} cmp={cmp_name} arity={arity}: {e}")
    
    return results

def run_remove_benchmarks(sizes: list[int] = [100, 1000]) -> list[BenchmarkResult]:
    """Benchmark remove with key parameter combinations."""
    results = []
    
    for size in sizes:
        for selection in ["indices", "predicate"]:
            for max_heap in [False, True]:
                for cmp in [None, abs]:
                    for arity in [2, 3, 4]:
                        def setup(s=size, mh=max_heap, c=cmp, a=arity):
                            data = list(range(s))
                            heapx.heapify(data, max_heap=mh, cmp=c, arity=a)
                            return data
                        
                        if selection == "indices":
                            def func(data, mh=max_heap, c=cmp, a=arity):
                                heapx.remove(data, indices=0, max_heap=mh, cmp=c, arity=a)
                        else:
                            def func(data, mh=max_heap, c=cmp, a=arity):
                                heapx.remove(data, predicate=lambda x: x == data[0], n=1, max_heap=mh, cmp=c, arity=a)
                        
                        cmp_name = "None" if cmp is None else cmp.__name__
                        try:
                            mean, std, min_t = benchmark(func, setup, iterations=50)
                            results.append(BenchmarkResult(
                                function="remove",
                                params={"size": size, "selection": selection, "max_heap": max_heap, "cmp": cmp_name, "arity": arity},
                                mean_us=mean, std_us=std, min_us=min_t, iterations=50
                            ))
                        except Exception as e:
                            print(f"Error: remove size={size} selection={selection} max_heap={max_heap} cmp={cmp_name} arity={arity}: {e}")
    
    return results

def run_replace_benchmarks(sizes: list[int] = [100, 1000]) -> list[BenchmarkResult]:
    """Benchmark replace with key parameter combinations."""
    results = []
    
    for size in sizes:
        for max_heap in [False, True]:
            for cmp in [None, abs]:
                for arity in [2, 3, 4]:
                    def setup(s=size, mh=max_heap, c=cmp, a=arity):
                        data = list(range(s))
                        heapx.heapify(data, max_heap=mh, cmp=c, arity=a)
                        return data
                    
                    def func(data, mh=max_heap, c=cmp, a=arity):
                        heapx.replace(data, 999, indices=0, max_heap=mh, cmp=c, arity=a)
                    
                    cmp_name = "None" if cmp is None else cmp.__name__
                    try:
                        mean, std, min_t = benchmark(func, setup, iterations=50)
                        results.append(BenchmarkResult(
                            function="replace",
                            params={"size": size, "max_heap": max_heap, "cmp": cmp_name, "arity": arity},
                            mean_us=mean, std_us=std, min_us=min_t, iterations=50
                        ))
                    except Exception as e:
                        print(f"Error: replace size={size} max_heap={max_heap} cmp={cmp_name} arity={arity}: {e}")
    
    return results

def run_merge_benchmarks(sizes: list[int] = [100, 1000]) -> list[BenchmarkResult]:
    """Benchmark merge with key parameter combinations."""
    results = []
    
    for size in sizes:
        for max_heap in [False, True]:
            for cmp in [None, abs]:
                for arity in [2, 3, 4]:
                    def setup(s=size, mh=max_heap, c=cmp, a=arity):
                        h1 = list(range(s))
                        h2 = list(range(s, s*2))
                        heapx.heapify(h1, max_heap=mh, cmp=c, arity=a)
                        heapx.heapify(h2, max_heap=mh, cmp=c, arity=a)
                        return (h1, h2)
                    
                    def func(data, mh=max_heap, c=cmp, a=arity):
                        heapx.merge(data[0], data[1], max_heap=mh, cmp=c, arity=a)
                    
                    cmp_name = "None" if cmp is None else cmp.__name__
                    try:
                        mean, std, min_t = benchmark(func, setup, iterations=50)
                        results.append(BenchmarkResult(
                            function="merge",
                            params={"size": size, "max_heap": max_heap, "cmp": cmp_name, "arity": arity},
                            mean_us=mean, std_us=std, min_us=min_t, iterations=50
                        ))
                    except Exception as e:
                        print(f"Error: merge size={size} max_heap={max_heap} cmp={cmp_name} arity={arity}: {e}")
    
    return results

def print_results(results: list[BenchmarkResult], title: str):
    """Print benchmark results in a formatted table."""
    print(f"\n{'='*80}")
    print(f"{title}")
    print(f"{'='*80}")
    
    for r in sorted(results, key=lambda x: (str(x.params.get('size', 0)), x.mean_us)):
        params_str = ", ".join(f"{k}={v}" for k, v in r.params.items())
        print(f"{r.function}: {params_str}")
        print(f"  Mean: {r.mean_us:.2f} µs, Std: {r.std_us:.2f} µs, Min: {r.min_us:.2f} µs")

def main():
    print("heapx Comprehensive Benchmark Suite")
    print("="*80)
    
    # Run all benchmarks
    heapify_results = run_heapify_benchmarks()
    print_results(heapify_results, "HEAPIFY BENCHMARKS")
    
    push_results = run_push_benchmarks()
    print_results(push_results, "PUSH BENCHMARKS")
    
    pop_results = run_pop_benchmarks()
    print_results(pop_results, "POP BENCHMARKS")
    
    remove_results = run_remove_benchmarks()
    print_results(remove_results, "REMOVE BENCHMARKS")
    
    replace_results = run_replace_benchmarks()
    print_results(replace_results, "REPLACE BENCHMARKS")
    
    merge_results = run_merge_benchmarks()
    print_results(merge_results, "MERGE BENCHMARKS")
    
    print("\n" + "="*80)
    print("BENCHMARK COMPLETE")
    print("="*80)

if __name__ == "__main__":
    main()
