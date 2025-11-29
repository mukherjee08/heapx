"""
Comprehensive test suite for heapx.heapify function.

Tests cover all parameters, data types, edge cases, and performance benchmarks
against Python's standard heapq module.
"""

import heapx, heapq, pytest, random, string, time
from   typing     import List, Any, Tuple
from   statistics import mean, stdev
from   shutil     import get_terminal_size

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

def is_valid_heap(arr: List[Any], max_heap: bool = False, arity: int = 2) -> bool:
  """Verify heap property for n-ary heap."""
  n = len(arr)
  for i in range(n):
    for j in range(1, arity + 1):
      child = arity * i + j
      if child >= n:
        break
      if max_heap:
        if arr[i] < arr[child]:
          return False
      else:
        if arr[i] > arr[child]:
          return False
  return True

# ============================================================================
# Basic Functionality Tests
# ============================================================================

class TestBasicHeapify:
  """Test basic heapify functionality."""

  def test_empty_list(self):
    """Test heapify on empty list."""
    data = []; heapx.heapify(data)
    assert data == []

  def test_single_element(self):
    """Test heapify on single element."""
    data = [42]
    heapx.heapify(data)
    assert data == [42]

  def test_two_elements_min(self):
    """Test heapify on two elements (min-heap)."""
    data = [2, 1]
    heapx.heapify(data)
    assert data == [1, 2]

  def test_two_elements_max(self):
    """Test heapify on two elements (max-heap)."""
    data = [1, 2]
    heapx.heapify(data, max_heap=True)
    assert data == [2, 1]

  def test_already_heap_min(self):
    """Test heapify on already valid min-heap."""
    data = [1, 2, 3, 4, 5]
    heapx.heapify(data)
    assert is_valid_heap(data, max_heap=False)

  def test_already_heap_max(self):
    """Test heapify on already valid max-heap."""
    data = [5, 4, 3, 2, 1]
    heapx.heapify(data, max_heap=True)
    assert is_valid_heap(data, max_heap=True)

  def test_reverse_sorted_min(self):
    """Test heapify on reverse sorted list (min-heap)."""
    data = [10, 9, 8, 7, 6, 5, 4, 3, 2, 1]
    heapx.heapify(data)
    assert is_valid_heap(data, max_heap=False)
    assert data[0] == 1

  def test_reverse_sorted_max(self):
    """Test heapify on reverse sorted list (max-heap)."""
    data = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
    heapx.heapify(data, max_heap=True)
    assert is_valid_heap(data, max_heap=True)
    assert data[0] == 10

  def test_duplicates_min(self):
    """Test heapify with duplicate elements (min-heap)."""
    data = [5, 3, 5, 1, 3, 1, 5]
    heapx.heapify(data)
    assert is_valid_heap(data, max_heap=False)

  def test_duplicates_max(self):
    """Test heapify with duplicate elements (max-heap)."""
    data = [5, 3, 5, 1, 3, 1, 5]
    heapx.heapify(data, max_heap=True)
    assert is_valid_heap(data, max_heap=True)

# ============================================================================
# Integer Tests (Various Sizes)
# ============================================================================

class TestIntegerHeapify:
  """Test heapify with integer data."""

  @pytest.mark.parametrize("n", [100, 1000, 10000])
  def test_random_integers_min(self, n):
    """Test min-heap with random integers."""
    data = generate_integers(n)
    heapx.heapify(data)
    assert is_valid_heap(data, max_heap=False)
    assert data[0] == min(generate_integers(n))

  @pytest.mark.parametrize("n", [100, 1000, 10000])
  def test_random_integers_max(self, n):
    """Test max-heap with random integers."""
    data = generate_integers(n)
    heapx.heapify(data, max_heap=True)
    assert is_valid_heap(data, max_heap=True)
    assert data[0] == max(generate_integers(n))

  @pytest.mark.parametrize("n", [100, 1000, 10000])
  def test_sorted_integers_min(self, n):
    """Test min-heap with sorted integers."""
    data = list(range(n))
    heapx.heapify(data)
    assert is_valid_heap(data, max_heap=False)

  @pytest.mark.parametrize("n", [100, 1000, 10000])
  def test_sorted_integers_max(self, n):
    """Test max-heap with sorted integers."""
    data = list(range(n))
    heapx.heapify(data, max_heap=True)
    assert is_valid_heap(data, max_heap=True)

  def test_negative_integers(self):
    """Test heapify with negative integers."""
    data = [-5, -1, -10, -3, -7]
    heapx.heapify(data)
    assert is_valid_heap(data, max_heap=False)
    assert data[0] == -10

  def test_mixed_sign_integers(self):
    """Test heapify with mixed positive/negative integers."""
    data = [5, -3, 10, -7, 0, 2, -1]
    heapx.heapify(data)
    assert is_valid_heap(data, max_heap=False)
    assert data[0] == -7

