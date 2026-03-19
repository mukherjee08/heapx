# Case Study 1 — Financial Order Book Simulation

## 1. Introduction

The case study implements a **price–time priority limit order book** (LOB) backed by `heapx` heaps, benchmarks it against an identical engine built on Python's standard-library `heapq`, and produces ten figures that illustrate both the financial dynamics and the performance advantage of `heapx`.

The remainder of this document is organised as follows: Section 2 provides the financial and mathematical background a reader needs to understand the case study from first principles.  Section 3 describes the stochastic model that drives the simulation. Section 4 walks through the code architecture and explains every design decision. Section 5 presents the performance results and explains why `heapx` is faster. Section 6 discusses the practical value of `heapx` for quantitative finance professionals. Section 7 gives quick-start instructions for reproducing the results.

---

## 2. Financial and Mathematical Background

### 2.1 What Is a Limit Order Book?

Modern financial exchanges — the New York Stock Exchange (NYSE), NASDAQ, the Tokyo Stock Exchange (TSE), the London Stock Exchange (LSE), and virtually every electronic trading venue worldwide — operate as **order-driven markets**.  There is no single designated market maker who unilaterally sets prices.  Instead, any participant may submit orders, and the exchange maintains a data structure called the **limit order book** (LOB) that records every outstanding order.

The LOB has two sides:

- **Bid side (buy orders).**  Each bid states: "I am willing to buy *q* shares at price *p* or lower."  The highest bid price currently in the book is called the **best bid** (also called the "inside bid" or "top of book" on the buy side).

- **Ask side (sell orders).**  Each ask states: "I am willing to sell *q* shares at price *p* or higher."  The lowest ask price currently in the book is called the **best ask** (also called the "inside ask" or "top of book" on the sell side).

#### 2.1.1 The Bid–Ask Spread

The **bid–ask spread** is the difference between the best ask and the best bid:

```
spread = best_ask − best_bid
```

The spread is always non-negative.  It represents the cost of immediacy: a trader who wants to buy *right now* must pay the best ask, and a trader who wants to sell *right now* receives only the best bid.  The spread is the gap between these two prices.

**Example 1 (typical liquid stock).**  Suppose Apple Inc. (AAPL) has the following order book at a given instant:

```
  ASK SIDE (sell orders)         BID SIDE (buy orders)
  ────────────────────           ────────────────────
  $182.05  ×  200 shares         $182.02  ×  500 shares   ← best bid
  $182.06  ×  150 shares         $182.01  ×  300 shares
  $182.07  ×  400 shares         $182.00  ×  800 shares
  ↑ best ask
```

Here the best bid is $182.02 and the best ask is $182.05, so the spread is $182.05 − $182.02 = **$0.03** (three cents, or three "ticks" if the tick size is $0.01).

**Example 2 (wide spread in an illiquid stock).**  A thinly traded small-cap stock might show:

```
  Best ask: $14.50   (100 shares)
  Best bid: $14.20   (100 shares)
  Spread:   $0.30    (30 ticks)
```

The wide spread reflects low liquidity — few participants are competing to trade, so the gap between the best buyer and the best seller is large.  A trader who buys at $14.50 and immediately sells would lose $0.30 per share to the spread alone.

**Example 3 (crossed book — an edge case).**  In theory, if a bid arrives at a price equal to or higher than the best ask, the orders would immediately match and execute as a trade.  For instance, if the best ask is $50.00 and a new bid arrives at $50.00, the exchange matches them instantly.  The book never actually displays a "negative spread" because the matching engine resolves the cross before it enters the book.  This is why the spread is always ≥ 0 in a correctly functioning market.

#### 2.1.2 The Midprice

The **midprice** is the arithmetic mean of the best bid and the best ask:

```
midprice = (best_bid + best_ask) / 2
```

The midprice is the most commonly used proxy for the "current price" of an asset because it sits exactly between the two most competitive quotes and is not biased toward either buyers or sellers.

**Example.**  Using the AAPL book from Example 1 above:

```
midprice = ($182.02 + $182.05) / 2 = $364.07 / 2 = $182.035
```

Note that the midprice can fall between tick levels (here, $182.035 is not a valid order price if the tick size is $0.01).  This is normal — the midprice is a theoretical reference value, not a tradeable price.

**Edge case — empty side.**  If one side of the book is completely empty (e.g., no ask orders exist), the midprice is undefined.  In practice this is rare for liquid securities but can occur during market halts, at the open before the first orders arrive, or in very illiquid instruments.  Our simulation handles this by returning `None` for the midprice when either side is empty.

### 2.2 Order Types

Three types of events drive the evolution of the LOB.  Understanding how they interact is essential to understanding the simulation.

#### 2.2.1 Limit Orders

A **limit order** is an instruction to buy or sell a specified quantity of shares at a specified price *or better*.  "Or better" means: for a buy limit order, the execution price must be at or below the limit price; for a sell limit order, the execution price must be at or above the limit price.

A limit order is called a **passive order** because it does not execute immediately upon submission (unless it crosses the spread — see edge case below).  Instead, it is placed into the order book and waits there until one of three things happens:

1. A matching market order arrives and executes against it.
2. Another limit order arrives at a crossing price and executes against it.
3. The trader who submitted it decides to cancel it.

Limit orders **provide liquidity** to the market.  The term "liquidity" refers to the ability to buy or sell an asset quickly without causing a large price movement.  Every limit order sitting in the book represents a standing offer to trade, and the more such offers exist, the easier it is for other participants to find a counterparty.  Traders who submit limit orders are therefore called **liquidity providers** (or "makers").

**Example.**  A trader submits: "Buy 100 shares of AAPL at $182.00." This order is placed on the bid side of the book at the $182.00 price level.  It will sit there until either (a) a market sell order arrives and is matched against it, (b) another seller submits a limit sell order at $182.00 or lower that crosses it, or (c) the trader cancels it.

**Edge case — marketable limit order.**  If a buy limit order arrives with a price at or above the current best ask, it immediately executes (partially or fully) against the resting ask orders.  For example, if the best ask is $182.05 and a buy limit order arrives at $182.06, it will execute at $182.05 (the best available price).  Any unfilled remainder is then placed in the book at $182.06.  In this case the limit order briefly acts like a market order for the portion that crosses the spread.

#### 2.2.2 Market Orders

A **market order** is an instruction to buy or sell a specified quantity of shares *immediately* at the best available price.  It specifies no price — only a quantity and a direction (buy or sell).

A market order is called an **aggressive order** because it demands immediate execution.  It **consumes liquidity**: it removes resting limit orders from the book by executing against them.  Traders who submit market orders are called **liquidity takers** (or "takers").

**Example.**  The book currently shows:

```
  Best ask: $182.05  ×  200 shares
  Next ask: $182.06  ×  150 shares
```

A market buy order for 300 shares arrives.  The matching engine fills it in two steps:

1. 200 shares execute at $182.05 (exhausting the best ask level).
2. 100 shares execute at $182.06 (partially filling the next level).

After execution, the best ask is now $182.06 with 50 shares remaining.  The market order has "walked the book" — consuming liquidity at successively worse prices.  This phenomenon is called **price impact**: large market orders move the price.

**Edge case — empty book.**  If a market buy order arrives but there are no ask orders in the book, the order cannot be filled.  In a real exchange, the order would typically be rejected or queued.  In our simulation, the market order simply produces no fills.

#### 2.2.3 Cancellations

A **cancellation** is the withdrawal of a previously submitted limit order.  The order is removed from the book without any execution.

Cancellations are extremely common in modern electronic markets. Empirical studies consistently report that the vast majority of limit orders are cancelled before they are ever executed.  Cont, Stoikov and Talreja (2010) report cancellation rates comparable to or exceeding limit-order arrival rates for stocks on the Tokyo Stock Exchange.  Bouchaud, Mézard and Potters (2002) report similar findings for stocks on the Paris Bourse.

**Why are cancellations so frequent?**  Many market participants — especially algorithmic traders and market makers — continuously adjust their quotes in response to new information (price changes in related assets, news events, changes in inventory).  Each adjustment involves cancelling the old order and submitting a new one at a different price.  A single market-making algorithm may cancel and resubmit thousands of orders per second.

#### 2.2.4 How the Three Order Types Work Together: A Running Example

Consider a simplified order book for a fictional stock "XYZ" with a tick size of $0.01.  We trace through a sequence of events to show how limit orders, market orders, and cancellations interact.

**Initial state (empty book):**

```
  ASK SIDE: (empty)
  BID SIDE: (empty)
```

**Event 1: Limit sell, 100 shares at $50.03.**

```
  ASK: $50.03 × 100
  BID: (empty)
```

**Event 2: Limit sell, 200 shares at $50.05.**

```
  ASK: $50.03 × 100,  $50.05 × 200
  BID: (empty)
```

**Event 3: Limit buy, 150 shares at $50.00.**

```
  ASK: $50.03 × 100,  $50.05 × 200
  BID: $50.00 × 150
  Spread: $50.03 − $50.00 = $0.03
  Midprice: ($50.00 + $50.03) / 2 = $50.015
```

**Event 4: Limit buy, 100 shares at $50.01.**

```
  ASK: $50.03 × 100,  $50.05 × 200
  BID: $50.01 × 100,  $50.00 × 150
  Best bid is now $50.01.  Spread narrows to $0.02.
  Midprice: ($50.01 + $50.03) / 2 = $50.02
```

**Event 5: Market buy, 100 shares.**  This aggressive order lifts the best ask:

```
  Trade: 100 shares at $50.03.
  ASK: $50.05 × 200          ← $50.03 level is exhausted
  BID: $50.01 × 100,  $50.00 × 150
  Spread widens to $50.05 − $50.01 = $0.04.
  Midprice: ($50.01 + $50.05) / 2 = $50.03
```

**Event 6: Cancel the bid at $50.01.**  The trader who placed it withdraws the order:

```
  ASK: $50.05 × 200
  BID: $50.00 × 150
  Spread widens further to $50.05 − $50.00 = $0.05.
  Midprice: ($50.00 + $50.05) / 2 = $50.025
```

