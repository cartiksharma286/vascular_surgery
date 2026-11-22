# Boston Scientific catheter preprint — Version 1.1 extension draft (prepared 2026-11-18)

Prepared for Cartik. This is a draft specification for delivery to build as
Version 1.1 of `boston-scientific-catheter-supply-chain-qml-preprint.pdf`
(11 pp., v1.0, 18 Nov 2026). It is NOT yet a PDF. The user only needs to
approve building it, pick a different extension, or leave v1.0 as is.

## Why this extension, now

v1.0 itself flagged three gaps in §7 (Discussion, limitations):
1. a single seed and configuration were tested — "multi-seed intervals are
   required before any operational inference";
2. QAOA was formulated but not executed, and the shadow decomposition was
   said to separate "periodic content from decaying disruption" — but no
   disruption was ever simulated;
3. expiry was in the objective but "not simulated lot-by-lot, so expiry
   write-off savings … are not quantified here".

The assistant's delivery message for v1.0 offered exactly this next step:
"extend it next — for example with a real catheter family, a disruption
scenario, or a cost / service-level sensitivity?" This draft does the
disruption scenario + cost/service sensitivity + multi-seed robustness, and
closes the expiry question with a checked (negative) result.

## What was actually computed (verified 2026-11-18, local Python, NumPy/SciPy)

The v1.0 generator was re-run first as a replication check. Seed 7 reproduces
v1.0 Tables 2–3 exactly: pooled MAPE 17.25% baseline / 12.27% elliptic-modular
/ 12.22% quantum-kernel emulation; fill 97.25% / 98.71% / 98.75%;
average inventory 1,124 / 1,133 / 1,133 units; test demand 92,386 units.
All numbers below use the identical generator, bases (A balloon 420,
B ablation 180, C diagnostic 650, D guiding 310), trend, seasonality,
log-normal σ = 0.14, 104-week train / 52-week test split, and (s, S) policy
with 3-week lead time — only the seed, the disruption window, or the safety
multiplier changes, as stated per table.

### 1. Multi-seed robustness — seeds 7, 11, 23, 42, 101 (new Table 4)

| Forecaster | Pooled MAPE, mean ± SD (%) | MAPE range | Fill rate, mean ± SD (%) | Fill range |
|---|---|---|---|---|
| Trailing-mean baseline | 17.15 ± 0.26 | 16.84–17.52 | 96.95 ± 0.81 | 95.57–97.53 |
| Elliptic-modular | 13.31 ± 0.82 | 12.27–14.15 | 98.69 ± 0.90 | 97.28–99.60 |
| Quantum-kernel emulation | 13.21 ± 0.79 | 12.22–14.02 | 98.74 ± 0.89 | 97.34–99.60 |

Reading: the v1.0 finding survives across seeds — the modular gain over
baseline is ~3.8 pp of MAPE and ~1.7 pp of fill. The quantum–classical gap
is 0.10 pp of MAPE (13.21 vs 13.31) and 0.05 pp of fill, far smaller than the
across-seed SD (~0.8 pp). Same null conclusion as v1.0, now with intervals.

### 2. Disruption scenario — the shadow / non-holomorphic component, made concrete (new §9, Table 5)

Scenario, stated as an equation in the draft: lead time L = 3 weeks
normally; for orders placed in test weeks 20–27, L = 8 weeks
(a 5-week delay, e.g. a plant / lane interruption). Demand unchanged.
This is the decaying-disruption residual that §4.1 said the shadow
ξ_k f carries — here it is imposed, not fitted, so the test is whether the
seasonal policy degrades more gracefully.

Seed 7: fill 97.25% → 87.46% (baseline), 98.71% → 89.34% (modular),
98.75% → 89.36% (quantum emulation). Weekly fill in weeks 20–31 averages
59.3% (baseline) vs 60.1% (modular); fill is 0% for 4–5 weeks (weeks 24–28
seed 7) until delayed arrivals land in week 28, then recovers to 100%
within one week. That 0% stretch is a property of the stylised pooled model
(no expediting, no substitution, no safety-stock draw beyond the (s, S)
target) and must be labelled as a stress test, not a forecast of a real
disruption.