# ============================================================================
# Float Tests
# ============================================================================

class TestFloatHeapify:
  """Test heapify with float data."""

  @pytest.mark.parametrize("n", [100, 1000, 10000])
  def test_random_floats_min(self, n):
    """Test min-heap with random floats."""
    data = generate_floats(n)
    heapx.heapify(data)
    assert is_valid_heap(data, max_heap=False)

  @pytest.mark.parametrize("n", [100, 1000, 10000])
  def test_random_floats_max(self, n):
    """Test max-heap with random floats."""
    data = generate_floats(n)
    heapx.heapify(data, max_heap=True)
    assert is_valid_heap(data, max_heap=True)

  def test_float_precision(self):
    """Test heapify with high precision floats."""
    data = [1.0000001, 1.0000002, 1.0, 1.0000003]
    heapx.heapify(data)
    assert is_valid_heap(data, max_heap=False)
    assert data[0] == 1.0

  def test_float_special_values(self):
    """Test heapify with special float values."""
    data = [1.0, 0.0, -1.0, float('inf'), float('-inf')]
    heapx.heapify(data)
    assert is_valid_heap(data, max_heap=False)
    assert data[0] == float('-inf')

# ============================================================================
# String Tests
# ============================================================================

class TestStringHeapify:
  """Test heapify with string data."""

  @pytest.mark.parametrize("n", [100, 1000, 10000])
  def test_random_strings_min(self, n):
    """Test min-heap with random strings."""
    data = generate_strings(n)
    heapx.heapify(data)
    assert is_valid_heap(data, max_heap=False)

  @pytest.mark.parametrize("n", [100, 1000, 10000])
  def test_random_strings_max(self, n):
    """Test max-heap with random strings."""
    data = generate_strings(n)
    heapx.heapify(data, max_heap=True)
    assert is_valid_heap(data, max_heap=True)

  def test_string_case_sensitivity(self):
    """Test heapify with case-sensitive strings."""
    data = ['Zebra', 'apple', 'Banana', 'cherry']
    heapx.heapify(data)
    assert is_valid_heap(data, max_heap=False)

  def test_empty_strings(self):
    """Test heapify with empty strings."""
    data = ['', 'a', '', 'b', '']
    heapx.heapify(data)
    assert is_valid_heap(data, max_heap=False)

# ============================================================================
# Tuple Tests
# ============================================================================

class TestTupleHeapify:
  """Test heapify with tuple data."""

  @pytest.mark.parametrize("n", [100, 1000, 10000])
  def test_random_tuples_min(self, n):
    """Test min-heap with random tuples."""
    data = generate_tuples(n)
    heapx.heapify(data)
    assert is_valid_heap(data, max_heap=False)

  @pytest.mark.parametrize("n", [100, 1000, 10000])
  def test_random_tuples_max(self, n):
    """Test max-heap with random tuples."""
    data = generate_tuples(n)
    heapx.heapify(data, max_heap=True)
    assert is_valid_heap(data, max_heap=True)

  def test_tuple_lexicographic(self):
    """Test heapify with lexicographic tuple comparison."""
    data = [(1, 'b'), (1, 'a'), (2, 'a'), (1, 'c')]
    heapx.heapify(data)
    assert is_valid_heap(data, max_heap=False)
    assert data[0] == (1, 'a')

# ============================================================================
# N-ary Heap Tests (Arity Parameter)
# ============================================================================

