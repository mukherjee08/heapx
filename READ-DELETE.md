# heapx - Understanding the Implementation

## What is heapx?

Imagine you have a pile of numbered cards, and you always want to quickly find the smallest (or largest) card. A "heap" is a clever way to organize these cards so finding the smallest/largest is super fast.

**heapx** is a tool that does this organization extremely quickly - much faster than Python's built-in tools.

---

## The Big Picture

The code has **7 main operations** you can do with your pile of cards:

| Operation | What it does |
|-----------|--------------|
| `heapify` | Organize a messy pile into a proper heap |
| `push` | Add new cards to the pile |
| `pop` | Remove and return the top card(s) |
| `sort` | Arrange all cards in order |
| `remove` | Take out specific cards |
| `replace` | Swap cards for new ones |
| `merge` | Combine multiple piles into one |

---

## How a Heap Works (The Core Concept)

Think of a heap like a family tree:
- The **root** (top) is always the smallest (or largest) value
- Each **parent** has up to 2, 3, or 4 **children** (configurable)
- Every parent is smaller than all its children

```
        1          ← smallest at top
       / \
      3   5
     / \   \
    7   4   8
```

To find the smallest? Just look at the top - instant!

---

## Key Features Explained

### 1. Min-Heap vs Max-Heap
- **Min-heap**: Smallest card always on top (default)
- **Max-heap**: Largest card always on top (set `max_heap=True`)

### 2. N-ary Heaps (Arity)
The "arity" is how many children each parent can have:
- **Binary (arity=2)**: Each parent has up to 2 children (most common)
- **Ternary (arity=3)**: Up to 3 children
- **Quaternary (arity=4)**: Up to 4 children

Higher arity = shallower tree = faster for some operations.

### 3. Key Functions
Sometimes you want to sort cards by something other than their face value. A "key function" transforms each card before comparing:
```python
# Sort people by age, not name
heapify(people, cmp=lambda person: person.age)
```

---

## Speed Tricks (Why It's Fast)

The code uses many clever techniques:

### Fast Comparisons
Instead of using Python's slow comparison system, it directly compares:
- **Integers**: Extracts the raw number and compares in C
- **Floats**: Uses direct floating-point comparison
- **Strings**: Uses memory comparison (like comparing letter-by-letter, but faster)
- **Tuples**: Compares element-by-element

### Memory Prefetching
The code tells the computer "I'll need this data soon" so it loads it into fast memory before it's needed - like a waiter bringing your next course before you finish the current one.

### Algorithm Selection
The code automatically picks the best algorithm based on:
- How big is your pile? (Small piles use simpler methods)
- What type of heap? (Binary, ternary, etc.)
- Do you have a key function?

---

## The Main Operations in Detail

### `heapify(heap, max_heap=False, cmp=None, arity=2)`
Transforms a regular list into a heap.

**How it works (Floyd's Algorithm):**
1. Start from the middle of the list
2. For each element, "sift down" - push it down until it's smaller than its children
3. Work backwards to the beginning

This is O(n) - meaning it takes time proportional to the number of items.

### `push(heap, items, ...)`
Adds items to the heap.

**How it works:**
1. Add the new item at the end
2. "Sift up" - compare with parent, swap if smaller, repeat until in correct position

### `pop(heap, n=1, ...)`
Removes and returns the top item(s).

**How it works:**
1. Save the top item (that's your answer)
2. Move the last item to the top
3. "Sift down" - push it down until heap property is restored
4. Return the saved item

### `sort(heap, reverse=False, inplace=False, ...)`
Sorts the heap using "heapsort".

**How it works:**
1. Build a max-heap (largest on top)
2. Swap top with last position
3. Shrink the heap by 1
4. Restore heap property
5. Repeat until sorted

### `remove(heap, indices=None, object=None, predicate=None, ...)`
Removes items by:
- **indices**: Position numbers
- **object**: The exact item (by identity)
- **predicate**: A test function (remove all items where test returns True)

### `replace(heap, values, ...)`
Replaces items with new values, then fixes the heap.

### `merge(*heaps, ...)`
Combines multiple heaps:
1. Concatenate all items into one list
2. Heapify the result

---

## The 11-Priority Dispatch System

The code has a clever decision tree that picks the fastest algorithm:

| Priority | Condition | Algorithm |
|----------|-----------|-----------|
| 1 | Small heap (≤16 items), no key | Insertion sort |
| 2 | Arity=1 (sorted list) | Binary insertion |
| 3 | Binary heap, no key | Floyd's algorithm |
| 4 | Ternary heap, no key | Specialized ternary |
| 5 | Quaternary heap, no key | Specialized quaternary |
| 6 | N-ary, no key, small | Small heap optimization |
| 7 | N-ary, no key, large | Generic algorithm |
| 8 | Binary heap with key | Key-cached Floyd's |
| 9 | Ternary heap with key | Key-cached ternary |
| 10 | N-ary with key | Generic with key |
| 11 | Non-list sequence | Generic sequence handling |

---

## Memory Pool

The code reuses memory for key arrays instead of constantly allocating/freeing:
```c
static struct {
  PyObject **arrays[8];  // Store up to 8 arrays
  size_t sizes[8];       // Their sizes
  int count;             // How many stored
} key_pool;
```

This avoids the overhead of asking the operating system for memory repeatedly.

---

## Summary

**heapx** is a highly optimized heap library that:
1. Supports min-heaps and max-heaps
2. Allows different tree shapes (binary, ternary, quaternary, n-ary)
3. Supports custom comparison functions
4. Automatically selects the fastest algorithm for your situation
5. Uses low-level C tricks for maximum speed

The result is heap operations that are 40-80% faster than Python's standard `heapq` module, especially for large datasets.