**Event 7: Market sell, 200 shares.**  This aggressive order hits the bid side.  Only 150 shares are available at $50.00:

```
  Trade: 150 shares at $50.00.
  50 shares of the market sell order remain unfilled (no more bids).
  ASK: $50.05 × 200
  BID: (empty)
  Midprice: undefined (no bids).
```

This example illustrates several important dynamics:

- **Limit orders build the book** by adding resting liquidity.
- **Market orders consume the book** by executing against resting orders, often widening the spread.
- **Cancellations thin the book** by removing resting liquidity, also widening the spread.
- **The spread fluctuates** as the balance between these three forces shifts.
- **The midprice moves** as a consequence of which orders are added, executed, or removed.

**What happens when one order type dominates?**

- *Many limit orders, few market orders:*  The book becomes deep (many orders at many price levels), the spread narrows, and the midprice is stable.  This is characteristic of a calm, liquid market.

- *Many market orders, few limit orders:*  The book is thin, market orders quickly exhaust available liquidity, the spread widens, and the midprice moves sharply.  This is characteristic of a volatile, illiquid market or a period of intense directional trading.

- *Many cancellations:*  The book thins out even without market orders.  If cancellations outpace new limit orders, the spread widens and liquidity deteriorates.  This can happen during periods of uncertainty when market makers withdraw their quotes.

### 2.3 Price–Time Priority

When multiple limit orders exist at the same price level, the exchange must decide which order is executed first when a market order arrives.  The universal rule on major exchanges is **price–time priority** (also called FIFO matching):

1. **Price priority.**  The order with the best price is served first. For buy orders, "best" means the highest price (the buyer willing to pay the most gets served first).  For sell orders, "best" means the lowest price (the seller willing to accept the least gets served first).

2. **Time priority.**  Among orders at the *same* price, the order that arrived *earliest* is served first (first in, first out).

#### 2.3.1 Worked Example of Price–Time Priority

Suppose the ask side of the book contains the following four sell orders, listed in the order they arrived:

```
  Order A: sell 100 @ $50.03  (arrived at t = 1)
  Order B: sell 200 @ $50.05  (arrived at t = 2)
  Order C: sell 150 @ $50.03  (arrived at t = 3)
  Order D: sell 100 @ $50.04  (arrived at t = 4)
```

A market buy order for 400 shares arrives.  The matching engine processes it as follows:

1. **Price priority selects $50.03 first** (the lowest ask price). At $50.03, there are two orders: A (arrived t=1) and C (arrived t=3).
2. **Time priority selects Order A first** (it arrived earlier). Fill: 100 shares at $50.03.  Order A is fully consumed. Remaining demand: 300 shares.
3. **Time priority selects Order C next** (the only remaining order at $50.03).  Fill: 150 shares at $50.03.  Order C is fully consumed.  Remaining demand: 150 shares.
4. **Price priority moves to $50.04** (the next-best ask price). Fill: 100 shares at $50.04.  Order D is fully consumed. Remaining demand: 50 shares.
5. **Price priority moves to $50.05.**  Fill: 50 shares at $50.05. Order B is partially filled (150 shares remain).

Final state of the ask side:

```
  Order B: sell 150 @ $50.05  (partially filled)
```

Note that Order B arrived *before* Orders C and D, but was filled *after* them because its price ($50.05) was worse (higher) than theirs.  Price priority always dominates time priority.

### 2.4 Why Heaps?

The price–time priority rule maps directly onto a **heap** (priority queue) data structure.

A **binary heap** is an array-based data structure that maintains the **heap property**: the element at the root is the minimum (in a min-heap) or maximum (in a max-heap) of all elements.  The key operations and their time complexities are:

| Operation                       | Time complexity |
|---------------------------------|-----------------|
| Insert (push)                   | O(log n)        |
| Extract-min/max (pop)           | O(log n)        |
| Peek at min/max                 | O(1)            |
| Build heap from array (heapify) | O(n)            |
| Remove element at known index   | O(log n)        |
| Remove element (index unknown)  | O(n)            |

#### 2.4.1 Representing the Bid and Ask Sides as Heaps

**Ask side → min-heap.**  The best ask is the *lowest* price, so a min-heap naturally places it at the root.  Each entry is a tuple `(price, timestamp, order)`.  The min-heap ordering ensures that the lowest price is always at position 0, and among equal prices, the smallest timestamp (earliest arrival) comes first.

```
  Example ask-side min-heap (array representation):
  Index 0: ($50.03, t=1, Order_A)   ← root = best ask
  Index 1: ($50.05, t=2, Order_B)
  Index 2: ($50.03, t=3, Order_C)
  Index 3: ($50.04, t=4, Order_D)
```

**Bid side → max-heap.**  The best bid is the *highest* price, so a max-heap places it at the root.  In practice, since Python's `heapq` only provides a min-heap, the standard technique is to negate the price: store `(-price, timestamp, order)` in a min-heap, so the most negative value (corresponding to the highest original price) is at the root.

