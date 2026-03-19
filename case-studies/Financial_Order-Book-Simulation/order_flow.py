"""
Stochastic order-flow generator following Cont-Stoikov-Talreja (2010).

Generates limit-order, market-order, and cancellation events whose
inter-arrival times are exponentially distributed (Poisson process).
Limit-order arrival rates depend on the distance from the current
midprice, and cancellation rates are proportional to the number of
outstanding orders — matching the empirical findings in [1].

The generator maintains a lightweight internal book state so that
limit orders are placed relative to the evolving midprice, producing
a diffusive price trajectory, a stationary book depth, and a spread
distribution concentrated near the minimum tick size.

References:
  [1] R. Cont, S. Stoikov, R. Talreja, "A Stochastic Model for Order
      Book Dynamics," Operations Research 58(3), 2010.
  [2] F. Abergel, A. Jedidi, "A Mathematical Approach to Order Book
      Modeling," arXiv:1010.5136, 2013.
  [3] T. Preis et al., "Multi-agent-based Order Book Model of Financial
      Markets," Europhysics Letters 75(3), 2006.
"""

from __future__ import annotations

import math
import numpy as np
from dataclasses import dataclass
from typing import List, Optional


@dataclass(slots=True)
class OrderEvent:
  """A single event in the order-flow stream."""
  timestamp: float
  event_type: str   # 'limit_bid', 'limit_ask', 'market_buy',
                    # 'market_sell', 'cancel'
  price: float      # relevant for limit orders; 0.0 for others
  quantity: int
  order_id: int     # relevant for cancellations (-1 otherwise)


@dataclass
class FlowParams:
  """Parameters for the Cont-Stoikov-Talreja order-flow model.

  Calibrated so that the book reaches a stationary depth of roughly
  100–500 orders per side, the spread stays near 1–3 ticks, and the
  midprice exhibits a realistic random walk.

  Attributes:
    lambda_limit: base arrival rate of limit orders (per distance
        level, per second).  Rate at distance *i* ticks from the
        midprice is ``lambda_limit * exp(-kappa * i)``.
    kappa: exponential decay constant for limit-order placement depth.
    mu: arrival rate of market orders per second (each side).
    theta: per-order cancellation rate (per second).
    max_depth: maximum tick-distance from the midprice at which
        limit orders may be placed.
    tick_size: minimum price increment.
    initial_price: reference price at simulation start.
    lot_size: fixed order size (shares per order).
  """
  lambda_limit: float = 2.0
  kappa: float = 0.3
  mu: float = 2.5
  theta: float = 0.02
  max_depth: int = 20
  tick_size: float = 0.01
  initial_price: float = 100.0
  lot_size: int = 100


def generate_order_flow(
  params: FlowParams,
  n_events: int,
  seed: int = 42,
) -> List[OrderEvent]:
  """Generate exactly *n_events* order events.

  The generator maintains a lightweight internal book state (best bid,
  best ask, and a list of live order ids with their prices and sides)
  so that new limit orders are placed relative to the *current
  midprice* — producing a diffusive midprice and stationary book.

  Uses a thinning (Lewis-Shedler) algorithm on the superposition of
  all Poisson intensity components.
  """
  rng = np.random.default_rng(seed)
  p = params

  # Per-level limit-order arrival rates.
  limit_rates = np.array([
    p.lambda_limit * math.exp(-p.kappa * i)
    for i in range(p.max_depth)
  ])
  total_limit_rate = 2.0 * limit_rates.sum()
  total_market_rate = 2.0 * p.mu

  # Upper bound for thinning.
  max_book = 2000
  upper_rate = total_limit_rate + total_market_rate + p.theta * max_book

  # Internal book state.
  best_bid: Optional[float] = None
  best_ask: Optional[float] = None
  midprice: float = p.initial_price
  live_orders: list[tuple[int, float, str]] = []  # (oid, price, side)

  events: List[OrderEvent] = []
  t = 0.0
  oid = 0

  def _update_bbo() -> None:
    nonlocal best_bid, best_ask, midprice
    bids = [o[1] for o in live_orders if o[2] == "bid"]
    asks = [o[1] for o in live_orders if o[2] == "ask"]
    best_bid = max(bids) if bids else None
    best_ask = min(asks) if asks else None
    if best_bid is not None and best_ask is not None:
      midprice = round((best_bid + best_ask) / 2.0, 4)

  while len(events) < n_events:
    dt = rng.exponential(1.0 / upper_rate)
    t += dt

    n_live = len(live_orders)
    cancel_rate = p.theta * n_live
    actual_total = total_limit_rate + total_market_rate + cancel_rate

    if rng.random() * upper_rate > actual_total:
      continue

    u = rng.random() * actual_total
    cum = 0.0
    emitted = False

    # --- Limit bid orders (placed below midprice) ---
    for i in range(p.max_depth):
      cum += limit_rates[i]
      if u < cum:
        price = round(midprice - (i + 1) * p.tick_size, 4)
        live_orders.append((oid, price, "bid"))
        events.append(OrderEvent(t, "limit_bid", price, p.lot_size, oid))
        oid += 1
        if best_bid is None or price > best_bid:
          best_bid = price
        emitted = True
        break
    if emitted:
      continue

    # --- Limit ask orders (placed above midprice) ---
    for i in range(p.max_depth):
      cum += limit_rates[i]
      if u < cum:
        price = round(midprice + (i + 1) * p.tick_size, 4)
        live_orders.append((oid, price, "ask"))
        events.append(OrderEvent(t, "limit_ask", price, p.lot_size, oid))
        oid += 1
        if best_ask is None or price < best_ask:
          best_ask = price
        emitted = True
        break
    if emitted:
      continue

    # --- Market buy (lifts best ask) ---
    cum += p.mu
    if u < cum:
      events.append(OrderEvent(t, "market_buy", 0.0, p.lot_size, -1))
      if best_ask is not None:
        for j, o in enumerate(live_orders):
          if o[2] == "ask" and o[1] == best_ask:
            live_orders[j] = live_orders[-1]
            live_orders.pop()
            break
        _update_bbo()
      continue

    # --- Market sell (hits best bid) ---
    cum += p.mu
    if u < cum:
      events.append(OrderEvent(t, "market_sell", 0.0, p.lot_size, -1))
      if best_bid is not None:
        for j, o in enumerate(live_orders):
          if o[2] == "bid" and o[1] == best_bid:
            live_orders[j] = live_orders[-1]
            live_orders.pop()
            break
        _update_bbo()
      continue

    # --- Cancellation ---
    if n_live == 0:
      continue
    idx = rng.integers(n_live)
    cid, cprice, cside = live_orders[idx]
    live_orders[idx] = live_orders[-1]
    live_orders.pop()
    events.append(OrderEvent(t, "cancel", 0.0, 0, cid))
    if (cside == "bid" and best_bid is not None and cprice >= best_bid) or \
       (cside == "ask" and best_ask is not None and cprice <= best_ask):
      _update_bbo()

  return events
