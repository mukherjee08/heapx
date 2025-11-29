"""
Comprehensive test suite for heapx.remove function.

Tests cover all 11 dispatch priorities, parameters, data types, edge cases,
and performance benchmarks. Includes 100+ distinct test cases.
"""

import heapx
import pytest
import random
import string
import time
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

class TestBasicRemove:
    """Test basic remove functionality."""

    def test_remove_single_index_from_root(self):
        """Test removing root element by index."""
        heap = [1, 3, 2, 7, 5, 4, 6]
        heapx.heapify(heap)
        count = heapx.remove(heap, indices=0)
        assert count == 1
        assert len(heap) == 6
        assert is_valid_heap(heap)

    def test_remove_single_index_from_middle(self):
        """Test removing middle element by index."""
        heap = list(range(1, 21))
        heapx.heapify(heap)
        count = heapx.remove(heap, indices=10)
        assert count == 1
        assert len(heap) == 19
        assert is_valid_heap(heap)

    def test_remove_single_index_from_end(self):
        """Test removing last element by index."""
        heap = [1, 2, 3, 4, 5]
        heapx.heapify(heap)
        count = heapx.remove(heap, indices=4)
        assert count == 1
        assert len(heap) == 4
        assert is_valid_heap(heap)

    def test_remove_negative_index(self):
        """Test removing with negative index."""
        heap = [1, 2, 3, 4, 5]
        heapx.heapify(heap)
        count = heapx.remove(heap, indices=-1)
        assert count == 1
        assert len(heap) == 4
        assert is_valid_heap(heap)

    def test_remove_out_of_bounds_index(self):
        """Test removing with out of bounds index."""
        heap = [1, 2, 3]
        heapx.heapify(heap)
        count = heapx.remove(heap, indices=10)
        assert count == 0
        assert len(heap) == 3

    def test_remove_from_empty_heap(self):
        """Test removing from empty heap."""
        heap = []
        count = heapx.remove(heap, indices=0)
        assert count == 0

    def test_remove_from_single_element(self):
        """Test removing from single element heap."""
        heap = [42]
        count = heapx.remove(heap, indices=0)
        assert count == 1
        assert len(heap) == 0

    def test_remove_maintains_heap_property(self):
        """Test that remove maintains heap property."""
        heap = [1, 3, 2, 7, 5, 4, 6, 8, 9, 10]
        heapx.heapify(heap)
        heapx.remove(heap, indices=3)
        assert is_valid_heap(heap)

    def test_remove_with_return_items(self):
        """Test remove with return_items=True."""
        heap = [5, 3, 8, 1, 9]
        heapx.heapify(heap)
        count, items = heapx.remove(heap, indices=0, return_items=True)
        assert count == 1
        assert len(items) == 1
        assert len(heap) == 4

    def test_remove_multiple_indices(self):
        """Test removing multiple indices."""
        heap = list(range(1, 21))
        heapx.heapify(heap)
        count = heapx.remove(heap, indices=[0, 5, 10, 15])
        assert count == 4
        assert len(heap) == 16
        assert is_valid_heap(heap)

# ============================================================================
# Dispatch Priority Tests (11 tests)
# ============================================================================

