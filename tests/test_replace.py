"""
Comprehensive test suite for heapx.replace function.

Tests cover all 11 dispatch priorities, parameters, data types, edge cases,
and performance benchmarks. Includes 120+ distinct test cases.
"""

import heapx
import pytest
import random
import string
import time
import sys
from typing import List, Any, Tuple
from statistics import mean, stdev

# ============================================================================
# Test Data Generators
# ============================================================================

def generate_integers(n: int, seed: int = 42) -> List[int]:
  """Generate list of random integers."""
  random.seed(seed); return [random.randint(-1000000, 1000000) for _ in range(n)]

def generate_floats(n: int, seed: int = 42) -> List[float]:
  """Generate list of random floats."""
  random.seed(seed); return [random.uniform(-1000.0, 1000.0) for _ in range(n)]

def generate_complex(n: int, seed: int = 42) -> List[complex]:
  """Generate list of random complex numbers (not directly comparable)."""
  random.seed(seed); return [complex(random.uniform(-100, 100), random.uniform(-100, 100)) for _ in range(n)]

def generate_strings(n: int, seed: int = 42) -> List[str]:
  """Generate list of random strings."""
  random.seed(seed); return [''.join(random.choices(string.ascii_letters, k=10)) for _ in range(n)]

def generate_lists(n: int, seed: int = 42) -> List[List[int]]:
  """Generate list of random lists (comparable lexicographically)."""
  random.seed(seed); return [[random.randint(0, 100) for _ in range(3)] for _ in range(n)]

def generate_tuples(n: int, seed: int = 42) -> List[Tuple[int, str]]:
  """Generate list of random tuples."""
  random.seed(seed); return [(random.randint(0, 1000), ''.join(random.choices(string.ascii_letters, k=5))) for _ in range(n)]

def generate_range(n: int) -> range:
  """Generate range object."""
  return range(n)

def generate_booleans(n: int, seed: int = 42) -> List[bool]:
  """Generate list of random booleans."""
  random.seed(seed); return [random.choice([True, False]) for _ in range(n)]

def generate_bytes(n: int, seed: int = 42) -> List[bytes]:
  """Generate list of random bytes objects."""
  random.seed(seed); return [bytes([random.randint(0, 255) for _ in range(5)]) for _ in range(n)]

def generate_bytearrays(n: int, seed: int = 42) -> List[bytearray]:
  """Generate list of random bytearray objects."""
  random.seed(seed); return [bytearray([random.randint(0, 255) for _ in range(5)]) for _ in range(n)]

def generate_mixed(n: int, seed: int = 42) -> List[Any]:
  """Generate list of mixed comparable types (integers and floats)."""
  random.seed(seed)
  result = []
  for _ in range(n):
    if random.random() < 0.5:
      result.append(random.randint(-100, 100))
    else:
      result.append(random.uniform(-100.0, 100.0))
  return result

def is_valid_heap(arr: List[Any], max_heap: bool = False, arity: int = 2, cmp=None) -> bool:
    """Verify heap property for n-ary heap."""
    if not arr:
        return True
    n = len(arr)
    for i in range(n):
        for j in range(1, arity + 1):
            child = arity * i + j
            if child >= n:
                break
            if cmp:
                parent_key = cmp(arr[i])
                child_key = cmp(arr[child])
                if max_heap:
                    if parent_key < child_key:
                        return False
                else:
                    if parent_key > child_key:
                        return False
            else:
                if max_heap:
                    if arr[i] < arr[child]:
                        return False
                else:
                    if arr[i] > arr[child]:
                        return False
    return True

# ============================================================================
# Basic Functionality Tests (10 tests)
# ============================================================================

class TestBasicReplace:
    """Test basic replace functionality."""

    def test_replace_single_index_root(self):
        """Test replacing root element by index."""
        heap = [1, 3, 2, 7, 5, 4, 6]
        heapx.heapify(heap)
        count = heapx.replace(heap, 10, indices=0)
        assert count == 1
        assert len(heap) == 7
        assert is_valid_heap(heap)

    def test_replace_single_index_middle(self):
        """Test replacing middle element by index."""
        heap = list(range(1, 21))
        heapx.heapify(heap)
        count = heapx.replace(heap, 100, indices=10)
        assert count == 1
        assert len(heap) == 20
        assert is_valid_heap(heap)

    def test_replace_single_index_end(self):
        """Test replacing last element by index."""
        heap = [1, 2, 3, 4, 5]
        heapx.heapify(heap)
        count = heapx.replace(heap, 10, indices=4)
        assert count == 1
        assert len(heap) == 5
        assert is_valid_heap(heap)

    def test_replace_negative_index(self):
        """Test replacing with negative index."""
        heap = [1, 2, 3, 4, 5]
        heapx.heapify(heap)
        count = heapx.replace(heap, 10, indices=-1)
        assert count == 1
        assert len(heap) == 5
        assert is_valid_heap(heap)

    def test_replace_out_of_bounds_index(self):
        """Test replacing with out of bounds index."""
        heap = [1, 2, 3]
        heapx.heapify(heap)
        count = heapx.replace(heap, 10, indices=10)
        assert count == 0
        assert len(heap) == 3

    def test_replace_from_empty_heap(self):
        """Test replacing from empty heap."""
        heap = []
        count = heapx.replace(heap, 1, indices=0)
        assert count == 0

    def test_replace_maintains_heap_property(self):
        """Test that replace maintains heap property."""
        heap = [1, 3, 2, 7, 5, 4, 6, 8, 9, 10]
        heapx.heapify(heap)
        heapx.replace(heap, 15, indices=3)
        assert is_valid_heap(heap)

    def test_replace_multiple_indices(self):
        """Test replacing multiple indices."""
        heap = list(range(1, 21))
        heapx.heapify(heap)
        count = heapx.replace(heap, [100, 101, 102, 103], indices=[0, 5, 10, 15])
        assert count == 4
        assert len(heap) == 20
        assert is_valid_heap(heap)

    def test_replace_single_value_multiple_indices(self):
        """Test replacing multiple indices with single value."""
        heap = list(range(1, 11))
        heapx.heapify(heap)
        count = heapx.replace(heap, 50, indices=[0, 1, 2])
        assert count == 3
        assert len(heap) == 10
        assert is_valid_heap(heap)

    def test_replace_preserves_size(self):
        """Test that replace preserves heap size."""
        heap = [1, 2, 3, 4, 5]
        heapx.heapify(heap)
        original_size = len(heap)
        heapx.replace(heap, 10, indices=2)
        assert len(heap) == original_size