class TestArityParameter:
  """Test heapify with different arity values."""

  @pytest.mark.parametrize("arity", [1, 2, 3, 4, 5, 8, 16])
  @pytest.mark.parametrize("n", [100, 1000])
  def test_various_arity_min(self, arity, n):
    """Test min-heap with various arity values."""
    data = generate_integers(n)
    heapx.heapify(data, arity=arity)
    assert is_valid_heap(data, max_heap=False, arity=arity)

  @pytest.mark.parametrize("arity", [1, 2, 3, 4, 5, 8, 16])
  @pytest.mark.parametrize("n", [100, 1000])
  def test_various_arity_max(self, arity, n):
    """Test max-heap with various arity values."""
    data = generate_integers(n)
    heapx.heapify(data, max_heap=True, arity=arity)
    assert is_valid_heap(data, max_heap=True, arity=arity)

  def test_unary_heap(self):
    """Test unary heap (arity=1)."""
    data = [5, 2, 8, 1, 9]
    heapx.heapify(data, arity=1)
    assert is_valid_heap(data, max_heap=False, arity=1)

  def test_ternary_heap(self):
    """Test ternary heap (arity=3)."""
    data = generate_integers(1000)
    heapx.heapify(data, arity=3)
    assert is_valid_heap(data, max_heap=False, arity=3)

  def test_quaternary_heap(self):
    """Test quaternary heap (arity=4)."""
    data = generate_integers(1000)
    heapx.heapify(data, arity=4)
    assert is_valid_heap(data, max_heap=False, arity=4)

# ============================================================================
# Custom Comparison Function Tests
# ============================================================================

class TestCustomComparison:
  """Test heapify with custom comparison functions."""

  def test_absolute_value_comparison(self):
    """Test heapify with absolute value comparison."""
    data = [-5, 2, -8, 1, 9, -3]
    heapx.heapify(data, cmp=abs)
    # Verify heap property on transformed values
    abs_data = [abs(x) for x in data]
    assert is_valid_heap(abs_data, max_heap=False, arity=2)

  def test_reverse_comparison(self):
    """Test heapify with reverse comparison."""
    data = [5, 2, 8, 1, 9]
    heapx.heapify(data, cmp=lambda x: -x)
    # Verify heap property on transformed values
    neg_data = [-x for x in data]
    assert is_valid_heap(neg_data, max_heap=False, arity=2)

  def test_tuple_second_element(self):
    """Test heapify comparing by tuple second element."""
    data = [(1, 5), (2, 3), (3, 7), (4, 1)]
    heapx.heapify(data, cmp=lambda x: x[1])
    # Verify heap property on transformed values
    second_vals = [x[1] for x in data]
    assert is_valid_heap(second_vals, max_heap=False, arity=2)

  def test_string_length_comparison(self):
    """Test heapify comparing by string length."""
    data = ['short', 'a', 'medium', 'verylongstring', 'mid']
    heapx.heapify(data, cmp=len)
    assert data[0] == 'a'

  @pytest.mark.parametrize("n", [100, 1000, 10000])
  def test_custom_cmp_with_arity(self, n):
    """Test custom comparison with different arity."""
    data = generate_integers(n)
    heapx.heapify(data, cmp=abs, arity=3)
    # Verify heap property with absolute values
    abs_data = [abs(x) for x in data]
    assert is_valid_heap(abs_data, max_heap=False, arity=3)

# ============================================================================
# Edge Cases and Error Handling
# ============================================================================

class TestEdgeCases:
  """Test edge cases and error conditions."""

  def test_all_equal_elements(self):
    """Test heapify with all equal elements."""
    data = [5] * 100
    heapx.heapify(data)
    assert is_valid_heap(data, max_heap=False)

  def test_large_range_integers(self):
    """Test heapify with very large integers."""
    data = [10**15, -10**15, 10**14, -10**14, 0]
    heapx.heapify(data)
    assert is_valid_heap(data, max_heap=False)
    assert data[0] == -10**15

  def test_small_heap_optimization(self):
    """Test small heap optimization (n <= 16)."""
    for n in range(1, 17):
      data = generate_integers(n)
      heapx.heapify(data)
      assert is_valid_heap(data, max_heap=False)

  def test_invalid_arity(self):
    """Test heapify with invalid arity."""
    data = [1, 2, 3]
    with pytest.raises(ValueError):
      heapx.heapify(data, arity=0)

  def test_invalid_cmp(self):
    """Test heapify with invalid comparison function."""
    data = [1, 2, 3]
    with pytest.raises(TypeError):
      heapx.heapify(data, cmp="not_callable")

