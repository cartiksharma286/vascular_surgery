# Draft — reconciling the two >$100M models (app vs preprint §11)

Prepared 2026-11-22, not yet built. The health-economics work finished
today in two places, and the two Year-3 numbers are different models,
not a mistake — but nothing in either place says that yet.

## The two numbers, checked

**App — Economics tab, service-line model (single hospital line)**
- Today: 2,850 cases/yr × $18,500 = $52.7M.
- Levers: volume +14%/yr, reimbursement +5%/yr, case-mix +4%/yr.
- Year 3: 4,222 cases × $24,090 = **$101.72M**, EBITDA $33.0M.
- What it measures: full procedure revenue per case.

**Preprint v1.2, §11 — platform model (many sites)**
- Year 1: 17,280 cases × $680 fee + 90 sites × $40,000 licence
  + 25% FE share × $300 royalty = $11.75M + $3.60M + $1.30M = $16.65M.
- Year 2: 50,400 cases, 210 sites, $740 fee, 40% FE share = $51.74M.
- Year 3: 97,920 cases × $800 fee + 340 sites × $40,000 licence
  + 55% FE share × $300 royalty = $78.34M + $13.60M + $16.16M
  = **$108.09M**.
- What it measures: software fee + site licence + FE royalty per case
  — $1,104 per case in Year 3, not procedure revenue.

Recomputed from the stated parameters; both totals reproduce exactly.

## Why they differ (and why neither is wrong)

- Different scope: one service line (4,222 cases) vs a 340-site
  platform (97,920 cases).
- Different unit: $24,090 of procedure revenue per case in the app
  vs $1,104 of platform revenue per case in the paper.
- Different levers: the app moves volume / reimbursement / case-mix;
  the paper moves sites, fee, licence and FE-royalty share.
- The paper's ML cross-check (ridge R² 0.997, GBM R² 0.989) checks
  the platform identity only; the app's ridge (R² 0.983) checks its
  own 36-month history only. Neither validates the other.

## Proposed fix (v1.3 note + app view)

1. **Preprint, new §11.7 "Reconciliation with the app":** a short
   scope note plus the bridge table above, stating explicitly that
   $101.7M and $108.09M are different models and must not be read
   as the same projection, or as two estimates of one number.
2. **App, Economics tab:** a "Platform view" toggle showing the
   §11 scale scenario alongside the current service-line view,
   with the same scope labels, so the two can be compared without
   confusion.
3. No numbers change in either place. This is a labelling and
   scope fix, not a re-model.

## What building it needs

1. Confirm the Year-2 fee ($740) in Table 6 — it reproduces the
   $51.74M total, but should be stated explicitly.
2. Add §11.7 and the bridge table to the preprint; rebuild as v1.3.
3. Add the Platform view to the app's Economics tab; relaunch.

## Honest limits to carry

- Both remain synthetic scenario models, not forecasts of any real
  hospital or platform; independent, not peer-reviewed.
- The $100M crossing is a property of each model's own scale
  scenario, not a prediction.