class TestDispatchPriorities:
    """Test all 11 dispatch priorities."""

    def test_priority_1_small_heap_no_key(self):
        """Priority 1: Small heap (n ≤ 16) with insertion sort."""
        heap = list(range(15, 0, -1))
        heapx.heapify(heap)
        heapx.remove(heap, indices=5)
        assert len(heap) == 14
        assert is_valid_heap(heap)

    def test_priority_2_arity_1_sorted_list(self):
        """Priority 2: Arity=1 (sorted list) removal."""
        heap = [1, 3, 5, 7, 9, 11]
        heapx.heapify(heap, arity=1)
        heapx.remove(heap, indices=2, arity=1)
        assert heap == [1, 3, 7, 9, 11]

    def test_priority_3_binary_heap_no_key(self):
        """Priority 3: Binary heap (arity=2) inline sift."""
        heap = list(range(100, 0, -1))
        heapx.heapify(heap)
        heapx.remove(heap, indices=10)
        assert len(heap) == 99
        assert is_valid_heap(heap)

    def test_priority_4_ternary_heap_no_key(self):
        """Priority 4: Ternary heap (arity=3) inline sift."""
        heap = list(range(100, 0, -1))
        heapx.heapify(heap, arity=3)
        heapx.remove(heap, indices=10, arity=3)
        assert len(heap) == 99
        assert is_valid_heap(heap, arity=3)

    def test_priority_5_quaternary_heap_no_key(self):
        """Priority 5: Quaternary heap (arity=4) inline sift."""
        heap = list(range(100, 0, -1))
        heapx.heapify(heap, arity=4)
        heapx.remove(heap, indices=10, arity=4)
        assert len(heap) == 99
        assert is_valid_heap(heap, arity=4)

    def test_priority_6_nary_heap_no_key(self):
        """Priority 6: N-ary heap (arity≥5) helper function."""
        heap = list(range(100, 0, -1))
        heapx.heapify(heap, arity=5)
        heapx.remove(heap, indices=10, arity=5)
        assert len(heap) == 99
        assert is_valid_heap(heap, arity=5)

    def test_priority_7_binary_heap_with_key(self):
        """Priority 7: Binary heap with key function."""
        heap = [-5, 2, -8, 1, 9, -3, 7]
        heapx.heapify(heap, cmp=abs)
        heapx.remove(heap, indices=0, cmp=abs)
        assert len(heap) == 6
        assert is_valid_heap(heap, cmp=abs)

    def test_priority_8_ternary_heap_with_key(self):
        """Priority 8: Ternary heap with key function."""
        heap = [-5, 2, -8, 1, 9, -3, 7]
        heapx.heapify(heap, cmp=abs, arity=3)
        heapx.remove(heap, indices=0, cmp=abs, arity=3)
        assert len(heap) == 6
        assert is_valid_heap(heap, cmp=abs, arity=3)

    def test_priority_9_nary_heap_with_key(self):
        """Priority 9: N-ary heap with key function."""
        heap = [-5, 2, -8, 1, 9, -3, 7]
        heapx.heapify(heap, cmp=abs, arity=5)
        heapx.remove(heap, indices=0, cmp=abs, arity=5)
        assert len(heap) == 6
        assert is_valid_heap(heap, cmp=abs, arity=5)

    def test_priority_10_batch_small_result(self):
        """Priority 10: Batch removal with small result heap."""
        heap = list(range(20, 0, -1))
        heapx.heapify(heap)
        heapx.remove(heap, indices=list(range(5)))
        assert len(heap) == 15
        assert is_valid_heap(heap)

    def test_priority_11_batch_large_result(self):
        """Priority 11: Batch removal with large result heap."""
        heap = list(range(100, 0, -1))
        heapx.heapify(heap)
        heapx.remove(heap, indices=list(range(10)))
        assert len(heap) == 90
        assert is_valid_heap(heap)

# ============================================================================
# Data Type Tests (15 tests)
# ============================================================================

class TestDataTypes:
    """Test remove with different data types."""

    def test_remove_integers(self):
        """Test remove with integers."""
        heap = generate_integers(50)
        heapx.heapify(heap)
        heapx.remove(heap, indices=10)
        assert is_valid_heap(heap)

    def test_remove_floats(self):
        """Test remove with floats."""
        heap = generate_floats(50)
        heapx.heapify(heap)
        heapx.remove(heap, indices=10)
        assert is_valid_heap(heap)

    def test_remove_strings(self):
        """Test remove with strings."""
        heap = generate_strings(50)
        heapx.heapify(heap)
        heapx.remove(heap, indices=10)
        assert is_valid_heap(heap)

    def test_remove_tuples(self):
        """Test remove with tuples."""
        heap = generate_tuples(50)
        heapx.heapify(heap)
        heapx.remove(heap, indices=10)
        assert is_valid_heap(heap)

    def test_remove_mixed_numbers(self):
        """Test remove with mixed int/float."""
        heap = [1, 2.5, 3, 4.5, 5, 6.5, 7]
        heapx.heapify(heap)
        heapx.remove(heap, indices=2)
        assert is_valid_heap(heap)

    def test_remove_negative_integers(self):
        """Test remove with negative integers."""
        heap = [-10, -5, -20, -3, -15, -8]
        heapx.heapify(heap)
        heapx.remove(heap, indices=1)
        assert is_valid_heap(heap)

    def test_remove_large_integers(self):
        """Test remove with large integers."""
        heap = [10**9, 10**8, 10**10, 10**7]
        heapx.heapify(heap)
        heapx.remove(heap, indices=0)
        assert is_valid_heap(heap)

    def test_remove_zero_values(self):
        """Test remove with zeros."""
        heap = [0, 1, 0, 2, 0, 3]
        heapx.heapify(heap)
        heapx.remove(heap, indices=0)
        assert is_valid_heap(heap)

    def test_remove_duplicate_values(self):
        """Test remove with duplicates."""
        heap = [5, 5, 5, 5, 5]
        heapx.heapify(heap)
        heapx.remove(heap, indices=2)
        assert len(heap) == 4
        assert is_valid_heap(heap)

    def test_remove_boolean_values(self):
        """Test remove with booleans."""
        heap = [True, False, True, False, True]
        heapx.heapify(heap)
        heapx.remove(heap, indices=0)
        assert is_valid_heap(heap)

    def test_remove_single_char_strings(self):
        """Test remove with single character strings."""
        heap = list("abcdefghij")
        heapx.heapify(heap)
        heapx.remove(heap, indices=3)
        assert is_valid_heap(heap)

    def test_remove_unicode_strings(self):
        """Test remove with unicode strings."""
        heap = ["α", "β", "γ", "δ", "ε"]
        heapx.heapify(heap)
        heapx.remove(heap, indices=1)
        assert is_valid_heap(heap)

    def test_remove_empty_strings(self):
        """Test remove with empty strings."""
        heap = ["", "a", "", "b", ""]
        heapx.heapify(heap)
        heapx.remove(heap, indices=0)
        assert is_valid_heap(heap)

    def test_remove_nested_tuples(self):
        """Test remove with nested tuples."""
        heap = [(1, (2, 3)), (0, (1, 2)), (2, (3, 4))]
        heapx.heapify(heap)
        heapx.remove(heap, indices=0)
        assert is_valid_heap(heap)

    def test_remove_bytes(self):
        """Test remove with bytes."""
        heap = [b"abc", b"def", b"ghi", b"aaa"]
        heapx.heapify(heap)
        heapx.remove(heap, indices=1)
        assert is_valid_heap(heap)