# ============================================================================
# Dispatch Priority Tests (11 tests)
# ============================================================================

class TestDispatchPriorities:
    """Test all 11 dispatch priorities."""

    def test_priority_1_small_heap_no_key(self):
        """Priority 1: Small heap (n ≤ 16) with insertion sort."""
        heap = list(range(15, 0, -1))
        heapx.heapify(heap)
        heapx.replace(heap, 100, indices=5)
        assert len(heap) == 15
        assert is_valid_heap(heap)

    def test_priority_2_arity_1_sorted_list(self):
        """Priority 2: Arity=1 (sorted list) replacement."""
        heap = [1, 3, 5, 7, 9, 11]
        heapx.heapify(heap, arity=1)
        heapx.replace(heap, 4, indices=2, arity=1)
        assert heap == sorted(heap)

    def test_priority_3_binary_heap_no_key(self):
        """Priority 3: Binary heap (arity=2) inline sift."""
        heap = list(range(100, 0, -1))
        heapx.heapify(heap)
        heapx.replace(heap, 50, indices=10)
        assert len(heap) == 100
        assert is_valid_heap(heap)

    def test_priority_4_ternary_heap_no_key(self):
        """Priority 4: Ternary heap (arity=3) inline sift."""
        heap = list(range(100, 0, -1))
        heapx.heapify(heap, arity=3)
        heapx.replace(heap, 50, indices=10, arity=3)
        assert len(heap) == 100
        assert is_valid_heap(heap, arity=3)

    def test_priority_5_quaternary_heap_no_key(self):
        """Priority 5: Quaternary heap (arity=4) inline sift."""
        heap = list(range(100, 0, -1))
        heapx.heapify(heap, arity=4)
        heapx.replace(heap, 50, indices=10, arity=4)
        assert len(heap) == 100
        assert is_valid_heap(heap, arity=4)

    def test_priority_6_nary_heap_no_key(self):
        """Priority 6: N-ary heap (arity≥5) helper function."""
        heap = list(range(100, 0, -1))
        heapx.heapify(heap, arity=5)
        heapx.replace(heap, 50, indices=10, arity=5)
        assert len(heap) == 100
        assert is_valid_heap(heap, arity=5)

    def test_priority_7_binary_heap_with_key(self):
        """Priority 7: Binary heap with key function."""
        heap = [-5, 2, -8, 1, 9, -3, 7]
        heapx.heapify(heap, cmp=abs)
        heapx.replace(heap, -1, indices=0, cmp=abs)
        assert len(heap) == 7
        assert is_valid_heap(heap, cmp=abs)

    def test_priority_8_ternary_heap_with_key(self):
        """Priority 8: Ternary heap with key function."""
        heap = [-5, 2, -8, 1, 9, -3, 7]
        heapx.heapify(heap, cmp=abs, arity=3)
        heapx.replace(heap, -1, indices=0, cmp=abs, arity=3)
        assert len(heap) == 7
        assert is_valid_heap(heap, cmp=abs, arity=3)

    def test_priority_9_nary_heap_with_key(self):
        """Priority 9: N-ary heap with key function."""
        heap = [-5, 2, -8, 1, 9, -3, 7]
        heapx.heapify(heap, cmp=abs, arity=5)
        heapx.replace(heap, -1, indices=0, cmp=abs, arity=5)
        assert len(heap) == 7
        assert is_valid_heap(heap, cmp=abs, arity=5)

    def test_priority_10_small_batch(self):
        """Priority 10: Small batch (k < n/4) sequential replacements."""
        heap = list(range(100, 0, -1))
        heapx.heapify(heap)
        heapx.replace(heap, [200, 201, 202], indices=[10, 20, 30])
        assert len(heap) == 100
        assert is_valid_heap(heap)

    def test_priority_11_large_batch(self):
        """Priority 11: Large batch (k ≥ n/4) batch + heapify."""
        heap = list(range(100, 0, -1))
        heapx.heapify(heap)
        indices = list(range(0, 50))
        values = [200 + i for i in range(50)]
        heapx.replace(heap, values, indices=indices)
        assert len(heap) == 100
        assert is_valid_heap(heap)

# ============================================================================
# Data Type Tests (15 tests)
# ============================================================================

