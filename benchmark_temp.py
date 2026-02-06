#!/usr/bin/env python3
"""
Comprehensive benchmark: heapx vs heapq for sequential push/pop operations.
Tests min-heap only, various data types, heap sizes, and operation counts.
"""

import heapx
import heapq
import time
import random
import string
import statistics
import sys

# Configuration
HEAP_SIZES = [0, 10, 100, 1000, 10000, 100000, 1000000, 10000000]
OP_COUNTS = [1, 10, 100, 1000]
REPEATS = 10

class CustomItem:
    __slots__ = ('value',)
    def __init__(self, v):
        self.value = v
    def __lt__(self, o):
        return self.value < o.value
    def __le__(self, o):
        return self.value <= o.value
    def __gt__(self, o):
        return self.value > o.value
    def __ge__(self, o):
        return self.value >= o.value
    def __eq__(self, o):
        return self.value == o.value

def gen_data(dtype, n):
    """Generate n elements of specified data type."""
    if n == 0:
        return []
    if dtype == 'int':
        return [random.randint(0, 10**9) for _ in range(n)]
    elif dtype == 'float':
        return [random.random() * 10**9 for _ in range(n)]
    elif dtype == 'string':
        return [''.join(random.choices(string.ascii_lowercase, k=10)) for _ in range(n)]
    elif dtype == 'bytes':
        return [bytes([random.randint(0, 255) for _ in range(10)]) for _ in range(n)]
    elif dtype == 'tuple':
        return [(random.randint(0, 10**6), random.randint(0, 10**6)) for _ in range(n)]
    elif dtype == 'bool':
        return [random.choice([True, False]) for _ in range(n)]
    elif dtype == 'custom':
        return [CustomItem(random.randint(0, 10**9)) for _ in range(n)]
    raise ValueError(f"Unknown dtype: {dtype}")

def benchmark_push_heapq(heap_data, items_to_push):
    """Benchmark heapq sequential push."""
    heap = list(heap_data)
    heapq.heapify(heap)
    start = time.perf_counter()
    for item in items_to_push:
        heapq.heappush(heap, item)
    return time.perf_counter() - start

def benchmark_push_heapx(heap_data, items_to_push):
    """Benchmark heapx sequential push."""
    heap = list(heap_data)
    heapx.heapify(heap)
    start = time.perf_counter()
    for item in items_to_push:
        heapx.push(heap, item)
    return time.perf_counter() - start

def benchmark_pop_heapq(heap_data, n_pops):
    """Benchmark heapq sequential pop."""
    heap = list(heap_data)
    heapq.heapify(heap)
    start = time.perf_counter()
    for _ in range(min(n_pops, len(heap))):
        heapq.heappop(heap)
    return time.perf_counter() - start

def benchmark_pop_heapx(heap_data, n_pops):
    """Benchmark heapx sequential pop."""
    heap = list(heap_data)
    heapx.heapify(heap)
    start = time.perf_counter()
    for _ in range(min(n_pops, len(heap))):
        heapx.pop(heap)
    return time.perf_counter() - start

def run_benchmark(dtype, heap_size, op_count, operation):
    """Run benchmark for a specific configuration."""
    heapq_times = []
    heapx_times = []
    
    for rep in range(REPEATS):
        # Generate fresh data for each repetition
        heap_data = gen_data(dtype, heap_size)
        
        if operation == 'push':
            items = gen_data(dtype, op_count)
            heapq_times.append(benchmark_push_heapq(heap_data, items))
            heapx_times.append(benchmark_push_heapx(heap_data, items))
        else:  # pop
            # Ensure heap has enough elements
            actual_heap_size = max(heap_size, op_count)
            if actual_heap_size > heap_size:
                heap_data = gen_data(dtype, actual_heap_size)
            heapq_times.append(benchmark_pop_heapq(heap_data, op_count))
            heapx_times.append(benchmark_pop_heapx(heap_data, op_count))
    
    return {
        'heapq_mean': statistics.mean(heapq_times),
        'heapq_std': statistics.stdev(heapq_times) if len(heapq_times) > 1 else 0,
        'heapx_mean': statistics.mean(heapx_times),
        'heapx_std': statistics.stdev(heapx_times) if len(heapx_times) > 1 else 0,
    }

def format_time(t):
    """Format time in appropriate units."""
    if t < 1e-6:
        return f"{t*1e9:.2f}ns"
    elif t < 1e-3:
        return f"{t*1e6:.2f}µs"
    elif t < 1:
        return f"{t*1e3:.2f}ms"
    else:
        return f"{t:.3f}s"

