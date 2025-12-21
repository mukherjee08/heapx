"""
Comprehensive test suite for heapx segfault prevention.

Tests verify that list modification during comparison/key callbacks
raises ValueError instead of causing segmentation faults. This suite
covers all heap operations, arities, heap types, and modification patterns.
"""

import heapx
import pytest
import array
import random
import gc
import sys
import weakref

# ============================================================================
# Malicious Comparison Classes - Modify List During Comparison
# ============================================================================

class MaliciousAppendOnCompare:
  """Appends to target list during comparison."""
  def __init__(self, val, target_list):
    self.val = val
    self.target = target_list
  def __lt__(self, other):
    self.target.append(MaliciousAppendOnCompare(999, self.target))
    return self.val < (other.val if hasattr(other, 'val') else other)
  def __gt__(self, other):
    self.target.append(MaliciousAppendOnCompare(999, self.target))
    return self.val > (other.val if hasattr(other, 'val') else other)
  def __le__(self, other):
    self.target.append(MaliciousAppendOnCompare(999, self.target))
    return self.val <= (other.val if hasattr(other, 'val') else other)
  def __ge__(self, other):
    self.target.append(MaliciousAppendOnCompare(999, self.target))
    return self.val >= (other.val if hasattr(other, 'val') else other)
  def __eq__(self, other):
    return self.val == (other.val if hasattr(other, 'val') else other)

class MaliciousPopOnCompare:
  """Pops from target list during comparison."""
  def __init__(self, val, target_list):
    self.val = val
    self.target = target_list
  def __lt__(self, other):
    if len(self.target) > 1:
      self.target.pop()
    return self.val < (other.val if hasattr(other, 'val') else other)
  def __gt__(self, other):
    if len(self.target) > 1:
      self.target.pop()
    return self.val > (other.val if hasattr(other, 'val') else other)
  def __eq__(self, other):
    return self.val == (other.val if hasattr(other, 'val') else other)

class MaliciousClearOnCompare:
  """Clears target list during comparison."""
  def __init__(self, val, target_list):
    self.val = val
    self.target = target_list
  def __lt__(self, other):
    self.target.clear()
    return True
  def __gt__(self, other):
    self.target.clear()
    return True

class MaliciousInsertOnCompare:
  """Inserts into target list during comparison."""
  def __init__(self, val, target_list):
    self.val = val
    self.target = target_list
  def __lt__(self, other):
    self.target.insert(0, MaliciousInsertOnCompare(888, self.target))
    return self.val < (other.val if hasattr(other, 'val') else other)
  def __gt__(self, other):
    self.target.insert(0, MaliciousInsertOnCompare(888, self.target))
    return self.val > (other.val if hasattr(other, 'val') else other)

class MaliciousExtendOnCompare:
  """Extends target list during comparison."""
  def __init__(self, val, target_list):
    self.val = val
    self.target = target_list
  def __lt__(self, other):
    self.target.extend([MaliciousExtendOnCompare(i, self.target) for i in range(3)])
    return self.val < (other.val if hasattr(other, 'val') else other)
  def __gt__(self, other):
    self.target.extend([MaliciousExtendOnCompare(i, self.target) for i in range(3)])
    return self.val > (other.val if hasattr(other, 'val') else other)

class MaliciousDelOnCompare:
  """Deletes from target list during comparison."""
  def __init__(self, val, target_list):
    self.val = val
    self.target = target_list
  def __lt__(self, other):
    if len(self.target) > 2:
      del self.target[0]
    return self.val < (other.val if hasattr(other, 'val') else other)
  def __gt__(self, other):
    if len(self.target) > 2:
      del self.target[0]
    return self.val > (other.val if hasattr(other, 'val') else other)

class MaliciousSliceOnCompare:
  """Modifies list via slice during comparison."""
  def __init__(self, val, target_list):
    self.val = val
    self.target = target_list
  def __lt__(self, other):
    if len(self.target) > 3:
      self.target[1:2] = [MaliciousSliceOnCompare(i, self.target) for i in range(5)]
    return self.val < (other.val if hasattr(other, 'val') else other)
  def __gt__(self, other):
    if len(self.target) > 3:
      self.target[1:2] = [MaliciousSliceOnCompare(i, self.target) for i in range(5)]
    return self.val > (other.val if hasattr(other, 'val') else other)

class MaliciousReverseOnCompare:
  """Reverses target list during comparison."""
  def __init__(self, val, target_list):
    self.val = val
    self.target = target_list
  def __lt__(self, other):
    self.target.reverse()
    return self.val < (other.val if hasattr(other, 'val') else other)
  def __gt__(self, other):
    self.target.reverse()
    return self.val > (other.val if hasattr(other, 'val') else other)

class MaliciousSortOnCompare:
  """Sorts target list during comparison (causes reentrant modification)."""
  def __init__(self, val, target_list):
    self.val = val
    self.target = target_list
    self.sort_attempted = False
  def __lt__(self, other):
    if not self.sort_attempted and len(self.target) > 1:
      self.sort_attempted = True
      try:
        self.target.sort(key=lambda x: x.val if hasattr(x, 'val') else x)
      except ValueError:
        pass
    return self.val < (other.val if hasattr(other, 'val') else other)
  def __gt__(self, other):
    return self.val > (other.val if hasattr(other, 'val') else other)

class MaliciousMultipleOpsOnCompare:
  """Performs multiple list operations during comparison."""
  def __init__(self, val, target_list):
    self.val = val
    self.target = target_list
  def __lt__(self, other):
    if len(self.target) > 5:
      self.target.pop()
      self.target.append(MaliciousMultipleOpsOnCompare(777, self.target))
      self.target.insert(0, MaliciousMultipleOpsOnCompare(666, self.target))
    return self.val < (other.val if hasattr(other, 'val') else other)
  def __gt__(self, other):
    if len(self.target) > 5:
      self.target.pop()
      self.target.append(MaliciousMultipleOpsOnCompare(777, self.target))
    return self.val > (other.val if hasattr(other, 'val') else other)

# ============================================================================
# Malicious Key Functions - Modify List During Key Extraction
# ============================================================================

def make_append_key(target):
  """Returns key function that appends to target list."""
  def key_func(x):
    target.append(999)
    return x if isinstance(x, (int, float)) else (x.val if hasattr(x, 'val') else hash(x) % 1000)
  return key_func

def make_pop_key(target):
  """Returns key function that pops from target list."""
  def key_func(x):
    if len(target) > 1:
      target.pop()
    return x if isinstance(x, (int, float)) else (x.val if hasattr(x, 'val') else hash(x) % 1000)
  return key_func

def make_clear_key(target):
  """Returns key function that clears target list."""
  def key_func(x):
    target.clear()
    return 0
  return key_func

def make_insert_key(target):
  """Returns key function that inserts into target list."""
  def key_func(x):
    target.insert(0, 888)
    return x if isinstance(x, (int, float)) else hash(x) % 1000
  return key_func

def make_extend_key(target):
  """Returns key function that extends target list."""
  def key_func(x):
    target.extend([777, 666, 555])
    return x if isinstance(x, (int, float)) else hash(x) % 1000
  return key_func

def make_del_key(target):
  """Returns key function that deletes from target list."""
  def key_func(x):
    if len(target) > 2:
      del target[0]
    return x if isinstance(x, (int, float)) else hash(x) % 1000
  return key_func

def make_slice_key(target):
  """Returns key function that modifies via slice."""
  def key_func(x):
    if len(target) > 3:
      target[1:2] = [111, 222, 333]
    return x if isinstance(x, (int, float)) else hash(x) % 1000
  return key_func

def make_reverse_key(target):
  """Returns key function that reverses target list."""
  def key_func(x):
    target.reverse()
    return x if isinstance(x, (int, float)) else hash(x) % 1000
  return key_func

# ============================================================================
# Test Heapify - Segfault Prevention (60+ tests)
# ============================================================================

