# Vascular Surgery App — v7 snapshot

Hosted fullstack app, launched 2026-11-22. This is a documentation snapshot;
the app itself runs in Muse, not from this folder.

## Tabs

- **Case board** — finite 8-state workflow: Referred → Imaging → Planning →
  Consent → Scheduled → In OR → Recovery → Follow-up. 6 synthetic demo
  patients, MRNs DEMO-001 to DEMO-006, each with a linked PACS study
  DEMO-ACC-001 to DEMO-ACC-006. No real patient data.
- **QML Lab** — exact, classically emulated 6-qubit angle-encoding quantum
  kernel vs higher/lower-risk prototypes, RBF comparison, two-vector kernel
  calculator, exact 8-state Markov forecast.
- **PACS board** — register studies, manage destination nodes, move jobs
  queued → sending → delivered. User-managed, not connected to a live
  hospital system.
- **Simulation** — experimental finite hyperelastic soft-tissue simulation
  (Neo-Hookean, Mooney–Rivlin, linear-elastic; five tissue presets; three
  plots with full legends; characteristics grid) plus a finite element
  simulation for minimally invasive intraoperative surgery (8–32 ring
  elements, Thomas solver K u = F, balloon/stent load, contact cap,
  plaque-yield softening). Verified default: lumen 1.20 mm → 6.00 mm,
  max hoop stress 629 kPa, 2 yielded elements, 5 contact nodes, 223 N.
  Labelled experimental, not for clinical decisions.
- **Economics** — health economics cost component. Ridge-regression
  statistical ML on 36 months of synthetic history, 3-year trajectory
  under Conservative / Base / Growth scenarios. Defaults: 2,850 cases/yr
  × $18,500 = $52.7M today; Base reaches $101.7M in Year 3, EBITDA $33.0M.
  Scenario model, not a forecast of any real hospital.
- **Optimize** — catheter performance optimization. Illustrative archetypes
  labelled Boston Scientific, Abbott, Johnson & Johnson (generic teaching
  archetypes, not real product specs). 8 design parameters with tolerances
  and manufacturing processes, deterministic generative recommendation
  engine, Neuromorph catheter characteristics. Verified: Boston Scientific
  archetype 63.2 → 77.0 (+22.0%), Cpk 0.77 → 1.43.
- **Math & code** — finite-math implementation in Python and JavaScript,
  including the Thomas solver, ridge fit, and economics projection.

## Limits

Synthetic-only throughout. Experimental, not for clinical decisions or
device guidance. No affiliation with Boston Scientific, Abbott, or
Johnson & Johnson; no quantum advantage claimed.