def main():
    dtypes = ['int', 'float', 'string', 'bytes', 'tuple', 'bool', 'custom']
    operations = ['push', 'pop']
    
    results = []
    slower_configs = []
    
    print("=" * 120)
    print("HEAPX vs HEAPQ SEQUENTIAL OPERATIONS BENCHMARK (MIN-HEAP)")
    print("=" * 120)
    print(f"Repeats per config: {REPEATS}")
    print(f"Heap sizes: {HEAP_SIZES}")
    print(f"Operation counts: {OP_COUNTS}")
    print(f"Data types: {dtypes}")
    print("=" * 120)
    print()
    
    total_configs = len(dtypes) * len(HEAP_SIZES) * len(OP_COUNTS) * len(operations)
    config_num = 0
    
    for operation in operations:
        print(f"\n{'='*120}")
        print(f"OPERATION: {operation.upper()}")
        print(f"{'='*120}")
        
        for dtype in dtypes:
            print(f"\n--- Data Type: {dtype.upper()} ---")
            print(f"{'Heap Size':>12} | {'Ops':>6} | {'heapq mean':>12} | {'heapq std':>12} | {'heapx mean':>12} | {'heapx std':>12} | {'Speedup':>10} | Winner")
            print("-" * 110)
            
            for heap_size in HEAP_SIZES:
                for op_count in OP_COUNTS:
                    config_num += 1
                    
                    # Skip configurations where pop count > heap size (unless heap_size is 0)
                    if operation == 'pop' and heap_size == 0:
                        print(f"{heap_size:>12} | {op_count:>6} | {'N/A':>12} | {'N/A':>12} | {'N/A':>12} | {'N/A':>12} | {'N/A':>10} | N/A (empty heap)")
                        continue
                    
                    sys.stdout.write(f"\r[{config_num}/{total_configs}] Testing {operation} {dtype} heap_size={heap_size} ops={op_count}...")
                    sys.stdout.flush()
                    
                    try:
                        result = run_benchmark(dtype, heap_size, op_count, operation)
                        
                        speedup = result['heapq_mean'] / result['heapx_mean'] if result['heapx_mean'] > 0 else float('inf')
                        winner = "heapx" if speedup > 1 else "heapq" if speedup < 1 else "tie"
                        
                        # Clear the progress line and print result
                        sys.stdout.write("\r" + " " * 100 + "\r")
                        print(f"{heap_size:>12} | {op_count:>6} | {format_time(result['heapq_mean']):>12} | {format_time(result['heapq_std']):>12} | {format_time(result['heapx_mean']):>12} | {format_time(result['heapx_std']):>12} | {speedup:>9.2f}x | {winner.upper()}")
                        
                        results.append({
                            'operation': operation,
                            'dtype': dtype,
                            'heap_size': heap_size,
                            'op_count': op_count,
                            **result,
                            'speedup': speedup,
                            'winner': winner
                        })
                        
                        if winner == 'heapq':
                            slower_configs.append({
                                'operation': operation,
                                'dtype': dtype,
                                'heap_size': heap_size,
                                'op_count': op_count,
                                'speedup': speedup,
                                'heapq_mean': result['heapq_mean'],
                                'heapx_mean': result['heapx_mean']
                            })
                    
                    except Exception as e:
                        sys.stdout.write("\r" + " " * 100 + "\r")
                        print(f"{heap_size:>12} | {op_count:>6} | ERROR: {str(e)[:50]}")
    
    # Summary
    print("\n" + "=" * 120)
    print("SUMMARY")
    print("=" * 120)
    
    heapx_wins = sum(1 for r in results if r['winner'] == 'heapx')
    heapq_wins = sum(1 for r in results if r['winner'] == 'heapq')
    ties = sum(1 for r in results if r['winner'] == 'tie')
    
    print(f"Total configurations tested: {len(results)}")
    print(f"heapx faster: {heapx_wins} ({100*heapx_wins/len(results):.1f}%)")
    print(f"heapq faster: {heapq_wins} ({100*heapq_wins/len(results):.1f}%)")
    print(f"Ties: {ties} ({100*ties/len(results):.1f}%)")
    
    if slower_configs:
        print("\n" + "=" * 120)
        print("CONFIGURATIONS WHERE HEAPX IS SLOWER (REQUIRES ANALYSIS)")
        print("=" * 120)
        for cfg in slower_configs:
            print(f"  {cfg['operation'].upper()} | {cfg['dtype']:>8} | heap_size={cfg['heap_size']:>10} | ops={cfg['op_count']:>5} | "
                  f"heapq={format_time(cfg['heapq_mean'])} | heapx={format_time(cfg['heapx_mean'])} | slowdown={1/cfg['speedup']:.2f}x")
    else:
        print("\nheapx is faster or equal in ALL configurations!")
    
    return slower_configs

if __name__ == "__main__":
    slower = main()