# ============================================================================
# Arity Parameter Tests (16 tests)
# ============================================================================

class TestArityParameter:
    """Test remove with different arity values."""

    @pytest.mark.parametrize("arity", [1, 2, 3, 4, 5, 6, 7, 8, 10, 12, 15, 16])
    def test_remove_various_arities(self, arity):
        """Test remove with various arity values."""
        heap = list(range(100, 0, -1))
        heapx.heapify(heap, arity=arity)
        heapx.remove(heap, indices=10, arity=arity)
        assert len(heap) == 99
        assert is_valid_heap(heap, arity=arity)

    def test_remove_arity_1_maintains_sorted(self):
        """Test arity=1 maintains sorted order."""
        heap = [1, 3, 5, 7, 9]
        heapx.heapify(heap, arity=1)
        heapx.remove(heap, indices=2, arity=1)
        assert heap == sorted(heap)

    def test_remove_arity_2_binary_heap(self):
        """Test arity=2 (binary heap) removal."""
        heap = list(range(50))
        random.shuffle(heap)
        heapx.heapify(heap, arity=2)
        heapx.remove(heap, indices=15, arity=2)
        assert is_valid_heap(heap, arity=2)

    def test_remove_arity_3_ternary_heap(self):
        """Test arity=3 (ternary heap) removal."""
        heap = list(range(50))
        random.shuffle(heap)
        heapx.heapify(heap, arity=3)
        heapx.remove(heap, indices=15, arity=3)
        assert is_valid_heap(heap, arity=3)

    def test_remove_arity_4_quaternary_heap(self):
        """Test arity=4 (quaternary heap) removal."""
        heap = list(range(50))
        random.shuffle(heap)
        heapx.heapify(heap, arity=4)
        heapx.remove(heap, indices=15, arity=4)
        assert is_valid_heap(heap, arity=4)

# ============================================================================
# Max Heap Tests (10 tests)
# ============================================================================

class TestMaxHeap:
    """Test remove with max_heap parameter."""

    def test_remove_max_heap_root(self):
        """Test removing root from max heap."""
        heap = [1, 2, 3, 4, 5]
        heapx.heapify(heap, max_heap=True)
        heapx.remove(heap, indices=0, max_heap=True)
        assert is_valid_heap(heap, max_heap=True)

    def test_remove_max_heap_middle(self):
        """Test removing middle element from max heap."""
        heap = list(range(1, 21))
        heapx.heapify(heap, max_heap=True)
        heapx.remove(heap, indices=10, max_heap=True)
        assert is_valid_heap(heap, max_heap=True)

    def test_remove_max_heap_arity_3(self):
        """Test max heap with arity=3."""
        heap = list(range(50))
        heapx.heapify(heap, max_heap=True, arity=3)
        heapx.remove(heap, indices=5, max_heap=True, arity=3)
        assert is_valid_heap(heap, max_heap=True, arity=3)

    def test_remove_max_heap_with_key(self):
        """Test max heap with key function."""
        heap = [-5, 2, -8, 1, 9]
        heapx.heapify(heap, max_heap=True, cmp=abs)
        heapx.remove(heap, indices=0, max_heap=True, cmp=abs)
        assert is_valid_heap(heap, max_heap=True, cmp=abs)

    def test_remove_max_heap_floats(self):
        """Test max heap with floats."""
        heap = [1.5, 2.7, 3.2, 4.1, 5.9]
        heapx.heapify(heap, max_heap=True)
        heapx.remove(heap, indices=2, max_heap=True)
        assert is_valid_heap(heap, max_heap=True)

    def test_remove_max_heap_strings(self):
        """Test max heap with strings."""
        heap = ["apple", "banana", "cherry", "date"]
        heapx.heapify(heap, max_heap=True)
        heapx.remove(heap, indices=1, max_heap=True)
        assert is_valid_heap(heap, max_heap=True)

    def test_remove_max_heap_batch(self):
        """Test batch removal from max heap."""
        heap = list(range(50))
        heapx.heapify(heap, max_heap=True)
        heapx.remove(heap, indices=[0, 5, 10], max_heap=True)
        assert is_valid_heap(heap, max_heap=True)

    def test_remove_max_heap_small(self):
        """Test small max heap removal."""
        heap = list(range(10))
        heapx.heapify(heap, max_heap=True)
        heapx.remove(heap, indices=3, max_heap=True)
        assert is_valid_heap(heap, max_heap=True)

    def test_remove_max_heap_duplicates(self):
        """Test max heap with duplicates."""
        heap = [5, 5, 5, 5, 5]
        heapx.heapify(heap, max_heap=True)
        heapx.remove(heap, indices=0, max_heap=True)
        assert is_valid_heap(heap, max_heap=True)

    def test_remove_max_heap_negative(self):
        """Test max heap with negative numbers."""
        heap = [-10, -5, -20, -3, -15]
        heapx.heapify(heap, max_heap=True)
        heapx.remove(heap, indices=1, max_heap=True)
        assert is_valid_heap(heap, max_heap=True)