```
  Example bid-side min-heap with negated prices:
  Index 0: (-$50.01, t=4, Order_X)  ← root = best bid ($50.01)
  Index 1: (-$50.00, t=3, Order_Y)
```

The heapx module also supports native max-heaps via `max_heap=True`, eliminating the need for price negation.

#### 2.4.2 The Cancellation Problem

The last two rows of the complexity table above are critical for this case study.  Python's standard-library `heapq` module provides push and pop but has **no remove operation at all**.  To cancel an order, a `heapq` user must:

1. Locate the order via a linear scan of the heap array — **O(n)**.
2. Remove the element (e.g., swap with the last element and pop).
3. Call `heapq.heapify()` to rebuild the entire heap — **O(n)**.

The total cost of a single cancellation is therefore **O(n)**.

The heapx module provides `heapx.remove(heap, indices=i)`, which removes the element at position *i* and restores the heap property via a single sift-up or sift-down — **O(log n)**.  When the book contains hundreds or thousands of orders and cancellations are frequent, this difference is decisive.

### 2.5 The Midprice as a Random Walk

A fundamental result in market microstructure theory is that the midprice of a limit order book, under certain conditions, converges to a **Brownian motion** (random walk) as the time scale shrinks.

The term **symmetric order flow** means that the statistical properties of buy-side activity are identical to those of sell-side activity.  Formally, the arrival rates, size distributions, and cancellation rates of bid orders are equal to those of ask orders. In our simulation, this symmetry holds by construction: the parameters for limit-bid and limit-ask arrivals are identical, and the market-buy and market-sell rates are equal.

The term **tick size** refers to the minimum price increment allowed by the exchange.  For example, if the tick size is $0.01, then valid order prices are $100.00, $100.01, $100.02, and so on — but not $100.005.  When we say the midprice converges to Brownian motion "as the tick size shrinks," we mean: in the mathematical limit where the tick size δ → 0 and the order arrival rates are scaled appropriately, the discrete price process (which jumps by multiples of δ) converges in distribution to a continuous Brownian motion.  This was proved rigorously by Abergel and Jedidi (2013) using the functional central limit theorem (FCLT) applied to a continuous-time Markov chain model of the LOB.

Our simulation reproduces this property: the midprice trajectory (Figure 1) exhibits the characteristic irregular, non-periodic fluctuations of a random walk — it has no discernible trend, no periodicity, and its variance grows approximately linearly with time.

### 2.6 Stylised Facts

Empirical studies of financial markets have identified a set of statistical regularities — called **stylised facts** — that are observed across different markets, asset classes, and time periods (Cont, 2001).  Two stylised facts are relevant to this case study:

#### 2.6.1 Fat-Tailed Return Distribution

The distribution of log-returns has heavier tails than a Gaussian (normal) distribution.  This means that extreme price movements — both large gains and large losses — occur more frequently than a normal model would predict.

Technically, this is described by **excess kurtosis**.  The kurtosis of a distribution measures the weight of its tails relative to a normal distribution.  A normal distribution has a kurtosis of exactly 3 (or equivalently, an excess kurtosis of 0).  A distribution with kurtosis greater than 3 (positive excess kurtosis) is called **leptokurtic** — it has a sharper peak near the mean and heavier tails.  Financial return distributions are consistently found to be leptokurtic.

Our Figure 5 demonstrates this clearly.  The plot uses a **logarithmic y-axis** so that the tail behaviour is visible.  On a log scale, a normal distribution appears as a downward-opening parabola.  The simulated returns (blue histogram) extend well beyond the normal fit (red curve) in both tails — the histogram bars are above the red curve at extreme return values.  This is the visual signature of fat tails.

#### 2.6.2 Volatility Clustering

**Volatility clustering** is the empirical observation, first noted by Mandelbrot (1963), that "large changes tend to be followed by large changes, of either sign, and small changes tend to be followed by small changes."  In other words, volatility (the magnitude of price changes) is not constant over time — it comes in clusters.

To understand this concretely, imagine watching a stock price throughout a trading day.  During the morning, the price might move by only a few cents per minute (low volatility).  Then, at 2:00 PM, a surprising earnings announcement is released.  For the next hour, the price swings by tens of cents per minute (high volatility). After the market digests the news, volatility subsides again.  The key observation is that the high-volatility period is not a single isolated event — it persists for a stretch of time.  This is volatility clustering.

Statistically, volatility clustering manifests as **positive autocorrelation in the absolute values (or squares) of returns**. The autocorrelation function (ACF) of |r_t| at lag k measures the linear dependence between |r_t| and |r_{t+k}|.  If volatility clusters, then a large |r_t| predicts a large |r_{t+k}| for small k, producing positive ACF values.  The ACF typically decays slowly (often following a power law), indicating that volatility persistence extends over many time steps.

Our Figure 6 shows the ACF of absolute returns from the simulation. The ACF starts at approximately 0.08 at lag 1 and decays slowly toward zero over hundreds of lags, confirming that the simulation reproduces volatility clustering.


---

## 3. The Stochastic Order-Flow Model

The order-flow generator implements the model of **Cont, Stoikov and Talreja (2010)**, published in *Operations Research* 58(3), pp. 549–563.  This is one of the most widely cited quantitative models of limit order book dynamics.

