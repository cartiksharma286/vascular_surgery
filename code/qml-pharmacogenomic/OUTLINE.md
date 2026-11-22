Section: Title / Abstract
Claim: A finite-dimensional QML signature can stratify pharmacogenomic states, but only as a testable preprint hypothesis with synthetic-data validation.
Source: Parent conversation summary of AstraZeneca quantum + genomics pilots; no real trial data claimed.

Section: Introduction
Claim: AstraZeneca-scale genomics defines the signature problem classically; QML is an experimental classifier layer, not a validated product.
Source: Parent conversation.

Section: Finite mathematics framework
Claim: All objects are finite: finite Hilbert space C^{2^n}, finite genotype alphabet, finite-sample Hoeffding / VC bounds, finite Markov chain for trial states.
Source: Standard finite math, derived in text.

Section: Methods - QML signature and trial management
Claim: Angle encoding + quantum kernel + pre-registered adaptive randomisation gives an auditable pipeline.
Source: Methods design in this preprint.

Section: Results on synthetic data
Claim: On clearly-labelled synthetic data the quantum-kernel classifier is comparable to classical RBF-SVM; no quantum advantage is claimed.
Source: Simulation design described; numbers presented as illustrative synthetic run.

Section: Discussion and limitations
Claim: NISQ noise, data loading and multiplicity bound any near-term claim; external validation is required.
Source: Parent conversation reality check.

Section: Appendix - Source code
Claim: Complete runnable Python reproduces the synthetic experiment and trial simulation.
Source: Code written for this preprint.

Section: Part II, Section 8 - Health economics, Sunnybrook Odette finite model
Claim: In Ontario's public system "revenue" means funding inflows, not sales; a finite discounted model anchored to published Odette scale (over 12,000 new patients/yr, 300,000 visits/yr) and Ontario incidence growth (+25.4% 2020-2030) can price the signature programme without any Sunnybrook internal data.
Source: Sunnybrook Foundation Odette page; Ontario Cancer Statistics 2020 Ch. 3; Sunnybrook FY2024 consolidated statements (hospital total revenue CAD 1,521.8M); Canada's Drug Agency discount rate 1.5% and CAD 50,000/QALY reference threshold.

Section: Part II, Section 9 - Ten-year projections 2027-2036
Claim: Under hypothetical base-case effects the payer system is dominant (CAD -95.8M discounted, 4,205 discounted QALYs) while the hospital roughly breaks even (funding CAD 111.4M vs costs CAD 117.4M); the conservative case gives an ICER of CAD 40,684/QALY. The split incentive, not the science alone, is the binding constraint.
Source: Deterministic model in .src/build_economics.py and .src/data/economics_model.json; every effect size labelled a planning assumption.

Section: Part II, Section 10 - Clinical trajectories
Claim: Partitioned-survival trajectories (median PFS 9 months standard; 14 months signature-positive, 8 months signature-negative if guided) imply 0.138 QALY per tested patient in the base case, and the programme is cost-saving only if at least about 24% of signature-negative patients actually change management - a measurable trial endpoint.
Source: Same model file; trajectories are assumption sets, not observed Sunnybrook outcomes.
