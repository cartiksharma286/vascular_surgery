# Draft — v1.1 extension for the quantum-kernel / soft-tissue preprint

Prepared 2026-11-22, not yet built into a PDF. Based on the Vascular Surgery App's
Simulation tab after the finite element (FE) simulation was added on 2026-11-22.
The v1.0 preprint is 13 pages, "Quantum kernel scoring coupled to finite hyperelastic
soft-tissue modelling for vascular surgery", Eqs. (1)–(15), Tables 1–3, Figures 1–2,
Appendices A–B.

## Proposed addition

A new section, §10 "Finite element simulation of minimally invasive intraoperative
expansion", inserted before the Discussion (then §11), plus a new Table 4, Figure 3,
and Appendix C (Thomas solver in Python). Sections after it renumber; §§1–9 unchanged.
Estimated length: 13 pages → about 16–17 pages.

## What it adds, in the paper's own terms

- The soft-tissue model in v1.0 is a static, thin-wall, single-ring inflation law
  (Eqs. 9–11). The FE section discretises the vessel longitudinally, so a focal
  lesion, a device of finite length, and a contact cap can be represented — things
  the single-ring law cannot express.
- Mesh: a vessel segment divided into N = 8–32 ring elements (N + 1 nodes,
  N − 1 free radial degrees of freedom after the two end nodes are fixed).
  Each element carries its own Mooney–Rivlin tangent modulus and plaque
  stiffening factor.
- Governing system, solved exactly (Thomas algorithm, two passes in the
  verified default run):

  K u = F,   with K tridiagonal, u the nodal radial displacements,
  F the device load vector.                                            (16)

- Element tangent stiffness from the Mooney–Rivlin hoop stress σ(λ)
  in Eq. (9), linearised about the current stretch:

  k_e = (dσ/dλ) · (h / r) · L_e,   dσ/dλ from Eq. (9) by differentiation. (17)

- Device load: balloon pressure P acts on the inner surface over the
  device length; stent is the same load with the contact cap applied
  as a displacement constraint rather than a pressure. Contact cap:
  u_i ≤ (D_device − D_i)/2 at every node i.                            (18)
- Plaque-yield softening: when an element's hoop stress exceeds the
  yield stress σ_y, its tangent modulus is reduced for the next pass,
  so yielded elements carry less additional load.                     (19)

## Verified computed case (defaults, balloon, from the app's FE action)

These numbers were verified by invoking the app's published
`finiteElementSimulation` action with its defaults on 2026-11-22 — they
were computed, not typed:

- Mesh: 16 elements / 17 nodes / 15 free degrees of freedom.
- Device pressure: 1013.25 kPa (= 10 atm, correct conversion).
- Minimum lumen: 1.20 mm → 6.00 mm; lumen gain 4.80 mm;
  residual stenosis ≈ 0%.
- Maximum hoop stress: 629 kPa, at the lesion centre.
- Yielded elements: 2, over a 7.5 mm zone.
- Contact nodes: 5. Total device force: 223 N. Solved in 2 passes.

## Proposed Table 4 (to be computed, same generator as Table 2)

| Quantity | Default balloon case |
|---|---|
| Elements / nodes / free DOF | 16 / 17 / 15 |
| Device pressure | 1013.25 kPa (10 atm) |
| Minimum lumen, before → after | 1.20 mm → 6.00 mm |
| Lumen gain / residual stenosis | 4.80 mm / ≈ 0% |
| Max hoop stress (lesion centre) | 629 kPa |
| Yielded elements | 2 (7.5 mm zone) |
| Contact nodes / total device force | 5 / 223 N |
| Solver passes | 2 |

A second row — the same lesion with a stent device, and a second
pressure — should be computed before building, so Table 4 compares
devices rather than reporting a single run. That comparison is not
yet computed; do not claim it until it is.

## Proposed Figure 3

a, Lumen diameter along the vessel before and after expansion, with
the contact-cap (nominal device diameter) line. b, Hoop stress and
radial displacement along the vessel, with the yield-threshold line —
the same two plots the app already shows, regenerated from the same
computed arrays.

## Honest limits to carry into §10

- One-dimensional ring elements: no bending, no axial coupling beyond
  the tridiagonal system, no balloon folding, no stent strut geometry.
- Plaque is a stiffening factor and a yield threshold, not a measured
  plaque composition; the lesion geometry in the verified run is the
  app's synthetic default.
- Static, quasi-static loading: no pulsatile pressure, no viscoelasticity,
  no recoil after deflation — so "residual stenosis ≈ 0%" is the
  at-pressure result, not a post-procedure outcome.
- Same caveats as v1.0 throughout: independent, not peer-reviewed,
  synthetic-only, no patient data, classically emulated kernel,
  experimental and not for clinical decisions.

## What building v1.1 needs

1. Confirm the FE default parameters from the app action (lesion
   length/stenosis, vessel diameter and wall thickness, plaque
   stiffening and yield stress) and record them in the Methods.
2. Compute the stent comparison row for Table 4 and Figure 3.
3. Add Appendix C: the Thomas solver and expansion routine in Python,
   matching the Math & code tab.
4. Rebuild the PDF; check the new section against the app's FE
   output by hand, as v1.0 did for Eq. (11).