### 3.1 Model Description

The model treats the LOB as a **continuous-time Markov chain**.  Three types of events — limit orders, market orders, and cancellations — arrive according to independent **Poisson processes**.

A **Poisson process** is a stochastic counting process N(t) that counts the number of events occurring in the time interval [0, t]. It is characterised by a single parameter λ > 0 called the **rate** (or **intensity**), and has three defining properties:

1. **No simultaneous events.**  The probability of two or more events occurring at exactly the same instant is zero.
2. **Independent increments.**  The numbers of events in non-overlapping time intervals are statistically independent.
3. **Exponential inter-arrival times.**  The time between consecutive events follows an exponential distribution with mean 1/λ.  That is, if T is the time until the next event, then P(T > t) = exp(−λt) for all t ≥ 0.

Property 3 is the key for simulation: to generate the next event time, we draw a random sample from an exponential distribution.

#### 3.1.1 Limit Orders

In the Cont–Stoikov–Talreja model, limit orders arrive at each price level independently.  The rate at which limit orders arrive at a price that is *i* ticks away from the current midprice is:

```
rate(i) = λ · exp(−κ · i)       for i = 1, 2, 3, …, D
```

where:
- λ > 0 is the **base arrival rate** (orders per second at the nearest tick level),
- κ > 0 is the **decay constant** controlling how quickly the rate falls with distance,
- D is the maximum depth (the furthest tick-distance at which orders are placed).

The phrase **"i ticks away"** means the order is placed at a price that differs from the current midprice by exactly i × (tick size). For example, if the midprice is $100.00 and the tick size is $0.01:

- 1 tick away on the bid side = $99.99
- 2 ticks away on the bid side = $99.98
- 1 tick away on the ask side = $100.01
- 3 ticks away on the ask side = $100.03

The exponential decay exp(−κ · i) captures the empirical observation that most limit orders are placed near the current price, with progressively fewer orders at distant price levels.  With κ = 0.3 (our default), the rate at 1 tick away is λ · exp(−0.3) ≈ 0.74λ, at 5 ticks away it is λ · exp(−1.5) ≈ 0.22λ, and at 10 ticks away it is λ · exp(−3.0) ≈ 0.05λ.  In absolute terms with λ = 2.0, these are approximately 1.48, 0.45, and 0.10 orders per second, respectively.

The total limit-order arrival rate across all price levels on both sides of the book is:

```
Λ_limit = 2 · Σ_{i=1}^{D} λ · exp(−κ · i)
```

The factor of 2 accounts for both the bid and ask sides (the model assumes symmetric order flow).

#### 3.1.2 Market Orders

Market orders arrive at rate μ per second on each side (buy and sell), independently.  The total market-order arrival rate is 2μ.

#### 3.1.3 Cancellations

Cancellations occur at rate θ per outstanding order per second.  If there are N(t) live orders in the book at time t, the total cancellation intensity at time t is:

```
Λ_cancel(t) = θ · N(t)
```

This proportional structure is the mechanism that ensures the book reaches a **stationary** (bounded) depth.  As the book accumulates more orders, the cancellation rate increases, creating a self-regulating feedback loop: inflow (limit orders) is balanced by outflow (market orders + cancellations).

#### 3.1.4 How the Three Event Types Interact in the Model

Consider a book that starts empty.  Initially, N(t) = 0, so the cancellation rate is zero.  Limit orders arrive and accumulate.  As the book fills, N(t) grows, and the cancellation rate θ · N(t) increases.  Eventually, the rate of cancellations plus the rate of market-order executions equals the rate of new limit-order arrivals, and the book reaches a statistical equilibrium (steady state).

At steady state, the expected book depth is approximately:

```
E[N] ≈ Λ_limit / (θ + 2μ / E[N])
```

With our default parameters (λ=2.0, κ=0.3, μ=2.5, θ=0.02), the book stabilises at roughly 250–350 orders per side.

**What happens if parameters are unbalanced?**

- *High θ (aggressive cancellation):*  Orders are cancelled quickly, the book is thin, the spread is wide, and the midprice is volatile.
- *Low θ (few cancellations):*  The book grows deep, the spread is tight, and the midprice is stable — but the simulation becomes unrealistic because real markets have high cancellation rates.
- *High μ (many market orders):*  Liquidity is consumed rapidly, the book thins out, and the midprice moves sharply.
- *Low μ (few market orders):*  The book accumulates orders without much execution, and the midprice barely moves.

### 3.2 Simulation via the Thinning Algorithm

Because the cancellation rate depends on the current book state (specifically, the number of live orders), the total event intensity is **time-varying** — it changes as the simulation progresses.  A standard homogeneous Poisson process (with a fixed rate) cannot directly generate events from a time-varying intensity.

The **thinning algorithm**, introduced by Lewis and Shedler (1979), solves this problem.  It is a rejection-sampling method that converts a simple homogeneous Poisson process into a non-homogeneous one.

#### 3.2.1 The Algorithm, Step by Step