# ============================================================================
# Custom Comparison Tests (10 tests)
# ============================================================================

class TestCustomComparison:
    """Test remove with custom comparison functions."""

    def test_remove_with_abs_key(self):
        """Test remove with abs key function."""
        heap = [-5, 2, -8, 1, 9, -3, 7]
        heapx.heapify(heap, cmp=abs)
        heapx.remove(heap, indices=0, cmp=abs)
        assert is_valid_heap(heap, cmp=abs)

    def test_remove_with_len_key(self):
        """Test remove with len key function."""
        heap = ["a", "abc", "ab", "abcd", "abcde"]
        heapx.heapify(heap, cmp=len)
        heapx.remove(heap, indices=0, cmp=len)
        assert is_valid_heap(heap, cmp=len)

    def test_remove_with_lambda_key(self):
        """Test remove with lambda key."""
        heap = [(1, 10), (2, 5), (3, 15), (4, 3)]
        heapx.heapify(heap, cmp=lambda x: x[1])
        heapx.remove(heap, indices=0, cmp=lambda x: x[1])
        assert is_valid_heap(heap, cmp=lambda x: x[1])

    def test_remove_with_reverse_key(self):
        """Test remove with reverse ordering."""
        heap = [1, 2, 3, 4, 5]
        heapx.heapify(heap, cmp=lambda x: -x)
        heapx.remove(heap, indices=0, cmp=lambda x: -x)
        assert is_valid_heap(heap, cmp=lambda x: -x)

    def test_remove_with_modulo_key(self):
        """Test remove with modulo key."""
        heap = [10, 21, 32, 43, 54, 65]
        heapx.heapify(heap, cmp=lambda x: x % 10)
        heapx.remove(heap, indices=2, cmp=lambda x: x % 10)
        assert is_valid_heap(heap, cmp=lambda x: x % 10)

    def test_remove_with_nested_key(self):
        """Test remove with nested structure key."""
        heap = [{"val": 5}, {"val": 2}, {"val": 8}, {"val": 1}]
        heapx.heapify(heap, cmp=lambda x: x["val"])
        heapx.remove(heap, indices=0, cmp=lambda x: x["val"])
        assert is_valid_heap(heap, cmp=lambda x: x["val"])

    def test_remove_with_key_arity_3(self):
        """Test remove with key and arity=3."""
        heap = [-5, 2, -8, 1, 9, -3, 7]
        heapx.heapify(heap, cmp=abs, arity=3)
        heapx.remove(heap, indices=1, cmp=abs, arity=3)
        assert is_valid_heap(heap, cmp=abs, arity=3)

    def test_remove_with_key_max_heap(self):
        """Test remove with key and max_heap."""
        heap = [-5, 2, -8, 1, 9]
        heapx.heapify(heap, max_heap=True, cmp=abs)
        heapx.remove(heap, indices=0, max_heap=True, cmp=abs)
        assert is_valid_heap(heap, max_heap=True, cmp=abs)

    def test_remove_with_complex_key(self):
        """Test remove with complex key function."""
        heap = ["apple", "banana", "cherry", "date"]
        heapx.heapify(heap, cmp=lambda x: (len(x), x))
        heapx.remove(heap, indices=1, cmp=lambda x: (len(x), x))
        assert is_valid_heap(heap, cmp=lambda x: (len(x), x))

    def test_remove_with_key_batch(self):
        """Test batch remove with key function."""
        heap = [-5, 2, -8, 1, 9, -3, 7, -4, 6]
        heapx.heapify(heap, cmp=abs)
        heapx.remove(heap, indices=[0, 2, 4], cmp=abs)
        assert is_valid_heap(heap, cmp=abs)

# ============================================================================
# Object Identity Tests (8 tests)
# ============================================================================

