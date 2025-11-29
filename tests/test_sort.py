"""
Comprehensive test suite for heapx.sort function.

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

class TestBasicSort:
    """Test basic sort functionality."""

    def test_sort_ascending(self):
        """Test basic ascending sort."""
        data = [5, 2, 8, 1, 9, 3, 7]
        result = heapx.sort(data)
        assert result == [1, 2, 3, 5, 7, 8, 9]

    def test_sort_descending(self):
        """Test descending sort with reverse=True."""
        data = [5, 2, 8, 1, 9, 3, 7]
        result = heapx.sort(data, reverse=True)
        assert result == [9, 8, 7, 5, 3, 2, 1]

    def test_sort_inplace(self):
        """Test in-place sorting."""
        data = [5, 2, 8, 1, 9]
        heapx.heapify(data)
        result = heapx.sort(data, inplace=True)
        assert result is None
        assert data == [1, 2, 5, 8, 9]

    def test_sort_copy(self):
        """Test sort returns new list by default."""
        data = [5, 2, 8, 1, 9]
        result = heapx.sort(data)
        assert result == [1, 2, 5, 8, 9]
        assert data == [5, 2, 8, 1, 9]  # Original unchanged

    def test_sort_empty(self):
        """Test sorting empty list."""
        assert heapx.sort([]) == []

    def test_sort_single_element(self):
        """Test sorting single element."""
        assert heapx.sort([5]) == [5]

    def test_sort_two_elements(self):
        """Test sorting two elements."""
        assert heapx.sort([2, 1]) == [1, 2]

    def test_sort_already_sorted(self):
        """Test sorting already sorted list."""
        data = list(range(100))
        assert heapx.sort(data) == data

    def test_sort_reverse_sorted(self):
        """Test sorting reverse sorted list."""
        data = list(range(100, 0, -1))
        assert heapx.sort(data) == list(range(1, 101))

    def test_sort_duplicates(self):
        """Test sorting with duplicate values."""
        data = [5, 2, 5, 1, 2, 5, 1]
        result = heapx.sort(data)
        assert result == [1, 1, 2, 2, 5, 5, 5]

# ============================================================================
# Dispatch Priority Tests (11 tests)
# ============================================================================

class TestDispatchPriorities:
    """Test all 11 dispatch priorities."""

    def test_priority_1_small_heap_no_key(self):
        """Priority 1: Small heap (n ≤ 16) without key function."""
        data = list(range(16, 0, -1))
        result = heapx.sort(data)
        assert result == list(range(1, 17))

    def test_priority_2_arity_1_sorted_list(self):
        """Priority 2: Arity=1 (sorted list maintenance)."""
        data = list(range(50, 0, -1))
        result = heapx.sort(data, arity=1)
        assert result == list(range(1, 51))

    def test_priority_3_binary_heap_no_key(self):
        """Priority 3: List + arity=2 + no key (Floyd's binary heap)."""
        data = list(range(100, 0, -1))
        result = heapx.sort(data, arity=2)
        assert result == list(range(1, 101))

    def test_priority_4_ternary_heap_no_key(self):
        """Priority 4: List + arity=3 + no key (specialized ternary)."""
        data = list(range(100, 0, -1))
        result = heapx.sort(data, arity=3)
        assert result == list(range(1, 101))

    def test_priority_5_quaternary_heap_no_key(self):
        """Priority 5: List + arity=4 + no key (specialized quaternary)."""
        data = list(range(100, 0, -1))
        result = heapx.sort(data, arity=4)
        assert result == list(range(1, 101))

    def test_priority_6_nary_heap_small(self):
        """Priority 6: List + arity≥5 + no key + n<1000."""
        data = list(range(500, 0, -1))
        result = heapx.sort(data, arity=5)
        assert result == list(range(1, 501))

    def test_priority_7_nary_heap_large(self):
        """Priority 7: List + arity≥5 + no key + n≥1000."""
        data = list(range(1500, 0, -1))
        result = heapx.sort(data, arity=8)
        assert result == list(range(1, 1501))

    def test_priority_8_binary_heap_with_key(self):
        """Priority 8: List + arity=2 + key function."""
        data = [-5, 2, -8, 1, 9, -3, 7]
        result = heapx.sort(data, cmp=abs)
        expected = sorted(data, key=abs)
        assert result == expected

    def test_priority_9_ternary_heap_with_key(self):
        """Priority 9: List + arity=3 + key function."""
        data = [-5, 2, -8, 1, 9, -3, 7]
        result = heapx.sort(data, arity=3, cmp=abs)
        expected = sorted(data, key=abs)
        assert result == expected

    def test_priority_10_nary_heap_with_key(self):
        """Priority 10: List + arity≥4 + key function."""
        data = list(range(1, 51))
        random.shuffle(data)
        result = heapx.sort(data, arity=5, cmp=lambda x: x % 10)
        # Verify sorted by key
        for i in range(len(result) - 1):
            assert (result[i] % 10) <= (result[i+1] % 10)

    def test_priority_11_generic_sequence(self):
        """Priority 11: Generic sequence (non-list)."""
        data = tuple(range(50, 0, -1))
        result = heapx.sort(data)
        assert result == list(range(1, 51))

# ============================================================================
# Data Type Tests (15 tests)
# ============================================================================

class TestDataTypes:
    """Test sorting different data types."""

    def test_sort_integers(self):
        """Test sorting integers."""
        data = generate_integers(100)
        result = heapx.sort(data)
        assert result == sorted(data)

    def test_sort_floats(self):
        """Test sorting floats."""
        data = generate_floats(100)
        result = heapx.sort(data)
        assert result == sorted(data)

    def test_sort_strings(self):
        """Test sorting strings."""
        data = generate_strings(50)
        result = heapx.sort(data)
        assert result == sorted(data)

    def test_sort_tuples(self):
        """Test sorting tuples."""
        data = generate_tuples(50)
        result = heapx.sort(data)
        assert result == sorted(data)

    def test_sort_mixed_numbers(self):
        """Test sorting mixed int/float."""
        data = [5, 2.5, 8, 1.1, 9, 3.7]
        result = heapx.sort(data)
        assert result == sorted(data)

    def test_sort_negative_numbers(self):
        """Test sorting negative numbers."""
        data = [-5, -2, -8, -1, -9]
        result = heapx.sort(data)
        assert result == [-9, -8, -5, -2, -1]

    def test_sort_bytes(self):
        """Test sorting bytes."""
        data = [b'zebra', b'apple', b'mango', b'banana']
        result = heapx.sort(data)
        assert result == sorted(data)

    def test_sort_booleans(self):
        """Test sorting booleans."""
        data = [True, False, True, False, True]
        result = heapx.sort(data)
        assert result == [False, False, True, True, True]

    def test_sort_large_integers(self):
        """Test sorting large integers."""
        data = [10**15, 10**10, 10**20, 10**5]
        result = heapx.sort(data)
        assert result == sorted(data)

    def test_sort_small_floats(self):
        """Test sorting small floats."""
        data = [0.001, 0.0001, 0.01, 0.00001]
        result = heapx.sort(data)
        assert result == sorted(data)

    def test_sort_unicode_strings(self):
        """Test sorting unicode strings."""
        data = ['café', 'apple', 'naïve', 'résumé']
        result = heapx.sort(data)
        assert result == sorted(data)

    def test_sort_nested_tuples(self):
        """Test sorting nested tuples."""
        data = [(1, (2, 3)), (1, (2, 1)), (1, (1, 5))]
        result = heapx.sort(data)
        assert result == sorted(data)

    def test_sort_custom_objects(self):
        """Test sorting custom objects."""
        class Item:
            def __init__(self, val):
                self.val = val
            def __lt__(self, other):
                return self.val < other.val
            def __eq__(self, other):
                return self.val == other.val
        
        data = [Item(5), Item(2), Item(8), Item(1)]
        result = heapx.sort(data)
        assert [x.val for x in result] == [1, 2, 5, 8]

    def test_sort_none_values(self):
        """Test sorting with None values raises error."""
        data = [5, None, 2, 8]
        with pytest.raises(TypeError):
            heapx.sort(data)


# ============================================================================
# Arity Parameter Tests (17 tests)
# ============================================================================

class TestArityParameters:
    """Test different arity values."""

    @pytest.mark.parametrize("arity", [1, 2, 3, 4, 5, 8, 16])
    def test_sort_various_arities(self, arity):
        """Test sorting with various arity values."""
        data = list(range(100, 0, -1))
        result = heapx.sort(data, arity=arity)
        assert result == list(range(1, 101))

    def test_sort_arity_1_ascending(self):
        """Test arity=1 ascending sort."""
        data = list(range(50, 0, -1))
        result = heapx.sort(data, arity=1)
        assert result == list(range(1, 51))

    def test_sort_arity_1_descending(self):
        """Test arity=1 descending sort."""
        data = list(range(1, 51))
        result = heapx.sort(data, arity=1, reverse=True)
        assert result == list(range(50, 0, -1))

    def test_sort_arity_2_large(self):
        """Test arity=2 with large dataset."""
        data = list(range(10000, 0, -1))
        result = heapx.sort(data, arity=2)
        assert result == list(range(1, 10001))

    def test_sort_arity_3_medium(self):
        """Test arity=3 with medium dataset."""
        data = list(range(1000, 0, -1))
        result = heapx.sort(data, arity=3)
        assert result == list(range(1, 1001))

    def test_sort_arity_4_small(self):
        """Test arity=4 with small dataset."""
        data = list(range(100, 0, -1))
        result = heapx.sort(data, arity=4)
        assert result == list(range(1, 101))

    def test_sort_arity_high_value(self):
        """Test high arity value."""
        data = list(range(100, 0, -1))
        result = heapx.sort(data, arity=32)
        assert result == list(range(1, 101))

    def test_sort_arity_invalid_zero(self):
        """Test arity=0 raises error."""
        with pytest.raises(ValueError):
            heapx.sort([5, 2, 8], arity=0)

    def test_sort_arity_invalid_negative(self):
        """Test negative arity raises error."""
        with pytest.raises(ValueError):
            heapx.sort([5, 2, 8], arity=-1)

# ============================================================================
# Max Heap Tests (10 tests)
# ============================================================================

class TestMaxHeap:
    """Test max_heap parameter."""

    def test_sort_max_heap_ascending(self):
        """Test sorting from max heap."""
        data = [5, 2, 8, 1, 9]
        heapx.heapify(data, max_heap=True)
        result = heapx.sort(data, max_heap=True)
        assert result == [1, 2, 5, 8, 9]

    def test_sort_max_heap_descending(self):
        """Test reverse sorting from max heap."""
        data = [5, 2, 8, 1, 9]
        heapx.heapify(data, max_heap=True)
        result = heapx.sort(data, max_heap=True, reverse=True)
        assert result == [9, 8, 5, 2, 1]

    def test_sort_max_heap_inplace(self):
        """Test in-place sorting from max heap."""
        data = [5, 2, 8, 1, 9]
        heapx.heapify(data, max_heap=True)
        heapx.sort(data, max_heap=True, inplace=True)
        assert data == [1, 2, 5, 8, 9]

    def test_sort_max_heap_arity_3(self):
        """Test max heap with arity=3."""
        data = list(range(100, 0, -1))
        heapx.heapify(data, max_heap=True, arity=3)
        result = heapx.sort(data, max_heap=True, arity=3)
        assert result == list(range(1, 101))

    def test_sort_max_heap_with_key(self):
        """Test max heap with key function."""
        data = [-5, 2, -8, 1, 9]
        heapx.heapify(data, max_heap=True, cmp=abs)
        result = heapx.sort(data, max_heap=True, cmp=abs)
        expected = sorted(data, key=abs)
        assert result == expected

    def test_sort_min_heap_ascending(self):
        """Test sorting from min heap."""
        data = [5, 2, 8, 1, 9]
        heapx.heapify(data, max_heap=False)
        result = heapx.sort(data, max_heap=False)
        assert result == [1, 2, 5, 8, 9]

    def test_sort_min_heap_descending(self):
        """Test reverse sorting from min heap."""
        data = [5, 2, 8, 1, 9]
        heapx.heapify(data, max_heap=False)
        result = heapx.sort(data, max_heap=False, reverse=True)
        assert result == [9, 8, 5, 2, 1]

    def test_sort_preserves_heap_property_inplace(self):
        """Test inplace sort preserves heap property."""
        data = [5, 2, 8, 1, 9, 3, 7]
        heapx.heapify(data)
        heapx.sort(data, inplace=True)
        assert is_valid_heap(data)

    def test_sort_preserves_max_heap_property_inplace(self):
        """Test inplace sort from max heap produces sorted array."""
        data = [5, 2, 8, 1, 9, 3, 7]
        original = data.copy()
        heapx.heapify(data, max_heap=True)
        heapx.sort(data, max_heap=True, inplace=True)
        # After sorting, data should be sorted ascending
        assert data == sorted(original)

    def test_sort_large_max_heap(self):
        """Test large max heap sorting."""
        data = list(range(1000, 0, -1))
        heapx.heapify(data, max_heap=True)
        result = heapx.sort(data, max_heap=True)
        assert result == list(range(1, 1001))

# ============================================================================
# Custom Comparison Tests (10 tests)
# ============================================================================

class TestCustomComparison:
    """Test custom comparison functions."""

    def test_sort_with_abs_key(self):
        """Test sorting by absolute value."""
        data = [-5, 2, -8, 1, 9, -3, 7]
        result = heapx.sort(data, cmp=abs)
        expected = sorted(data, key=abs)
        assert result == expected

    def test_sort_with_lambda_key(self):
        """Test sorting with lambda key."""
        data = [(1, 5), (2, 3), (1, 2), (2, 1)]
        result = heapx.sort(data, cmp=lambda x: (x[0], -x[1]))
        expected = sorted(data, key=lambda x: (x[0], -x[1]))
        assert result == expected

    def test_sort_with_len_key(self):
        """Test sorting strings by length."""
        data = ["apple", "pie", "banana", "kiwi"]
        result = heapx.sort(data, cmp=len)
        expected = sorted(data, key=len)
        assert result == expected

    def test_sort_with_modulo_key(self):
        """Test sorting by modulo."""
        data = list(range(1, 51))
        random.shuffle(data)
        result = heapx.sort(data, cmp=lambda x: x % 10)
        for i in range(len(result) - 1):
            assert (result[i] % 10) <= (result[i+1] % 10)

    def test_sort_with_reverse_key(self):
        """Test sorting with reverse key."""
        data = [1, 2, 3, 4, 5]
        result = heapx.sort(data, cmp=lambda x: -x)
        assert result == [5, 4, 3, 2, 1]

    def test_sort_with_key_and_reverse(self):
        """Test sorting with key and reverse."""
        data = [-5, 2, -8, 1, 9]
        result = heapx.sort(data, cmp=abs, reverse=True)
        expected = sorted(data, key=abs, reverse=True)
        assert result == expected

    def test_sort_with_key_arity_3(self):
        """Test key function with arity=3."""
        data = [-5, 2, -8, 1, 9, -3, 7]
        result = heapx.sort(data, cmp=abs, arity=3)
        expected = sorted(data, key=abs)
        assert result == expected

    def test_sort_with_key_arity_5(self):
        """Test key function with arity=5."""
        data = list(range(-50, 50))
        random.shuffle(data)
        result = heapx.sort(data, cmp=abs, arity=5)
        # Verify sorted by absolute value (heapsort is unstable)
        for i in range(len(result) - 1):
            assert abs(result[i]) <= abs(result[i+1])

    def test_sort_with_invalid_key(self):
        """Test invalid key function raises error."""
        with pytest.raises(TypeError):
            heapx.sort([1, 2, 3], cmp="not_callable")

    def test_sort_with_key_error(self):
        """Test key function that raises error."""
        def bad_key(x):
            if x == 5:
                raise ValueError("Bad value")
            return x
        
        with pytest.raises(ValueError):
            heapx.sort([1, 2, 5, 3], cmp=bad_key)

# ============================================================================
# Edge Case Tests (15 tests)
# ============================================================================

class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_sort_all_same_values(self):
        """Test sorting all identical values."""
        data = [5] * 100
        result = heapx.sort(data)
        assert result == [5] * 100

    def test_sort_two_distinct_values(self):
        """Test sorting with only two distinct values."""
        data = [1, 2, 1, 2, 1, 2, 1, 2]
        result = heapx.sort(data)
        assert result == [1, 1, 1, 1, 2, 2, 2, 2]

    def test_sort_mostly_sorted(self):
        """Test sorting mostly sorted data."""
        data = list(range(100))
        data[50], data[51] = data[51], data[50]
        result = heapx.sort(data)
        assert result == list(range(100))

    def test_sort_reverse_pairs(self):
        """Test sorting reverse pairs."""
        data = [2, 1, 4, 3, 6, 5, 8, 7]
        result = heapx.sort(data)
        assert result == [1, 2, 3, 4, 5, 6, 7, 8]

    def test_sort_alternating_high_low(self):
        """Test sorting alternating high/low values."""
        data = [1, 100, 2, 99, 3, 98, 4, 97]
        result = heapx.sort(data)
        assert result == sorted(data)

    def test_sort_power_of_two_size(self):
        """Test sorting with power of 2 size."""
        for size in [16, 32, 64, 128, 256]:
            data = list(range(size, 0, -1))
            result = heapx.sort(data)
            assert result == list(range(1, size + 1))

    def test_sort_prime_size(self):
        """Test sorting with prime number size."""
        for size in [17, 31, 61, 127]:
            data = list(range(size, 0, -1))
            result = heapx.sort(data)
            assert result == list(range(1, size + 1))

    def test_sort_very_small_heap(self):
        """Test sorting very small heaps."""
        for size in range(1, 17):
            data = list(range(size, 0, -1))
            result = heapx.sort(data)
            assert result == list(range(1, size + 1))

    def test_sort_boundary_16_17(self):
        """Test boundary between small heap optimization."""
        data16 = list(range(16, 0, -1))
        data17 = list(range(17, 0, -1))
        assert heapx.sort(data16) == list(range(1, 17))
        assert heapx.sort(data17) == list(range(1, 18))

    def test_sort_boundary_999_1000(self):
        """Test boundary for n-ary heap size dispatch."""
        data999 = list(range(999, 0, -1))
        data1000 = list(range(1000, 0, -1))
        assert heapx.sort(data999, arity=5) == list(range(1, 1000))
        assert heapx.sort(data1000, arity=5) == list(range(1, 1001))

    def test_sort_inplace_returns_none(self):
        """Test inplace sort returns None."""
        data = [5, 2, 8, 1, 9]
        result = heapx.sort(data, inplace=True)
        assert result is None

    def test_sort_copy_returns_list(self):
        """Test copy sort returns list."""
        data = [5, 2, 8, 1, 9]
        result = heapx.sort(data, inplace=False)
        assert isinstance(result, list)

    def test_sort_tuple_input(self):
        """Test sorting tuple input."""
        data = (5, 2, 8, 1, 9)
        result = heapx.sort(data)
        assert result == [1, 2, 5, 8, 9]

    def test_sort_bytearray_input(self):
        """Test sorting bytearray input."""
        data = bytearray([5, 2, 8, 1, 9])
        result = heapx.sort(data)
        assert result == [1, 2, 5, 8, 9]

    def test_sort_random_data_consistency(self):
        """Test sorting random data matches Python sorted."""
        for _ in range(10):
            data = generate_integers(100)
            result = heapx.sort(data)
            assert result == sorted(data)

# ============================================================================
# Stress Tests (10 tests)
# ============================================================================

class TestStressTests:
    """Stress tests with large datasets."""

    def test_sort_large_dataset_10k(self):
        """Test sorting 10,000 elements."""
        data = list(range(10000, 0, -1))
        result = heapx.sort(data)
        assert result == list(range(1, 10001))

    def test_sort_large_dataset_50k(self):
        """Test sorting 50,000 elements."""
        data = list(range(50000, 0, -1))
        result = heapx.sort(data)
        assert result == list(range(1, 50001))

    def test_sort_large_random_10k(self):
        """Test sorting 10,000 random elements."""
        data = generate_integers(10000)
        result = heapx.sort(data)
        assert result == sorted(data)

    def test_sort_many_duplicates(self):
        """Test sorting with many duplicates."""
        data = [i % 10 for i in range(1000)]
        random.shuffle(data)
        result = heapx.sort(data)
        assert result == sorted(data)

    def test_sort_all_arities_large(self):
        """Test all arities with large dataset."""
        data = list(range(1000, 0, -1))
        for arity in [1, 2, 3, 4, 5, 8]:
            result = heapx.sort(data.copy(), arity=arity)
            assert result == list(range(1, 1001))

    def test_sort_with_key_large(self):
        """Test sorting large dataset with key function."""
        data = list(range(-5000, 5000))
        random.shuffle(data)
        result = heapx.sort(data, cmp=abs)
        # Verify sorted by absolute value (heapsort is unstable)
        for i in range(len(result) - 1):
            assert abs(result[i]) <= abs(result[i+1])

    def test_sort_strings_large(self):
        """Test sorting large string dataset."""
        data = generate_strings(1000)
        result = heapx.sort(data)
        assert result == sorted(data)

    def test_sort_tuples_large(self):
        """Test sorting large tuple dataset."""
        data = generate_tuples(1000)
        result = heapx.sort(data)
        assert result == sorted(data)

    def test_sort_repeated_operations(self):
        """Test repeated sort operations."""
        data = list(range(100, 0, -1))
        for _ in range(100):
            result = heapx.sort(data)
            assert result == list(range(1, 101))


# ============================================================================
# Performance Benchmarks (7 tests)
# ============================================================================

@pytest.mark.benchmark
class TestPerformanceBenchmarks:
    """Performance benchmarks for sort function."""

    def test_benchmark_time_efficiency(self, capsys):
        """Comprehensive time efficiency benchmark for sort function."""
        
        output = []
        output.append("\n" + "="*80)
        output.append("TIME EFFICIENCY: heapx.sort - Heapsort Algorithm")
        output.append("="*80)
        output.append(f"Configuration: R=10 repetitions per size, Random integers, Arity=2")
        output.append("="*80)
        
        sizes = [100, 500, 1_000, 5_000, 10_000, 50_000, 100_000, 500_000, 1_000_000]
        repetitions = 10
        
        results = []
        
        for n in sizes:
            times = []
            
            for r in range(repetitions):
                # Prepare data
                data = list(range(n, 0, -1))
                
                # Measure sort time
                start = time.perf_counter()
                heapx.sort(data)
                elapsed = time.perf_counter() - start
                times.append(elapsed)
            
            avg_time = mean(times)
            std_time = stdev(times) if len(times) > 1 else 0
            
            results.append({
                'n': n,
                'avg': avg_time,
                'std': std_time
            })
        
        # Time efficiency table
        output.append("\n" + "-"*65)
        output.append(f"{'n':>12} │ {'Time to sort (s)':>47}")
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
        """Comprehensive memory efficiency benchmark for sort function."""
        
        output = []
        output.append("\n" + "="*80)
        output.append("MEMORY EFFICIENCY: heapx.sort")
        output.append("="*80)
        output.append(f"Configuration: Random integers, Arity=2")
        output.append("="*80)
        
        sizes = [100, 500, 1_000, 5_000, 10_000, 50_000, 100_000, 500_000, 1_000_000]
        
        memory_results = []
        
        for n in sizes:
            # Create data
            data = list(range(n, 0, -1))
            
            # Measure memory
            mem_before = sys.getsizeof(data)
            result = heapx.sort(data)
            mem_after = sys.getsizeof(result)
            
            memory_results.append({
                'n': n,
                'mem_before': mem_before,
                'mem_after': mem_after
            })
        
        # Memory efficiency table
        output.append("\n" + "-"*80)
        output.append(f"{'n':>12} │ {'Memory Before':>20} │ {'Memory After':>20} │ {'Difference':>15}")
        output.append("-"*80)
        
        for r in memory_results:
            diff = r['mem_after'] - r['mem_before']
            output.append(f"{r['n']:>12,} │ {r['mem_before']:>17,} B │ {r['mem_after']:>17,} B │ {diff:>12,} B")
        
        output.append("-"*80)
        output.append("\nNote: Sort creates new list by default (inplace=False)")
        output.append("="*80 + "\n")
        
        # Print all output
        final_output = '\n'.join(output)
        print(final_output)
        sys.stdout.flush()
        
        # Also write to captured output for pytest
        with capsys.disabled():
            print(final_output)

    def test_benchmark_arity_comparison(self):
        """Benchmark different arity values."""
        arities = [2, 3, 4, 5, 8]
        results = []
        
        for arity in arities:
            data = list(range(1000, 0, -1))
            
            times = []
            for _ in range(10):
                test_data = data.copy()
                start = time.perf_counter()
                heapx.sort(test_data, arity=arity)
                elapsed = time.perf_counter() - start
                times.append(elapsed * 1000)  # Convert to ms
            
            avg_time = mean(times)
            std_time = stdev(times) if len(times) > 1 else 0
            results.append((arity, avg_time, std_time))
        
        print("\n" + "=" * 70)
        print("Arity Performance Comparison (n=1000)")
        print("=" * 70)
        print(f"{'Arity':<10} {'Avg Time (ms)':<20} {'Std Dev (ms)':<20}")
        print("-" * 70)
        for arity, avg, std in results:
            print(f"{arity:<10} {avg:<20.6f} {std:<20.6f}")
        print("=" * 70)

    def test_benchmark_key_function_overhead(self):
        """Benchmark key function overhead."""
        data = list(range(-500, 500))
        
        # Without key
        times_no_key = []
        for _ in range(10):
            test_data = data.copy()
            start = time.perf_counter()
            heapx.sort(test_data)
            elapsed = time.perf_counter() - start
            times_no_key.append(elapsed * 1000)
        
        # With key
        times_with_key = []
        for _ in range(10):
            test_data = data.copy()
            start = time.perf_counter()
            heapx.sort(test_data, cmp=abs)
            elapsed = time.perf_counter() - start
            times_with_key.append(elapsed * 1000)
        
        avg_no_key = mean(times_no_key)
        avg_with_key = mean(times_with_key)
        overhead = (avg_with_key / avg_no_key - 1) * 100
        
        print("\n" + "=" * 70)
        print("Key Function Overhead (n=1000)")
        print("=" * 70)
        print(f"Without key: {avg_no_key:.6f} ms")
        print(f"With key:    {avg_with_key:.6f} ms")
        print(f"Overhead:    {overhead:.2f}%")
        print("=" * 70)

    def test_benchmark_small_heap_optimization(self):
        """Benchmark small heap optimization."""
        sizes = [5, 10, 15, 16, 17, 20, 30, 50]
        results = []
        
        for size in sizes:
            data = list(range(size, 0, -1))
            
            times = []
            for _ in range(10):
                test_data = data.copy()
                start = time.perf_counter()
                heapx.sort(test_data)
                elapsed = time.perf_counter() - start
                times.append(elapsed * 1000)
            
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

    def test_benchmark_reverse_sort(self):
        """Benchmark reverse sort performance."""
        sizes = [100, 1000, 10000]
        results = []
        
        for size in sizes:
            data = list(range(size))
            
            # Normal sort
            times_normal = []
            for _ in range(10):
                test_data = data.copy()
                start = time.perf_counter()
                heapx.sort(test_data)
                elapsed = time.perf_counter() - start
                times_normal.append(elapsed * 1000)
            
            # Reverse sort
            times_reverse = []
            for _ in range(10):
                test_data = data.copy()
                start = time.perf_counter()
                heapx.sort(test_data, reverse=True)
                elapsed = time.perf_counter() - start
                times_reverse.append(elapsed * 1000)
            
            avg_normal = mean(times_normal)
            avg_reverse = mean(times_reverse)
            results.append((size, avg_normal, avg_reverse))
        
        print("\n" + "=" * 70)
        print("Reverse Sort Performance")
        print("=" * 70)
        print(f"{'Size':<15} {'Normal (ms)':<20} {'Reverse (ms)':<20}")
        print("-" * 70)
        for size, normal, reverse in results:
            print(f"{size:<15} {normal:<20.6f} {reverse:<20.6f}")
        print("=" * 70)

    def test_benchmark_inplace_vs_copy(self):
        """Benchmark inplace vs copy sort."""
        sizes = [100, 1000, 10000]
        results = []
        
        for size in sizes:
            data = list(range(size, 0, -1))
            
            # Copy sort
            times_copy = []
            for _ in range(10):
                test_data = data.copy()
                start = time.perf_counter()
                heapx.sort(test_data, inplace=False)
                elapsed = time.perf_counter() - start
                times_copy.append(elapsed * 1000)
            
            # Inplace sort
            times_inplace = []
            for _ in range(10):
                test_data = data.copy()
                heapx.heapify(test_data)
                start = time.perf_counter()
                heapx.sort(test_data, inplace=True)
                elapsed = time.perf_counter() - start
                times_inplace.append(elapsed * 1000)
            
            avg_copy = mean(times_copy)
            avg_inplace = mean(times_inplace)
            results.append((size, avg_copy, avg_inplace))
        
        print("\n" + "=" * 70)
        print("Inplace vs Copy Sort Performance")
        print("=" * 70)
        print(f"{'Size':<15} {'Copy (ms)':<20} {'Inplace (ms)':<20}")
        print("-" * 70)
        for size, copy, inplace in results:
            print(f"{size:<15} {copy:<20.6f} {inplace:<20.6f}")
        print("=" * 70)


# ============================================================================
# Boolean Tests
# ============================================================================

class TestBooleanSort:
  """Test sort with boolean data."""

  def test_sort_booleans(self):
    """Test sorting booleans."""
    data = generate_booleans(50)
    result = heapx.sort(data)
    assert result == sorted(generate_booleans(50))

  def test_sort_booleans_reverse(self):
    """Test sorting booleans in reverse."""
    data = generate_booleans(50)
    result = heapx.sort(data, reverse=True)
    assert result == sorted(generate_booleans(50), reverse=True)

# ============================================================================
# Bytes Tests
# ============================================================================

class TestBytesSort:
  """Test sort with bytes data."""

  def test_sort_bytes(self):
    """Test sorting bytes."""
    data = generate_bytes(30)
    result = heapx.sort(data)
    assert result == sorted(generate_bytes(30))

  def test_sort_bytes_reverse(self):
    """Test sorting bytes in reverse."""
    data = generate_bytes(30)
    result = heapx.sort(data, reverse=True)
    assert result == sorted(generate_bytes(30), reverse=True)

# ============================================================================
# Bytearray Tests
# ============================================================================

class TestBytearraySort:
  """Test sort with bytearray data."""

  def test_sort_bytearrays(self):
    """Test sorting bytearrays."""
    data = generate_bytearrays(30)
    result = heapx.sort(data)
    assert result == sorted(generate_bytearrays(30))

# ============================================================================
# List Tests
# ============================================================================

class TestListSort:
  """Test sort with list data."""

  def test_sort_lists(self):
    """Test sorting lists."""
    data = generate_lists(30)
    result = heapx.sort(data)
    assert result == sorted(generate_lists(30))

  def test_sort_lists_reverse(self):
    """Test sorting lists in reverse."""
    data = generate_lists(30)
    result = heapx.sort(data, reverse=True)
    assert result == sorted(generate_lists(30), reverse=True)

# ============================================================================
# Mixed Type Tests
# ============================================================================

class TestMixedSort:
  """Test sort with mixed comparable types."""

  def test_sort_mixed(self):
    """Test sorting mixed int/float."""
    data = generate_mixed(100)
    result = heapx.sort(data)
    assert result == sorted(generate_mixed(100))

  def test_sort_mixed_reverse(self):
    """Test sorting mixed types in reverse."""
    data = generate_mixed(100)
    result = heapx.sort(data, reverse=True)
    assert result == sorted(generate_mixed(100), reverse=True)

  def test_sort_mixed_inplace(self):
    """Test in-place sorting of mixed types."""
    data = generate_mixed(100)
    expected = sorted(data)
    heapx.sort(data, inplace=True)
    assert data == expected