class TestDataTypes:
    """Test replace with different data types."""

    def test_replace_integers(self):
        """Test replace with integers."""
        heap = generate_integers(50)
        heapx.heapify(heap)
        heapx.replace(heap, 999999, indices=10)
        assert is_valid_heap(heap)

    def test_replace_floats(self):
        """Test replace with floats."""
        heap = generate_floats(50)
        heapx.heapify(heap)
        heapx.replace(heap, 999.999, indices=10)
        assert is_valid_heap(heap)

    def test_replace_strings(self):
        """Test replace with strings."""
        heap = generate_strings(50)
        heapx.heapify(heap)
        heapx.replace(heap, "zzzzzzzzz", indices=10)
        assert is_valid_heap(heap)

    def test_replace_tuples(self):
        """Test replace with tuples."""
        heap = generate_tuples(50)
        heapx.heapify(heap)
        heapx.replace(heap, (9999, "zzzzz"), indices=10)
        assert is_valid_heap(heap)

    def test_replace_mixed_numbers(self):
        """Test replace with mixed int/float."""
        heap = [1, 2.5, 3, 4.5, 5, 6.5, 7]
        heapx.heapify(heap)
        heapx.replace(heap, 10.5, indices=2)
        assert is_valid_heap(heap)

    def test_replace_negative_integers(self):
        """Test replace with negative integers."""
        heap = [-10, -5, -20, -3, -15, -8]
        heapx.heapify(heap)
        heapx.replace(heap, -1, indices=1)
        assert is_valid_heap(heap)

    def test_replace_large_integers(self):
        """Test replace with large integers."""
        heap = [10**9, 10**8, 10**10, 10**7]
        heapx.heapify(heap)
        heapx.replace(heap, 10**11, indices=0)
        assert is_valid_heap(heap)

    def test_replace_zero_values(self):
        """Test replace with zeros."""
        heap = [0, 1, 0, 2, 0, 3]
        heapx.heapify(heap)
        heapx.replace(heap, 5, indices=0)
        assert is_valid_heap(heap)

    def test_replace_duplicate_values(self):
        """Test replace with duplicates."""
        heap = [5, 5, 5, 5, 5]
        heapx.heapify(heap)
        heapx.replace(heap, 10, indices=2)
        assert len(heap) == 5
        assert is_valid_heap(heap)

    def test_replace_boolean_values(self):
        """Test replace with booleans."""
        heap = [True, False, True, False, True]
        heapx.heapify(heap)
        heapx.replace(heap, True, indices=0)
        assert is_valid_heap(heap)

    def test_replace_single_char_strings(self):
        """Test replace with single character strings."""
        heap = list("abcdefghij")
        heapx.heapify(heap)
        heapx.replace(heap, "z", indices=3)
        assert is_valid_heap(heap)

    def test_replace_unicode_strings(self):
        """Test replace with unicode strings."""
        heap = ["α", "β", "γ", "δ", "ε"]
        heapx.heapify(heap)
        heapx.replace(heap, "ω", indices=1)
        assert is_valid_heap(heap)

    def test_replace_empty_strings(self):
        """Test replace with empty strings."""
        heap = ["", "a", "", "b", ""]
        heapx.heapify(heap)
        heapx.replace(heap, "z", indices=0)
        assert is_valid_heap(heap)

    def test_replace_nested_tuples(self):
        """Test replace with nested tuples."""
        heap = [(1, (2, 3)), (0, (1, 2)), (2, (3, 4))]
        heapx.heapify(heap)
        heapx.replace(heap, (5, (6, 7)), indices=0)
        assert is_valid_heap(heap)

    def test_replace_bytes(self):
        """Test replace with bytes."""
        heap = [b"abc", b"def", b"ghi", b"aaa"]
        heapx.heapify(heap)
        heapx.replace(heap, b"zzz", indices=1)
        assert is_valid_heap(heap)

# ============================================================================
# Arity Parameter Tests (16 tests)
# ============================================================================

class TestArityParameter:
    """Test replace with different arity values."""

    @pytest.mark.parametrize("arity", [1, 2, 3, 4, 5, 6, 7, 8, 10, 12, 15, 16])
    def test_replace_various_arities(self, arity):
        """Test replace with various arity values."""
        heap = list(range(100, 0, -1))
        heapx.heapify(heap, arity=arity)
        heapx.replace(heap, 50, indices=10, arity=arity)
        assert len(heap) == 100
        assert is_valid_heap(heap, arity=arity)

    def test_replace_arity_1_maintains_sorted(self):
        """Test arity=1 maintains sorted order."""
        heap = [1, 3, 5, 7, 9]
        heapx.heapify(heap, arity=1)
        heapx.replace(heap, 4, indices=2, arity=1)
        assert heap == sorted(heap)

    def test_replace_arity_2_binary_heap(self):
        """Test arity=2 (binary heap) replacement."""
        heap = list(range(50))
        random.shuffle(heap)
        heapx.heapify(heap, arity=2)
        heapx.replace(heap, 100, indices=15, arity=2)
        assert is_valid_heap(heap, arity=2)

    def test_replace_arity_3_ternary_heap(self):
        """Test arity=3 (ternary heap) replacement."""
        heap = list(range(50))
        random.shuffle(heap)
        heapx.heapify(heap, arity=3)
        heapx.replace(heap, 100, indices=15, arity=3)
        assert is_valid_heap(heap, arity=3)

    def test_replace_arity_4_quaternary_heap(self):
        """Test arity=4 (quaternary heap) replacement."""
        heap = list(range(50))
        random.shuffle(heap)
        heapx.heapify(heap, arity=4)
        heapx.replace(heap, 100, indices=15, arity=4)
        assert is_valid_heap(heap, arity=4)

# ============================================================================
# Max Heap Tests (10 tests)
# ============================================================================

class TestMaxHeap:
    """Test replace with max_heap parameter."""

    def test_replace_max_heap_root(self):
        """Test replacing root from max heap."""
        heap = [1, 2, 3, 4, 5]
        heapx.heapify(heap, max_heap=True)
        heapx.replace(heap, 10, indices=0, max_heap=True)
        assert is_valid_heap(heap, max_heap=True)

    def test_replace_max_heap_middle(self):
        """Test replacing middle element from max heap."""
        heap = list(range(1, 21))
        heapx.heapify(heap, max_heap=True)
        heapx.replace(heap, 100, indices=10, max_heap=True)
        assert is_valid_heap(heap, max_heap=True)

    def test_replace_max_heap_arity_3(self):
        """Test max heap with arity=3."""
        heap = list(range(50))
        heapx.heapify(heap, max_heap=True, arity=3)
        heapx.replace(heap, 100, indices=5, max_heap=True, arity=3)
        assert is_valid_heap(heap, max_heap=True, arity=3)

    def test_replace_max_heap_with_key(self):
        """Test max heap with key function."""
        heap = [-5, 2, -8, 1, 9]
        heapx.heapify(heap, max_heap=True, cmp=abs)
        heapx.replace(heap, -1, indices=0, max_heap=True, cmp=abs)
        assert is_valid_heap(heap, max_heap=True, cmp=abs)

    def test_replace_max_heap_floats(self):
        """Test max heap with floats."""
        heap = [1.5, 2.7, 3.2, 4.1, 5.9]
        heapx.heapify(heap, max_heap=True)
        heapx.replace(heap, 10.5, indices=2, max_heap=True)
        assert is_valid_heap(heap, max_heap=True)

    def test_replace_max_heap_strings(self):
        """Test max heap with strings."""
        heap = ["apple", "banana", "cherry", "date"]
        heapx.heapify(heap, max_heap=True)
        heapx.replace(heap, "zebra", indices=1, max_heap=True)
        assert is_valid_heap(heap, max_heap=True)

    def test_replace_max_heap_batch(self):
        """Test batch replacement from max heap."""
        heap = list(range(50))
        heapx.heapify(heap, max_heap=True)
        heapx.replace(heap, [100, 101, 102], indices=[0, 5, 10], max_heap=True)
        assert is_valid_heap(heap, max_heap=True)

    def test_replace_max_heap_small(self):
        """Test small max heap replacement."""
        heap = list(range(10))
        heapx.heapify(heap, max_heap=True)
        heapx.replace(heap, 100, indices=3, max_heap=True)
        assert is_valid_heap(heap, max_heap=True)

    def test_replace_max_heap_duplicates(self):
        """Test max heap with duplicates."""
        heap = [5, 5, 5, 5, 5]
        heapx.heapify(heap, max_heap=True)
        heapx.replace(heap, 10, indices=0, max_heap=True)
        assert is_valid_heap(heap, max_heap=True)

    def test_replace_max_heap_negative(self):
        """Test max heap with negative numbers."""
        heap = [-10, -5, -20, -3, -15]
        heapx.heapify(heap, max_heap=True)
        heapx.replace(heap, -1, indices=1, max_heap=True)
        assert is_valid_heap(heap, max_heap=True)