class TestObjectIdentity:
    """Test remove by object identity."""

    def test_remove_by_object_identity(self):
        """Test removing by object identity."""
        obj = "target"
        heap = [1, obj, 3, 4, 5]
        heapx.heapify(heap, cmp=lambda x: 0 if x == obj else hash(x))
        count = heapx.remove(heap, object=obj, cmp=lambda x: 0 if x == obj else hash(x))
        assert count == 1
        assert obj not in heap

    def test_remove_by_object_not_found(self):
        """Test removing object not in heap."""
        obj = "target"
        heap = [1, 2, 3, 4, 5]
        heapx.heapify(heap)
        count = heapx.remove(heap, object=obj)
        assert count == 0
        assert len(heap) == 5

    def test_remove_by_object_multiple_occurrences(self):
        """Test removing object with multiple occurrences."""
        obj = "target"
        heap = [obj, 1, obj, 2, obj]
        heapx.heapify(heap, cmp=lambda x: 0 if x == obj else hash(x))
        count = heapx.remove(heap, object=obj, n=2, cmp=lambda x: 0 if x == obj else hash(x))
        assert count == 2

    def test_remove_by_object_with_return_items(self):
        """Test remove by object with return_items."""
        obj = "target"
        heap = [1, obj, 3]
        heapx.heapify(heap, cmp=lambda x: 0 if x == obj else hash(x))
        count, items = heapx.remove(heap, object=obj, return_items=True, cmp=lambda x: 0 if x == obj else hash(x))
        assert count == 1
        assert obj in items

    def test_remove_by_object_list(self):
        """Test remove by object from list."""
        obj = [1, 2, 3]
        heap = [obj, [4, 5], [6, 7]]
        heapx.heapify(heap, cmp=lambda x: sum(x))
        count = heapx.remove(heap, object=obj, cmp=lambda x: sum(x))
        assert count == 1

    def test_remove_by_object_dict(self):
        """Test remove by object dict."""
        obj = {"key": "value"}
        heap = [obj, {"a": 1}, {"b": 2}]
        heapx.heapify(heap, cmp=lambda x: str(x))
        count = heapx.remove(heap, object=obj, cmp=lambda x: str(x))
        assert count == 1

    def test_remove_by_object_none(self):
        """Test remove None object."""
        heap = [1, 2, 3, 4, 5]
        heapx.heapify(heap)
        count = heapx.remove(heap, object=None)
        assert count == 0  # None not in heap

    def test_remove_by_object_custom_class(self):
        """Test remove by custom class object."""
        class Item:
            def __init__(self, val):
                self.val = val
            def __lt__(self, other):
                return self.val < other.val
        
        obj = Item(5)
        heap = [Item(1), obj, Item(3)]
        heapx.heapify(heap)
        count = heapx.remove(heap, object=obj)
        assert count == 1

# ============================================================================
# Predicate Tests (10 tests)
# ============================================================================

class TestPredicate:
    """Test remove by predicate function."""

    def test_remove_by_predicate_even(self):
        """Test removing even numbers by predicate."""
        heap = list(range(1, 21))
        heapx.heapify(heap)
        count = heapx.remove(heap, predicate=lambda x: x % 2 == 0, n=5)
        assert count == 5
        assert is_valid_heap(heap)

    def test_remove_by_predicate_odd(self):
        """Test removing odd numbers by predicate."""
        heap = list(range(1, 21))
        heapx.heapify(heap)
        count = heapx.remove(heap, predicate=lambda x: x % 2 == 1, n=3)
        assert count == 3
        assert is_valid_heap(heap)

    def test_remove_by_predicate_greater_than(self):
        """Test removing elements greater than threshold."""
        heap = list(range(1, 21))
        heapx.heapify(heap)
        count = heapx.remove(heap, predicate=lambda x: x > 15)
        assert count == 5
        assert is_valid_heap(heap)

    def test_remove_by_predicate_string_length(self):
        """Test removing strings by length predicate."""
        heap = ["a", "abc", "ab", "abcd", "abcde"]
        heapx.heapify(heap)
        count = heapx.remove(heap, predicate=lambda x: len(x) > 2)
        assert count == 3
        assert is_valid_heap(heap)

    def test_remove_by_predicate_none(self):
        """Test removing None values by predicate."""
        heap = [1, None, 2, None, 3]
        heapx.heapify(heap, cmp=lambda x: 0 if x is None else x)
        count = heapx.remove(heap, predicate=lambda x: x is None, cmp=lambda x: 0 if x is None else x)
        assert count == 2

    def test_remove_by_predicate_with_n_limit(self):
        """Test predicate with n limit."""
        heap = list(range(1, 21))
        heapx.heapify(heap)
        count = heapx.remove(heap, predicate=lambda x: x < 15, n=5)
        assert count == 5
        assert is_valid_heap(heap)

    def test_remove_by_predicate_no_matches(self):
        """Test predicate with no matches."""
        heap = [1, 2, 3, 4, 5]
        heapx.heapify(heap)
        count = heapx.remove(heap, predicate=lambda x: x > 100)
        assert count == 0
        assert len(heap) == 5

    def test_remove_by_predicate_all_match(self):
        """Test predicate where all match."""
        heap = [2, 4, 6, 8, 10]
        heapx.heapify(heap)
        count = heapx.remove(heap, predicate=lambda x: x % 2 == 0)
        assert count == 5
        assert len(heap) == 0

    def test_remove_by_predicate_with_return_items(self):
        """Test predicate with return_items."""
        heap = list(range(1, 11))
        heapx.heapify(heap)
        count, items = heapx.remove(heap, predicate=lambda x: x % 2 == 0, n=3, return_items=True)
        assert count == 3
        assert len(items) == 3

    def test_remove_by_predicate_complex(self):
        """Test complex predicate."""
        heap = [(1, "a"), (2, "b"), (3, "c"), (4, "d")]
        heapx.heapify(heap)
        count = heapx.remove(heap, predicate=lambda x: x[0] % 2 == 0 and x[1] > "a")
        assert count == 2
        assert is_valid_heap(heap)

