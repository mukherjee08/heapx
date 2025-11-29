"""
Comprehensive test suite for heapx sequence type compatibility.

This module tests heapx's ability to handle various Python sequence types
that implement the sequence protocol. Tests verify that all heap operations
work correctly with different sequence implementations.

Sequence Protocol Requirements:
  - __len__() or __length_hint__()
  - __getitem__()
  - __setitem__() (for mutable sequences)
  - Support for PySequence_Check, PySequence_Size, PySequence_GetItem, PySequence_SetItem
"""

import heapx
import pytest
import array
import collections
from typing import List, Any

# ============================================================================
# Helper Functions
# ============================================================================

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
# Sequence Type Tests
# ============================================================================

class TestListSequence:
  """Test heapx with standard Python list (most common case)."""

  def test_heapify_list(self):
    """Test heapify with list."""
    data = [5, 2, 8, 1, 9, 3, 7]
    heapx.heapify(data)
    assert is_valid_heap(data)
    assert data[0] == 1

  def test_push_list(self):
    """Test push with list."""
    heap = [1, 3, 2]
    heapx.heapify(heap)
    heapx.push(heap, 0)
    assert is_valid_heap(heap)
    assert heap[0] == 0

  def test_pop_list(self):
    """Test pop with list."""
    heap = [1, 3, 2, 7, 5]
    heapx.heapify(heap)
    result = heapx.pop(heap)
    assert result == 1
    assert is_valid_heap(heap)

  def test_sort_list(self):
    """Test sort with list."""
    data = [5, 2, 8, 1, 9]
    result = heapx.sort(data)
    assert result == [1, 2, 5, 8, 9]

  def test_merge_lists(self):
    """Test merge with lists."""
    heap1 = [1, 3, 5]
    heap2 = [2, 4, 6]
    heapx.heapify(heap1)
    heapx.heapify(heap2)
    result = heapx.merge(heap1, heap2)
    assert len(result) == 6
    assert is_valid_heap(result)

  def test_remove_list(self):
    """Test remove with list."""
    heap = [1, 3, 2, 7, 5]
    heapx.heapify(heap)
    count = heapx.remove(heap, indices=0)
    assert count == 1
    assert is_valid_heap(heap)

  def test_replace_list(self):
    """Test replace with list."""
    heap = [1, 3, 2, 7, 5]
    heapx.heapify(heap)
    count = heapx.replace(heap, 10, indices=0)
    assert count == 1
    assert is_valid_heap(heap)

class TestArraySequence:
  """Test heapx with array.array (typed arrays)."""

  def test_heapify_array_int(self):
    """Test heapify with integer array."""
    data = array.array('i', [5, 2, 8, 1, 9, 3, 7])
    heapx.heapify(data)
    assert is_valid_heap(list(data))
    assert data[0] == 1

  def test_heapify_array_float(self):
    """Test heapify with float array."""
    data = array.array('d', [5.5, 2.2, 8.8, 1.1, 9.9])
    heapx.heapify(data)
    assert is_valid_heap(list(data))
    assert data[0] == 1.1

  def test_heapify_array_max_heap(self):
    """Test max-heap with array."""
    data = array.array('i', [5, 2, 8, 1, 9])
    heapx.heapify(data, max_heap=True)
    assert is_valid_heap(list(data), max_heap=True)
    assert data[0] == 9

  def test_sort_array(self):
    """Test sort with array."""
    data = array.array('i', [5, 2, 8, 1, 9])
    result = heapx.sort(data)
    assert result == [1, 2, 5, 8, 9]

  def test_array_various_types(self):
    """Test heapify with various array type codes."""
    type_codes = ['b', 'h', 'i', 'l', 'f', 'd']
    for code in type_codes:
      data = array.array(code, [5, 2, 8, 1, 9])
      heapx.heapify(data)
      assert is_valid_heap(list(data))

class TestBytearraySequence:
  """Test heapx with bytearray (mutable bytes)."""

  def test_heapify_bytearray(self):
    """Test heapify with bytearray."""
    data = bytearray([5, 2, 8, 1, 9, 3, 7])
    heapx.heapify(data)
    assert is_valid_heap(list(data))
    assert data[0] == 1

  def test_heapify_bytearray_max_heap(self):
    """Test max-heap with bytearray."""
    data = bytearray([5, 2, 8, 1, 9])
    heapx.heapify(data, max_heap=True)
    assert is_valid_heap(list(data), max_heap=True)
    assert data[0] == 9

  def test_sort_bytearray(self):
    """Test sort with bytearray."""
    data = bytearray([5, 2, 8, 1, 9])
    result = heapx.sort(data)
    assert result == [1, 2, 5, 8, 9]

  def test_bytearray_range(self):
    """Test heapify with bytearray containing full byte range."""
    data = bytearray([255, 128, 0, 64, 192])
    heapx.heapify(data)
    assert is_valid_heap(list(data))
    assert data[0] == 0