**Inputs:**
- A time-varying intensity function λ(t) that gives the actual event rate at any time t.
- An upper bound Λ such that λ(t) ≤ Λ for all t in the simulation interval.  (In our case, Λ is computed by assuming a maximum book size of 2,000 orders.)

**Procedure:**

1. **Generate a candidate event time.**  Draw a random inter-arrival time Δt from an exponential distribution with rate Λ (the upper bound).  Set the candidate time t_candidate = t_current + Δt.

2. **Compute the actual intensity.**  At time t_candidate, evaluate the true intensity λ(t_candidate).  In our simulation, this means computing the current cancellation rate θ · N(t) and adding it to the fixed limit-order and market-order rates.

3. **Accept or reject.**  Draw a uniform random number U ∈ [0, 1].
   - If U ≤ λ(t_candidate) / Λ, **accept** the candidate: an event occurs at time t_candidate.
   - If U > λ(t_candidate) / Λ, **reject** the candidate: no event occurs.  Return to step 1.

4. **If accepted, determine the event type.**  Draw another uniform random number to select among the competing event types (limit bid, limit ask, market buy, market sell, cancellation), with probabilities proportional to their respective rates.

5. **Repeat** until the desired number of events has been generated.

#### 3.2.2 Why Thinning Works

The key insight is that a homogeneous Poisson process with rate Λ generates candidate times at a rate that is *always at least as high* as the true rate λ(t).  By randomly rejecting candidates with probability 1 − λ(t)/Λ, we "thin out" the excess events, leaving behind exactly the events that would have been generated by the true non-homogeneous process.

**Concrete example.**  Suppose at some moment the book contains 100 orders.  The actual total intensity is:

```
λ(t) = Λ_limit + 2μ + θ · 100
      = 15.4 + 5.0 + 0.02 · 100
      = 22.4 events/second
```

But our upper bound is Λ = 15.4 + 5.0 + 0.02 · 2000 = 60.4.  So the acceptance probability is 22.4 / 60.4 ≈ 0.37.  About two-thirds of candidate events are rejected.  This is computationally wasteful but mathematically exact.

Later, if the book grows to 1,500 orders, the actual intensity rises to 15.4 + 5.0 + 0.02 · 1500 = 50.4, and the acceptance probability increases to 50.4 / 60.4 ≈ 0.83.  The algorithm automatically adapts to the changing intensity.

**Edge case — intensity exceeds the bound.**  If the book ever grows beyond 2,000 orders, the actual intensity would exceed Λ, and the algorithm would undercount events.  In practice, with our default parameters, the book stabilises well below 2,000, so this does not occur.  A production implementation would dynamically adjust Λ.

### 3.3 Default Parameters

| Parameter             | Symbol | Default    | Meaning                                           |
|-----------------------|--------|------------|---------------------------------------------------|
| Limit-order base rate | λ      | 2.0 s⁻¹    | Arrival rate at the nearest tick level            |
| Decay constant        | κ      | 0.3        | Controls how quickly the rate falls with distance |
| Market-order rate     | μ      | 2.5 s⁻¹    | Rate per side (buy and sell independently)        |
| Cancellation rate     | θ      | 0.02 s⁻¹   | Per outstanding order per second                  |
| Max depth             | D      | 20 levels  | Furthest tick-distance for limit orders           |
| Tick size             | δ      | $0.01      | Minimum price increment                           |
| Initial price         | —      | $100.00    | Starting midprice                                 |
| Lot size              | —      | 100 shares | Fixed order quantity                              |

These parameters produce:
- A stationary book depth of approximately 250–350 orders per side.
- A bid–ask spread concentrated near 1–3 ticks ($0.01–$0.03).
- A diffusive midprice trajectory.
- An event mix of approximately 50% limit orders, 17% market orders, and 33% cancellations.

---

## 4. Code Architecture and Implementation

### 4.1 File Overview

```
src/
├── order_book.py        # heapx-backed LOB engine
├── order_book_heapq.py  # heapq-backed LOB engine (baseline)
├── order_flow.py        # Cont–Stoikov–Talreja order-flow generator
├── simulation.py        # Run simulation, collect time-series snapshots
├── benchmark.py         # Latency benchmark: heapx vs heapq
├── plot_results.py      # Generate 10 publication-quality PNG figures
├── run_all.py           # Master pipeline (simulation → benchmark → plots)
└── README.md            # This file
```

### 4.2 The heapx Order Book Engine (`order_book.py`)

The `OrderBook` class maintains two Python lists that serve as heaps:

- `self.bids`: a min-heap of tuples `(-price, timestamp, Order)`. By negating the price, the standard min-heap ordering yields the highest-priced bid at the root.

- `self.asks`: a min-heap of tuples `(price, timestamp, Order)`. The lowest-priced ask is at the root.

Each tuple's second element is the order's timestamp, which serves as the tiebreaker for price–time priority: among orders at the same price, the one with the smallest timestamp (earliest arrival) is served first.

**Limit order submission** calls `heapx.push(heap, entry)`, which appends the entry and performs a sift-up to restore the heap property. Time complexity: **O(log n)**.