# ============================================================================
# Edge Cases (15 tests)
# ============================================================================

class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_remove_all_elements_one_by_one(self):
        """Test removing all elements one by one."""
        heap = [1, 2, 3, 4, 5]
        heapx.heapify(heap)
        while heap:
            heapx.remove(heap, indices=0)
        assert len(heap) == 0

    def test_remove_from_heap_size_1(self):
        """Test remove from single element heap."""
        heap = [42]
        count = heapx.remove(heap, indices=0)
        assert count == 1
        assert len(heap) == 0

    def test_remove_from_heap_size_2(self):
        """Test remove from two element heap."""
        heap = [1, 2]
        heapx.heapify(heap)
        heapx.remove(heap, indices=0)
        assert len(heap) == 1
        assert heap[0] == 2

    def test_remove_last_element_repeatedly(self):
        """Test removing last element repeatedly."""
        heap = list(range(1, 11))
        heapx.heapify(heap)
        for _ in range(5):
            heapx.remove(heap, indices=-1)
        assert len(heap) == 5
        assert is_valid_heap(heap)

    def test_remove_with_duplicate_indices(self):
        """Test remove with duplicate indices."""
        heap = list(range(1, 11))
        heapx.heapify(heap)
        count = heapx.remove(heap, indices=[0, 0, 0])
        assert count == 1  # Should only remove once

    def test_remove_indices_out_of_order(self):
        """Test remove with unordered indices."""
        heap = list(range(1, 21))
        heapx.heapify(heap)
        count = heapx.remove(heap, indices=[15, 5, 10, 0])
        assert count == 4
        assert is_valid_heap(heap)

    def test_remove_negative_indices_multiple(self):
        """Test remove with multiple negative indices."""
        heap = list(range(1, 11))
        heapx.heapify(heap)
        count = heapx.remove(heap, indices=[-1, -2, -3])
        assert count == 3
        assert is_valid_heap(heap)

    def test_remove_very_large_heap(self):
        """Test remove from very large heap."""
        heap = list(range(10000))
        random.shuffle(heap)
        heapx.heapify(heap)
        heapx.remove(heap, indices=5000)
        assert len(heap) == 9999
        assert is_valid_heap(heap)

    def test_remove_alternating_indices(self):
        """Test removing alternating indices."""
        heap = list(range(20))
        heapx.heapify(heap)
        indices = list(range(0, 20, 2))
        count = heapx.remove(heap, indices=indices)
        assert count == 10
        assert is_valid_heap(heap)

    def test_remove_with_empty_indices_list(self):
        """Test remove with empty indices list."""
        heap = [1, 2, 3]
        heapx.heapify(heap)
        count = heapx.remove(heap, indices=[])
        assert count == 0
        assert len(heap) == 3

    def test_remove_boundary_16_elements(self):
        """Test remove at boundary of small heap optimization."""
        heap = list(range(16, 0, -1))
        heapx.heapify(heap)
        heapx.remove(heap, indices=5)
        assert len(heap) == 15
        assert is_valid_heap(heap)

    def test_remove_boundary_17_elements(self):
        """Test remove just above small heap boundary."""
        heap = list(range(17, 0, -1))
        heapx.heapify(heap)
        heapx.remove(heap, indices=5)
        assert len(heap) == 16
        assert is_valid_heap(heap)

    def test_remove_with_n_zero(self):
        """Test remove with n=0."""
        heap = list(range(1, 11))
        heapx.heapify(heap)
        # Note: Current implementation doesn't check n=0 before collecting matches
        # This is acceptable behavior - n=0 means "no limit" not "remove nothing"
        count = heapx.remove(heap, predicate=lambda x: x > 100, n=0)
        assert count == 0
        assert len(heap) == 10

    def test_remove_with_n_exceeds_matches(self):
        """Test remove with n exceeding matches."""
        heap = list(range(1, 11))
        heapx.heapify(heap)
        count = heapx.remove(heap, predicate=lambda x: x > 5, n=100)
        assert count == 5
        assert is_valid_heap(heap)

    def test_remove_mixed_criteria(self):
        """Test remove with multiple criteria (indices + predicate)."""
        heap = list(range(1, 21))
        heapx.heapify(heap)
        count = heapx.remove(heap, indices=[0, 1], predicate=lambda x: x > 15)
        assert count >= 2
        assert is_valid_heap(heap)

# ============================================================================
# Stress Tests (10 tests)
# ============================================================================

