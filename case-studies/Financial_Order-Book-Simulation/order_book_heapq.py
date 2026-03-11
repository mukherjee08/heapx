"""
Baseline order book using Python's standard-library heapq.

Provides the same interface as ``order_book.OrderBook`` so that the
benchmark harness can compare heapx-backed and heapq-backed engines
on identical event streams.
"""

from __future__ import annotations

import heapq
from typing import List, Optional, Tuple

from order_book import Order, Trade


class OrderBookHeapq:
  """heapq-backed limit order book (baseline).

  Because heapq provides only a min-heap and has no ``remove``
  operation, this implementation:
    - Negates bid prices to simulate a max-heap.
    - Performs cancellation via linear scan followed by element
      swap-with-last, pop, and full O(n) heapify.
  """

  def __init__(self) -> None:
    self.bids: List[Tuple[float, float, Order]] = []
    self.asks: List[Tuple[float, float, Order]] = []
    self._id_to_side: dict[int, str] = {}
    self.trades: List[Trade] = []
    self._next_id: int = 0

  def submit_limit(self, price: float, quantity: int,
                   side: str, timestamp: float) -> int:
    oid = self._next_id
    self._next_id += 1
    order = Order(oid, price, quantity, timestamp, side)

    if side == "bid":
      heapq.heappush(self.bids, (-price, timestamp, order))
    else:
      heapq.heappush(self.asks, (price, timestamp, order))

    self._id_to_side[oid] = side
    return oid

  def submit_market(self, quantity: int, side: str,
                    timestamp: float) -> List[Trade]:
    fills: List[Trade] = []
    remaining = quantity
    heap = self.asks if side == "buy" else self.bids

    while remaining > 0 and heap:
      order: Order = heap[0][2]
      fill_qty = min(remaining, order.quantity)
      fills.append(Trade(order.price, fill_qty, timestamp, side))
      remaining -= fill_qty
      order.quantity -= fill_qty

      if order.quantity == 0:
        heapq.heappop(heap)
        self._id_to_side.pop(order.order_id, None)

    self.trades.extend(fills)
    return fills

  def cancel(self, order_id: int) -> bool:
    """O(n) cancellation: linear scan + swap-with-last + heapify."""
    side = self._id_to_side.pop(order_id, None)
    if side is None:
      return False

    heap = self.bids if side == "bid" else self.asks
    for i, entry in enumerate(heap):
      if entry[2].order_id == order_id:
        heap[i] = heap[-1]
        heap.pop()
        heapq.heapify(heap)
        return True
    return False

  @property
  def best_bid(self) -> Optional[float]:
    return -self.bids[0][0] if self.bids else None

  @property
  def best_ask(self) -> Optional[float]:
    return self.asks[0][0] if self.asks else None

  @property
  def midprice(self) -> Optional[float]:
    bb, ba = self.best_bid, self.best_ask
    if bb is not None and ba is not None:
      return (bb + ba) / 2.0
    return None

  @property
  def spread(self) -> Optional[float]:
    bb, ba = self.best_bid, self.best_ask
    if bb is not None and ba is not None:
      return ba - bb
    return None

  @property
  def bid_depth(self) -> int:
    return len(self.bids)

  @property
  def ask_depth(self) -> int:
    return len(self.asks)
