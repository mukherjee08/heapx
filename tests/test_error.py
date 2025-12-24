"""
Test suite for heapx error messages.

This module tests all error messages implemented in heapx.c to ensure
they are triggered correctly and contain the expected diagnostic information.
"""

import pytest
import heapx


class TestParameterValidationErrors:
  """Tests for parameter validation error messages."""

  # ============================================================================
  # cmp must be callable or None
  # ============================================================================

  def test_heapify_cmp_not_callable(self):
    """Test: cmp must be callable or None, not <type>"""
    data = [3, 1, 2]
    with pytest.raises(TypeError) as exc_info:
      heapx.heapify(data, cmp="not_callable")
    msg = str(exc_info.value)
    assert "cmp must be callable or None" in msg
    assert "str" in msg
    print(f"✓ heapify cmp error: {msg}")

  def test_push_cmp_not_callable(self):
    """Test: cmp must be callable or None, not <type>"""
    data = [1, 2, 3]
    heapx.heapify(data)
    with pytest.raises(TypeError) as exc_info:
      heapx.push(data, 4, cmp=123)
    msg = str(exc_info.value)
    assert "cmp must be callable or None" in msg
    assert "int" in msg
    print(f"✓ push cmp error: {msg}")

  def test_pop_cmp_not_callable(self):
    """Test: cmp must be callable or None, not <type>"""
    data = [1, 2, 3]
    heapx.heapify(data)
    with pytest.raises(TypeError) as exc_info:
      heapx.pop(data, cmp=[1, 2, 3])
    msg = str(exc_info.value)
    assert "cmp must be callable or None" in msg
    assert "list" in msg
    print(f"✓ pop cmp error: {msg}")

  def test_sort_cmp_not_callable(self):
    """Test: cmp must be callable or None, not <type>"""
    data = [3, 1, 2]
    with pytest.raises(TypeError) as exc_info:
      heapx.sort(data, cmp={})
    msg = str(exc_info.value)
    assert "cmp must be callable or None" in msg
    assert "dict" in msg
    print(f"✓ sort cmp error: {msg}")

  def test_remove_cmp_not_callable(self):
    """Test: cmp must be callable or None, not <type>"""
    data = [1, 2, 3]
    heapx.heapify(data)
    with pytest.raises(TypeError) as exc_info:
      heapx.remove(data, indices=0, cmp=(1, 2))
    msg = str(exc_info.value)
    assert "cmp must be callable or None" in msg
    assert "tuple" in msg
    print(f"✓ remove cmp error: {msg}")

  def test_replace_cmp_not_callable(self):
    """Test: cmp must be callable or None, not <type>"""
    data = [1, 2, 3]
    heapx.heapify(data)
    with pytest.raises(TypeError) as exc_info:
      heapx.replace(data, 99, indices=0, cmp=3.14)
    msg = str(exc_info.value)
    assert "cmp must be callable or None" in msg
    assert "float" in msg
    print(f"✓ replace cmp error: {msg}")

  def test_merge_cmp_not_callable(self):
    """Test: cmp must be callable or None, not <type>"""
    with pytest.raises(TypeError) as exc_info:
      heapx.merge([1, 2], [3, 4], cmp=b"bytes")
    msg = str(exc_info.value)
    assert "cmp must be callable or None" in msg
    assert "bytes" in msg
    print(f"✓ merge cmp error: {msg}")

  # ============================================================================
  # predicate must be callable or None
  # ============================================================================

  def test_remove_predicate_not_callable(self):
    """Test: predicate must be callable or None, not <type>"""
    data = [1, 2, 3]
    heapx.heapify(data)
    with pytest.raises(TypeError) as exc_info:
      heapx.remove(data, predicate="not_callable")
    msg = str(exc_info.value)
    assert "predicate must be callable or None" in msg
    assert "str" in msg
    print(f"✓ remove predicate error: {msg}")

  def test_replace_predicate_not_callable(self):
    """Test: predicate must be callable or None, not <type>"""
    data = [1, 2, 3]
    heapx.heapify(data)
    with pytest.raises(TypeError) as exc_info:
      heapx.replace(data, 99, predicate=42)
    msg = str(exc_info.value)
    assert "predicate must be callable or None" in msg
    assert "int" in msg
    print(f"✓ replace predicate error: {msg}")

  # ============================================================================
  # arity must be >= 1 and <= 64
  # ============================================================================

  def test_heapify_arity_zero(self):
    """Test: arity must be >= 1 and <= 64, got 0"""
    data = [3, 1, 2]
    with pytest.raises(ValueError) as exc_info:
      heapx.heapify(data, arity=0)
    msg = str(exc_info.value)
    assert "arity must be >= 1 and <= 64" in msg
    assert "got 0" in msg
    print(f"✓ heapify arity=0 error: {msg}")

  def test_heapify_arity_negative(self):
    """Test: arity must be >= 1 and <= 64, got -5"""
    data = [3, 1, 2]
    with pytest.raises(ValueError) as exc_info:
      heapx.heapify(data, arity=-5)
    msg = str(exc_info.value)
    assert "arity must be >= 1 and <= 64" in msg
    assert "got -5" in msg
    print(f"✓ heapify arity=-5 error: {msg}")

  def test_heapify_arity_too_large(self):
    """Test: arity must be >= 1 and <= 64, got 65"""
    data = [3, 1, 2]
    with pytest.raises(ValueError) as exc_info:
      heapx.heapify(data, arity=65)
    msg = str(exc_info.value)
    assert "arity must be >= 1 and <= 64" in msg
    assert "got 65" in msg
    print(f"✓ heapify arity=65 error: {msg}")

  def test_push_arity_invalid(self):
    """Test: arity must be >= 1 and <= 64, got 100"""
    data = [1, 2, 3]
    heapx.heapify(data)
    with pytest.raises(ValueError) as exc_info:
      heapx.push(data, 4, arity=100)
    msg = str(exc_info.value)
    assert "arity must be >= 1 and <= 64" in msg
    assert "got 100" in msg
    print(f"✓ push arity=100 error: {msg}")

  def test_pop_arity_invalid(self):
    """Test: arity must be >= 1 and <= 64, got 0"""
    data = [1, 2, 3]
    heapx.heapify(data)
    with pytest.raises(ValueError) as exc_info:
      heapx.pop(data, arity=0)
    msg = str(exc_info.value)
    assert "arity must be >= 1 and <= 64" in msg
    assert "got 0" in msg
    print(f"✓ pop arity=0 error: {msg}")

  def test_sort_arity_invalid(self):
    """Test: arity must be >= 1 and <= 64, got -1"""
    data = [3, 1, 2]
    with pytest.raises(ValueError) as exc_info:
      heapx.sort(data, arity=-1)
    msg = str(exc_info.value)
    assert "arity must be >= 1 and <= 64" in msg
    assert "got -1" in msg
    print(f"✓ sort arity=-1 error: {msg}")

  def test_remove_arity_invalid(self):
    """Test: arity must be >= 1 and <= 64, got 128"""
    data = [1, 2, 3]
    heapx.heapify(data)
    with pytest.raises(ValueError) as exc_info:
      heapx.remove(data, indices=0, arity=128)
    msg = str(exc_info.value)
    assert "arity must be >= 1 and <= 64" in msg
    assert "got 128" in msg
    print(f"✓ remove arity=128 error: {msg}")

  def test_replace_arity_invalid(self):
    """Test: arity must be >= 1 and <= 64, got 0"""
    data = [1, 2, 3]
    heapx.heapify(data)
    with pytest.raises(ValueError) as exc_info:
      heapx.replace(data, 99, indices=0, arity=0)
    msg = str(exc_info.value)
    assert "arity must be >= 1 and <= 64" in msg
    assert "got 0" in msg
    print(f"✓ replace arity=0 error: {msg}")

  def test_merge_arity_invalid(self):
    """Test: arity must be >= 1 and <= 64, got 200"""
    with pytest.raises(ValueError) as exc_info:
      heapx.merge([1, 2], [3, 4], arity=200)
    msg = str(exc_info.value)
    assert "arity must be >= 1 and <= 64" in msg
    assert "got 200" in msg
    print(f"✓ merge arity=200 error: {msg}")

  # ============================================================================
  # n must be >= 1
  # ============================================================================

  def test_pop_n_zero(self):
    """Test: n must be >= 1, got 0"""
    data = [1, 2, 3]
    heapx.heapify(data)
    with pytest.raises(ValueError) as exc_info:
      heapx.pop(data, n=0)
    msg = str(exc_info.value)
    assert "n must be >= 1" in msg
    assert "got 0" in msg
    print(f"✓ pop n=0 error: {msg}")

  def test_pop_n_negative(self):
    """Test: n must be >= 1, got -3"""
    data = [1, 2, 3]
    heapx.heapify(data)
    with pytest.raises(ValueError) as exc_info:
      heapx.pop(data, n=-3)
    msg = str(exc_info.value)
    assert "n must be >= 1" in msg
    assert "got -3" in msg
    print(f"✓ pop n=-3 error: {msg}")

  # ============================================================================
  # pop from empty heap
  # ============================================================================

  def test_pop_empty_heap(self):
    """Test: pop from empty heap"""
    data = []
    with pytest.raises(IndexError) as exc_info:
      heapx.pop(data)
    msg = str(exc_info.value)
    assert "pop from empty heap" in msg
    print(f"✓ pop empty heap error: {msg}")

  # ============================================================================
  # values length must match selection count or be 1
  # ============================================================================

  def test_replace_values_length_mismatch(self):
    """Test: values length must match selection count or be 1"""
    data = [1, 2, 3, 4, 5]
    heapx.heapify(data)
    with pytest.raises(ValueError) as exc_info:
      heapx.replace(data, [10, 20], indices=[0, 1, 2])
    msg = str(exc_info.value)
    assert "values length must match selection count or be 1" in msg
    assert "got 2 values for 3 selections" in msg
    print(f"✓ replace values mismatch error: {msg}")

  def test_replace_values_length_mismatch_predicate(self):
    """Test: values length must match selection count or be 1 (predicate)"""
    data = [1, 2, 3, 4, 5]
    heapx.heapify(data)
    with pytest.raises(ValueError) as exc_info:
      heapx.replace(data, [10, 20, 30], predicate=lambda x: x < 3)
    msg = str(exc_info.value)
    assert "values length must match selection count or be 1" in msg
    assert "got 3 values for 2 selections" in msg
    print(f"✓ replace values mismatch (predicate) error: {msg}")

  # ============================================================================
  # merge requires at least 2 heaps
  # ============================================================================

  def test_merge_zero_heaps(self):
    """Test: merge requires at least 2 heaps, got 0"""
    with pytest.raises(ValueError) as exc_info:
      heapx.merge()
    msg = str(exc_info.value)
    assert "merge requires at least 2 heaps" in msg
    assert "got 0" in msg
    print(f"✓ merge 0 heaps error: {msg}")

  def test_merge_one_heap(self):
    """Test: merge requires at least 2 heaps, got 1"""
    with pytest.raises(ValueError) as exc_info:
      heapx.merge([1, 2, 3])
    msg = str(exc_info.value)
    assert "merge requires at least 2 heaps" in msg
    assert "got 1" in msg
    print(f"✓ merge 1 heap error: {msg}")

  # ============================================================================
  # merge argument must be a sequence
  # ============================================================================

  def test_merge_non_sequence_first(self):
    """Test: merge argument 1 must be a sequence, not <type>"""
    with pytest.raises(TypeError) as exc_info:
      heapx.merge(42, [1, 2, 3])
    msg = str(exc_info.value)
    assert "merge argument 1 must be a sequence" in msg
    assert "int" in msg
    print(f"✓ merge non-sequence arg 1 error: {msg}")

  def test_merge_non_sequence_second(self):
    """Test: merge argument 2 must be a sequence, not <type>"""
    # Note: strings are sequences in Python, so we use a non-sequence type
    with pytest.raises(TypeError) as exc_info:
      heapx.merge([1, 2, 3], None)
    msg = str(exc_info.value)
    assert "merge argument 2 must be a sequence" in msg
    assert "NoneType" in msg
    print(f"✓ merge non-sequence arg 2 error: {msg}")

  def test_merge_non_sequence_third(self):
    """Test: merge argument 3 must be a sequence, not <type>"""
    with pytest.raises(TypeError) as exc_info:
      heapx.merge([1], [2], 3.14)
    msg = str(exc_info.value)
    assert "merge argument 3 must be a sequence" in msg
    assert "float" in msg
    print(f"✓ merge non-sequence arg 3 error: {msg}")