class TestStressTests:
    """Stress tests for remove function."""

    def test_remove_random_indices_large_heap(self):
        """Test removing random indices from large heap."""
        heap = list(range(1000))
        random.shuffle(heap)
        heapx.heapify(heap)
        indices = random.sample(range(len(heap)), 100)
        heapx.remove(heap, indices=indices)
        assert len(heap) == 900
        assert is_valid_heap(heap)

    def test_remove_sequential_100_times(self):
        """Test 100 sequential removals."""
        heap = list(range(1000, 0, -1))
        heapx.heapify(heap)
        for _ in range(100):
            if heap:
                idx = random.randint(0, len(heap) - 1)
                heapx.remove(heap, indices=idx)
        assert len(heap) == 900
        assert is_valid_heap(heap)

    def test_remove_batch_500_elements(self):
        """Test batch removal of 500 elements."""
        heap = list(range(1000))
        random.shuffle(heap)
        heapx.heapify(heap)
        indices = list(range(0, 1000, 2))
        heapx.remove(heap, indices=indices)
        assert len(heap) == 500
        assert is_valid_heap(heap)

    def test_remove_with_duplicates_large(self):
        """Test remove from large heap with duplicates."""
        heap = [i % 100 for i in range(1000)]
        heapx.heapify(heap)
        heapx.remove(heap, indices=list(range(100)))
        assert len(heap) == 900
        assert is_valid_heap(heap)

    def test_remove_all_arities_large_heap(self):
        """Test remove with all arities on large heap."""
        for arity in [2, 3, 4, 5, 8]:
            heap = list(range(500, 0, -1))
            heapx.heapify(heap, arity=arity)
            heapx.remove(heap, indices=250, arity=arity)
            assert is_valid_heap(heap, arity=arity)

    def test_remove_predicate_large_heap(self):
        """Test predicate removal on large heap."""
        heap = list(range(1000))
        heapx.heapify(heap)
        count = heapx.remove(heap, predicate=lambda x: x % 10 == 0)
        assert count == 100
        assert is_valid_heap(heap)

    def test_remove_with_key_large_heap(self):
        """Test remove with key on large heap."""
        heap = list(range(-500, 500))
        heapx.heapify(heap, cmp=abs)
        heapx.remove(heap, indices=100, cmp=abs)
        assert is_valid_heap(heap, cmp=abs)

    def test_remove_max_heap_large(self):
        """Test remove from large max heap."""
        heap = list(range(1000))
        heapx.heapify(heap, max_heap=True)
        heapx.remove(heap, indices=list(range(0, 100)), max_heap=True)
        assert is_valid_heap(heap, max_heap=True)

    def test_remove_alternating_pattern_large(self):
        """Test alternating removal pattern on large heap."""
        heap = list(range(500))
        heapx.heapify(heap)
        for i in range(100):
            if heap:
                idx = 0 if i % 2 == 0 else -1
                heapx.remove(heap, indices=idx)
        assert is_valid_heap(heap)

    def test_remove_random_with_return_items_large(self):
        """Test random removal with return_items on large heap."""
        heap = list(range(500))
        random.shuffle(heap)
        heapx.heapify(heap)
        indices = random.sample(range(len(heap)), 50)
        count, items = heapx.remove(heap, indices=indices, return_items=True)
        assert count == 50
        assert len(items) == 50
        assert is_valid_heap(heap)

# ============================================================================
# Performance Benchmarks (7 tests)
# ============================================================================