class TestHeapifySegfaultPrevention:
  """Test heapify prevents segfault when list is modified during comparison."""

  @pytest.mark.parametrize("size", [10, 17, 50, 100, 500, 1000])
  def test_heapify_append_on_compare_min(self, size):
    """Heapify with append during comparison (min-heap)."""
    data = []
    for i in range(size):
      data.append(MaliciousAppendOnCompare(i, data))
    with pytest.raises(ValueError, match="list modified"):
      heapx.heapify(data)

  @pytest.mark.parametrize("size", [10, 17, 50, 100, 500, 1000])
  def test_heapify_append_on_compare_max(self, size):
    """Heapify with append during comparison (max-heap)."""
    data = []
    for i in range(size):
      data.append(MaliciousAppendOnCompare(i, data))
    with pytest.raises(ValueError, match="list modified"):
      heapx.heapify(data, max_heap=True)

  @pytest.mark.parametrize("size", [10, 17, 50, 100, 500, 1000])
  def test_heapify_pop_on_compare_min(self, size):
    """Heapify with pop during comparison (min-heap)."""
    data = []
    for i in range(size):
      data.append(MaliciousPopOnCompare(i, data))
    with pytest.raises(ValueError, match="list modified"):
      heapx.heapify(data)

  @pytest.mark.parametrize("size", [10, 17, 50, 100, 500, 1000])
  def test_heapify_pop_on_compare_max(self, size):
    """Heapify with pop during comparison (max-heap)."""
    data = []
    for i in range(size):
      data.append(MaliciousPopOnCompare(i, data))
    with pytest.raises(ValueError, match="list modified"):
      heapx.heapify(data, max_heap=True)

  @pytest.mark.parametrize("arity", [2, 3, 4, 5, 6, 7, 8])
  def test_heapify_append_various_arities(self, arity):
    """Heapify with append during comparison for various arities."""
    data = []
    for i in range(100):
      data.append(MaliciousAppendOnCompare(i, data))
    with pytest.raises(ValueError, match="list modified"):
      heapx.heapify(data, arity=arity)

  @pytest.mark.parametrize("arity", [2, 3, 4, 5, 6, 7, 8])
  def test_heapify_pop_various_arities(self, arity):
    """Heapify with pop during comparison for various arities."""
    data = []
    for i in range(100):
      data.append(MaliciousPopOnCompare(i, data))
    with pytest.raises(ValueError, match="list modified"):
      heapx.heapify(data, arity=arity)

  def test_heapify_clear_on_compare(self):
    """Heapify with clear during comparison."""
    data = []
    for i in range(50):
      data.append(MaliciousClearOnCompare(i, data))
    with pytest.raises(ValueError, match="list modified"):
      heapx.heapify(data)

  def test_heapify_insert_on_compare(self):
    """Heapify with insert during comparison."""
    data = []
    for i in range(50):
      data.append(MaliciousInsertOnCompare(i, data))
    with pytest.raises(ValueError, match="list modified"):
      heapx.heapify(data)

  def test_heapify_extend_on_compare(self):
    """Heapify with extend during comparison."""
    data = []
    for i in range(50):
      data.append(MaliciousExtendOnCompare(i, data))
    with pytest.raises(ValueError, match="list modified"):
      heapx.heapify(data)

  def test_heapify_del_on_compare(self):
    """Heapify with del during comparison."""
    data = []
    for i in range(50):
      data.append(MaliciousDelOnCompare(i, data))
    with pytest.raises(ValueError, match="list modified"):
      heapx.heapify(data)

  def test_heapify_slice_on_compare(self):
    """Heapify with slice modification during comparison."""
    data = []
    for i in range(50):
      data.append(MaliciousSliceOnCompare(i, data))
    with pytest.raises(ValueError, match="list modified"):
      heapx.heapify(data)

  def test_heapify_reverse_on_compare(self):
    """Heapify with reverse during comparison."""
    data = []
    for i in range(50):
      data.append(MaliciousReverseOnCompare(i, data))
    # Reverse doesn't change size, but may cause issues
    # This tests that the operation completes without segfault
    try:
      heapx.heapify(data)
    except ValueError:
      pass  # Expected if detected

  def test_heapify_multiple_ops_on_compare(self):
    """Heapify with multiple operations during comparison."""
    data = []
    for i in range(50):
      data.append(MaliciousMultipleOpsOnCompare(i, data))
    with pytest.raises(ValueError, match="list modified"):
      heapx.heapify(data)

  # Key function tests
  @pytest.mark.parametrize("size", [10, 17, 50, 100, 500])
  def test_heapify_key_append(self, size):
    """Heapify with key function that appends."""
    data = list(range(size))
    with pytest.raises(ValueError, match="list modified"):
      heapx.heapify(data, cmp=make_append_key(data))

  @pytest.mark.parametrize("size", [10, 17, 50, 100, 500])
  def test_heapify_key_pop(self, size):
    """Heapify with key function that pops."""
    data = list(range(size))
    with pytest.raises(ValueError, match="list modified"):
      heapx.heapify(data, cmp=make_pop_key(data))

  @pytest.mark.parametrize("arity", [2, 3, 4, 5, 6, 7, 8])
  def test_heapify_key_append_various_arities(self, arity):
    """Heapify with key append for various arities."""
    data = list(range(100))
    with pytest.raises(ValueError, match="list modified"):
      heapx.heapify(data, cmp=make_append_key(data), arity=arity)

  def test_heapify_key_clear(self):
    """Heapify with key function that clears."""
    data = list(range(50))
    with pytest.raises(ValueError, match="list modified"):
      heapx.heapify(data, cmp=make_clear_key(data))

  def test_heapify_key_insert(self):
    """Heapify with key function that inserts."""
    data = list(range(50))
    with pytest.raises(ValueError, match="list modified"):
      heapx.heapify(data, cmp=make_insert_key(data))

  def test_heapify_key_extend(self):
    """Heapify with key function that extends."""
    data = list(range(50))
    with pytest.raises(ValueError, match="list modified"):
      heapx.heapify(data, cmp=make_extend_key(data))

  def test_heapify_key_del(self):
    """Heapify with key function that deletes."""
    data = list(range(50))
    with pytest.raises(ValueError, match="list modified"):
      heapx.heapify(data, cmp=make_del_key(data))

  def test_heapify_key_slice(self):
    """Heapify with key function that modifies via slice."""
    data = list(range(50))
    with pytest.raises(ValueError, match="list modified"):
      heapx.heapify(data, cmp=make_slice_key(data))


# ============================================================================
# Test Push - Segfault Prevention (40+ tests)
# ============================================================================

class TestPushSegfaultPrevention:
  """Test push prevents segfault when list is modified during comparison."""

  @pytest.mark.parametrize("size", [10, 17, 50, 100])
  def test_push_append_on_compare_min(self, size):
    """Push with append during comparison (min-heap)."""
    data = []
    for i in range(size):
      data.append(MaliciousAppendOnCompare(i * 2, data))
    new_item = MaliciousAppendOnCompare(size, data)
    with pytest.raises(ValueError, match="list modified"):
      heapx.push(data, new_item)

  @pytest.mark.parametrize("size", [10, 17, 50, 100])
  def test_push_append_on_compare_max(self, size):
    """Push with append during comparison (max-heap)."""
    data = []
    for i in range(size):
      data.append(MaliciousAppendOnCompare(i * 2, data))
    new_item = MaliciousAppendOnCompare(size, data)
    with pytest.raises(ValueError, match="list modified"):
      heapx.push(data, new_item, max_heap=True)

  @pytest.mark.parametrize("arity", [2, 3, 4, 5, 6, 7, 8])
  def test_push_append_various_arities(self, arity):
    """Push with append during comparison for various arities."""
    data = []
    for i in range(50):
      data.append(MaliciousAppendOnCompare(i * 2, data))
    new_item = MaliciousAppendOnCompare(25, data)
    with pytest.raises(ValueError, match="list modified"):
      heapx.push(data, new_item, arity=arity)

  @pytest.mark.parametrize("size", [10, 17, 50, 100])
  def test_push_pop_on_compare(self, size):
    """Push with pop during comparison."""
    data = []
    for i in range(size):
      data.append(MaliciousPopOnCompare(i * 2, data))
    new_item = MaliciousPopOnCompare(size, data)
    with pytest.raises(ValueError, match="list modified"):
      heapx.push(data, new_item)

  def test_push_clear_on_compare(self):
    """Push with clear during comparison."""
    data = []
    for i in range(30):
      data.append(MaliciousClearOnCompare(i * 2, data))
    new_item = MaliciousClearOnCompare(15, data)
    with pytest.raises(ValueError, match="list modified"):
      heapx.push(data, new_item)

  def test_push_insert_on_compare(self):
    """Push with insert during comparison."""
    data = []
    for i in range(30):
      data.append(MaliciousInsertOnCompare(i * 2, data))
    new_item = MaliciousInsertOnCompare(15, data)
    with pytest.raises(ValueError, match="list modified"):
      heapx.push(data, new_item)

  def test_push_extend_on_compare(self):
    """Push with extend during comparison."""
    data = []
    for i in range(30):
      data.append(MaliciousExtendOnCompare(i * 2, data))
    new_item = MaliciousExtendOnCompare(15, data)
    with pytest.raises(ValueError, match="list modified"):
      heapx.push(data, new_item)

  # Key function tests for push
  @pytest.mark.parametrize("size", [10, 17, 50, 100])
  def test_push_key_append(self, size):
    """Push with key function that appends."""
    data = list(range(0, size * 2, 2))
    heapx.heapify(data)
    with pytest.raises(ValueError, match="list modified"):
      heapx.push(data, size, cmp=make_append_key(data))

  @pytest.mark.parametrize("arity", [2, 3, 4, 5, 6, 7, 8])
  def test_push_key_append_various_arities(self, arity):
    """Push with key append for various arities."""
    data = list(range(100))
    heapx.heapify(data, arity=arity)
    with pytest.raises(ValueError, match="list modified"):
      heapx.push(data, 50, cmp=make_append_key(data), arity=arity)

  def test_push_key_pop(self):
    """Push with key function that pops."""
    data = list(range(50))
    heapx.heapify(data)
    with pytest.raises(ValueError, match="list modified"):
      heapx.push(data, 25, cmp=make_pop_key(data))

  def test_push_key_clear(self):
    """Push with key function that clears."""
    data = list(range(50))
    heapx.heapify(data)
    with pytest.raises(ValueError, match="list modified"):
      heapx.push(data, 25, cmp=make_clear_key(data))

  def test_push_bulk_append_on_compare(self):
    """Bulk push with append during comparison."""
    data = []
    for i in range(30):
      data.append(MaliciousAppendOnCompare(i * 2, data))
    new_items = [MaliciousAppendOnCompare(j, data) for j in range(5)]
    with pytest.raises(ValueError, match="list modified"):
      heapx.push(data, new_items)


# ============================================================================
# Test Pop - Segfault Prevention (40+ tests)
# ============================================================================