# ============================================================================
# Sequence Type Tests
# ============================================================================

class TestSequenceTypes:
  """Test heapify with different sequence types."""

  def test_list(self):
    """Test heapify with list."""
    data = [5, 2, 8, 1, 9]
    heapx.heapify(data)
    assert is_valid_heap(data, max_heap=False)

  def test_bytearray(self):
    """Test heapify with bytearray."""
    data = bytearray([5, 2, 8, 1, 9])
    heapx.heapify(data)
    assert is_valid_heap(list(data), max_heap=False)

# ============================================================================
# Correctness Verification Tests
# ============================================================================

class TestCorrectnessVerification:
  """Verify correctness by comparing with sorted output."""

  @pytest.mark.parametrize("n", [100, 1000, 10000])
  def test_extract_all_min_heap(self, n):
    """Test extracting all elements from min-heap gives sorted order using heapq."""
    data = generate_integers(n)
    expected = sorted(data)
    heapx.heapify(data)
    
    # Use heapq.heappop for extraction since heapx.pop may not be fully implemented
    result = []
    while data:
      result.append(heapq.heappop(data))
    
    assert result == expected

  @pytest.mark.parametrize("n", [100, 1000, 10000])
  def test_extract_all_max_heap(self, n):
    """Test max-heap correctness by verifying heap property."""
    data = generate_integers(n)
    heapx.heapify(data, max_heap=True)
    
    # Verify heap property is maintained
    assert is_valid_heap(data, max_heap=True)
    # Verify root is maximum
    assert data[0] == max(generate_integers(n))

    return None

# ============================================================================
# Boolean Tests
# ============================================================================

class TestBooleanHeapify:
  """Test heapify with boolean data."""

  def test_booleans_min(self):
    """Test min-heap with booleans."""
    data = generate_booleans(100)
    heapx.heapify(data)
    assert is_valid_heap(data, max_heap=False)

  def test_booleans_max(self):
    """Test max-heap with booleans."""
    data = generate_booleans(100)
    heapx.heapify(data, max_heap=True)
    assert is_valid_heap(data, max_heap=True)

  def test_all_true(self):
    """Test heapify with all True values."""
    data = [True] * 50
    heapx.heapify(data)
    assert is_valid_heap(data, max_heap=False)

  def test_all_false(self):
    """Test heapify with all False values."""
    data = [False] * 50
    heapx.heapify(data)
    assert is_valid_heap(data, max_heap=False)

# ============================================================================
# Bytes Tests
# ============================================================================

class TestBytesHeapify:
  """Test heapify with bytes data."""

  @pytest.mark.parametrize("n", [50, 100, 500])
  def test_bytes_min(self, n):
    """Test min-heap with bytes objects."""
    data = generate_bytes(n)
    heapx.heapify(data)
    assert is_valid_heap(data, max_heap=False)

  @pytest.mark.parametrize("n", [50, 100, 500])
  def test_bytes_max(self, n):
    """Test max-heap with bytes objects."""
    data = generate_bytes(n)
    heapx.heapify(data, max_heap=True)
    assert is_valid_heap(data, max_heap=True)

  def test_empty_bytes(self):
    """Test heapify with empty bytes."""
    data = [b'', b'a', b'', b'b']
    heapx.heapify(data)
    assert is_valid_heap(data, max_heap=False)

# ============================================================================
# Bytearray Tests
# ============================================================================

class TestBytearrayHeapify:
  """Test heapify with bytearray data."""

  @pytest.mark.parametrize("n", [50, 100, 500])
  def test_bytearrays_min(self, n):
    """Test min-heap with bytearray objects."""
    data = generate_bytearrays(n)
    heapx.heapify(data)
    assert is_valid_heap(data, max_heap=False)

  @pytest.mark.parametrize("n", [50, 100, 500])
  def test_bytearrays_max(self, n):
    """Test max-heap with bytearray objects."""
    data = generate_bytearrays(n)
    heapx.heapify(data, max_heap=True)
    assert is_valid_heap(data, max_heap=True)

# ============================================================================
# List Tests
# ============================================================================