**Market order execution** peeks at `heap[0]` to find the best available order, fills as much quantity as possible, and calls `heapx.pop(heap)` if the order is fully consumed.  Time complexity: **O(log n)** per fill.

**Order cancellation** proceeds in two steps:

1. **Locate the order.**  A dictionary `_id_to_side` maps each live order id to its side ("bid" or "ask") in O(1).  A linear scan of the heap then finds the positional index.

2. **Remove and restore.**  `heapx.remove(heap, indices=idx)` removes the element at position `idx` and restores the heap property via a single sift-up or sift-down.  Time complexity: **O(log n)**.

### 4.3 The heapq Baseline Engine (`order_book_heapq.py`)

The `OrderBookHeapq` class provides an identical interface using Python's standard-library `heapq`.  Push and pop use `heapq.heappush()` and `heapq.heappop()`.

For cancellation, because `heapq` has no remove operation, the baseline must:

1. Locate the order via the same linear scan.
2. Swap the found element with the last element in the list.
3. Pop the last element.
4. Call `heapq.heapify()` to rebuild the entire heap — **O(n)**.

### 4.4 The Order-Flow Generator (`order_flow.py`)

The `generate_order_flow()` function produces a list of `OrderEvent` objects using the thinning algorithm described in Section 3.2. Crucially, the generator maintains a lightweight internal book state — tracking the best bid, best ask, and midprice — so that new limit orders are placed relative to the **current midprice**, not a fixed reference price.  This is what produces the diffusive price trajectory visible in Figure 1.

### 4.5 The Benchmark Harness (`benchmark.py`)

The benchmark drives both engines through the **identical** event stream and records nanosecond-precision timings using `time.perf_counter_ns()`.

For cancellation events, the timing is **split into two phases**:

- `cancel_find_ns`: the time to locate the order in the heap (linear scan — identical cost for both engines).
- `cancel_maintain_ns`: the time for the heap-maintenance step after removal (heapx.remove vs heapq.heapify — the metric of interest).

This separation is essential for a fair comparison.  Without it, the linear-scan cost dominates both measurements and masks the O(log n) vs O(n) difference.

Garbage collection is disabled during each timed run (`gc.disable()`) to prevent GC pauses from contaminating the measurements.

### 4.6 The Plotting Module (`plot_results.py`)

Produces ten PNG figures at 300 DPI:

| #  | File                           | What it shows                               |
|----|--------------------------------|---------------------------------------------|
| 1  | `fig01_midprice.png`           | Midprice random walk with spread band       |
| 2  | `fig02_spread_dist.png`        | Right-skewed spread distribution            |
| 3  | `fig03_depth.png`              | Stationary bid/ask depth over time          |
| 4  | `fig04_volume.png`             | Linear cumulative traded volume             |
| 5  | `fig05_returns.png`            | Fat-tailed returns vs normal (log-scale)    |
| 6  | `fig06_autocorr.png`           | Volatility clustering (ACF of abs. returns) |
| 7  | `fig07_latency_bars.png`       | Push/pop/cancel latency with 26× annotation |
| 8  | `fig08_wall_speedup.png`       | End-to-end wall-clock speedup per trial     |
| 9  | `fig09_cancel_maintenance.png` | Isolated cancel heap-maintenance cost       |
| 10 | `fig10_event_mix.png`          | Event-type distribution bar chart           |

---

## 5. Performance Results

### 5.1 End-to-End Speedup

On a 50,000-event workload (seed 42, default parameters), heapx achieves a consistent **2.7–2.8× wall-clock speedup** over heapq across repeated trials.  This speedup is driven almost entirely by the cancellation operation.

### 5.2 Cancellation: O(log n) vs O(n)

The benchmark isolates the heap-maintenance cost of cancellation:

| Engine                  | Mean cancel maintenance | Complexity |
|-------------------------|-------------------------|------------|
| heapx (`heapx.remove`)  | ~270 ns                 | O(log n)   |
| heapq (`heapq.heapify`) | ~7,200 ns               | O(n)       |

This is a **27× speedup** on the heap-maintenance step alone, with a book depth of approximately 300 orders per side.  The ratio grows with book size because heapq's O(n) heapify scales linearly while heapx's O(log n) remove scales logarithmically.

### 5.3 Push and Pop

For push (limit order submission) and pop (market order execution), both engines perform comparably (~300 ns for push, ~550 ns for pop). This is expected: both are O(log n) operations.  The heapx advantage on these operations becomes more pronounced at larger heap sizes due to its type-specialised comparison paths, but at n ≈ 300 the constant-factor difference is small.

### 5.4 Why the Cancellation Difference Matters

In real financial markets, cancellations are the **most frequent** event type.  Empirical studies consistently report that the majority of limit orders are cancelled before execution (Cont et al., 2010; Bouchaud et al., 2002).  In our simulation, cancellations constitute approximately 33% of all events.  In a production order book with tens of thousands of outstanding orders and millions of events per day, the O(n) vs O(log n) difference on each cancellation translates to a substantial aggregate performance gap.

---

## 6. Value for Quantitative Finance Professionals

### 6.1 Who Benefits

This case study is directly relevant to:

