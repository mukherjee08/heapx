"""Profile exact overhead sources - isolate pop only."""
import heapq, time, random
import optimized_pop

def profile_pop(name, gen, size, iters=3000):
    # Create heaps to pop from
    heaps_hq = [gen(size) for _ in range(iters)]
    heaps_op = [h.copy() for h in heaps_hq]
    for h in heaps_hq:
        heapq.heapify(h)
    for h in heaps_op:
        heapq.heapify(h)
    
    # heapq - measure just the pop
    t0 = time.perf_counter()
    for h in heaps_hq:
        heapq.heappop(h)
    hq_time = (time.perf_counter() - t0) / iters * 1e6
    
    # optimized_pop - measure just the pop
    t0 = time.perf_counter()
    for h in heaps_op:
        optimized_pop.pop(h)
    op_time = (time.perf_counter() - t0) / iters * 1e6
    
    ratio = hq_time / op_time
    mark = "✓" if ratio >= 1.0 else "✗"
    print(f"{name:10} {size:7}: heapq={hq_time:.3f}µs opt={op_time:.3f}µs ratio={ratio:.3f}x diff={op_time-hq_time:+.3f}µs {mark}")

print("FLOAT:")
for size in [1000, 10000, 100000]:
    profile_pop("FLOAT", lambda s: [random.random() for _ in range(s)], size)

print("\nSTR:")
for size in [1000, 10000, 100000]:
    profile_pop("STR", lambda s: [f"s{i:08d}" for i in range(s,0,-1)], size)
