"""
Simulation driver: run the order-book simulation and collect time-series
data for analysis and visualisation.

Produces a pandas DataFrame with per-event snapshots of midprice,
spread, bid/ask depth, and cumulative trade volume.

Usage:
  python simulation.py [--events N] [--seed S] [--output PATH]
"""

from __future__ import annotations

import argparse
import time
from pathlib import Path

import pandas as pd

from order_flow import FlowParams, generate_order_flow
from order_book import OrderBook


def run_simulation(n_events: int, seed: int) -> pd.DataFrame:
  """Execute the simulation and return a DataFrame of snapshots."""
  params = FlowParams()

  print(f"Generating {n_events} order-flow events ...")
  events = generate_order_flow(params, n_events, seed)
  print(f"  {len(events)} events generated.")

  book = OrderBook()
  records: list[dict] = []
  cum_volume = 0

  t0 = time.perf_counter()
  for ev in events:
    if ev.event_type == "limit_bid":
      book.submit_limit(ev.price, ev.quantity, "bid", ev.timestamp)
    elif ev.event_type == "limit_ask":
      book.submit_limit(ev.price, ev.quantity, "ask", ev.timestamp)
    elif ev.event_type == "market_buy":
      fills = book.submit_market(ev.quantity, "buy", ev.timestamp)
      cum_volume += sum(f.quantity for f in fills)
    elif ev.event_type == "market_sell":
      fills = book.submit_market(ev.quantity, "sell", ev.timestamp)
      cum_volume += sum(f.quantity for f in fills)
    elif ev.event_type == "cancel":
      book.cancel(ev.order_id)

    records.append({
      "timestamp": ev.timestamp,
      "event_type": ev.event_type,
      "midprice": book.midprice,
      "spread": book.spread,
      "bid_depth": book.bid_depth,
      "ask_depth": book.ask_depth,
      "cum_volume": cum_volume,
    })

  wall = time.perf_counter() - t0
  print(f"  Simulation completed in {wall:.3f}s")

  return pd.DataFrame(records)


def main() -> None:
  ap = argparse.ArgumentParser(description="Order-book simulation")
  ap.add_argument("--events", type=int, default=200_000)
  ap.add_argument("--seed", type=int, default=42)
  ap.add_argument("--output", type=str, default="simulation.parquet")
  args = ap.parse_args()

  df = run_simulation(args.events, args.seed)
  out = Path(args.output)
  df.to_parquet(out, index=False)
  print(f"Snapshot data written to {out}  ({len(df)} rows)")


if __name__ == "__main__":
  main()
