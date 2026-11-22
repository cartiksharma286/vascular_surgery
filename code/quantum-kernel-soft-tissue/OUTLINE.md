Section: Abstract and framing
Claim: A finite, exactly emulated 6-qubit quantum kernel can score vascular cases against risk prototypes while a finite hyperelastic model predicts vessel inflation; both are synthetic and experimental with no quantum advantage claimed.
Source: Parent conversation - vascular app QML Lab (6-qubit angle encoding) and Simulation tab (Neo-Hookean / Mooney-Rivlin, presets, characteristics).

Section: Finite quantum kernel
Claim: Angle encoding gives a closed-form product kernel that is positive semidefinite on a finite grid and exactly computable classically.
Source: Computed in Appendix code.

Section: Finite hyperelastic soft-tissue model
Claim: Incompressible uniaxial-azimuthal inflation with lambda_z=1 yields closed-form Cauchy stress and a Laplace pressure-diameter law.
Source: Computed in Appendix code; healthy carotid check 6.0 mm to 6.47 mm at 80 mmHg, 6.79 mm at 120 mmHg.

Section: Coupled workflow
Claim: Kernel similarity and mechanical characteristics are complementary finite descriptors, not a clinical predictor.
Source: Synthetic cohort of six demo archetypes computed deterministically.

Section: Results - kernel table, tissue table, plots
Claim: Stiffer presets show higher wall stress and lower compliance; kernel separates low- and high-risk prototypes on synthetic data only.
Source: Deterministic Python computation in .src/compute.py, output JSON.

Section: Limitations and methods
Claim: No patient data, no live PACS, no hardware quantum run, thin-wall and isotropy limits stated.
Source: Parent conversation caveats.