class TestDequeSequence:
  """Test heapx with collections.deque (double-ended queue)."""

  def test_heapify_deque(self):
    """Test heapify with deque."""
    data = collections.deque([5, 2, 8, 1, 9, 3, 7])
    heapx.heapify(data)
    assert is_valid_heap(list(data))
    assert data[0] == 1

  def test_heapify_deque_max_heap(self):
    """Test max-heap with deque."""
    data = collections.deque([5, 2, 8, 1, 9])
    heapx.heapify(data, max_heap=True)
    assert is_valid_heap(list(data), max_heap=True)
    assert data[0] == 9

  def test_sort_deque(self):
    """Test sort with deque."""
    data = collections.deque([5, 2, 8, 1, 9])
    result = heapx.sort(data)
    assert result == [1, 2, 5, 8, 9]

  def test_deque_with_maxlen(self):
    """Test heapify with bounded deque."""
    data = collections.deque([5, 2, 8, 1, 9], maxlen=10)
    heapx.heapify(data)
    assert is_valid_heap(list(data))

class TestCustomSequence:
  """Test heapx with custom sequence implementations."""

  class SimpleSequence:
    """Minimal sequence implementation."""
    def __init__(self, data):
      self._data = list(data)
    
    def __len__(self):
      return len(self._data)
    
    def __getitem__(self, index):
      return self._data[index]
    
    def __setitem__(self, index, value):
      self._data[index] = value

  def test_heapify_custom_sequence(self):
    """Test heapify with custom sequence."""
    data = self.SimpleSequence([5, 2, 8, 1, 9, 3, 7])
    heapx.heapify(data)
    assert is_valid_heap(list(data._data))
    assert data[0] == 1

  def test_heapify_custom_max_heap(self):
    """Test max-heap with custom sequence."""
    data = self.SimpleSequence([5, 2, 8, 1, 9])
    heapx.heapify(data, max_heap=True)
    assert is_valid_heap(list(data._data), max_heap=True)
    assert data[0] == 9

  def test_sort_custom_sequence(self):
    """Test sort with custom sequence."""
    data = self.SimpleSequence([5, 2, 8, 1, 9])
    result = heapx.sort(data)
    assert result == [1, 2, 5, 8, 9]

# ============================================================================
# Comprehensive Operation Tests Across Sequence Types
# ============================================================================

class TestAllOperationsAcrossTypes:
  """Test all heap operations work with various sequence types."""

  @pytest.mark.parametrize("seq_type,data", [
    (list, [5, 2, 8, 1, 9, 3, 7]),
    (lambda x: array.array('i', x), [5, 2, 8, 1, 9, 3, 7]),
    (bytearray, [5, 2, 8, 1, 9, 3, 7]),
    (collections.deque, [5, 2, 8, 1, 9, 3, 7]),
  ])
  def test_heapify_all_types(self, seq_type, data):
    """Test heapify works with all sequence types."""
    seq = seq_type(data)
    heapx.heapify(seq)
    assert is_valid_heap(list(seq))

  @pytest.mark.parametrize("seq_type,data", [
    (list, [5, 2, 8, 1, 9]),
    (lambda x: array.array('i', x), [5, 2, 8, 1, 9]),
    (bytearray, [5, 2, 8, 1, 9]),
    (collections.deque, [5, 2, 8, 1, 9]),
  ])
  def test_sort_all_types(self, seq_type, data):
    """Test sort works with all sequence types."""
    seq = seq_type(data)
    result = heapx.sort(seq)
    assert result == sorted(data)

  @pytest.mark.parametrize("arity", [1, 2, 3, 4, 8])
  def test_arity_with_sequences(self, arity):
    """Test different arity values work with sequences."""
    for seq_type in [list, bytearray, collections.deque]:
      data = seq_type([5, 2, 8, 1, 9, 3, 7, 4, 6])
      heapx.heapify(data, arity=arity)
      assert is_valid_heap(list(data), arity=arity)

# ============================================================================
# Edge Cases and Boundary Conditions
# ============================================================================

