Title: Quantum machine learning for catheter supply chains: elliptic-integral seasonality and harmonic modular-form features
Section: Abstract
Claim: A finite, reproducible framework links QML forecasting, elliptic-integral seasonality and harmonic Maass features to catheter inventory policy; on synthetic data it matches, not beats, classical baselines.
Source: Synthetic simulation in Appendix A; public Boston Scientific footprint only for stylised network motivation.
Section: 1 Introduction - catheter supply chains are high-mix, sterile, expiry-constrained
Claim: Stockouts and expiries coexist, so forecasting must capture multi-scale seasonality.
Source: General supply-chain literature; public company footprint.
Section: 2 Finite supply-chain model
Claim: A finite multi-echelon (s,S) model with expiry makes the decision problem well-posed and auditable.
Source: Model defined in paper.
Section: 3 Elliptic integrals and seasonal periods
Claim: Complete elliptic integrals give closed-form periods for non-sinusoidal seasonal cycles.
Source: Standard definitions K(k), E(k), Jacobi sn.
Section: 4 Harmonic modular forms as features
Claim: Fourier coefficients of a harmonic Maass form and its shadow provide a multi-scale, symmetry-constrained feature dictionary.
Source: Bruinier-Funke; Alfes et al. arXiv:1406.0443.
Section: 5 Quantum machine learning layer
Claim: A quantum kernel and QAOA routing layer can encode the same features; no advantage is claimed on NISQ hardware.
Source: Standard QSVM / QAOA definitions.
Section: 6 Synthetic experiment
Claim: Modular-elliptic features help classical and quantum-kernel models equally; gains come from features, not quantumness.
Source: Deterministic simulation, seed 7, Appendix A code.
Section: 7 Discussion, limitations, governance
Claim: Deployment requires validated demand data, UDI/expiry controls and human oversight; this is a methods preprint.
Source: Limitations section.
Section: Appendix A Source code
Claim: Code regenerates every reported number.
Source: Included code.
