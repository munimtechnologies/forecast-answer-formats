# What a numeric misread costs — and when it is worse than a drop

`numeric_misread_cost.py` prices the last failure mode this repo had not made
type-specific: a **numeric misread**, where a forecasting bot's extractor reads the
wrong *number* out of a continuous forecast (drops a unit, reads "2 million" as
"2.0", grabs a figure from the reasoning, or takes the wrong one of several
percentiles). The binary misread model (`misread_cost.py`) left the penalty `L` as
a free scenario parameter. For a numeric forecast the penalty is **not** free: it
is fixed by the geometry of the continuous log score and the size of the misread.

## The law

Model the intended (correctly read) forecast as a predictive density centred at
`c0` with scale `sigma`, calibrated so the outcome `x` is drawn from it. A misread
submits the same shape centred at a wrong value, displaced by

```
z = (c1 - c0) / sigma          # displacement in standard deviations
```

For a Gaussian predictive density the extra log-score loss, averaged over the
calibrated outcome, is exactly

```
Delta(z) = 0.5 * z**2          # nats, independent of sigma
```

(The realized loss is `0.5*z**2 - z*g` with `g ~ N(0,1)`; its mean is `0.5*z**2`.)
With per-question peer edge `mu` for a correct read, one numeric misread earns peer
`mu - 0.5*z**2` and costs, relative to a correct read, `Delta(z)` of Total Score —
i.e. it behaves like

```
k(z) = z**2 / (2*mu)           # effective drops per misread
```

This is the **same** "effective drops per event" rule as the binary misread, where
`k = 1 + rho` with `rho = L/mu`. In both legs `k = (log-score loss relative to a
correct read) / mu`; the binary and numeric cases are two instances of one law, and
the prize factor is the familiar square-of-sum form

```
factor(d, m, z) = (max(0, 1 - d - m*k(z)))**2
```

reducing to `drop_cost`'s `(1-d)**2` when `m=0`.

## Three consequences the binary leg could not pin down

1. **Break-even displacement.** A numeric misread is worse than a *drop* (peer
   below 0) once `0.5*z**2 > mu`, i.e. once

   ```
   z > z* = sqrt(2*mu)
   ```

   Tournament edges are small (`mu ~ 0.02–0.1` nat), so `z*` is only about
   **0.2–0.45 sigma**. Any numeric misread that moves the forecast more than a
   small fraction of a standard deviation is already worse than giving no answer.

2. **Unit / magnitude misreads are catastrophic.** Reading "2 million" as "2.0"
   displaces the centre by many sigma, so `k = z**2/(2*mu)` runs into the hundreds:
   one such misread can erase the edge of hundreds of good forecasts.

3. **Zeroing.** A misread rate `m` drives the Total Score to 0 (prize 0, not merely
   smaller) once `m*k(z) >= 1`, i.e. above `2*mu / z**2`.

| z (sigma) | loss (nats) | k = drops (mu=0.03) | misread peer | factor at m=5% |
|---|---|---|---|---|
| 0.2 | 0.020 | 0.67 | +0.010 | 0.934 |
| 0.5 | 0.125 | 4.17 | −0.095 | 0.627 |
| 1.0 | 0.500 | 16.7 | −0.470 | 0.028 |
| 2.0 | 2.000 | 66.7 | −1.970 | 0 |
| 4.0 | 8.000 | 266.7 | −7.970 | 0 |

(At `mu=0.03` the break-even displacement is `z* = sqrt(0.06) ≈ 0.245 sigma`, so the
`z=0.2` row still beats a drop while every larger row is worse than dropping.)

## Honesty

The `0.5*z**2` loss is exact for a Gaussian predictive density and is the leading
term for any smooth density. The `(1 - d - m*k)**2` prize law is exact for the
sum-then-square rule when one bot does not move the pool's denominator (any
non-dominant entrant). `z` and `m` are scenario inputs, not measured frequencies,
and misreads may be correlated with a format family. `test_numeric_misread_cost.py`
checks the analytic law and a Monte Carlo that draws calibrated outcomes and a
realistic non-dominant pool reproduces both the `0.5*z**2` loss and the prize
factor.

*Made with AI, by MV2 of Munim, Inc. Code Apache-2.0; text CC BY 4.0.*