# ============================================================================
# Custom Comparison Tests (10 tests)
# ============================================================================

class TestCustomComparison:
    """Test replace with custom comparison functions."""

    def test_replace_with_abs_key(self):
        """Test replace with abs key function."""
        heap = [-5, 2, -8, 1, 9, -3, 7]
        heapx.heapify(heap, cmp=abs)
        heapx.replace(heap, -1, indices=0, cmp=abs)
        assert is_valid_heap(heap, cmp=abs)

    def test_replace_with_len_key(self):
        """Test replace with len key function."""
        heap = ["a", "abc", "ab", "abcd", "abcde"]
        heapx.heapify(heap, cmp=len)
        heapx.replace(heap, "z", indices=0, cmp=len)
        assert is_valid_heap(heap, cmp=len)

    def test_replace_with_lambda_key(self):
        """Test replace with lambda key."""
        heap = [(1, 10), (2, 5), (3, 15), (4, 3)]
        heapx.heapify(heap, cmp=lambda x: x[1])
        heapx.replace(heap, (5, 1), indices=0, cmp=lambda x: x[1])
        assert is_valid_heap(heap, cmp=lambda x: x[1])

    def test_replace_with_reverse_key(self):
        """Test replace with reverse ordering."""
        heap = [1, 2, 3, 4, 5]
        heapx.heapify(heap, cmp=lambda x: -x)
        heapx.replace(heap, 10, indices=0, cmp=lambda x: -x)
        assert is_valid_heap(heap, cmp=lambda x: -x)

    def test_replace_with_modulo_key(self):
        """Test replace with modulo key."""
        heap = [10, 21, 32, 43, 54, 65]
        heapx.heapify(heap, cmp=lambda x: x % 10)
        heapx.replace(heap, 99, indices=2, cmp=lambda x: x % 10)
        assert is_valid_heap(heap, cmp=lambda x: x % 10)

    def test_replace_with_nested_key(self):
        """Test replace with nested structure key."""
        heap = [{"val": 5}, {"val": 2}, {"val": 8}, {"val": 1}]
        heapx.heapify(heap, cmp=lambda x: x["val"])
        heapx.replace(heap, {"val": 3}, indices=0, cmp=lambda x: x["val"])
        assert is_valid_heap(heap, cmp=lambda x: x["val"])

    def test_replace_with_key_arity_3(self):
        """Test replace with key and arity=3."""
        heap = [-5, 2, -8, 1, 9, -3, 7]
        heapx.heapify(heap, cmp=abs, arity=3)
        heapx.replace(heap, -1, indices=1, cmp=abs, arity=3)
        assert is_valid_heap(heap, cmp=abs, arity=3)

    def test_replace_with_key_max_heap(self):
        """Test replace with key and max_heap."""
        heap = [-5, 2, -8, 1, 9]
        heapx.heapify(heap, max_heap=True, cmp=abs)
        heapx.replace(heap, -1, indices=0, max_heap=True, cmp=abs)
        assert is_valid_heap(heap, max_heap=True, cmp=abs)

    def test_replace_with_complex_key(self):
        """Test replace with complex key function."""
        heap = ["apple", "banana", "cherry", "date"]
        heapx.heapify(heap, cmp=lambda x: (len(x), x))
        heapx.replace(heap, "fig", indices=1, cmp=lambda x: (len(x), x))
        assert is_valid_heap(heap, cmp=lambda x: (len(x), x))

    def test_replace_with_key_batch(self):
        """Test batch replace with key function."""
        heap = [-5, 2, -8, 1, 9, -3, 7, -4, 6]
        heapx.heapify(heap, cmp=abs)
        heapx.replace(heap, [-1, -2, -10], indices=[0, 2, 4], cmp=abs)
        assert is_valid_heap(heap, cmp=abs)

# ============================================================================
# Object Identity Tests (8 tests)
# ============================================================================

class TestObjectIdentity:
    """Test replace by object identity."""

    def test_replace_by_object_identity(self):
        """Test replacing by object identity."""
        obj = "target"
        heap = [1, obj, 3, 4, 5]
        heapx.heapify(heap, cmp=lambda x: 0 if x == obj else hash(x))
        count = heapx.replace(heap, "new", object=obj, cmp=lambda x: 0 if x == obj else hash(x))
        assert count == 1
        assert obj not in heap

    def test_replace_by_object_not_found(self):
        """Test replacing object not in heap."""
        obj = "target"
        heap = [1, 2, 3, 4, 5]
        heapx.heapify(heap)
        count = heapx.replace(heap, "new", object=obj)
        assert count == 0
        assert len(heap) == 5

    def test_replace_by_object_multiple_occurrences(self):
        """Test replacing object with multiple occurrences."""
        obj = "target"
        heap = [obj, 1, obj, 2, obj]
        heapx.heapify(heap, cmp=lambda x: 0 if x == obj else hash(x))
        count = heapx.replace(heap, "new", object=obj, cmp=lambda x: 0 if x == obj else hash(x))
        assert count == 3

    def test_replace_by_object_list(self):
        """Test replace by object from list."""
        obj = [1, 2, 3]
        heap = [obj, [4, 5], [6, 7]]
        heapx.heapify(heap, cmp=lambda x: sum(x))
        count = heapx.replace(heap, ([0, 0, 0],), object=obj, cmp=lambda x: sum(x))
        assert count == 1
        assert [0, 0, 0] in heap

    def test_replace_by_object_dict(self):
        """Test replace by object dict."""
        obj = {"key": "value"}
        heap = [obj, {"a": 1}, {"b": 2}]
        heapx.heapify(heap, cmp=lambda x: str(x))
        count = heapx.replace(heap, {"z": 9}, object=obj, cmp=lambda x: str(x))
        assert count == 1

    def test_replace_by_object_custom_class(self):
        """Test replace by custom class object."""
        class Item:
            def __init__(self, val):
                self.val = val
            def __lt__(self, other):
                return self.val < other.val
        
        obj = Item(5)
        heap = [Item(1), obj, Item(3)]
        heapx.heapify(heap)
        count = heapx.replace(heap, Item(10), object=obj)
        assert count == 1

    def test_replace_by_object_with_batch(self):
        """Test replace by object with batch values."""
        obj1 = "target1"
        obj2 = "target2"
        heap = [obj1, 1, obj2, 2, 3]
        heapx.heapify(heap, cmp=lambda x: 0 if isinstance(x, str) else x)
        count = heapx.replace(heap, "new1", object=obj1, cmp=lambda x: 0 if isinstance(x, str) else x)
        assert count >= 1

    def test_replace_by_object_preserves_heap(self):
        """Test replace by object preserves heap property."""
        obj = 5
        heap = [1, 2, obj, 4, 6, 7]
        heapx.heapify(heap)
        heapx.replace(heap, 3, object=obj)
        assert is_valid_heap(heap)

