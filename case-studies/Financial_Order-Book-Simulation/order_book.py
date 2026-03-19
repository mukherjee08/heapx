"""
Limit Order Book Engine Backed by heapx Heaps.

Implements a price-time priority matching engine where:
  - Bids are maintained in a max-heap (highest price = best bid).
  - Asks are maintained in a min-heap (lowest price = best ask).

This module is part of Case Study 1 for the heapx research paper
submitted to Software: Practice and Experience (Wiley).

References:
  [1] R. Cont, S. Stoikov, R. Talreja, "A Stochastic Model for Order
      Book Dynamics," Operations Research 58(3), 2010.
  [2] T. Preis et al., "Multi-agent-based Order Book Model of Financial
      Markets," Europhysics Letters 75(3), 2006.
"""

from __future__ import annotations

import heapx
from dataclasses import dataclass
from typing import List, Optional, Tuple


@dataclass(slots=True)
class Order:
  """A single limit order in the book."""
  order_id: int
  price: float
  quantity: int
  timestamp: float
  side: str  # 'bid' or 'ask'


@dataclass(slots=True)
class Trade:
  """Record of an executed trade."""
  price: float
  quantity: int
  timestamp: float
  aggressor: str  # 'buy' or 'sell'


class OrderBook:
  """Price-time priority limit order book using heapx heaps.

  Heap entries are tuples ``(sort_key, timestamp, Order)`` where
  *sort_key* is the negated price for bids (so that a standard
  min-heap yields the highest bid first) and the raw price for asks.

  An auxiliary dictionary ``_id_to_side`` maps each live order id to
  its side ('bid' or 'ask') so that cancellation can locate the
  correct heap in O(1).  Finding the *position* within the heap still
  requires a linear scan; in a production system an index-tracking
  map would eliminate this, but here the heap-maintenance cost after
  removal is the operation under study.
  """

  def __init__(self) -> None:
    self.bids: List[Tuple[float, float, Order]] = []
    self.asks: List[Tuple[float, float, Order]] = []
    self._id_to_side: dict[int, str] = {}
    self.trades: List[Trade] = []
    self._next_id: int = 0

  # ------------------------------------------------------------------
  # Public API
  # ------------------------------------------------------------------

  def submit_limit(self, price: float, quantity: int,
                   side: str, timestamp: float) -> int:
    """Submit a limit order.  Returns the assigned order id."""
    oid = self._next_id
    self._next_id += 1
    order = Order(oid, price, quantity, timestamp, side)

    if side == "bid":
      entry = (-price, timestamp, order)
      heapx.push(self.bids, entry)
    else:
      entry = (price, timestamp, order)
      heapx.push(self.asks, entry)

    self._id_to_side[oid] = side
    return oid

  def submit_market(self, quantity: int, side: str,
                    timestamp: float) -> List[Trade]:
    """Execute a market order against the opposite side of the book.

    Args:
      quantity: number of shares to fill.
      side: 'buy' (lifts asks) or 'sell' (hits bids).
      timestamp: event time.

    Returns:
      List of Trade objects for each fill.
    """
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
        heapx.pop(heap)
        self._id_to_side.pop(order.order_id, None)

    self.trades.extend(fills)
    return fills

  def cancel(self, order_id: int) -> bool:
    """Cancel an outstanding limit order by id.

    Uses heapx.remove with an index for O(log n) heap maintenance
    after the position is located.
    Returns True if the order was found and removed.
    """
    side = self._id_to_side.pop(order_id, None)
    if side is None:
      return False

    heap = self.bids if side == "bid" else self.asks
    idx = self._find_index(heap, order_id)
    if idx is None:
      return False

    heapx.remove(heap, indices=idx)
    return True

  # ------------------------------------------------------------------
  # Queries
  # ------------------------------------------------------------------

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

  # ------------------------------------------------------------------
  # Internals
  # ------------------------------------------------------------------

  @staticmethod
  def _find_index(heap: list, order_id: int) -> Optional[int]:
    """Linear scan for the heap index of a given order id."""
    for i, entry in enumerate(heap):
      if entry[2].order_id == order_id:
        return i
    return None