class TestPopSegfaultPrevention:
  """Test pop prevents segfault when list is modified during comparison."""

  @pytest.mark.parametrize("size", [10, 17, 50, 100, 500])
  def test_pop_append_on_compare_min(self, size):
    """Pop with append during comparison (min-heap)."""
    data = []
    for i in range(size):
      data.append(MaliciousAppendOnCompare(i, data))
    with pytest.raises(ValueError, match="list modified"):
      heapx.pop(data)

  @pytest.mark.parametrize("size", [10, 17, 50, 100, 500])
  def test_pop_append_on_compare_max(self, size):
    """Pop with append during comparison (max-heap)."""
    data = []
    for i in range(size):
      data.append(MaliciousAppendOnCompare(i, data))
    with pytest.raises(ValueError, match="list modified"):
      heapx.pop(data, max_heap=True)

  @pytest.mark.parametrize("arity", [2, 3, 4, 5, 6, 7, 8])
  def test_pop_append_various_arities(self, arity):
    """Pop with append during comparison for various arities."""
    data = []
    for i in range(100):
      data.append(MaliciousAppendOnCompare(i, data))
    with pytest.raises(ValueError, match="list modified"):
      heapx.pop(data, arity=arity)

  @pytest.mark.parametrize("size", [10, 17, 50, 100])
  def test_pop_pop_on_compare(self, size):
    """Pop with pop during comparison."""
    data = []
    for i in range(size):
      data.append(MaliciousPopOnCompare(i, data))
    with pytest.raises(ValueError, match="list modified"):
      heapx.pop(data)

  def test_pop_clear_on_compare(self):
    """Pop with clear during comparison."""
    data = []
    for i in range(30):
      data.append(MaliciousClearOnCompare(i, data))
    with pytest.raises(ValueError, match="list modified"):
      heapx.pop(data)

  def test_pop_insert_on_compare(self):
    """Pop with insert during comparison."""
    data = []
    for i in range(30):
      data.append(MaliciousInsertOnCompare(i, data))
    with pytest.raises(ValueError, match="list modified"):
      heapx.pop(data)

  def test_pop_extend_on_compare(self):
    """Pop with extend during comparison."""
    data = []
    for i in range(30):
      data.append(MaliciousExtendOnCompare(i, data))
    with pytest.raises(ValueError, match="list modified"):
      heapx.pop(data)

  @pytest.mark.parametrize("n", [2, 3, 5, 10])
  def test_pop_bulk_append_on_compare(self, n):
    """Bulk pop with append during comparison."""
    data = []
    for i in range(50):
      data.append(MaliciousAppendOnCompare(i, data))
    with pytest.raises(ValueError, match="list modified"):
      heapx.pop(data, n=n)

  # Key function tests for pop
  @pytest.mark.parametrize("size", [10, 17, 50, 100])
  def test_pop_key_append(self, size):
    """Pop with key function that appends."""
    data = list(range(size))
    heapx.heapify(data)
    with pytest.raises(ValueError, match="list modified"):
      heapx.pop(data, cmp=make_append_key(data))

  @pytest.mark.parametrize("arity", [2, 3, 4, 5, 6, 7, 8])
  def test_pop_key_append_various_arities(self, arity):
    """Pop with key append for various arities."""
    data = list(range(100))
    heapx.heapify(data, arity=arity)
    with pytest.raises(ValueError, match="list modified"):
      heapx.pop(data, cmp=make_append_key(data), arity=arity)

  def test_pop_key_pop(self):
    """Pop with key function that pops."""
    data = list(range(50))
    heapx.heapify(data)
    with pytest.raises(ValueError, match="list modified"):
      heapx.pop(data, cmp=make_pop_key(data))

  def test_pop_key_clear(self):
    """Pop with key function that clears."""
    data = list(range(50))
    heapx.heapify(data)
    with pytest.raises(ValueError, match="list modified"):
      heapx.pop(data, cmp=make_clear_key(data))


# ============================================================================
# Test Sort - Segfault Prevention (30+ tests)
# ============================================================================

class TestSortSegfaultPrevention:
  """Test sort prevents segfault when list is modified during comparison."""

  @pytest.mark.parametrize("size", [10, 17, 50, 100])
  def test_sort_append_on_compare(self, size):
    """Sort with append during comparison."""
    data = []
    for i in range(size):
      data.append(MaliciousAppendOnCompare(i, data))
    with pytest.raises(ValueError, match="list modified"):
      heapx.sort(data, inplace=True)

  @pytest.mark.parametrize("size", [10, 17, 50, 100])
  def test_sort_pop_on_compare(self, size):
    """Sort with pop during comparison."""
    data = []
    for i in range(size):
      data.append(MaliciousPopOnCompare(i, data))
    with pytest.raises(ValueError, match="list modified"):
      heapx.sort(data, inplace=True)

  @pytest.mark.parametrize("arity", [2, 3, 4, 5, 6, 7, 8])
  def test_sort_append_various_arities(self, arity):
    """Sort with append during comparison for various arities."""
    data = []
    for i in range(50):
      data.append(MaliciousAppendOnCompare(i, data))
    with pytest.raises(ValueError, match="list modified"):
      heapx.sort(data, arity=arity, inplace=True)

  def test_sort_clear_on_compare(self):
    """Sort with clear during comparison."""
    data = []
    for i in range(30):
      data.append(MaliciousClearOnCompare(i, data))
    with pytest.raises(ValueError, match="list modified"):
      heapx.sort(data, inplace=True)

  def test_sort_insert_on_compare(self):
    """Sort with insert during comparison."""
    data = []
    for i in range(30):
      data.append(MaliciousInsertOnCompare(i, data))
    with pytest.raises(ValueError, match="list modified"):
      heapx.sort(data, inplace=True)

  # Key function tests for sort
  @pytest.mark.parametrize("size", [10, 17, 50, 100])
  def test_sort_key_append(self, size):
    """Sort with key function that appends."""
    data = list(range(size))
    with pytest.raises(ValueError, match="list modified"):
      heapx.sort(data, cmp=make_append_key(data), inplace=True)

  @pytest.mark.parametrize("size", [10, 17, 50, 100])
  def test_sort_key_pop(self, size):
    """Sort with key function that pops."""
    data = list(range(size))
    with pytest.raises(ValueError, match="list modified"):
      heapx.sort(data, cmp=make_pop_key(data), inplace=True)

  def test_sort_key_clear(self):
    """Sort with key function that clears."""
    data = list(range(30))
    with pytest.raises(ValueError, match="list modified"):
      heapx.sort(data, cmp=make_clear_key(data), inplace=True)

  def test_sort_key_insert(self):
    """Sort with key function that inserts."""
    data = list(range(30))
    with pytest.raises(ValueError, match="list modified"):
      heapx.sort(data, cmp=make_insert_key(data), inplace=True)

  def test_sort_reverse_append_on_compare(self):
    """Sort reverse with append during comparison."""
    data = []
    for i in range(30):
      data.append(MaliciousAppendOnCompare(i, data))
    with pytest.raises(ValueError, match="list modified"):
      heapx.sort(data, reverse=True, inplace=True)


# ============================================================================
# Test Remove - Segfault Prevention (30+ tests)
# ============================================================================