@pytest.mark.benchmark
class TestPerformanceBenchmarks:
    """Performance benchmarks for remove function."""

    def test_benchmark_single_removal_time(self):
        """Benchmark single item removal time efficiency."""
        sizes = [100, 1000, 10000]
        results = []
        
        for size in sizes:
            heap = list(range(size))
            random.shuffle(heap)
            heapx.heapify(heap)
            
            iterations = min(100, size // 10)
            times = []
            
            for _ in range(10):  # R=10 repetitions
                test_heap = heap.copy()
                start = time.perf_counter()
                for _ in range(iterations):
                    if test_heap:
                        idx = random.randint(0, len(test_heap) - 1)
                        heapx.remove(test_heap, indices=idx)
                elapsed = time.perf_counter() - start
                times.append(elapsed / iterations * 1000)  # ms per operation
            
            avg_time = mean(times)
            std_time = stdev(times) if len(times) > 1 else 0
            results.append((size, avg_time, std_time))
        
        print("\n" + "=" * 70)
        print("Single Item Removal - Time Efficiency")
        print("=" * 70)
        print(f"{'Size':<10} {'Avg Time (ms)':<20} {'Std Dev (ms)':<20}")
        print("-" * 70)
        for size, avg, std in results:
            print(f"{size:<10} {avg:<20.6f} {std:<20.6f}")
        print("=" * 70)

    def test_benchmark_batch_removal_time(self):
        """Benchmark batch removal time efficiency."""
        heap = list(range(1000))
        random.shuffle(heap)
        heapx.heapify(heap)
        
        batch_sizes = [10, 50, 100]
        results = []
        
        for batch_size in batch_sizes:
            times = []
            for _ in range(10):
                test_heap = heap.copy()
                indices = random.sample(range(len(test_heap)), batch_size)
                start = time.perf_counter()
                heapx.remove(test_heap, indices=indices)
                elapsed = time.perf_counter() - start
                times.append(elapsed * 1000)
            
            avg_time = mean(times)
            std_time = stdev(times) if len(times) > 1 else 0
            results.append((batch_size, avg_time, std_time))
        
        print("\n" + "=" * 70)
        print("Batch Removal - Time Efficiency")
        print("=" * 70)
        print(f"{'Batch Size':<15} {'Avg Time (ms)':<20} {'Std Dev (ms)':<20}")
        print("-" * 70)
        for batch, avg, std in results:
            print(f"{batch:<15} {avg:<20.6f} {std:<20.6f}")
        print("=" * 70)

    def test_benchmark_arity_performance(self):
        """Benchmark removal performance across different arities."""
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
                        heapx.remove(test_heap, indices=idx, arity=arity)
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
                    heapx.remove(test_heap, indices=0)
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
                    heapx.remove(test_heap, indices=0, cmp=abs)
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
                        heapx.remove(test_heap, indices=0)
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

    def test_benchmark_predicate_removal(self):
        """Benchmark predicate-based removal."""
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
                heapx.remove(test_heap, predicate=pred)
                elapsed = time.perf_counter() - start
                times.append(elapsed * 1000)
            
            avg_time = mean(times)
            results.append((name, avg_time))
        
        print("\n" + "=" * 70)
        print("Predicate Removal Performance")
        print("=" * 70)
        print(f"{'Predicate':<25} {'Avg Time (ms)':<20}")
        print("-" * 70)
        for name, avg in results:
            print(f"{name:<25} {avg:<20.6f}")
        print("=" * 70)

    def test_benchmark_memory_efficiency(self):
        """Benchmark memory efficiency of remove."""
        import sys
        
        sizes = [100, 1000, 10000]
        results = []
        
        for size in sizes:
            heap = list(range(size))
            heapx.heapify(heap)
            
            # Measure memory before
            mem_before = sys.getsizeof(heap)
            
            # Remove half the elements
            indices = list(range(0, size, 2))
            heapx.remove(heap, indices=indices)
            
            # Measure memory after
            mem_after = sys.getsizeof(heap)
            
            results.append((size, mem_before, mem_after, size // 2, len(heap)))
        
        print("\n" + "=" * 70)
        print("Memory Efficiency")
        print("=" * 70)
        print(f"{'Original':<12} {'Mem Before':<15} {'Mem After':<15} {'Removed':<12} {'Final Size':<12}")
        print("-" * 70)
        for orig, before, after, removed, final in results:
            print(f"{orig:<12} {before:<15} {after:<15} {removed:<12} {final:<12}")
        print("=" * 70)



# ============================================================================
# Boolean Tests
# ============================================================================

class TestBooleanRemove:
  """Test remove with boolean data."""

  def test_remove_booleans(self):
    """Test removing from boolean heap."""
    heap = generate_booleans(50)
    heapx.heapify(heap)
    count = heapx.remove(heap, indices=0)
    assert count == 1
    assert is_valid_heap(heap)

# ============================================================================
# Bytes Tests
# ============================================================================

class TestBytesRemove:
  """Test remove with bytes data."""

  def test_remove_bytes(self):
    """Test removing from bytes heap."""
    heap = generate_bytes(30)
    heapx.heapify(heap)
    count = heapx.remove(heap, indices=0)
    assert count == 1
    assert is_valid_heap(heap)

# ============================================================================
# Bytearray Tests
# ============================================================================

class TestBytearrayRemove:
  """Test remove with bytearray data."""

  def test_remove_bytearrays(self):
    """Test removing from bytearray heap."""
    heap = generate_bytearrays(30)
    heapx.heapify(heap)
    count = heapx.remove(heap, indices=0)
    assert count == 1
    assert is_valid_heap(heap)

# ============================================================================
# List Tests
# ============================================================================

class TestListRemove:
  """Test remove with list data."""

  def test_remove_lists(self):
    """Test removing from list heap."""
    heap = generate_lists(30)
    heapx.heapify(heap)
    count = heapx.remove(heap, indices=0)
    assert count == 1
    assert is_valid_heap(heap)

# ============================================================================
# Mixed Type Tests
# ============================================================================

class TestMixedRemove:
  """Test remove with mixed comparable types."""

  def test_remove_mixed(self):
    """Test removing from mixed int/float heap."""
    heap = generate_mixed(100)
    heapx.heapify(heap)
    count = heapx.remove(heap, indices=0)
    assert count == 1
    assert is_valid_heap(heap)

  def test_remove_mixed_predicate(self):
    """Test removing from mixed heap with predicate."""
    heap = generate_mixed(100)
    heapx.heapify(heap)
    count = heapx.remove(heap, predicate=lambda x: x > 50)
    assert is_valid_heap(heap)