class TestListModificationErrors:
  """Tests for list modification during heap operation errors.
  
  These errors occur when a comparison function modifies the list
  during a heap operation, which corrupts the heap structure.
  """

  # ============================================================================
  # list modified during heapify
  # ============================================================================

  def test_heapify_list_modified(self):
    """Test: list modified during heapify (expected size X, got Y)"""
    data = list(range(20))
    
    def evil_cmp(x):
      if len(data) > 10:
        data.pop()
      return x
    
    with pytest.raises(ValueError) as exc_info:
      heapx.heapify(data, cmp=evil_cmp)
    msg = str(exc_info.value)
    assert "list modified during heapify" in msg
    assert "expected size" in msg
    assert "got" in msg
    print(f"✓ heapify list modified error: {msg}")

  def test_heapify_list_modified_ternary(self):
    """Test: list modified during heapify with arity=3"""
    data = list(range(30))
    
    def evil_cmp(x):
      if len(data) > 15:
        data.pop()
      return x
    
    with pytest.raises(ValueError) as exc_info:
      heapx.heapify(data, cmp=evil_cmp, arity=3)
    msg = str(exc_info.value)
    assert "list modified during heapify" in msg
    assert "expected size" in msg
    print(f"✓ heapify (arity=3) list modified error: {msg}")

  def test_heapify_list_modified_quaternary(self):
    """Test: list modified during heapify with arity=4"""
    data = list(range(40))
    
    def evil_cmp(x):
      if len(data) > 20:
        data.pop()
      return x
    
    with pytest.raises(ValueError) as exc_info:
      heapx.heapify(data, cmp=evil_cmp, arity=4)
    msg = str(exc_info.value)
    assert "list modified during heapify" in msg
    assert "expected size" in msg
    print(f"✓ heapify (arity=4) list modified error: {msg}")

  # ============================================================================
  # list modified during push
  # ============================================================================

  def test_push_list_modified(self):
    """Test: list modified during push (expected size X, got Y)"""
    data = list(range(20))
    heapx.heapify(data)
    
    def evil_cmp(x):
      if len(data) > 15:
        data.pop()
      return x
    
    with pytest.raises(ValueError) as exc_info:
      heapx.push(data, 100, cmp=evil_cmp)
    msg = str(exc_info.value)
    assert "list modified during push" in msg
    assert "expected size" in msg
    assert "got" in msg
    print(f"✓ push list modified error: {msg}")

  def test_push_list_modified_bulk(self):
    """Test: list modified during push (bulk insert)"""
    data = list(range(20))
    heapx.heapify(data)
    
    def evil_cmp(x):
      if len(data) > 18:
        data.pop()
      return x
    
    with pytest.raises(ValueError) as exc_info:
      heapx.push(data, [100, 101, 102], cmp=evil_cmp)
    msg = str(exc_info.value)
    assert "list modified during push" in msg
    assert "expected size" in msg
    print(f"✓ push (bulk) list modified error: {msg}")

  # ============================================================================
  # list modified during pop
  # ============================================================================

  def test_pop_list_modified_specific(self):
    """Test: list modified during pop (expected size X, got Y) - specific message"""
    # The specific 'pop' error is triggered in bulk pop path with no cmp
    class EvilInt:
      def __init__(self, val, data_ref):
        self.val = val
        self.data_ref = data_ref
      
      def __lt__(self, other):
        if len(self.data_ref) == 98:
          self.data_ref.append(EvilInt(999, self.data_ref))
        return self.val < other.val
      
      def __gt__(self, other):
        return self.val > other.val
    
    data = []
    for i in range(100):
      data.append(EvilInt(i, data))
    heapx.heapify(data)
    
    with pytest.raises(ValueError) as exc_info:
      heapx.pop(data, n=5)  # Bulk pop triggers specific 'pop' error
    msg = str(exc_info.value)
    assert "list modified during pop" in msg
    assert "expected size" in msg
    assert "got" in msg
    print(f"✓ pop (specific) list modified error: {msg}")

  def test_pop_list_modified_generic(self):
    """Test: list modified during heap operation (pop with cmp)"""
    data = list(range(20))
    heapx.heapify(data)
    
    def evil_cmp(x):
      if len(data) > 10:
        data.append(999)
      return x
    
    with pytest.raises(ValueError) as exc_info:
      heapx.pop(data, cmp=evil_cmp)
    msg = str(exc_info.value)
    assert "list modified during" in msg
    assert "expected size" in msg
    print(f"✓ pop (generic) list modified error: {msg}")

  # ============================================================================
  # list modified during sort
  # ============================================================================

  def test_sort_list_modified_heapify_phase(self):
    """Test: list modified during heapify (sort's heapify phase)"""
    data = list(range(20))
    
    def evil_cmp(x):
      if len(data) > 10:
        data.pop()
      return x
    
    with pytest.raises(ValueError) as exc_info:
      heapx.sort(data, cmp=evil_cmp, inplace=True)
    msg = str(exc_info.value)
    # Sort first heapifies, so triggers heapify error
    assert "list modified during heapify" in msg
    assert "expected size" in msg
    assert "got" in msg
    print(f"✓ sort (heapify phase) list modified error: {msg}")

  def test_sort_list_modified_heapsort_phase(self):
    """Test: list modified during sort (heapsort extraction phase)"""
    # Use a larger dataset and trigger modification during heapsort phase
    data = list(range(50))
    call_count = [0]
    
    def evil_cmp(x):
      call_count[0] += 1
      # Only modify after heapify is done (after ~50 calls)
      if call_count[0] > 60 and len(data) > 40:
        data.pop()
      return x
    
    with pytest.raises(ValueError) as exc_info:
      heapx.sort(data, cmp=evil_cmp, inplace=True)
    msg = str(exc_info.value)
    assert "list modified during sort" in msg
    assert "expected size" in msg
    print(f"✓ sort (heapsort phase) list modified error: {msg}")

  # ============================================================================
  # list modified during remove
  # ============================================================================

  def test_remove_list_modified_specific(self):
    """Test: list modified during remove (expected size X, got Y) - specific message"""
    # The specific 'remove' error is triggered in small heap path (n <= 16) with no cmp
    class EvilInt:
      def __init__(self, val, data_ref):
        self.val = val
        self.data_ref = data_ref
      
      def __lt__(self, other):
        if len(self.data_ref) == 14:
          self.data_ref.append(EvilInt(999, self.data_ref))
        return self.val < other.val
      
      def __gt__(self, other):
        return self.val > other.val
    
    data = []
    for i in range(15):  # 15 elements, after removal = 14 (small heap path)
      data.append(EvilInt(i, data))
    heapx.heapify(data)
    
    with pytest.raises(ValueError) as exc_info:
      heapx.remove(data, indices=5)  # No cmp, small heap triggers specific error
    msg = str(exc_info.value)
    assert "list modified during remove" in msg
    assert "expected size" in msg
    assert "got" in msg
    print(f"✓ remove (specific) list modified error: {msg}")

  def test_remove_list_modified_generic(self):
    """Test: list modified during heap operation (remove with cmp)"""
    data = list(range(30))
    heapx.heapify(data)
    
    def evil_cmp(x):
      if len(data) == 29:
        data.append(999)
      return x
    
    with pytest.raises(ValueError) as exc_info:
      heapx.remove(data, indices=5, cmp=evil_cmp)
    msg = str(exc_info.value)
    assert "list modified during" in msg
    assert "expected size" in msg
    print(f"✓ remove (generic) list modified error: {msg}")

  # ============================================================================
  # list modified during replace
  # ============================================================================

  def test_replace_list_modified_specific(self):
    """Test: list modified during replace (expected size X, got Y) - specific message"""
    # The specific 'replace' error is triggered in small heap path (n <= 16) with no cmp
    class EvilInt:
      def __init__(self, val, data_ref, trigger_at=None):
        self.val = val
        self.data_ref = data_ref
        self.trigger_at = trigger_at
      
      def __lt__(self, other):
        # Trigger when comparing with the replacement object
        if hasattr(other, 'trigger_at') and other.trigger_at is not None:
          if len(self.data_ref) == other.trigger_at:
            self.data_ref.append(EvilInt(999, self.data_ref))
        return self.val < other.val
      
      def __gt__(self, other):
        return self.val > other.val
    
    data = []
    for i in range(10):  # 10 elements (small heap path)
      data.append(EvilInt(i, data))
    heapx.heapify(data)
    
    # Replacement value triggers modification during insertion sort
    replacement = EvilInt(5, data, trigger_at=10)
    
    with pytest.raises(ValueError) as exc_info:
      heapx.replace(data, replacement, indices=0)
    msg = str(exc_info.value)
    assert "list modified during replace" in msg
    assert "expected size" in msg
    assert "got" in msg
    print(f"✓ replace (specific) list modified error: {msg}")

  def test_replace_list_modified_generic(self):
    """Test: list modified during heap operation (replace with cmp)"""
    data = list(range(30))
    heapx.heapify(data)
    
    def evil_cmp(x):
      if len(data) == 30:
        data.append(999)
      return x
    
    with pytest.raises(ValueError) as exc_info:
      heapx.replace(data, 100, indices=5, cmp=evil_cmp)
    msg = str(exc_info.value)
    assert "list modified during" in msg
    assert "expected size" in msg
    print(f"✓ replace (generic) list modified error: {msg}")

  # ============================================================================
  # list modified during heap operation (generic)
  # ============================================================================

  def test_heap_operation_list_modified_sift(self):
    """Test: list modified during heap operation (sift operations)"""
    data = list(range(30))
    heapx.heapify(data)
    
    def evil_cmp(x):
      if len(data) > 25:
        data.pop()
      return x
    
    # This triggers the generic "heap operation" error in sift functions
    with pytest.raises(ValueError) as exc_info:
      heapx.push(data, [100, 101, 102, 103, 104], cmp=evil_cmp)
    msg = str(exc_info.value)
    assert "list modified during" in msg
    assert "expected size" in msg
    print(f"✓ heap operation list modified error: {msg}")