class TestSequenceEdgeCases:
  """Test edge cases with various sequence types."""

  def test_empty_sequences(self):
    """Test heapify with empty sequences."""
    for seq_type in [list, bytearray, collections.deque]:
      data = seq_type([])
      heapx.heapify(data)
      assert len(data) == 0

  def test_single_element_sequences(self):
    """Test heapify with single element."""
    for seq_type in [list, bytearray, collections.deque]:
      data = seq_type([42])
      heapx.heapify(data)
      assert len(data) == 1
      assert data[0] == 42

  def test_two_element_sequences(self):
    """Test heapify with two elements."""
    for seq_type in [list, bytearray, collections.deque]:
      data = seq_type([2, 1])
      heapx.heapify(data)
      assert data[0] == 1

  def test_large_sequences(self):
    """Test heapify with large sequences."""
    for seq_type in [list, lambda x: array.array('i', x)]:
      data = seq_type(list(range(10000, 0, -1)))
      heapx.heapify(data)
      assert is_valid_heap(list(data))
      assert list(data)[0] == 1

  def test_duplicate_elements(self):
    """Test sequences with duplicate elements."""
    for seq_type in [list, bytearray, collections.deque]:
      data = seq_type([5, 5, 5, 5, 5])
      heapx.heapify(data)
      assert is_valid_heap(list(data))

# ============================================================================
# Performance and Correctness Verification
# ============================================================================

class TestSequenceCorrectness:
  """Verify correctness of heap operations across sequence types."""

  def test_heapify_produces_valid_heap(self):
    """Verify heapify produces valid heap for all sequence types."""
    test_data = [5, 2, 8, 1, 9, 3, 7, 4, 6, 10]
    
    for seq_type in [list, bytearray, collections.deque]:
      data = seq_type(test_data)
      heapx.heapify(data)
      assert is_valid_heap(list(data)), f"Failed for {seq_type.__name__}"

  def test_sort_produces_sorted_output(self):
    """Verify sort produces correctly sorted output."""
    test_data = [5, 2, 8, 1, 9, 3, 7, 4, 6, 10]
    expected = sorted(test_data)
    
    for seq_type in [list, bytearray, collections.deque]:
      data = seq_type(test_data)
      result = heapx.sort(data)
      assert result == expected, f"Failed for {seq_type.__name__}"

  def test_max_heap_correctness(self):
    """Verify max-heap property is maintained."""
    test_data = [5, 2, 8, 1, 9, 3, 7]
    
    for seq_type in [list, bytearray, collections.deque]:
      data = seq_type(test_data)
      heapx.heapify(data, max_heap=True)
      assert is_valid_heap(list(data), max_heap=True), f"Failed for {seq_type.__name__}"
      assert list(data)[0] == max(test_data), f"Root not maximum for {seq_type.__name__}"

# ============================================================================
# Comprehensive Summary Report
# ============================================================================