# ============================================================================
# Predicate Tests (10 tests)
# ============================================================================

class TestPredicate:
    """Test replace by predicate function."""

    def test_replace_by_predicate_even(self):
        """Test replacing even numbers by predicate."""
        heap = list(range(1, 21))
        heapx.heapify(heap)
        count = heapx.replace(heap, 100, predicate=lambda x: x % 2 == 0)
        assert count == 10
        assert is_valid_heap(heap)

    def test_replace_by_predicate_odd(self):
        """Test replacing odd numbers by predicate."""
        heap = list(range(1, 21))
        heapx.heapify(heap)
        count = heapx.replace(heap, 100, predicate=lambda x: x % 2 == 1)
        assert count == 10
        assert is_valid_heap(heap)

    def test_replace_by_predicate_greater_than(self):
        """Test replacing elements greater than threshold."""
        heap = list(range(1, 21))
        heapx.heapify(heap)
        count = heapx.replace(heap, 0, predicate=lambda x: x > 15)
        assert count == 5
        assert is_valid_heap(heap)

    def test_replace_by_predicate_string_length(self):
        """Test replacing strings by length predicate."""
        heap = ["a", "abc", "ab", "abcd", "abcde"]
        heapx.heapify(heap)
        count = heapx.replace(heap, "z", predicate=lambda x: len(x) > 2)
        assert count == 3
        assert is_valid_heap(heap)

    def test_replace_by_predicate_no_matches(self):
        """Test predicate with no matches."""
        heap = [1, 2, 3, 4, 5]
        heapx.heapify(heap)
        count = heapx.replace(heap, 100, predicate=lambda x: x > 100)
        assert count == 0
        assert len(heap) == 5

    def test_replace_by_predicate_all_match(self):
        """Test predicate where all match."""
        heap = [2, 4, 6, 8, 10]
        heapx.heapify(heap)
        count = heapx.replace(heap, 100, predicate=lambda x: x % 2 == 0)
        assert count == 5
        assert is_valid_heap(heap)

    def test_replace_by_predicate_with_values_list(self):
        """Test predicate with list of values."""
        heap = list(range(1, 11))
        heapx.heapify(heap)
        values = [100, 101, 102, 103, 104]
        count = heapx.replace(heap, values, predicate=lambda x: x % 2 == 0)
        assert count == 5
        assert is_valid_heap(heap)

    def test_replace_by_predicate_complex(self):
        """Test complex predicate."""
        heap = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
        heapx.heapify(heap)
        count = heapx.replace(heap, 99, predicate=lambda x: x % 2 == 0 and x > 2)
        assert count == 4  # Replaces 4, 6, 8, 10
        assert is_valid_heap(heap)

    def test_replace_by_predicate_with_key(self):
        """Test predicate with key function."""
        heap = [-5, 2, -8, 1, 9, -3, 7]
        heapx.heapify(heap, cmp=abs)
        count = heapx.replace(heap, -100, predicate=lambda x: abs(x) > 5, cmp=abs)
        assert count == 3
        assert is_valid_heap(heap, cmp=abs)

    def test_replace_by_predicate_preserves_heap(self):
        """Test predicate replacement preserves heap property."""
        heap = list(range(1, 51))
        heapx.heapify(heap)
        heapx.replace(heap, 100, predicate=lambda x: x > 40)
        assert is_valid_heap(heap)

# ============================================================================
# Edge Cases (15 tests)
# ============================================================================