class TestListHeapify:
  """Test heapify with list data (lexicographic comparison)."""

  @pytest.mark.parametrize("n", [50, 100, 500])
  def test_lists_min(self, n):
    """Test min-heap with list objects."""
    data = generate_lists(n)
    heapx.heapify(data)
    assert is_valid_heap(data, max_heap=False)

  @pytest.mark.parametrize("n", [50, 100, 500])
  def test_lists_max(self, n):
    """Test max-heap with list objects."""
    data = generate_lists(n)
    heapx.heapify(data, max_heap=True)
    assert is_valid_heap(data, max_heap=True)

  def test_empty_lists(self):
    """Test heapify with empty lists."""
    data = [[], [1], [], [2]]
    heapx.heapify(data)
    assert is_valid_heap(data, max_heap=False)

  def test_nested_lists(self):
    """Test heapify with nested lists."""
    data = [[1, 2], [1, 1], [2, 1], [1, 3]]
    heapx.heapify(data)
    assert is_valid_heap(data, max_heap=False)
    assert data[0] == [1, 1]

# ============================================================================
# Mixed Type Tests
# ============================================================================

class TestMixedHeapify:
  """Test heapify with mixed comparable types."""

  @pytest.mark.parametrize("n", [100, 500, 1000])
  def test_mixed_int_float_min(self, n):
    """Test min-heap with mixed integers and floats."""
    data = generate_mixed(n)
    heapx.heapify(data)
    assert is_valid_heap(data, max_heap=False)

  @pytest.mark.parametrize("n", [100, 500, 1000])
  def test_mixed_int_float_max(self, n):
    """Test max-heap with mixed integers and floats."""
    data = generate_mixed(n)
    heapx.heapify(data, max_heap=True)
    assert is_valid_heap(data, max_heap=True)

  def test_mixed_with_zero(self):
    """Test heapify with mixed types including zero."""
    data = [0, 0.0, 1, 1.0, -1, -1.0]
    heapx.heapify(data)
    assert is_valid_heap(data, max_heap=False)

# ============================================================================
# Range Tests
# ============================================================================

class TestRangeHeapify:
  """Test heapify with range objects."""

  def test_range_as_list(self):
    """Test heapify with range converted to list."""
    data = list(generate_range(100))
    heapx.heapify(data)
    assert is_valid_heap(data, max_heap=False)

  def test_reverse_range(self):
    """Test heapify with reverse range."""
    data = list(range(100, 0, -1))
    heapx.heapify(data)
    assert is_valid_heap(data, max_heap=False)
    assert data[0] == 1

# ============================================================================
# Performance Benchmark Tests
# ============================================================================