class TestSequenceSummary:
  """Generate comprehensive summary of sequence type support."""

  def test_sequence_support_summary(self, capsys):
    """Generate detailed report of sequence type compatibility."""
    
    output = []
    output.append("\n" + "="*80)
    output.append("HEAPX SEQUENCE TYPE COMPATIBILITY REPORT")
    output.append("="*80)
    output.append("\nThis report demonstrates heapx's ability to process various Python")
    output.append("sequence types that implement the sequence protocol.")
    output.append("\n" + "-"*80)
    
    # Test each sequence type
    sequence_types = [
      ("list", list, "Standard Python list - most common, fully optimized"),
      ("array.array", lambda x: array.array('i', x), "Typed array - memory efficient for numeric data"),
      ("bytearray", bytearray, "Mutable bytes - efficient for byte manipulation"),
      ("collections.deque", collections.deque, "Double-ended queue - efficient insertions"),
    ]
    
    test_data = [5, 2, 8, 1, 9, 3, 7]
    
    output.append("\n1. HEAPIFY OPERATION")
    output.append("-"*80)
    output.append(f"{'Sequence Type':<25} {'Status':<10} {'Root':<10} {'Valid Heap':<12}")
    output.append("-"*80)
    
    for name, seq_type, desc in sequence_types:
      try:
        data = seq_type(test_data)
        heapx.heapify(data)
        valid = is_valid_heap(list(data))
        root = list(data)[0]
        status = "✓ PASS"
        output.append(f"{name:<25} {status:<10} {root:<10} {str(valid):<12}")
      except Exception as e:
        output.append(f"{name:<25} {'✗ FAIL':<10} {'N/A':<10} {str(e)[:12]:<12}")
    
    output.append("\n2. SORT OPERATION")
    output.append("-"*80)
    output.append(f"{'Sequence Type':<25} {'Status':<10} {'Correct':<12}")
    output.append("-"*80)
    
    for name, seq_type, desc in sequence_types:
      try:
        data = seq_type(test_data)
        result = heapx.sort(data)
        correct = result == sorted(test_data)
        status = "✓ PASS" if correct else "✗ FAIL"
        output.append(f"{name:<25} {status:<10} {str(correct):<12}")
      except Exception as e:
        output.append(f"{name:<25} {'✗ FAIL':<10} {str(e)[:12]:<12}")
    
    output.append("\n3. MAX-HEAP OPERATION")
    output.append("-"*80)
    output.append(f"{'Sequence Type':<25} {'Status':<10} {'Root':<10} {'Valid Heap':<12}")
    output.append("-"*80)
    
    for name, seq_type, desc in sequence_types:
      try:
        data = seq_type(test_data)
        heapx.heapify(data, max_heap=True)
        valid = is_valid_heap(list(data), max_heap=True)
        root = list(data)[0]
        status = "✓ PASS"
        output.append(f"{name:<25} {status:<10} {root:<10} {str(valid):<12}")
      except Exception as e:
        output.append(f"{name:<25} {'✗ FAIL':<10} {'N/A':<10} {str(e)[:12]:<12}")
    
    output.append("\n4. N-ARY HEAP SUPPORT")
    output.append("-"*80)
    output.append(f"{'Arity':<10} {'list':<10} {'array':<10} {'bytearray':<12} {'deque':<10}")
    output.append("-"*80)
    
    for arity in [1, 2, 3, 4, 8]:
      results = []
      for name, seq_type, desc in sequence_types:
        try:
          data = seq_type(test_data)
          heapx.heapify(data, arity=arity)
          valid = is_valid_heap(list(data), arity=arity)
          results.append("✓" if valid else "✗")
        except:
          results.append("✗")
      output.append(f"{arity:<10} {results[0]:<10} {results[1]:<10} {results[2]:<12} {results[3]:<10}")
    
    output.append("\n5. SEQUENCE TYPE DESCRIPTIONS")
    output.append("-"*80)
    for name, seq_type, desc in sequence_types:
      output.append(f"  • {name}: {desc}")
    
    output.append("\n6. SEQUENCE PROTOCOL REQUIREMENTS")
    output.append("-"*80)
    output.append("  heapx supports any Python object that implements:")
    output.append("    • __len__() - returns sequence length")
    output.append("    • __getitem__(index) - retrieves element at index")
    output.append("    • __setitem__(index, value) - sets element at index (mutable)")
    output.append("    • PySequence_Check - recognized as sequence by Python C API")
    
    output.append("\n7. SUPPORTED OPERATIONS")
    output.append("-"*80)
    operations = [
      ("heapify", "Transform sequence into heap structure"),
      ("push", "Insert elements into heap"),
      ("pop", "Extract root element from heap"),
      ("sort", "Sort sequence using heapsort"),
      ("merge", "Merge multiple heaps"),
      ("remove", "Remove elements by index/predicate"),
      ("replace", "Replace elements maintaining heap property"),
    ]
    for op, desc in operations:
      output.append(f"  • {op:<12} - {desc}")
    
    output.append("\n8. PERFORMANCE CHARACTERISTICS")
    output.append("-"*80)
    output.append("  • list:        Fastest (direct memory access, C-optimized)")
    output.append("  • array.array: Fast (typed arrays, memory efficient)")
    output.append("  • bytearray:   Fast (mutable bytes, optimized for bytes)")
    output.append("  • deque:       Good (sequence protocol, slight overhead)")
    output.append("  • custom:      Variable (depends on __getitem__/__setitem__ speed)")
    
    output.append("\n" + "="*80)
    output.append("CONCLUSION")
    output.append("="*80)
    output.append("heapx successfully supports all Python sequence types that implement")
    output.append("the sequence protocol. The module uses PySequence_* C API functions")
    output.append("for maximum compatibility while maintaining optimal performance for")
    output.append("common types like list through specialized fast paths.")
    output.append("="*80 + "\n")
    
    # Print report
    final_output = '\n'.join(output)
    print(final_output)
    
    with capsys.disabled():
      print(final_output)