Multi-seed mean fill under disruption: baseline 87.28 ± 0.74%
(range 86.01–87.99); modular 89.14 ± 0.98% (87.82–90.32);
quantum emulation 89.19 ± 0.96% (87.89–90.32).
So the modular advantage under disruption is +1.86 pp of fill, larger than
in normal operation (+1.74 pp), while the quantum layer again adds ~0.05 pp.

### 3. Cost / service-level sensitivity (new §10, Table 6, seed 7, modular forecast)

Safety multiplier z in Eq. (3), modular forecast, pooled test year:

| z | Fill (%) | Avg inventory (units) | Total ordered (units) |
|---|---|---|---|
| 0.80 | 97.34 | 977 | 83,008 |
| 1.00 | 98.02 | 1,037 | 83,740 |
| 1.28 (v1.0) | 98.71 | 1,133 | 84,530 |
| 1.65 | 99.49 | 1,270 | 85,448 |
| 2.00 | 99.84 | 1,421 | 85,960 |
| 2.33 | 100.00 | 1,572 | 86,281 |

Baseline forecast at the same multipliers: z = 1.28 → 96.05% / 1,013 units;
z = 1.65 → 97.25% / 1,124; z = 2.00 → 98.19% / 1,239.
Headline trade: the modular forecast at z = 1.00 already beats the baseline
at z = 1.65 on fill (98.02% vs 97.25%) with 87 fewer average inventory
units — the seasonal forecast buys service, it does not just buy stock.

### 4. Lot-by-lot expiry — checked, negative result (new §10.2, must be included honestly)

A FEFO lot simulation was run (lots carry an expiry week; expired units
removed before demand is served; orders arrive as new lots).
Result: 0 expired units for every policy at shelf lives of 52, 26, and
13 weeks (seed 7). Reason, to state in the paper: pooled average inventory
is ~1,133 units against ~1,777 units/week pooled demand, so stock turns in
under a week — expiry cannot bind in a pooled model. The v1.0 limitation
therefore is NOT closed by this extension: quantifying expiry savings needs
a per-SKU, slow-mover model (low-volume sizes / families with weeks of
cover), which is the honest next step to name, not a number to invent.
Do not let v1.1 claim any expiry write-off saving.

## Proposed v1.1 structure

- Keep Part I / §§1–7 and Appendices A–B unchanged.
- New Part II: §8 Multi-seed robustness (Table 4), §9 Disruption and the
  shadow component (Table 5, lead-time equation, recovery discussion),
  §10 Service–cost sensitivity and the expiry check (Table 6, §10.2 negative
  result), plus a one-paragraph revised conclusion.
- New Appendix C: complete deterministic code regenerating Tables 4–6
  (multi-seed loop, lot/FEFO simulator, disruption lead-time switch,
  sensitivity sweep; seeds 7, 11, 23, 42, 101).
- Version line: Version 1.1 | 18 November 2026. All existing caveats carry
  forward verbatim: independent, not peer-reviewed, no Boston Scientific
  affiliation, all numbers synthetic, quantum kernel classically emulated,
  QAOA still formulated not run, no quantum advantage claimed.

## Files / sources for delivery

- v1.0 PDF (verified, 11 pp.):
  `/home/hatch/workspace/your_files/boston-scientific-catheter-supply-chain-qml-preprint/boston-scientific-catheter-supply-chain-qml-preprint.pdf`
- v1.0 §7 limitations and the extension offer are in the 2026-11-18
  conversation (Boston delivery message, 05:32:57 UTC).
- Computation scripts used for this draft (local, reproducible):
  `/tmp/boston_ext.py`, `/tmp/boston_ext2.py`, `/tmp/boston_ext3.py`
  — delivery should re-run / fold the Appendix C code from these, not
  re-derive the numbers from the tables above alone.
- Expected length: ~15–16 pages (v1.0 11 pp. + ~4–5 pp. Part II + Appendix C).

## Decision left to Cartik

1. Build v1.1 as specified above, or
2. Build a different extension instead (e.g. a named catheter family, or
   the per-SKU slow-mover expiry model), or
3. Leave v1.0 as is — no action.