class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_replace_single_element_heap(self):
        """Test replace from single element heap."""
        heap = [42]
        count = heapx.replace(heap, 100, indices=0)
        assert count == 1
        assert len(heap) == 1
        assert heap[0] == 100

    def test_replace_two_element_heap(self):
        """Test replace from two element heap."""
        heap = [1, 2]
        heapx.heapify(heap)
        heapx.replace(heap, 10, indices=0)
        assert len(heap) == 2
        assert is_valid_heap(heap)

    def test_replace_duplicate_indices(self):
        """Test replace with duplicate indices."""
        heap = list(range(1, 11))
        heapx.heapify(heap)
        count = heapx.replace(heap, [100, 101, 102], indices=[0, 0, 0])
        assert count == 3  # All replacements occur

    def test_replace_indices_out_of_order(self):
        """Test replace with unordered indices."""
        heap = list(range(1, 21))
        heapx.heapify(heap)
        count = heapx.replace(heap, [100, 101, 102, 103], indices=[15, 5, 10, 0])
        assert count == 4
        assert is_valid_heap(heap)

    def test_replace_negative_indices_multiple(self):
        """Test replace with multiple negative indices."""
        heap = list(range(1, 11))
        heapx.heapify(heap)
        count = heapx.replace(heap, [100, 101, 102], indices=[-1, -2, -3])
        assert count == 3
        assert is_valid_heap(heap)

    def test_replace_very_large_heap(self):
        """Test replace from very large heap."""
        heap = list(range(10000))
        random.shuffle(heap)
        heapx.heapify(heap)
        heapx.replace(heap, 99999, indices=5000)
        assert len(heap) == 10000
        assert is_valid_heap(heap)

    def test_replace_alternating_indices(self):
        """Test replacing alternating indices."""
        heap = list(range(20))
        heapx.heapify(heap)
        indices = list(range(0, 20, 2))
        values = [100 + i for i in range(10)]
        count = heapx.replace(heap, values, indices=indices)
        assert count == 10
        assert is_valid_heap(heap)

    def test_replace_boundary_16_elements(self):
        """Test replace at boundary of small heap optimization."""
        heap = list(range(16, 0, -1))
        heapx.heapify(heap)
        heapx.replace(heap, 100, indices=5)
        assert len(heap) == 16
        assert is_valid_heap(heap)

    def test_replace_boundary_17_elements(self):
        """Test replace just above small heap boundary."""
        heap = list(range(17, 0, -1))
        heapx.heapify(heap)
        heapx.replace(heap, 100, indices=5)
        assert len(heap) == 17
        assert is_valid_heap(heap)

    def test_replace_with_same_value(self):
        """Test replacing with same value."""
        heap = [1, 2, 3, 4, 5]
        heapx.heapify(heap)
        heapx.replace(heap, 3, indices=2)
        assert is_valid_heap(heap)

    def test_replace_all_elements(self):
        """Test replacing all elements."""
        heap = list(range(1, 11))
        heapx.heapify(heap)
        indices = list(range(10))
        values = [100 + i for i in range(10)]
        count = heapx.replace(heap, values, indices=indices)
        assert count == 10
        assert is_valid_heap(heap)

    def test_replace_with_none_values(self):
        """Test replace with None values."""
        heap = [1, 2, 3, 4, 5]
        heapx.heapify(heap, cmp=lambda x: 0 if x is None else x)
        heapx.replace(heap, None, indices=2, cmp=lambda x: 0 if x is None else x)
        assert is_valid_heap(heap, cmp=lambda x: 0 if x is None else x)

    def test_replace_batch_threshold(self):
        """Test batch at k=n/4 threshold."""
        heap = list(range(100))
        heapx.heapify(heap)
        indices = list(range(25))  # Exactly n/4
        values = [200 + i for i in range(25)]
        count = heapx.replace(heap, values, indices=indices)
        assert count == 25
        assert is_valid_heap(heap)

    def test_replace_mixed_criteria(self):
        """Test replace with multiple criteria."""
        heap = list(range(1, 21))
        heapx.heapify(heap)
        count = heapx.replace(heap, 100, indices=[0, 1], predicate=lambda x: x > 15)
        assert count >= 2
        assert is_valid_heap(heap)

    def test_replace_values_length_mismatch(self):
        """Test replace with mismatched values length."""
        heap = list(range(1, 11))
        heapx.heapify(heap)
        with pytest.raises(ValueError):
            heapx.replace(heap, [100, 101], indices=[0, 1, 2])

# ============================================================================
# Stress Tests (10 tests)
# ============================================================================

class TestStressTests:
    """Stress tests for replace function."""

    def test_replace_random_indices_large_heap(self):
        """Test replacing random indices from large heap."""
        heap = list(range(1000))
        random.shuffle(heap)
        heapx.heapify(heap)
        indices = random.sample(range(len(heap)), 100)
        values = [10000 + i for i in range(100)]
        heapx.replace(heap, values, indices=indices)
        assert len(heap) == 1000
        assert is_valid_heap(heap)

    def test_replace_sequential_100_times(self):
        """Test 100 sequential replacements."""
        heap = list(range(1000, 0, -1))
        heapx.heapify(heap)
        for i in range(100):
            idx = random.randint(0, len(heap) - 1)
            heapx.replace(heap, 10000 + i, indices=idx)
        assert len(heap) == 1000
        assert is_valid_heap(heap)

    def test_replace_batch_500_elements(self):
        """Test batch replacement of 500 elements."""
        heap = list(range(1000))
        random.shuffle(heap)
        heapx.heapify(heap)
        indices = list(range(0, 1000, 2))
        values = [10000 + i for i in range(500)]
        heapx.replace(heap, values, indices=indices)
        assert len(heap) == 1000
        assert is_valid_heap(heap)

    def test_replace_with_duplicates_large(self):
        """Test replace from large heap with duplicates."""
        heap = [i % 100 for i in range(1000)]
        heapx.heapify(heap)
        heapx.replace(heap, 999, indices=list(range(100)))
        assert len(heap) == 1000
        assert is_valid_heap(heap)

    def test_replace_all_arities_large_heap(self):
        """Test replace with all arities on large heap."""
        for arity in [2, 3, 4, 5, 8]:
            heap = list(range(500, 0, -1))
            heapx.heapify(heap, arity=arity)
            heapx.replace(heap, 9999, indices=250, arity=arity)
            assert is_valid_heap(heap, arity=arity)

    def test_replace_predicate_large_heap(self):
        """Test predicate replacement on large heap."""
        heap = list(range(1000))
        heapx.heapify(heap)
        count = heapx.replace(heap, 9999, predicate=lambda x: x % 10 == 0)
        assert count == 100
        assert is_valid_heap(heap)

    def test_replace_with_key_large_heap(self):
        """Test replace with key on large heap."""
        heap = list(range(-500, 500))
        heapx.heapify(heap, cmp=abs)
        heapx.replace(heap, -9999, indices=100, cmp=abs)
        assert is_valid_heap(heap, cmp=abs)

    def test_replace_max_heap_large(self):
        """Test replace from large max heap."""
        heap = list(range(1000))
        heapx.heapify(heap, max_heap=True)
        heapx.replace(heap, 9999, indices=list(range(0, 100)), max_heap=True)
        assert is_valid_heap(heap, max_heap=True)

    def test_replace_alternating_pattern_large(self):
        """Test alternating replacement pattern on large heap."""
        heap = list(range(500))
        heapx.heapify(heap)
        for i in range(100):
            idx = 0 if i % 2 == 0 else len(heap) - 1
            heapx.replace(heap, 10000 + i, indices=idx)
        assert is_valid_heap(heap)

    def test_replace_random_large_scale(self):
        """Test random replacements on large scale."""
        heap = list(range(500))
        random.shuffle(heap)
        heapx.heapify(heap)
        indices = random.sample(range(len(heap)), 50)
        values = [10000 + i for i in range(50)]
        count = heapx.replace(heap, values, indices=indices)
        assert count == 50
        assert is_valid_heap(heap)

