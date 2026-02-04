"""Careful benchmark - single heap, multiple pops."""
import heapq, time, random
import optimized_pop

def bench(name, gen, size):
    # Create fresh heap for each measurement
    iters = 5000
    
    times_hq = []
    times_op = []
    
    for _ in range(iters):
        # Fresh heap for heapq
        h = gen(size)
        heapq.heapify(h)
        t = time.perf_counter()
        heapq.heappop(h)
        times_hq.append(time.perf_counter() - t)
        
        # Fresh heap for optimized_pop
        h = gen(size)
        heapq.heapify(h)
        t = time.perf_counter()
        optimized_pop.pop(h)
        times_op.append(time.perf_counter() - t)
    
    # Remove outliers (top/bottom 10%)
    times_hq.sort()
    times_op.sort()
    trim = iters // 10
    hq = sum(times_hq[trim:-trim]) / (iters - 2*trim) * 1e6
    op = sum(times_op[trim:-trim]) / (iters - 2*trim) * 1e6
    
    ratio = hq / op
    mark = "✓" if ratio >= 1.0 else "✗"
    print(f"{name:10} {size:7}: heapq={hq:.3f}µs opt={op:.3f}µs ratio={ratio:.3f}x {mark}")

print("FLOAT sequential pop:")
for size in [100, 1000, 10000, 100000]:
    bench("FLOAT", lambda s: [random.random() for _ in range(s)], size)

print("\nSTR sequential pop:")
for size in [100, 1000, 10000, 100000]:
    bench("STR", lambda s: [f"s{i:08d}" for i in range(s,0,-1)], size)

print("\nINT sequential pop:")
for size in [100, 1000, 10000, 100000]:
    bench("INT", lambda s: list(range(s,0,-1)), size)