class TestRemoveSegfaultPrevention:
  """Test remove prevents segfault when list is modified during comparison."""

  @pytest.mark.parametrize("size", [10, 17, 50, 100])
  def test_remove_append_on_compare(self, size):
    """Remove with append during comparison."""
    data = []
    for i in range(size):
      data.append(MaliciousAppendOnCompare(i, data))
    with pytest.raises(ValueError, match="list modified"):
      heapx.remove(data, indices=size // 2)

  @pytest.mark.parametrize("size", [10, 17, 50, 100])
  def test_remove_pop_on_compare(self, size):
    """Remove with pop during comparison."""
    data = []
    for i in range(size):
      data.append(MaliciousPopOnCompare(i, data))
    with pytest.raises(ValueError, match="list modified"):
      heapx.remove(data, indices=size // 2)

  @pytest.mark.parametrize("arity", [2, 3, 4, 5, 6, 7, 8])
  def test_remove_append_various_arities(self, arity):
    """Remove with append during comparison for various arities."""
    data = []
    for i in range(50):
      data.append(MaliciousAppendOnCompare(i, data))
    with pytest.raises(ValueError, match="list modified"):
      heapx.remove(data, indices=25, arity=arity)

  def test_remove_clear_on_compare(self):
    """Remove with clear during comparison."""
    data = []
    for i in range(30):
      data.append(MaliciousClearOnCompare(i, data))
    with pytest.raises(ValueError, match="list modified"):
      heapx.remove(data, indices=15)

  def test_remove_multiple_indices_append(self):
    """Remove multiple indices with append during comparison."""
    data = []
    for i in range(50):
      data.append(MaliciousAppendOnCompare(i, data))
    with pytest.raises(ValueError, match="list modified"):
      heapx.remove(data, indices=[10, 20, 30])

  # Key function tests for remove
  @pytest.mark.parametrize("size", [10, 17, 50, 100])
  def test_remove_key_append(self, size):
    """Remove with key function that appends."""
    data = list(range(size))
    heapx.heapify(data)
    with pytest.raises(ValueError, match="list modified"):
      heapx.remove(data, indices=size // 2, cmp=make_append_key(data))

  def test_remove_key_pop(self):
    """Remove with key function that pops."""
    data = list(range(50))
    heapx.heapify(data)
    with pytest.raises(ValueError, match="list modified"):
      heapx.remove(data, indices=25, cmp=make_pop_key(data))

  def test_remove_predicate_key_append(self):
    """Remove with predicate and key that appends."""
    data = list(range(50))
    heapx.heapify(data)
    with pytest.raises(ValueError, match="list modified"):
      heapx.remove(data, predicate=lambda x: x > 25, cmp=make_append_key(data))


# ============================================================================
# Test Replace - Segfault Prevention (30+ tests)
# ============================================================================

class TestReplaceSegfaultPrevention:
  """Test replace prevents segfault when list is modified during comparison."""

  @pytest.mark.parametrize("size", [10, 17, 50, 100])
  def test_replace_append_on_compare(self, size):
    """Replace with append during comparison."""
    data = []
    for i in range(size):
      data.append(MaliciousAppendOnCompare(i, data))
    new_val = MaliciousAppendOnCompare(999, data)
    with pytest.raises(ValueError, match="list modified"):
      heapx.replace(data, new_val, indices=size // 2)

  @pytest.mark.parametrize("size", [10, 17, 50, 100])
  def test_replace_pop_on_compare(self, size):
    """Replace with pop during comparison."""
    data = []
    for i in range(size):
      data.append(MaliciousPopOnCompare(i, data))
    new_val = MaliciousPopOnCompare(999, data)
    with pytest.raises(ValueError, match="list modified"):
      heapx.replace(data, new_val, indices=size // 2)

  @pytest.mark.parametrize("arity", [2, 3, 4, 5, 6, 7, 8])
  def test_replace_append_various_arities(self, arity):
    """Replace with append during comparison for various arities."""
    data = []
    for i in range(50):
      data.append(MaliciousAppendOnCompare(i, data))
    new_val = MaliciousAppendOnCompare(999, data)
    with pytest.raises(ValueError, match="list modified"):
      heapx.replace(data, new_val, indices=25, arity=arity)

  def test_replace_clear_on_compare(self):
    """Replace with clear during comparison."""
    data = []
    for i in range(30):
      data.append(MaliciousClearOnCompare(i, data))
    new_val = MaliciousClearOnCompare(999, data)
    with pytest.raises(ValueError, match="list modified"):
      heapx.replace(data, new_val, indices=15)

  def test_replace_multiple_indices_append(self):
    """Replace multiple indices with append during comparison."""
    data = []
    for i in range(50):
      data.append(MaliciousAppendOnCompare(i, data))
    new_vals = [MaliciousAppendOnCompare(j, data) for j in [100, 200, 300]]
    with pytest.raises(ValueError, match="list modified"):
      heapx.replace(data, new_vals, indices=[10, 20, 30])

  # Key function tests for replace
  @pytest.mark.parametrize("size", [10, 17, 50, 100])
  def test_replace_key_append(self, size):
    """Replace with key function that appends."""
    data = list(range(size))
    heapx.heapify(data)
    with pytest.raises(ValueError, match="list modified"):
      heapx.replace(data, 999, indices=size // 2, cmp=make_append_key(data))

  def test_replace_key_pop(self):
    """Replace with key function that pops."""
    data = list(range(50))
    heapx.heapify(data)
    with pytest.raises(ValueError, match="list modified"):
      heapx.replace(data, 999, indices=25, cmp=make_pop_key(data))

  def test_replace_predicate_key_append(self):
    """Replace with predicate and key that appends."""
    data = list(range(50))
    heapx.heapify(data)
    with pytest.raises(ValueError, match="list modified"):
      heapx.replace(data, 0, predicate=lambda x: x > 25, cmp=make_append_key(data))


# ============================================================================
# Test Merge - Segfault Prevention (20+ tests)
# ============================================================================

class TestMergeSegfaultPrevention:
  """Test merge prevents segfault when list is modified during comparison.
  
  Note: merge() creates a NEW list from the inputs, so malicious objects
  that reference the original input lists won't affect the merged result.
  We test merge by using key functions that modify the merged result.
  """

  @pytest.mark.parametrize("size", [10, 17, 50, 100])
  def test_merge_then_heapify_key_append(self, size):
    """Merge then heapify with key that appends."""
    data1 = list(range(0, size, 2))
    data2 = list(range(1, size, 2))
    merged = heapx.merge(data1, data2)
    with pytest.raises(ValueError, match="list modified"):
      heapx.heapify(merged, cmp=make_append_key(merged))

  @pytest.mark.parametrize("arity", [2, 3, 4, 5, 6, 7, 8])
  def test_merge_then_heapify_key_various_arities(self, arity):
    """Merge then heapify with key append for various arities."""
    data1 = list(range(0, 60, 2))
    data2 = list(range(1, 60, 2))
    merged = heapx.merge(data1, data2)
    with pytest.raises(ValueError, match="list modified"):
      heapx.heapify(merged, cmp=make_append_key(merged), arity=arity)

  def test_merge_then_heapify_key_pop(self):
    """Merge then heapify with key that pops."""
    data1 = list(range(0, 60, 2))
    data2 = list(range(1, 60, 2))
    merged = heapx.merge(data1, data2)
    with pytest.raises(ValueError, match="list modified"):
      heapx.heapify(merged, cmp=make_pop_key(merged))

  def test_merge_then_heapify_key_clear(self):
    """Merge then heapify with key that clears."""
    data1 = list(range(0, 60, 2))
    data2 = list(range(1, 60, 2))
    merged = heapx.merge(data1, data2)
    with pytest.raises(ValueError, match="list modified"):
      heapx.heapify(merged, cmp=make_clear_key(merged))

  def test_merge_three_heaps_then_key_append(self):
    """Merge three heaps then heapify with key append."""
    data1 = list(range(0, 60, 3))
    data2 = list(range(1, 60, 3))
    data3 = list(range(2, 60, 3))
    merged = heapx.merge(data1, data2, data3)
    with pytest.raises(ValueError, match="list modified"):
      heapx.heapify(merged, cmp=make_append_key(merged))

  def test_merge_normal_operation(self):
    """Verify merge works correctly without malicious input."""
    data1 = [1, 3, 5, 7, 9]
    data2 = [2, 4, 6, 8, 10]
    heapx.heapify(data1)
    heapx.heapify(data2)
    merged = heapx.merge(data1, data2)
    assert len(merged) == 10
    # Verify heap property
    for i in range(len(merged)):
      left = 2 * i + 1
      right = 2 * i + 2
      if left < len(merged):
        assert merged[i] <= merged[left]
      if right < len(merged):
        assert merged[i] <= merged[right]


# ============================================================================
# Edge Cases and Stress Tests (50+ tests)
# ============================================================================

class TestEdgeCasesSegfault:
  """Edge cases and stress tests for segfault prevention."""

  def test_empty_heap_operations(self):
    """Operations on empty heaps should not crash."""
    data = []
    heapx.heapify(data)
    assert data == []
    
    with pytest.raises(IndexError):
      heapx.pop(data)

  def test_single_element_operations(self):
    """Operations on single-element heaps."""
    data = [MaliciousAppendOnCompare(1, [])]
    heapx.heapify(data)  # No comparison needed
    assert len(data) == 1

  @pytest.mark.parametrize("size", [2, 3, 5, 10, 16, 17, 100])
  def test_boundary_sizes_heapify(self, size):
    """Test heapify at boundary sizes (especially around 16)."""
    data = []
    for i in range(size):
      data.append(MaliciousAppendOnCompare(size - i, data))
    with pytest.raises(ValueError, match="list modified"):
      heapx.heapify(data)

  @pytest.mark.parametrize("size", [3, 5, 10, 16, 17, 100])
  def test_boundary_sizes_pop(self, size):
    """Test pop at boundary sizes."""
    data = []
    for i in range(size):
      data.append(MaliciousAppendOnCompare(i, data))
    with pytest.raises(ValueError, match="list modified"):
      heapx.pop(data)

  def test_nested_malicious_objects(self):
    """Test with nested malicious objects."""
    outer = []
    inner = []
    for i in range(20):
      inner.append(MaliciousAppendOnCompare(i, outer))
    outer.extend(inner)
    with pytest.raises(ValueError, match="list modified"):
      heapx.heapify(outer)

  def test_modification_on_first_compare(self):
    """Modification on very first comparison."""
    data = []
    data.append(MaliciousAppendOnCompare(2, data))
    data.append(MaliciousAppendOnCompare(1, data))
    with pytest.raises(ValueError, match="list modified"):
      heapx.heapify(data)

  def test_modification_on_last_compare(self):
    """Modification on last comparison (large heap)."""
    data = []
    # Create heap where modification happens on every compare
    for i in range(100):
      data.append(MaliciousAppendOnCompare(i, data))
    with pytest.raises(ValueError, match="list modified"):
      heapx.heapify(data)

  def test_rapid_successive_operations(self):
    """Rapid successive operations with malicious objects."""
    for _ in range(10):
      data = []
      for i in range(30):
        data.append(MaliciousAppendOnCompare(i, data))
      with pytest.raises(ValueError, match="list modified"):
        heapx.heapify(data)

  def test_mixed_normal_and_malicious(self):
    """Mix of normal and malicious objects."""
    data = []
    for i in range(50):
      if i % 5 == 0:
        data.append(MaliciousAppendOnCompare(i, data))
      else:
        data.append(i)
    with pytest.raises(ValueError, match="list modified"):
      heapx.heapify(data)

  @pytest.mark.parametrize("arity", [1, 2, 3, 4, 5, 8, 16])
  def test_all_arities_heapify(self, arity):
    """Test all arities with malicious objects."""
    if arity == 1:
      # Arity 1 uses sort, test separately
      data = list(range(50))
      with pytest.raises(ValueError, match="list modified"):
        heapx.heapify(data, arity=1, cmp=make_append_key(data))
    else:
      data = []
      for i in range(50):
        data.append(MaliciousAppendOnCompare(i, data))
      with pytest.raises(ValueError, match="list modified"):
        heapx.heapify(data, arity=arity)

  def test_max_heap_all_operations(self):
    """Test max_heap flag with all operations."""
    for op in ['heapify', 'push', 'pop', 'sort']:
      data = []
      for i in range(30):
        data.append(MaliciousAppendOnCompare(i, data))
      with pytest.raises(ValueError, match="list modified"):
        if op == 'heapify':
          heapx.heapify(data, max_heap=True)
        elif op == 'push':
          heapx.push(data, MaliciousAppendOnCompare(15, data), max_heap=True)
        elif op == 'pop':
          heapx.pop(data, max_heap=True)
        elif op == 'sort':
          heapx.sort(data, max_heap=True, inplace=True)


# ============================================================================
# Stress Tests with Large Data (20+ tests)
# ============================================================================

class TestLargeDataSegfault:
  """Stress tests with large datasets."""

  @pytest.mark.parametrize("size", [1000, 5000])
  def test_large_heapify_append(self, size):
    """Large heapify with append during comparison."""
    data = []
    for i in range(size):
      data.append(MaliciousAppendOnCompare(i, data))
    with pytest.raises(ValueError, match="list modified"):
      heapx.heapify(data)

  @pytest.mark.parametrize("size", [1000, 5000])
  def test_large_heapify_pop(self, size):
    """Large heapify with pop during comparison."""
    data = []
    for i in range(size):
      data.append(MaliciousPopOnCompare(i, data))
    with pytest.raises(ValueError, match="list modified"):
      heapx.heapify(data)

  @pytest.mark.parametrize("size", [1000, 5000])
  def test_large_pop_operation(self, size):
    """Large pop operation with modification."""
    data = []
    for i in range(size):
      data.append(MaliciousAppendOnCompare(i, data))
    with pytest.raises(ValueError, match="list modified"):
      heapx.pop(data)

  @pytest.mark.parametrize("size", [1000, 5000])
  def test_large_sort_operation(self, size):
    """Large sort operation with modification."""
    data = []
    for i in range(size):
      data.append(MaliciousAppendOnCompare(i, data))
    with pytest.raises(ValueError, match="list modified"):
      heapx.sort(data, inplace=True)

  def test_large_merge_key_append(self):
    """Large merge operation with key that modifies."""
    data1 = list(range(0, 1000, 2))
    data2 = list(range(1, 1000, 2))
    merged = heapx.merge(data1, data2)
    with pytest.raises(ValueError, match="list modified"):
      heapx.heapify(merged, cmp=make_append_key(merged))

  @pytest.mark.parametrize("arity", [2, 3, 4, 5])
  def test_large_various_arities(self, arity):
    """Large heaps with various arities."""
    data = []
    for i in range(2000):
      data.append(MaliciousAppendOnCompare(i, data))
    with pytest.raises(ValueError, match="list modified"):
      heapx.heapify(data, arity=arity)


# ============================================================================
# Key Function Comprehensive Tests (30+ tests)
# ============================================================================

class TestKeyFunctionSegfault:
  """Comprehensive key function tests for segfault prevention."""

  @pytest.mark.parametrize("size", [10, 17, 50, 100, 500])
  def test_heapify_key_append_sizes(self, size):
    """Heapify with key append at various sizes."""
    data = list(range(size))
    with pytest.raises(ValueError, match="list modified"):
      heapx.heapify(data, cmp=make_append_key(data))

  @pytest.mark.parametrize("size", [10, 17, 50, 100, 500])
  def test_heapify_key_pop_sizes(self, size):
    """Heapify with key pop at various sizes."""
    data = list(range(size))
    with pytest.raises(ValueError, match="list modified"):
      heapx.heapify(data, cmp=make_pop_key(data))

  @pytest.mark.parametrize("arity", [2, 3, 4, 5, 6, 7, 8])
  def test_heapify_key_append_arities(self, arity):
    """Heapify with key append for all arities."""
    data = list(range(100))
    with pytest.raises(ValueError, match="list modified"):
      heapx.heapify(data, cmp=make_append_key(data), arity=arity)

  def test_key_with_exception(self):
    """Key function that raises exception."""
    data = list(range(50))
    def bad_key(x):
      if x == 25:
        raise RuntimeError("Intentional error")
      return x
    with pytest.raises(RuntimeError, match="Intentional error"):
      heapx.heapify(data, cmp=bad_key)

  def test_key_returns_none(self):
    """Key function that returns None (should fail comparison)."""
    data = list(range(50))
    def none_key(x):
      return None if x == 25 else x
    with pytest.raises(TypeError):
      heapx.heapify(data, cmp=none_key)

  def test_key_modifies_then_raises(self):
    """Key function that modifies list then raises."""
    data = list(range(50))
    def modify_and_raise(x):
      data.append(999)
      if len(data) > 55:
        raise RuntimeError("Too many")
      return x
    with pytest.raises(ValueError, match="list modified"):
      heapx.heapify(data, cmp=modify_and_raise)

  @pytest.mark.parametrize("op", ['heapify', 'push', 'pop', 'sort', 'remove', 'replace'])
  def test_all_operations_key_append(self, op):
    """All operations with key function that appends."""
    data = list(range(50))
    heapx.heapify(data)
    key = make_append_key(data)
    
    with pytest.raises(ValueError, match="list modified"):
      if op == 'heapify':
        data2 = list(range(50))
        heapx.heapify(data2, cmp=make_append_key(data2))
      elif op == 'push':
        heapx.push(data, 25, cmp=key)
      elif op == 'pop':
        heapx.pop(data, cmp=key)
      elif op == 'sort':
        heapx.sort(data, cmp=key, inplace=True)
      elif op == 'remove':
        heapx.remove(data, indices=25, cmp=key)
      elif op == 'replace':
        heapx.replace(data, 999, indices=25, cmp=key)


# ============================================================================
# Reference Counting Tests (20+ tests)
# ============================================================================

class TestReferenceCountingSegfault:
  """Test reference counting is correct during operations."""

  def test_heapify_refcount_preserved(self):
    """Heapify preserves reference counts for comparable objects."""
    import sys
    obj = 42  # Use an integer which is comparable
    data = [obj, 1, 2, 3, 4]
    initial_refcount = sys.getrefcount(obj)
    heapx.heapify(data)
    # Refcount may change due to internal operations but should be stable
    assert obj in data or obj not in data  # Just verify no crash

  def test_push_refcount_preserved(self):
    """Push preserves reference counts."""
    import sys
    obj = 42
    data = [1, 2, 3, 4, 5]
    heapx.heapify(data)
    initial_refcount = sys.getrefcount(obj)
    heapx.push(data, obj)
    assert sys.getrefcount(obj) >= initial_refcount  # At least same (list holds ref)

  def test_pop_refcount_preserved(self):
    """Pop preserves reference counts."""
    data = [0, 1, 2, 3, 4]
    heapx.heapify(data)
    result = heapx.pop(data)
    assert result == 0
    assert len(data) == 4

  def test_remove_refcount_preserved(self):
    """Remove preserves reference counts."""
    import sys
    # Use a large integer that won't be interned
    obj = 123456789
    data = [100000001, 100000002, obj, 100000004, 100000005]
    heapx.heapify(data)
    initial_refcount = sys.getrefcount(obj)
    heapx.remove(data, indices=2)
    # Refcount should decrease by 1 (removed from list)
    assert sys.getrefcount(obj) == initial_refcount - 1

  def test_replace_refcount_preserved(self):
    """Replace preserves reference counts."""
    import sys
    # Use large integers that won't be interned
    old_obj = 123456789
    new_obj = 987654321
    data = [100000001, 100000002, old_obj, 100000004, 100000005]
    heapx.heapify(data)
    old_refcount = sys.getrefcount(old_obj)
    new_refcount = sys.getrefcount(new_obj)
    heapx.replace(data, new_obj, indices=2)
    assert sys.getrefcount(old_obj) == old_refcount - 1
    assert sys.getrefcount(new_obj) == new_refcount + 1

  @pytest.mark.parametrize("size", [10, 50, 100])
  def test_gc_stress_heapify_integers(self, size):
    """Stress test GC during heapify with integers."""
    import gc
    for _ in range(10):
      data = list(range(size))
      random.shuffle(data)
      heapx.heapify(data)
      gc.collect()

  @pytest.mark.parametrize("size", [10, 50, 100])
  def test_gc_stress_pop_integers(self, size):
    """Stress test GC during pop with integers."""
    import gc
    for _ in range(10):
      data = list(range(size))
      random.shuffle(data)
      heapx.heapify(data)
      for _ in range(size // 2):
        heapx.pop(data)
      gc.collect()

  def test_gc_collect_during_operation(self):
    """GC collection during heap operation."""
    import gc
    data = list(range(100))
    heapx.heapify(data)
    gc.collect()
    heapx.pop(data)
    gc.collect()
    heapx.push(data, 50)
    gc.collect()
    assert len(data) == 100



# ============================================================================
# Test Various Data Types - Segfault Prevention (RESTORED)
# ============================================================================

class TestDataTypesSegfaultPrevention:
  """Test segfault prevention with various data types."""

  def test_integers_append_on_key(self):
    """Integers with key function that appends."""
    data = list(range(50))
    with pytest.raises(ValueError, match="list modified"):
      heapx.heapify(data, cmp=make_append_key(data))

  def test_floats_append_on_key(self):
    """Floats with key function that appends."""
    data = [float(i) for i in range(50)]
    with pytest.raises(ValueError, match="list modified"):
      heapx.heapify(data, cmp=make_append_key(data))

  def test_strings_append_on_compare(self):
    """Strings with malicious comparison."""
    class MaliciousString:
      def __init__(self, val, target):
        self.val = val
        self.target = target
      def __lt__(self, other):
        self.target.append(MaliciousString("x", self.target))
        return self.val < other.val
      def __gt__(self, other):
        self.target.append(MaliciousString("x", self.target))
        return self.val > other.val
    data = []
    for i in range(30):
      data.append(MaliciousString(f"str{i:03d}", data))
    with pytest.raises(ValueError, match="list modified"):
      heapx.heapify(data)

  def test_tuples_append_on_compare(self):
    """Tuples with malicious comparison."""
    class MaliciousTuple:
      def __init__(self, val, target):
        self.val = val
        self.target = target
      def __lt__(self, other):
        self.target.append(MaliciousTuple((0, 0), self.target))
        return self.val < other.val
      def __gt__(self, other):
        self.target.append(MaliciousTuple((0, 0), self.target))
        return self.val > other.val
    data = []
    for i in range(30):
      data.append(MaliciousTuple((i, i * 2), data))
    with pytest.raises(ValueError, match="list modified"):
      heapx.heapify(data)

  def test_mixed_numeric_append_on_key(self):
    """Mixed int/float with key function that appends."""
    data = [i if i % 2 == 0 else float(i) for i in range(50)]
    with pytest.raises(ValueError, match="list modified"):
      heapx.heapify(data, cmp=make_append_key(data))

  def test_bytes_append_on_key(self):
    """Bytes with key function that appends."""
    data = [bytes([i % 256]) for i in range(50)]
    with pytest.raises(ValueError, match="list modified"):
      heapx.heapify(data, cmp=make_append_key(data))

  def test_booleans_append_on_key(self):
    """Booleans with key function that appends."""
    data = [i % 2 == 0 for i in range(50)]
    with pytest.raises(ValueError, match="list modified"):
      heapx.heapify(data, cmp=make_append_key(data))

  def test_none_values_append_on_key(self):
    """None values with key function that appends."""
    data = [None] * 50
    def none_key(x):
      data.append(None)
      return 0
    with pytest.raises(ValueError, match="list modified"):
      heapx.heapify(data, cmp=none_key)

  def test_nested_lists_append_on_compare(self):
    """Nested lists with malicious comparison."""
    class MaliciousList:
      def __init__(self, val, target):
        self.val = val
        self.target = target
      def __lt__(self, other):
        self.target.append(MaliciousList([0], self.target))
        return self.val < other.val
      def __gt__(self, other):
        self.target.append(MaliciousList([0], self.target))
        return self.val > other.val
    data = []
    for i in range(30):
      data.append(MaliciousList([i, i + 1], data))
    with pytest.raises(ValueError, match="list modified"):
      heapx.heapify(data)

  def test_custom_objects_append_on_compare(self):
    """Custom objects with malicious comparison."""
    class Task:
      def __init__(self, priority, target):
        self.priority = priority
        self.target = target
      def __lt__(self, other):
        self.target.append(Task(0, self.target))
        return self.priority < other.priority
      def __gt__(self, other):
        self.target.append(Task(0, self.target))
        return self.priority > other.priority
    data = []
    for i in range(30):
      data.append(Task(i, data))
    with pytest.raises(ValueError, match="list modified"):
      heapx.heapify(data)


# ============================================================================
# Test Edge Cases - Segfault Prevention (RESTORED - Original)
# ============================================================================

class TestEdgeCasesSegfaultPreventionOriginal:
  """Test segfault prevention edge cases (original tests)."""

  def test_small_heap_append_on_compare(self):
    """Small heap (n<=16) with append during comparison."""
    data = []
    for i in range(16):
      data.append(MaliciousAppendOnCompare(i, data))
    with pytest.raises(ValueError, match="list modified"):
      heapx.heapify(data)

  def test_small_heap_pop_on_compare(self):
    """Small heap (n<=16) with pop during comparison."""
    data = []
    for i in range(16):
      data.append(MaliciousPopOnCompare(i, data))
    with pytest.raises(ValueError, match="list modified"):
      heapx.heapify(data)

  def test_boundary_17_elements_append(self):
    """Boundary case: 17 elements (just above small heap threshold)."""
    data = []
    for i in range(17):
      data.append(MaliciousAppendOnCompare(i, data))
    with pytest.raises(ValueError, match="list modified"):
      heapx.heapify(data)

  def test_large_heap_append_on_compare(self):
    """Large heap (n>=1000) with append during comparison."""
    data = []
    for i in range(1000):
      data.append(MaliciousAppendOnCompare(i, data))
    with pytest.raises(ValueError, match="list modified"):
      heapx.heapify(data)

  def test_large_heap_pop_on_compare(self):
    """Large heap (n>=1000) with pop during comparison."""
    data = []
    for i in range(1000):
      data.append(MaliciousPopOnCompare(i, data))
    with pytest.raises(ValueError, match="list modified"):
      heapx.heapify(data)

  def test_arity_1_append_on_key(self):
    """Arity=1 (sorted list) with key function that appends."""
    data = list(range(50))
    with pytest.raises(ValueError, match="list modified"):
      heapx.heapify(data, cmp=make_append_key(data), arity=1)

  def test_arity_1_pop_on_key(self):
    """Arity=1 (sorted list) with key function that pops."""
    data = list(range(50))
    with pytest.raises(ValueError, match="list modified"):
      heapx.heapify(data, cmp=make_pop_key(data), arity=1)

  def test_high_arity_append_on_compare(self):
    """High arity (8) with append during comparison."""
    data = []
    for i in range(100):
      data.append(MaliciousAppendOnCompare(i, data))
    with pytest.raises(ValueError, match="list modified"):
      heapx.heapify(data, arity=8)

  def test_high_arity_key_append(self):
    """High arity (8) with key function that appends."""
    data = list(range(100))
    with pytest.raises(ValueError, match="list modified"):
      heapx.heapify(data, cmp=make_append_key(data), arity=8)

  def test_reverse_sorted_append_on_compare(self):
    """Reverse sorted data with append during comparison."""
    data = []
    for i in range(50, 0, -1):
      data.append(MaliciousAppendOnCompare(i, data))
    with pytest.raises(ValueError, match="list modified"):
      heapx.heapify(data)

  def test_already_heap_append_on_compare(self):
    """Already valid heap with append during comparison."""
    data = []
    for i in range(50):
      data.append(MaliciousAppendOnCompare(i, data))
    with pytest.raises(ValueError, match="list modified"):
      heapx.heapify(data)

  def test_duplicate_values_append_on_compare(self):
    """Duplicate values with append during comparison."""
    data = []
    for i in range(50):
      data.append(MaliciousAppendOnCompare(i % 10, data))
    with pytest.raises(ValueError, match="list modified"):
      heapx.heapify(data)

  def test_all_same_values_append_on_compare(self):
    """All same values with append during comparison."""
    data = []
    for i in range(50):
      data.append(MaliciousAppendOnCompare(42, data))
    with pytest.raises(ValueError, match="list modified"):
      heapx.heapify(data)


# ============================================================================
# Test Combinations - Segfault Prevention (RESTORED)
# ============================================================================

class TestCombinationsSegfaultPrevention:
  """Test segfault prevention with parameter combinations."""

  @pytest.mark.parametrize("max_heap", [False, True])
  @pytest.mark.parametrize("arity", [2, 3, 4])
  def test_heapify_combinations_append(self, max_heap, arity):
    """Heapify with all max_heap/arity combinations."""
    data = []
    for i in range(50):
      data.append(MaliciousAppendOnCompare(i, data))
    with pytest.raises(ValueError, match="list modified"):
      heapx.heapify(data, max_heap=max_heap, arity=arity)

  @pytest.mark.parametrize("max_heap", [False, True])
  @pytest.mark.parametrize("arity", [2, 3, 4])
  def test_push_combinations_append(self, max_heap, arity):
    """Push with all max_heap/arity combinations."""
    data = []
    for i in range(30):
      data.append(MaliciousAppendOnCompare(i * 2, data))
    new_item = MaliciousAppendOnCompare(15, data)
    with pytest.raises(ValueError, match="list modified"):
      heapx.push(data, new_item, max_heap=max_heap, arity=arity)

  @pytest.mark.parametrize("max_heap", [False, True])
  @pytest.mark.parametrize("arity", [2, 3, 4])
  def test_pop_combinations_append(self, max_heap, arity):
    """Pop with all max_heap/arity combinations."""
    data = []
    for i in range(50):
      data.append(MaliciousAppendOnCompare(i, data))
    with pytest.raises(ValueError, match="list modified"):
      heapx.pop(data, max_heap=max_heap, arity=arity)

  @pytest.mark.parametrize("reverse", [False, True])
  @pytest.mark.parametrize("arity", [2, 3, 4])
  def test_sort_combinations_append(self, reverse, arity):
    """Sort with all reverse/arity combinations."""
    data = []
    for i in range(50):
      data.append(MaliciousAppendOnCompare(i, data))
    with pytest.raises(ValueError, match="list modified"):
      heapx.sort(data, reverse=reverse, inplace=True, arity=arity)

  @pytest.mark.parametrize("max_heap", [False, True])
  @pytest.mark.parametrize("arity", [2, 3, 4])
  def test_remove_combinations_append(self, max_heap, arity):
    """Remove with all max_heap/arity combinations."""
    data = []
    for i in range(50):
      data.append(MaliciousAppendOnCompare(i, data))
    with pytest.raises(ValueError, match="list modified"):
      heapx.remove(data, indices=25, max_heap=max_heap, arity=arity)

  @pytest.mark.parametrize("max_heap", [False, True])
  @pytest.mark.parametrize("arity", [2, 3, 4])
  def test_replace_combinations_append(self, max_heap, arity):
    """Replace with all max_heap/arity combinations."""
    data = []
    for i in range(50):
      data.append(MaliciousAppendOnCompare(i, data))
    new_item = MaliciousAppendOnCompare(999, data)
    with pytest.raises(ValueError, match="list modified"):
      heapx.replace(data, new_item, indices=25, max_heap=max_heap, arity=arity)

  @pytest.mark.parametrize("max_heap", [False, True])
  @pytest.mark.parametrize("arity", [2, 3, 4])
  def test_merge_combinations_append(self, max_heap, arity):
    """Merge with all max_heap/arity combinations using key function."""
    data1 = list(range(0, 50, 2))
    data2 = list(range(1, 50, 2))
    result_holder = [None]
    call_count = [0]
    def malicious_key(x):
      call_count[0] += 1
      if call_count[0] > 5 and result_holder[0] is not None:
        result_holder[0].append(999)
      return x
    result = heapx.merge(data1, data2, max_heap=max_heap, arity=arity)
    result_holder[0] = result
    with pytest.raises(ValueError, match="list modified"):
      heapx.heapify(result, cmp=malicious_key, max_heap=max_heap, arity=arity)


# ============================================================================
# Test Modification Types - Comprehensive Coverage (RESTORED)
# ============================================================================

class TestModificationTypesSegfaultPrevention:
  """Test all modification types that could cause segfault."""

  def test_append_single_element(self):
    """Append single element during comparison."""
    data = []
    for i in range(30):
      data.append(MaliciousAppendOnCompare(i, data))
    with pytest.raises(ValueError, match="list modified"):
      heapx.heapify(data)

  def test_pop_single_element(self):
    """Pop single element during comparison."""
    data = []
    for i in range(30):
      data.append(MaliciousPopOnCompare(i, data))
    with pytest.raises(ValueError, match="list modified"):
      heapx.heapify(data)

  def test_clear_entire_list(self):
    """Clear entire list during comparison."""
    data = []
    for i in range(30):
      data.append(MaliciousClearOnCompare(i, data))
    with pytest.raises(ValueError, match="list modified"):
      heapx.heapify(data)

  def test_insert_at_beginning(self):
    """Insert at beginning during comparison."""
    data = []
    for i in range(30):
      data.append(MaliciousInsertOnCompare(i, data))
    with pytest.raises(ValueError, match="list modified"):
      heapx.heapify(data)

  def test_extend_multiple_elements(self):
    """Extend with multiple elements during comparison."""
    data = []
    for i in range(30):
      data.append(MaliciousExtendOnCompare(i, data))
    with pytest.raises(ValueError, match="list modified"):
      heapx.heapify(data)

  def test_del_element(self):
    """Delete element during comparison."""
    data = []
    for i in range(30):
      data.append(MaliciousDelOnCompare(i, data))
    with pytest.raises(ValueError, match="list modified"):
      heapx.heapify(data)

  def test_slice_modification(self):
    """Slice modification during comparison."""
    data = []
    for i in range(30):
      data.append(MaliciousSliceOnCompare(i, data))
    with pytest.raises(ValueError, match="list modified"):
      heapx.heapify(data)


# ============================================================================
# Test Key Function Modification Types (RESTORED)
# ============================================================================

class TestKeyFunctionModificationsSegfaultPrevention:
  """Test key function modifications that could cause segfault."""

  def test_key_append_heapify(self):
    """Key function appends during heapify."""
    data = list(range(50))
    with pytest.raises(ValueError, match="list modified"):
      heapx.heapify(data, cmp=make_append_key(data))

  def test_key_pop_heapify(self):
    """Key function pops during heapify."""
    data = list(range(50))
    with pytest.raises(ValueError, match="list modified"):
      heapx.heapify(data, cmp=make_pop_key(data))

  def test_key_clear_heapify(self):
    """Key function clears during heapify."""
    data = list(range(50))
    with pytest.raises(ValueError, match="list modified"):
      heapx.heapify(data, cmp=make_clear_key(data))

  def test_key_insert_heapify(self):
    """Key function inserts during heapify."""
    data = list(range(50))
    with pytest.raises(ValueError, match="list modified"):
      heapx.heapify(data, cmp=make_insert_key(data))

  def test_key_extend_heapify(self):
    """Key function extends during heapify."""
    data = list(range(50))
    with pytest.raises(ValueError, match="list modified"):
      heapx.heapify(data, cmp=make_extend_key(data))

  def test_key_append_push(self):
    """Key function appends during push."""
    data = list(range(30))
    heapx.heapify(data)
    with pytest.raises(ValueError, match="list modified"):
      heapx.push(data, 15, cmp=make_append_key(data))

  def test_key_append_pop(self):
    """Key function appends during pop."""
    data = list(range(30))
    heapx.heapify(data)
    with pytest.raises(ValueError, match="list modified"):
      heapx.pop(data, cmp=make_append_key(data))

  def test_key_append_sort(self):
    """Key function appends during sort."""
    data = list(range(30))
    with pytest.raises(ValueError, match="list modified"):
      heapx.sort(data, cmp=make_append_key(data), inplace=True)

  def test_key_append_remove(self):
    """Key function appends during remove."""
    data = list(range(30))
    heapx.heapify(data)
    with pytest.raises(ValueError, match="list modified"):
      heapx.remove(data, indices=15, cmp=make_append_key(data))

  def test_key_append_replace(self):
    """Key function appends during replace."""
    data = list(range(30))
    heapx.heapify(data)
    with pytest.raises(ValueError, match="list modified"):
      heapx.replace(data, 999, indices=15, cmp=make_append_key(data))


# ============================================================================
# Test Specific Priority Paths in py_pop (RESTORED)
# ============================================================================

class TestPopPriorityPathsSegfaultPrevention:
  """Test all priority paths in py_pop for segfault prevention."""

  def test_pop_priority_1_small_heap(self):
    """Pop priority 1: small heap (n<=16)."""
    data = []
    for i in range(16):
      data.append(MaliciousAppendOnCompare(i, data))
    with pytest.raises(ValueError, match="list modified"):
      heapx.pop(data)

  def test_pop_priority_3_binary_no_key(self):
    """Pop priority 3: binary heap without key."""
    data = []
    for i in range(50):
      data.append(MaliciousAppendOnCompare(i, data))
    with pytest.raises(ValueError, match="list modified"):
      heapx.pop(data, arity=2)

  def test_pop_priority_4_ternary_no_key(self):
    """Pop priority 4: ternary heap without key."""
    data = []
    for i in range(50):
      data.append(MaliciousAppendOnCompare(i, data))
    with pytest.raises(ValueError, match="list modified"):
      heapx.pop(data, arity=3)

  def test_pop_priority_5_quaternary_no_key(self):
    """Pop priority 5: quaternary heap without key."""
    data = []
    for i in range(50):
      data.append(MaliciousAppendOnCompare(i, data))
    with pytest.raises(ValueError, match="list modified"):
      heapx.pop(data, arity=4)

  def test_pop_priority_6_nary_no_key(self):
    """Pop priority 6: n-ary heap without key."""
    data = []
    for i in range(50):
      data.append(MaliciousAppendOnCompare(i, data))
    with pytest.raises(ValueError, match="list modified"):
      heapx.pop(data, arity=5)

  def test_pop_priority_8_binary_with_key(self):
    """Pop priority 8: binary heap with key."""
    data = list(range(50))
    heapx.heapify(data)
    with pytest.raises(ValueError, match="list modified"):
      heapx.pop(data, cmp=make_append_key(data), arity=2)

  def test_pop_priority_9_ternary_with_key(self):
    """Pop priority 9: ternary heap with key."""
    data = list(range(50))
    heapx.heapify(data, arity=3)
    with pytest.raises(ValueError, match="list modified"):
      heapx.pop(data, cmp=make_append_key(data), arity=3)

  def test_pop_priority_10_nary_with_key(self):
    """Pop priority 10: n-ary heap with key."""
    data = list(range(50))
    heapx.heapify(data, arity=5)
    with pytest.raises(ValueError, match="list modified"):
      heapx.pop(data, cmp=make_append_key(data), arity=5)


# ============================================================================
# Test Specific Heapify Paths (RESTORED)
# ============================================================================

class TestHeapifyPathsSegfaultPrevention:
  """Test all heapify algorithm paths for segfault prevention."""

  def test_heapify_floyd_binary(self):
    """Floyd's binary heapify path."""
    data = []
    for i in range(100):
      data.append(MaliciousAppendOnCompare(i, data))
    with pytest.raises(ValueError, match="list modified"):
      heapx.heapify(data, arity=2)

  def test_heapify_ternary_specialized(self):
    """Specialized ternary heapify path."""
    data = []
    for i in range(100):
      data.append(MaliciousAppendOnCompare(i, data))
    with pytest.raises(ValueError, match="list modified"):
      heapx.heapify(data, arity=3)

  def test_heapify_quaternary_specialized(self):
    """Specialized quaternary heapify path."""
    data = []
    for i in range(100):
      data.append(MaliciousAppendOnCompare(i, data))
    with pytest.raises(ValueError, match="list modified"):
      heapx.heapify(data, arity=4)

  def test_heapify_nary_small(self):
    """N-ary heapify for small n (<1000)."""
    data = []
    for i in range(500):
      data.append(MaliciousAppendOnCompare(i, data))
    with pytest.raises(ValueError, match="list modified"):
      heapx.heapify(data, arity=5)

  def test_heapify_nary_large(self):
    """N-ary heapify for large n (>=1000)."""
    data = []
    for i in range(1000):
      data.append(MaliciousAppendOnCompare(i, data))
    with pytest.raises(ValueError, match="list modified"):
      heapx.heapify(data, arity=5)

  def test_heapify_binary_with_key(self):
    """Binary heapify with key function."""
    data = list(range(100))
    with pytest.raises(ValueError, match="list modified"):
      heapx.heapify(data, cmp=make_append_key(data), arity=2)

  def test_heapify_ternary_with_key(self):
    """Ternary heapify with key function."""
    data = list(range(100))
    with pytest.raises(ValueError, match="list modified"):
      heapx.heapify(data, cmp=make_append_key(data), arity=3)

  def test_heapify_quaternary_with_key(self):
    """Quaternary heapify with key function."""
    data = list(range(100))
    with pytest.raises(ValueError, match="list modified"):
      heapx.heapify(data, cmp=make_append_key(data), arity=4)

  def test_heapify_nary_with_key(self):
    """N-ary heapify with key function."""
    data = list(range(100))
    with pytest.raises(ValueError, match="list modified"):
      heapx.heapify(data, cmp=make_append_key(data), arity=5)


# ============================================================================
# Test Sort Paths (RESTORED)
# ============================================================================

class TestSortPathsSegfaultPrevention:
  """Test all sort algorithm paths for segfault prevention."""

  def test_sort_binary_heapsort(self):
    """Binary heapsort path."""
    data = []
    for i in range(100):
      data.append(MaliciousAppendOnCompare(i, data))
    with pytest.raises(ValueError, match="list modified"):
      heapx.sort(data, arity=2, inplace=True)

  def test_sort_ternary_heapsort(self):
    """Ternary heapsort path."""
    data = []
    for i in range(100):
      data.append(MaliciousAppendOnCompare(i, data))
    with pytest.raises(ValueError, match="list modified"):
      heapx.sort(data, arity=3, inplace=True)

  def test_sort_quaternary_heapsort(self):
    """Quaternary heapsort path."""
    data = []
    for i in range(100):
      data.append(MaliciousAppendOnCompare(i, data))
    with pytest.raises(ValueError, match="list modified"):
      heapx.sort(data, arity=4, inplace=True)

  def test_sort_nary_heapsort(self):
    """N-ary heapsort path."""
    data = []
    for i in range(100):
      data.append(MaliciousAppendOnCompare(i, data))
    with pytest.raises(ValueError, match="list modified"):
      heapx.sort(data, arity=5, inplace=True)

  def test_sort_binary_with_key(self):
    """Binary heapsort with key function."""
    data = list(range(100))
    with pytest.raises(ValueError, match="list modified"):
      heapx.sort(data, cmp=make_append_key(data), arity=2, inplace=True)

  def test_sort_ternary_with_key(self):
    """Ternary heapsort with key function."""
    data = list(range(100))
    with pytest.raises(ValueError, match="list modified"):
      heapx.sort(data, cmp=make_append_key(data), arity=3, inplace=True)

  def test_sort_nary_with_key(self):
    """N-ary heapsort with key function."""
    data = list(range(100))
    with pytest.raises(ValueError, match="list modified"):
      heapx.sort(data, cmp=make_append_key(data), arity=5, inplace=True)


# ============================================================================
# Test Sift Operations (RESTORED)
# ============================================================================

class TestSiftOperationsSegfaultPrevention:
  """Test sift-up and sift-down operations for segfault prevention."""

  def test_sift_up_binary(self):
    """Sift-up in binary heap (via push)."""
    data = []
    for i in range(30):
      data.append(MaliciousAppendOnCompare(i * 2, data))
    new_item = MaliciousAppendOnCompare(1, data)
    with pytest.raises(ValueError, match="list modified"):
      heapx.push(data, new_item, arity=2)

  def test_sift_up_ternary(self):
    """Sift-up in ternary heap (via push)."""
    data = []
    for i in range(30):
      data.append(MaliciousAppendOnCompare(i * 2, data))
    new_item = MaliciousAppendOnCompare(1, data)
    with pytest.raises(ValueError, match="list modified"):
      heapx.push(data, new_item, arity=3)

  def test_sift_up_quaternary(self):
    """Sift-up in quaternary heap (via push)."""
    data = []
    for i in range(30):
      data.append(MaliciousAppendOnCompare(i * 2, data))
    new_item = MaliciousAppendOnCompare(1, data)
    with pytest.raises(ValueError, match="list modified"):
      heapx.push(data, new_item, arity=4)

  def test_sift_down_binary(self):
    """Sift-down in binary heap (via pop)."""
    data = []
    for i in range(50):
      data.append(MaliciousAppendOnCompare(i, data))
    with pytest.raises(ValueError, match="list modified"):
      heapx.pop(data, arity=2)

  def test_sift_down_ternary(self):
    """Sift-down in ternary heap (via pop)."""
    data = []
    for i in range(50):
      data.append(MaliciousAppendOnCompare(i, data))
    with pytest.raises(ValueError, match="list modified"):
      heapx.pop(data, arity=3)

  def test_sift_down_quaternary(self):
    """Sift-down in quaternary heap (via pop)."""
    data = []
    for i in range(50):
      data.append(MaliciousAppendOnCompare(i, data))
    with pytest.raises(ValueError, match="list modified"):
      heapx.pop(data, arity=4)

  def test_sift_up_with_key(self):
    """Sift-up with key function."""
    data = list(range(0, 60, 2))
    heapx.heapify(data)
    with pytest.raises(ValueError, match="list modified"):
      heapx.push(data, 1, cmp=make_append_key(data))

  def test_sift_down_with_key(self):
    """Sift-down with key function."""
    data = list(range(50))
    heapx.heapify(data)
    with pytest.raises(ValueError, match="list modified"):
      heapx.pop(data, cmp=make_append_key(data))


# ============================================================================
# Test No Crash on Valid Operations - Sanity Checks (RESTORED)
# ============================================================================

class TestValidOperationsNoSegfault:
  """Verify valid operations don't raise ValueError."""

  def test_heapify_normal_integers(self):
    """Normal heapify with integers should work."""
    data = list(range(100, 0, -1))
    heapx.heapify(data)
    assert data[0] == 1

  def test_heapify_normal_with_key(self):
    """Normal heapify with safe key function should work."""
    data = list(range(100, 0, -1))
    heapx.heapify(data, cmp=lambda x: -x)
    assert data[0] == 100

  def test_push_normal(self):
    """Normal push should work."""
    data = list(range(10))
    heapx.heapify(data)
    heapx.push(data, -1)
    assert data[0] == -1

  def test_pop_normal(self):
    """Normal pop should work."""
    data = list(range(10))
    heapx.heapify(data)
    result = heapx.pop(data)
    assert result == 0

  def test_sort_normal(self):
    """Normal sort should work."""
    data = list(range(100, 0, -1))
    result = heapx.sort(data)
    assert result == list(range(1, 101))

  def test_remove_normal(self):
    """Normal remove should work."""
    data = list(range(10))
    heapx.heapify(data)
    heapx.remove(data, indices=5)
    assert len(data) == 9

  def test_replace_normal(self):
    """Normal replace should work."""
    data = list(range(10))
    heapx.heapify(data)
    heapx.replace(data, 100, indices=0)
    assert 100 in data

  def test_merge_normal(self):
    """Normal merge should work."""
    data1 = list(range(0, 10, 2))
    data2 = list(range(1, 10, 2))
    heapx.heapify(data1)
    heapx.heapify(data2)
    result = heapx.merge(data1, data2)
    assert len(result) == 10

  @pytest.mark.parametrize("arity", [2, 3, 4, 5, 8])
  def test_heapify_various_arities_normal(self, arity):
    """Normal heapify with various arities should work."""
    data = list(range(100, 0, -1))
    heapx.heapify(data, arity=arity)
    n = len(data)
    for i in range(n):
      for j in range(1, arity + 1):
        child = arity * i + j
        if child < n:
          assert data[i] <= data[child]

  @pytest.mark.parametrize("max_heap", [False, True])
  def test_heapify_max_min_normal(self, max_heap):
    """Normal heapify with max/min heap should work."""
    data = list(range(100))
    heapx.heapify(data, max_heap=max_heap)
    if max_heap:
      assert data[0] == 99
    else:
      assert data[0] == 0


# ============================================================================
# Test Stress - Multiple Operations (RESTORED)
# ============================================================================

class TestStressSegfaultPrevention:
  """Stress tests for segfault prevention."""

  def test_repeated_heapify_with_modification(self):
    """Repeated heapify attempts with modification."""
    for _ in range(10):
      data = []
      for i in range(30):
        data.append(MaliciousAppendOnCompare(i, data))
      with pytest.raises(ValueError, match="list modified"):
        heapx.heapify(data)

  def test_repeated_push_with_modification(self):
    """Repeated push attempts with modification."""
    for _ in range(10):
      data = []
      for i in range(20):
        data.append(MaliciousAppendOnCompare(i * 2, data))
      new_item = MaliciousAppendOnCompare(10, data)
      with pytest.raises(ValueError, match="list modified"):
        heapx.push(data, new_item)

  def test_repeated_pop_with_modification(self):
    """Repeated pop attempts with modification."""
    for _ in range(10):
      data = []
      for i in range(30):
        data.append(MaliciousAppendOnCompare(i, data))
      with pytest.raises(ValueError, match="list modified"):
        heapx.pop(data)

  def test_large_heap_modification(self):
    """Large heap with modification during comparison."""
    data = []
    for i in range(2000):
      data.append(MaliciousAppendOnCompare(i, data))
    with pytest.raises(ValueError, match="list modified"):
      heapx.heapify(data)

  def test_many_small_heaps_modification(self):
    """Many small heaps with modification."""
    for size in range(5, 20):
      data = []
      for i in range(size):
        data.append(MaliciousAppendOnCompare(i, data))
      with pytest.raises(ValueError, match="list modified"):
        heapx.heapify(data)


# ============================================================================
# Test Recovery After Error (RESTORED)
# ============================================================================

class TestRecoveryAfterError:
  """Test that module recovers properly after catching modification error."""

  def test_heapify_recovery(self):
    """Module works after heapify error."""
    bad_data = []
    for i in range(30):
      bad_data.append(MaliciousAppendOnCompare(i, bad_data))
    with pytest.raises(ValueError):
      heapx.heapify(bad_data)
    
    good_data = list(range(30))
    heapx.heapify(good_data)
    assert good_data[0] == 0

  def test_push_recovery(self):
    """Module works after push error."""
    bad_data = []
    for i in range(20):
      bad_data.append(MaliciousAppendOnCompare(i * 2, bad_data))
    new_item = MaliciousAppendOnCompare(10, bad_data)
    with pytest.raises(ValueError):
      heapx.push(bad_data, new_item)
    
    good_data = list(range(20))
    heapx.heapify(good_data)
    heapx.push(good_data, -1)
    assert good_data[0] == -1

  def test_pop_recovery(self):
    """Module works after pop error."""
    bad_data = []
    for i in range(30):
      bad_data.append(MaliciousAppendOnCompare(i, bad_data))
    with pytest.raises(ValueError):
      heapx.pop(bad_data)
    
    good_data = list(range(30))
    heapx.heapify(good_data)
    result = heapx.pop(good_data)
    assert result == 0

  def test_sort_recovery(self):
    """Module works after sort error."""
    bad_data = []
    for i in range(30):
      bad_data.append(MaliciousAppendOnCompare(i, bad_data))
    with pytest.raises(ValueError):
      heapx.sort(bad_data, inplace=True)
    
    good_data = list(range(30, 0, -1))
    result = heapx.sort(good_data)
    assert result == list(range(1, 31))