- **Quantitative developers** building matching engines, order management systems, or market simulators in Python.
- **Algorithmic traders** who backtest strategies involving frequent order placement and cancellation (e.g., market-making, statistical arbitrage).
- **Risk analysts** who run Monte Carlo simulations of order book dynamics for stress testing or value-at-risk estimation.
- **Academic researchers** in market microstructure who need a fast, correct, and reproducible LOB simulator.

### 6.2 Why heapx Over Alternatives

| Module             | Push     | Pop      | Cancel       | Max-heap | Key func |
|--------------------|----------|----------|--------------|----------|----------|
| `heapq` (stdlib)   | O(log n) | O(log n) | **O(n)**     | No       | No       |
| `sortedcontainers` | O(log n) | O(log n) | O(log n)     | Yes      | Yes      |
| `heapx`            | O(log n) | O(log n) | **O(log n)** | Yes      | Yes      |

While `sortedcontainers.SortedList` also provides O(log n) removal, it maintains full sorted order (not just the heap property), so its constant factors for push and pop are higher.  heapx provides the optimal combination: heap-speed push/pop **and** O(log n) removal.

Additional usability advantages of heapx:

- **Native max-heap support.**  The bid side of an order book is naturally a max-heap.  With `heapq`, the standard workaround is to negate prices — error-prone and inapplicable to non-numeric keys. heapx supports `max_heap=True` natively.

- **Key function support.**  heapx accepts a `cmp` parameter for key-based ordering, eliminating the need to wrap objects in `(priority, counter, object)` tuples as required by `heapq`.

- **Bulk operations.**  `heapx.push(heap, [items])` performs bulk insertion.  `heapx.pop(heap, n=k)` extracts the top-k elements in a single call.

- **Single C extension, no dependencies.**  Installs via `conda install mukherjee08::heapx` with pre-built binaries.

### 6.3 Production Considerations

In a production matching engine, the linear-scan step to locate an order by id would be replaced by an auxiliary hash map that tracks each order's heap index, updated on every push, pop, and swap.  This would reduce the total cancellation cost to O(log n) for heapx (O(1) lookup + O(log n) remove) versus O(n) for heapq (O(1) lookup + O(n) heapify).  The benchmark in this case study already isolates the heap-maintenance cost to demonstrate this difference cleanly.

---

## 7. Reproducing the Results

### 7.1 Prerequisites

```bash
conda install mukherjee08::heapx
pip install numpy pandas matplotlib pyarrow
```

Python ≥ 3.9 is required.

### 7.2 Quick Start

```bash
cd src/
python run_all.py
```

This runs the full pipeline with default parameters (200K simulation events, 500K benchmark events, 5 repetitions, seed 42) and writes:

- `simulation.parquet` — per-event order-book snapshots.
- `results.json` — benchmark timing data.
- `figures/` — 10 PNG figures.

### 7.3 Custom Parameters

```bash
python run_all.py --events 1000000 --bench-events 2000000 --repeats 10
```

### 7.4 Running Individual Steps

```bash
python simulation.py --events 200000 --output simulation.parquet
python benchmark.py  --events 500000 --repeats 5 --output results.json
python plot_results.py --sim simulation.parquet --bench results.json --outdir figures
```

---

## References

1. R. Cont, S. Stoikov, R. Talreja, "A Stochastic Model for Order Book Dynamics," *Operations Research* 58(3), pp. 549–563, 2010.

2. F. Abergel, A. Jedidi, "A Mathematical Approach to Order Book Modeling," *arXiv:1010.5136*, 2013.

3. T. Preis, S. Golke, W. Paul, J. J. Schneider, "Multi-agent-based Order Book Model of Financial Markets," *Europhysics Letters* 75(3), pp. 510–516, 2006.

4. L. Lalor, A. Swishchuk, "Event-Based Limit Order Book Simulation under a Neural Hawkes Process: Application in Market-Making," *arXiv:2502.17417*, 2025.

5. Y. Li, Y. Wu, M. Zhong, S. Liu, P. Yang, "SimLOB: Learning Representations of Limit Order Book for Financial Market Simulation," *arXiv:2406.19396*, 2025.

6. J.-P. Bouchaud, M. Mézard, M. Potters, "Statistical Properties of Stock Order Books: Empirical Results and Models," *Quantitative Finance* 2(4), pp. 251–256, 2002.

7. R. Cont, "Empirical Properties of Asset Returns: Stylized Facts and Statistical Issues," *Quantitative Finance* 1(2), pp. 223–236, 2001.

8. B. Mandelbrot, "The Variation of Certain Speculative Prices," *The Journal of Business* 36(4), pp. 394–419, 1963.

9. P. A. W. Lewis, G. S. Shedler, "Simulation of Nonhomogeneous Poisson Processes by Thinning," *Naval Research Logistics* 26(3), pp. 403–413, 1979.

10. R. W. Floyd, "Algorithm 245: Treesort 3," *Communications of the ACM* 7(12), p. 701, 1964.

11. J. W. J. Williams, "Algorithm 232: Heapsort," *Communications of the ACM* 7(6), pp. 347–349, 1964.