class TestPerformanceBenchmark:
  """Performance benchmarks comparing heapx vs heapq."""

  @pytest.mark.benchmark
  def test_performance_comparison(self, capsys):
    """Comprehensive performance comparison: heapx vs heapq."""
    
    import sys
    
    output = []
    output.append("\n" + "="*80)
    output.append("TIME EFFICIENCY COMPARISON: heapx.heapify vs heapq.heapify")
    output.append("="*80)
    output.append(f"Configuration: R=10 repetitions per size, Random integers, Min-heap, Arity=2")
    output.append("="*80)
    
    sizes = [1_000_000, 2_000_000, 3_000_000, 4_000_000, 5_000_000,
             6_000_000, 7_000_000, 8_000_000, 9_000_000, 10_000_000]
    repetitions = 10
    
    results = []
    memory_results = []
    
    for n in sizes:
      heapx_times = []
      heapq_times = []
      
      for r in range(repetitions):
        data_heapx = generate_integers(n, seed=r)
        data_heapq = data_heapx.copy()
        
        # Measure time
        start = time.perf_counter()
        heapx.heapify(data_heapx)
        heapx_times.append(time.perf_counter() - start)
        
        start = time.perf_counter()
        heapq.heapify(data_heapq)
        heapq_times.append(time.perf_counter() - start)
        
        assert is_valid_heap(data_heapx, max_heap=False)
        assert is_valid_heap(data_heapq, max_heap=False)
      
      heapx_avg = mean(heapx_times)
      heapx_std = stdev(heapx_times) if len(heapx_times) > 1 else 0
      heapq_avg = mean(heapq_times)
      heapq_std = stdev(heapq_times) if len(heapq_times) > 1 else 0
      
      results.append({
        'n': n,
        'heapx_avg': heapx_avg,
        'heapx_std': heapx_std,
        'heapq_avg': heapq_avg,
        'heapq_std': heapq_std
      })
      
      # Measure memory for each size
      data_heapx = generate_integers(n, seed=0)
      data_heapq = data_heapx.copy()
      
      heapx_mem_before = sys.getsizeof(data_heapx)
      heapx.heapify(data_heapx)
      heapx_mem_after = sys.getsizeof(data_heapx)
      
      heapq_mem_before = sys.getsizeof(data_heapq)
      heapq.heapify(data_heapq)
      heapq_mem_after = sys.getsizeof(data_heapq)
      
      memory_results.append({
        'n': n,
        'heapx_mem': heapx_mem_after,
        'heapq_mem': heapq_mem_after
      })
    
    # Time efficiency table
    output.append("\n" + "-"*65)
    output.append(f"{'n':>12} │ {'heapx (s)':>23} │ {'heapq (s)':>23}")
    output.append(f"{'':>12} │ {'avg ± std':>23} │ {'avg ± std':>23}")
    output.append("-"*65)
    
    for r in results:
      output.append(f"{r['n']:>12,} │ "
                   f"{r['heapx_avg']:>10.4f} ± {r['heapx_std']:>8.4f} │ "
                   f"{r['heapq_avg']:>10.4f} ± {r['heapq_std']:>8.4f}")
    
    output.append("-"*65)
    output.append("="*80)
    
    # Memory efficiency table
    output.append("\nMEMORY EFFICIENCY COMPARISON: heapx.heapify vs heapq.heapify")
    output.append("="*80)
    output.append(f"Configuration: Random integers, Min-heap, Arity=2")
    output.append("="*80)
    output.append("\n" + "-"*65)
    output.append(f"{'n':>12} │ {'heapx (bytes)':>23} │ {'heapq (bytes)':>23}")
    output.append("-"*65)
    
    for r in memory_results:
      output.append(f"{r['n']:>12,} │ {r['heapx_mem']:>23,} │ {r['heapq_mem']:>23,}")
    
    output.append("-"*65)
    output.append("\nNote: Both implementations use O(1) auxiliary space (in-place)")
    output.append("="*80 + "\n")
    
    # Print all output
    final_output = '\n'.join(output)
    print(final_output)
    sys.stdout.flush()
    
    # Also write to captured output for pytest
    with capsys.disabled():
      print(final_output)

  @pytest.mark.benchmark
  @pytest.mark.parametrize("arity", [2, 3, 4])
  def test_arity_performance(self, arity):
    """Test performance with different arity values."""
    n = 1_000_000; data = generate_integers(n)

    start = time.perf_counter()
    heapx.heapify(data, arity=arity)
    elapsed = time.perf_counter() - start

    assert is_valid_heap(data, max_heap=False, arity=arity)
    print(f"\nArity {arity}: {elapsed:.4f}s for {n:,} elements")

    return None

  @pytest.mark.benchmark
  def test_key_function_performance(self):
    """Test performance with key function."""
    n = 1_000_000; data = generate_integers(n)
    
    start = time.perf_counter()
    heapx.heapify(data, cmp=abs)
    elapsed = time.perf_counter() - start

    print(f"\nKey function (abs): {elapsed:.4f}s for {n:,} elements")

    return None

# ============================================================================
# Stress Tests
# ============================================================================

class TestStressTests:
  """Stress tests with extreme conditions."""

  def test_very_large_heap(self):
    """Test heapify with very large heap."""
    n = 100_000_000
    data = generate_integers(n)
    heapx.heapify(data)
    assert is_valid_heap(data, max_heap=False)

    return None

  @pytest.mark.parametrize("n", [100, 1000, 10000])
  def test_repeated_heapify(self, n):
    """Test repeated heapify operations."""
    data = generate_integers(n)
    for _ in range(10):
      heapx.heapify(data)
      assert is_valid_heap(data, max_heap=False)
      random.shuffle(data)
    
    return None

  def test_all_combinations(self):
    """Test various combinations of parameters."""
    n = 100; data = generate_integers(n)

    for max_heap in [False, True]:
      for arity in [2, 3, 4]:
        test_data = data.copy()
        heapx.heapify(test_data, max_heap=max_heap, arity=arity)
        assert is_valid_heap(test_data, max_heap=max_heap, arity=arity)

    return None