# ============================================================================
# Performance Benchmarks (7 tests)
# ============================================================================

@pytest.mark.benchmark
class TestPerformanceBenchmarks:
    """Performance benchmarks for replace function."""

    def test_benchmark_time_efficiency(self, capsys):
        """Comprehensive time efficiency benchmark for replace function."""
        
        output = []
        output.append("\n" + "="*80)
        output.append("TIME EFFICIENCY: heapx.replace - Single Item Replacement")
        output.append("="*80)
        output.append(f"Configuration: R=10 repetitions per size, Random integers, Min-heap, Arity=2")
        output.append("="*80)
        
        sizes = [100, 500, 1_000, 5_000, 10_000, 50_000, 100_000, 500_000, 1_000_000]
        repetitions = 10
        
        results = []
        
        for n in sizes:
            times = []
            
            for r in range(repetitions):
                # Prepare heap
                data = list(range(n))
                random.seed(r)
                random.shuffle(data)
                heapx.heapify(data)
                
                # Measure replace time (replace 100 random items)
                num_replacements = min(100, n)
                start = time.perf_counter()
                for _ in range(num_replacements):
                    idx = random.randint(0, len(data) - 1)
                    heapx.replace(data, 999999, indices=idx)
                elapsed = time.perf_counter() - start
                times.append(elapsed / num_replacements)  # Time per operation
            
            avg_time = mean(times)
            std_time = stdev(times) if len(times) > 1 else 0
            
            results.append({
                'n': n,
                'avg': avg_time,
                'std': std_time
            })
        
        # Time efficiency table
        output.append("\n" + "-"*65)
        output.append(f"{'n':>12} │ {'Time per replace (s)':>47}")
        output.append(f"{'':>12} │ {'avg ± std':>47}")
        output.append("-"*65)
        
        for r in results:
            output.append(f"{r['n']:>12,} │ {r['avg']:>20.8f} ± {r['std']:>20.8f}")
        
        output.append("-"*65)
        output.append("="*80 + "\n")
        
        # Print all output
        final_output = '\n'.join(output)
        print(final_output)
        sys.stdout.flush()
        
        # Also write to captured output for pytest
        with capsys.disabled():
            print(final_output)

    def test_benchmark_memory_efficiency(self, capsys):
        """Comprehensive memory efficiency benchmark for replace function."""
        
        output = []
        output.append("\n" + "="*80)
        output.append("MEMORY EFFICIENCY: heapx.replace")
        output.append("="*80)
        output.append(f"Configuration: Random integers, Min-heap, Arity=2")
        output.append("="*80)
        
        sizes = [100, 500, 1_000, 5_000, 10_000, 50_000, 100_000, 500_000, 1_000_000]
        
        memory_results = []
        
        for n in sizes:
            # Create heap
            data = list(range(n))
            random.seed(0)
            random.shuffle(data)
            heapx.heapify(data)
            
            # Measure memory
            mem_before = sys.getsizeof(data)
            
            # Replace 10% of items
            num_replacements = max(1, n // 10)
            indices = random.sample(range(n), num_replacements)
            heapx.replace(data, 999999, indices=indices)
            
            mem_after = sys.getsizeof(data)
            
            memory_results.append({
                'n': n,
                'mem_before': mem_before,
                'mem_after': mem_after,
                'replaced': num_replacements
            })
        
        # Memory efficiency table
        output.append("\n" + "-"*80)
        output.append(f"{'n':>12} │ {'Memory Before':>20} │ {'Memory After':>20} │ {'Items Replaced':>15}")
        output.append("-"*80)
        
        for r in memory_results:
            output.append(f"{r['n']:>12,} │ {r['mem_before']:>17,} B │ {r['mem_after']:>17,} B │ {r['replaced']:>15,}")
        
        output.append("-"*80)
        output.append("\nNote: Replace maintains O(1) auxiliary space (in-place modification)")
        output.append("="*80 + "\n")
        
        # Print all output
        final_output = '\n'.join(output)
        print(final_output)
        sys.stdout.flush()
        
        # Also write to captured output for pytest
        with capsys.disabled():
            print(final_output)

    def test_benchmark_batch_replacement_time(self):
        """Benchmark batch replacement time efficiency."""
        heap = list(range(1000))
        random.shuffle(heap)
        heapx.heapify(heap)
        
        batch_sizes = [10, 50, 100, 250, 500]
        results = []
        
        for batch_size in batch_sizes:
            times = []
            for _ in range(10):
                test_heap = heap.copy()
                indices = random.sample(range(len(test_heap)), batch_size)
                values = [10000 + i for i in range(batch_size)]
                start = time.perf_counter()
                heapx.replace(test_heap, values, indices=indices)
                elapsed = time.perf_counter() - start
                times.append(elapsed * 1000)
            
            avg_time = mean(times)
            std_time = stdev(times) if len(times) > 1 else 0
            strategy = "Sequential" if batch_size < 250 else "Batch+Heapify"
            results.append((batch_size, avg_time, std_time, strategy))
        
        print("\n" + "=" * 70)
        print("Batch Replacement - Time Efficiency")
        print("=" * 70)
        print(f"{'Batch Size':<15} {'Avg Time (ms)':<20} {'Std Dev (ms)':<15} {'Strategy':<15}")
        print("-" * 70)
        for batch, avg, std, strategy in results:
            print(f"{batch:<15} {avg:<20.6f} {std:<15.6f} {strategy:<15}")
        print("=" * 70)

    def test_benchmark_arity_performance(self):
        """Benchmark replacement performance across different arities."""
        arities = [2, 3, 4, 5, 8]
        results = []
        
        for arity in arities:
            heap = list(range(1000, 0, -1))
            heapx.heapify(heap, arity=arity)
            
            times = []
            for _ in range(10):
                test_heap = heap.copy()
                start = time.perf_counter()
                for _ in range(50):
                    if test_heap:
                        idx = random.randint(0, len(test_heap) - 1)
                        heapx.replace(test_heap, 99999, indices=idx, arity=arity)
                elapsed = time.perf_counter() - start
                times.append(elapsed / 50 * 1000)
            
            avg_time = mean(times)
            std_time = stdev(times) if len(times) > 1 else 0
            results.append((arity, avg_time, std_time))
        
        print("\n" + "=" * 70)
        print("Arity Performance Comparison")
        print("=" * 70)
        print(f"{'Arity':<10} {'Avg Time (ms)':<20} {'Std Dev (ms)':<20}")
        print("-" * 70)
        for arity, avg, std in results:
            print(f"{arity:<10} {avg:<20.6f} {std:<20.6f}")
        print("=" * 70)

    def test_benchmark_key_function_overhead(self):
        """Benchmark key function overhead."""
        heap = list(range(-500, 500))
        
        # Without key
        heapx.heapify(heap)
        times_no_key = []
        for _ in range(10):
            test_heap = heap.copy()
            start = time.perf_counter()
            for _ in range(50):
                if test_heap:
                    heapx.replace(test_heap, 9999, indices=0)
            elapsed = time.perf_counter() - start
            times_no_key.append(elapsed / 50 * 1000)
        
        # With key
        heapx.heapify(heap, cmp=abs)
        times_with_key = []
        for _ in range(10):
            test_heap = heap.copy()
            start = time.perf_counter()
            for _ in range(50):
                if test_heap:
                    heapx.replace(test_heap, -9999, indices=0, cmp=abs)
            elapsed = time.perf_counter() - start
            times_with_key.append(elapsed / 50 * 1000)
        
        avg_no_key = mean(times_no_key)
        avg_with_key = mean(times_with_key)
        overhead = (avg_with_key / avg_no_key - 1) * 100
        
        print("\n" + "=" * 70)
        print("Key Function Overhead")
        print("=" * 70)
        print(f"Without key: {avg_no_key:.6f} ms")
        print(f"With key:    {avg_with_key:.6f} ms")
        print(f"Overhead:    {overhead:.2f}%")
        print("=" * 70)

    def test_benchmark_small_heap_optimization(self):
        """Benchmark small heap optimization."""
        sizes = [5, 10, 15, 16, 17, 20, 30]
        results = []
        
        for size in sizes:
            heap = list(range(size, 0, -1))
            heapx.heapify(heap)
            
            times = []
            for _ in range(10):
                test_heap = heap.copy()
                start = time.perf_counter()
                for _ in range(min(50, size)):
                    if test_heap:
                        heapx.replace(test_heap, 9999, indices=0)
                elapsed = time.perf_counter() - start
                times.append(elapsed / min(50, size) * 1000)
            
            avg_time = mean(times)
            results.append((size, avg_time))
        
        print("\n" + "=" * 70)
        print("Small Heap Optimization (n ≤ 16)")
        print("=" * 70)
        print(f"{'Size':<10} {'Avg Time (ms)':<20}")
        print("-" * 70)
        for size, avg in results:
            marker = " *" if size <= 16 else ""
            print(f"{size:<10} {avg:<20.6f}{marker}")
        print("=" * 70)
        print("* = Uses insertion sort optimization")

    def test_benchmark_predicate_replacement(self):
        """Benchmark predicate-based replacement."""
        heap = list(range(1000))
        heapx.heapify(heap)
        
        predicates = [
            ("Even numbers", lambda x: x % 2 == 0),
            ("Divisible by 10", lambda x: x % 10 == 0),
            ("Greater than 500", lambda x: x > 500),
        ]
        
        results = []
        for name, pred in predicates:
            times = []
            for _ in range(10):
                test_heap = heap.copy()
                start = time.perf_counter()
                heapx.replace(test_heap, 9999, predicate=pred)
                elapsed = time.perf_counter() - start
                times.append(elapsed * 1000)
            
            avg_time = mean(times)
            results.append((name, avg_time))
        
        print("\n" + "=" * 70)
        print("Predicate Replacement Performance")
        print("=" * 70)
        print(f"{'Predicate':<25} {'Avg Time (ms)':<20}")
        print("-" * 70)
        for name, avg in results:
            print(f"{name:<25} {avg:<20.6f}")
        print("=" * 70)


# ============================================================================
# Boolean Tests
# ============================================================================

class TestBooleanReplace:
  """Test replace with boolean data."""

  def test_replace_booleans(self):
    """Test replacing in boolean heap."""
    heap = generate_booleans(50)
    heapx.heapify(heap)
    count = heapx.replace(heap, True, indices=0)
    assert count == 1
    assert is_valid_heap(heap)

# ============================================================================
# Bytes Tests
# ============================================================================

class TestBytesReplace:
  """Test replace with bytes data."""

  def test_replace_bytes(self):
    """Test replacing in bytes heap."""
    heap = generate_bytes(30)
    heapx.heapify(heap)
    count = heapx.replace(heap, b'test', indices=0)
    assert count == 1
    assert is_valid_heap(heap)

# ============================================================================
# Bytearray Tests
# ============================================================================

class TestBytearrayReplace:
  """Test replace with bytearray data."""

  def test_replace_bytearrays(self):
    """Test replacing in bytearray heap."""
    heap = generate_bytearrays(30)
    heapx.heapify(heap)
    count = heapx.replace(heap, bytearray(b'test'), indices=0)
    assert count == 1
    assert is_valid_heap(heap)

# ============================================================================
# List Tests
# ============================================================================

class TestListReplace:
  """Test replace with list data."""

  def test_replace_lists(self):
    """Test replacing in list heap."""
    heap = generate_lists(30)
    heapx.heapify(heap)
    count = heapx.replace(heap, [99, 99, 99], indices=0)
    assert count == 1
    assert is_valid_heap(heap)

# ============================================================================
# Mixed Type Tests
# ============================================================================

class TestMixedReplace:
  """Test replace with mixed comparable types."""

  def test_replace_mixed(self):
    """Test replacing in mixed int/float heap."""
    heap = generate_mixed(100)
    heapx.heapify(heap)
    count = heapx.replace(heap, 999, indices=0)
    assert count == 1
    assert is_valid_heap(heap)

  def test_replace_mixed_predicate(self):
    """Test replacing in mixed heap with predicate."""
    heap = generate_mixed(100)
    heapx.heapify(heap)
    count = heapx.replace(heap, 0, predicate=lambda x: x > 50)
    assert is_valid_heap(heap)