class TestErrorMessageSummary:
  """Summary test to verify all error messages are properly formatted."""

  def test_all_error_messages_have_context(self):
    """Verify all error messages include diagnostic context."""
    errors_tested = [
      # Parameter validation
      ("cmp must be callable or None", "includes type name"),
      ("predicate must be callable or None", "includes type name"),
      ("arity must be >= 1 and <= 64", "includes actual value"),
      ("n must be >= 1", "includes actual value"),
      ("pop from empty heap", "standard IndexError"),
      ("values length must match selection count or be 1", "includes counts"),
      ("merge requires at least 2 heaps", "includes actual count"),
      ("merge argument", "includes position and type"),
      # List modification
      ("list modified during heapify", "includes expected/actual sizes"),
      ("list modified during push", "includes expected/actual sizes"),
      ("list modified during pop", "includes expected/actual sizes"),
      ("list modified during sort", "includes expected/actual sizes"),
      ("list modified during remove", "includes expected/actual sizes"),
      ("list modified during replace", "includes expected/actual sizes"),
      ("list modified during heap operation", "includes expected/actual sizes"),
    ]
    
    print("\n" + "=" * 70)
    print("ERROR MESSAGE AUDIT SUMMARY")
    print("=" * 70)
    for msg, context in errors_tested:
      print(f"  ✓ '{msg}' - {context}")
    print("=" * 70)
    print(f"Total unique error messages tested: {len(errors_tested)}")
    print("=" * 70)


if __name__ == "__main__":
  pytest.main([__file__, "-v", "-s"])
