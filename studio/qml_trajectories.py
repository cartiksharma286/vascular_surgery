"""Quantum Machine Learning (QML) for postoperative clinical trajectories & recovery probabilities.

Educational finite-mathematics model on synthetic postoperative cohorts. Not a clinical tool.

Mathematical formulation:
  1. Angle-encoded 6-qubit product state:
       |psi(x)> = prod_{m=1}^6 (cos(pi*x_m/2)|0> + sin(pi*x_m/2)|1>)
  2. Exact quantum fidelity kernel with optional ZZ entangling phase modulation:
       K_0(x, z) = |<psi(x)|psi(z)>|^2 = prod_{m=1}^6 cos^2(pi*(x_m - z_m)/2)
       K_Q(x, z; gamma) = K_0(x, z) * exp(-gamma * sum_{m<n} sin^2(pi*(x_m*x_n - z_m*z_n)/2))
  3. Kernel ridge / logistic trajectory predictor at postoperative day t in [0, 90]:
       logit P_Q(recovery | x, t) = alpha_0(t) + sum_{i=1}^N w_i(t) K_Q(x, x_i)
  4. Discrete hazard-survival coupling:
       h(t | x) = h_base(t) * (1 + beta_J * J_norm) * (1 - 0.35 * P_Q(recovery | x, t))
"""

from __future__ import annotations

import math
from typing import Dict, List, Tuple

import numpy as np

FEATURE_NAMES = [
    "age_norm",
    "comorbidity",
    "baseline_burden",
    "mechanical_risk_J",
    "procedure_complexity",
    "ehr_delay",
]

FEATURE_LABELS = {
    "age_norm": "Age (normalized)",
    "comorbidity": "Comorbidity index",
    "baseline_burden": "Lesion / plaque burden",
    "mechanical_risk_J": "Mechanical / thermal risk J",
    "procedure_complexity": "Procedure complexity",
    "ehr_delay": "EHR scheduling delay",
}

PROCEDURES = {
    "stent": {"label": "Cardiovascular Stent (FEM)", "complexity": 0.45, "j_base": 0.058, "j_opt": 0.033, "base_los": 2.4},
    "gi": {"label": "GI Electrosurgery (BEM)", "complexity": 0.35, "j_base": 1.100, "j_opt": 0.240, "base_los": 4.2},
    "vascular_open": {"label": "Complex Vascular / Bypass", "complexity": 0.85, "j_base": 0.095, "j_opt": 0.048, "base_los": 6.8},
}

ARCHETYPES: Dict[str, Dict[str, object]] = {
    "low_risk_opt": {
        "label": "Low-risk · Physics-optimized",
        "x": [0.22, 0.15, 0.25, 0.18, 0.35, 0.15],
        "expected_90d": 0.96,
    },
    "stent_std": {
        "label": "Moderate · Standard Stent",
        "x": [0.50, 0.42, 0.55, 0.52, 0.45, 0.35],
        "expected_90d": 0.84,
    },
    "gi_std": {
        "label": "Moderate · GI Resection",
        "x": [0.48, 0.40, 0.50, 0.60, 0.35, 0.30],
        "expected_90d": 0.81,
    },
    "high_burden": {
        "label": "High-risk · Calcified / Frail",
        "x": [0.80, 0.78, 0.82, 0.80, 0.85, 0.65],
        "expected_90d": 0.54,
    },
}

DAYS = np.array([0, 1, 3, 7, 14, 21, 30, 45, 60, 75, 90], dtype=float)


def _sigmoid(z: np.ndarray | float) -> np.ndarray | float:
    return 1.0 / (1.0 + np.exp(-np.clip(z, -30.0, 30.0)))


def quantum_kernel(x: np.ndarray, z: np.ndarray, gamma: float = 0.25) -> float:
    """Exact 6-qubit fidelity kernel with optional ZZ entangling phase modulation."""
    x = np.asarray(x, dtype=float)
    z = np.asarray(z, dtype=float)
    k0 = float(np.prod(np.cos(0.5 * math.pi * (x - z)) ** 2))
    if gamma <= 0.0:
        return k0
    # Pairwise ZZ interaction term over adjacent & next-nearest qubit pairs
    zz = 0.0
    d = len(x)
    for i in range(d - 1):
        zz += math.sin(0.5 * math.pi * (x[i] * x[i + 1] - z[i] * z[i + 1])) ** 2
    return k0 * math.exp(-gamma * zz)


def quantum_kernel_matrix(X: np.ndarray, Z: np.ndarray | None = None, gamma: float = 0.25) -> np.ndarray:
    """Vectorized quantum kernel matrix K_Q(X, Z)."""
    X = np.asarray(X, dtype=float)
    Z = X if Z is None else np.asarray(Z, dtype=float)
    diff = X[:, None, :] - Z[None, :, :]
    K0 = np.prod(np.cos(0.5 * math.pi * diff) ** 2, axis=-1)
    if gamma <= 0.0:
        return K0
    px = X[:, :-1] * X[:, 1:]
    pz = Z[:, :-1] * Z[:, 1:]
    zz = np.sum(np.sin(0.5 * math.pi * (px[:, None, :] - pz[None, :, :])) ** 2, axis=-1)
    return K0 * np.exp(-gamma * zz)


def rbf_kernel_matrix(X: np.ndarray, Z: np.ndarray | None = None, length_scale: float = 0.65) -> np.ndarray:
    X = np.asarray(X, dtype=float)
    Z = X if Z is None else np.asarray(Z, dtype=float)
    sq = np.sum((X[:, None, :] - Z[None, :, :]) ** 2, axis=-1)
    return np.exp(-sq / (2.0 * length_scale ** 2))


def generate_cohort(n: int = 160, seed: int = 42) -> Dict[str, object]:
    """Generate a synthetic postoperative cohort with ground-truth latent recovery outcomes."""
    rng = np.random.default_rng(seed)
    X = rng.beta(2.0, 2.2, size=(n, 6))
    # Procedure complexity discrete-ish mixture
    proc_choices = rng.choice([0.35, 0.45, 0.85], size=n, p=[0.35, 0.45, 0.20])
    X[:, 4] = proc_choices

    # Latent risk score (nonlinear interaction between age, comorbidity, mechanical risk, delay)
    risk = (
        1.85 * X[:, 0]
        + 2.15 * X[:, 1]
        + 1.65 * X[:, 2]
        + 2.45 * X[:, 3]
        + 1.30 * X[:, 4]
        + 1.15 * X[:, 5]
        + 1.20 * X[:, 1] * X[:, 3]
        - 4.65
    )

    # Recovery probability at each landmark day
    tau = 16.0 + 18.0 * X[:, 4] + 12.0 * X[:, 3]
    asymptote = _sigmoid(-risk)
    # P(recovery | x, t) = asymptote * (1 - exp(-t / tau))
    probs = asymptote[:, None] * (1.0 - np.exp(-DAYS[None, :] / tau[:, None]))
    y_bin = (rng.uniform(size=probs.shape) < probs).astype(float)
    return {"X": X, "risk": risk, "probs": probs, "y_bin": y_bin, "asymptote": asymptote}


def _auc_roc(y_true: np.ndarray, y_score: np.ndarray) -> float:
    pos = y_score[y_true == 1]
    neg = y_score[y_true == 0]
    if len(pos) == 0 or len(neg) == 0:
        return 0.5
    wins = np.sum(pos[:, None] > neg[None, :]) + 0.5 * np.sum(pos[:, None] == neg[None, :])
    return float(wins / (len(pos) * len(neg)))


def fit_qml_model(gamma: float = 0.25, reg: float = 1.0, seed: int = 42) -> Dict[str, object]:
    """Fit Quantum Kernel Ridge & Classical RBF baselines on synthetic cohort (train/val split)."""
    cohort = generate_cohort(220, seed=seed)
    X, y_bin, probs = cohort["X"], cohort["y_bin"], cohort["probs"]
    n_train = 160
    X_tr, X_val = X[:n_train], X[n_train:]
    y_tr, y_val = y_bin[:n_train], y_bin[n_train:]
    p_val_true = probs[n_train:]

    K_tr = quantum_kernel_matrix(X_tr, X_tr, gamma=gamma)
    K_val = quantum_kernel_matrix(X_val, X_tr, gamma=gamma)
    eigs = np.linalg.eigvalsh(K_tr)

    # Solve kernel ridge for each landmark day t > 0
    A = K_tr + reg * np.eye(n_train)
    W_q = np.linalg.solve(A, y_tr)  # (n_train, len(DAYS))

    # Classical RBF comparison
    K_rbf_tr = rbf_kernel_matrix(X_tr, X_tr)
    K_rbf_val = rbf_kernel_matrix(X_val, X_tr)
    W_c = np.linalg.solve(K_rbf_tr + reg * np.eye(n_train), y_tr)

    pred_q_val = np.clip(K_val @ W_q, 0.01, 0.99)
    pred_c_val = np.clip(K_rbf_val @ W_c, 0.01, 0.99)

    # Validation metrics at day 30 (index 6) and day 90 (index 10)
    brier_q_30 = float(np.mean((pred_q_val[:, 6] - y_val[:, 6]) ** 2))
    brier_c_30 = float(np.mean((pred_c_val[:, 6] - y_val[:, 6]) ** 2))
    auroc_q_30 = _auc_roc(y_val[:, 6], pred_q_val[:, 6])
    auroc_c_30 = _auc_roc(y_val[:, 6], pred_c_val[:, 6])
    auroc_q_90 = _auc_roc(y_val[:, 10], pred_q_val[:, 10])
    mae_q_90 = float(np.mean(np.abs(pred_q_val[:, 10] - p_val_true[:, 10])))

    return {
        "X_tr": X_tr,
        "W_q": W_q,
        "W_c": W_c,
        "gamma": gamma,
        "reg": reg,
        "gram_eig_min": float(eigs.min()),
        "gram_eig_max": float(eigs.max()),
        "gram_trace": float(np.trace(K_tr)),
        "effective_rank": float(np.sum(eigs / np.sum(eigs) * np.log(np.maximum(eigs / np.sum(eigs), 1e-12))) * -1.0),
        "auroc_30d": auroc_q_30,
        "auroc_90d": auroc_q_90,
        "auroc_classical_30d": auroc_c_30,
        "brier_30d": brier_q_30,
        "brier_classical_30d": brier_c_30,
        "mae_90d": mae_q_90,
        "n_train": n_train,
        "n_val": len(X_val),
    }


def build_feature_vector(
    procedure: str = "stent",
    age: float = 64.0,
    comorbidity: float = 0.35,
    burden: float = 0.50,
    use_optimized: bool = True,
    ehr_delay: float = 0.25,
) -> np.ndarray:
    proc = PROCEDURES.get(procedure, PROCEDURES["stent"])
    age_norm = float(np.clip((age - 35.0) / 55.0, 0.0, 1.0))
    j_val = proc["j_opt"] if use_optimized else proc["j_base"]
    # Normalize J to [0, 1] scale across procedures
    j_norm = float(np.clip(j_val / (1.2 if procedure == "gi" else 0.12), 0.0, 1.0))
    return np.array([
        age_norm,
        float(np.clip(comorbidity, 0.0, 1.0)),
        float(np.clip(burden, 0.0, 1.0)),
        j_norm,
        float(proc["complexity"]),
        float(np.clip(ehr_delay, 0.0, 1.0)),
    ], dtype=float)


def predict_trajectory(
    procedure: str = "stent",
    age: float = 64.0,
    comorbidity: float = 0.35,
    burden: float = 0.50,
    use_optimized: bool = True,
    ehr_delay: float = 0.25,
    gamma: float = 0.25,
) -> Dict[str, object]:
    """Compute full 90-day postoperative clinical trajectory using QML + classical comparison."""
    model = fit_qml_model(gamma=gamma)
    x = build_feature_vector(procedure, age, comorbidity, burden, use_optimized, ehr_delay)
    x_base = build_feature_vector(procedure, age, comorbidity, burden, False, ehr_delay)

    k_q = quantum_kernel_matrix(x[None, :], model["X_tr"], gamma=gamma)[0]
    k_c = rbf_kernel_matrix(x[None, :], model["X_tr"])[0]
    k_q_base = quantum_kernel_matrix(x_base[None, :], model["X_tr"], gamma=gamma)[0]

    raw_q = np.clip(k_q @ model["W_q"], 0.02, 0.98)
    raw_c = np.clip(k_c @ model["W_c"], 0.02, 0.98)
    raw_q_base = np.clip(k_q_base @ model["W_q"], 0.02, 0.98)

    # Enforce monotonicity of cumulative recovery trajectory from day 0
    raw_q[0] = 0.02
    raw_c[0] = 0.02
    raw_q_base[0] = 0.02
    p_q = np.maximum.accumulate(raw_q)
    p_c = np.maximum.accumulate(raw_c)
    p_q_base = np.maximum.accumulate(raw_q_base)

    # Epistemic uncertainty band from kernel leverage (1 - max similarity)
    leverage = float(np.clip(1.0 - np.max(k_q), 0.04, 0.28))
    sigma_t = leverage * 0.45 * np.sqrt(np.maximum(p_q * (1.0 - p_q), 0.02))
    p5 = np.clip(p_q - 1.645 * sigma_t, 0.0, 1.0)
    p95 = np.clip(p_q + 1.645 * sigma_t, 0.0, 1.0)

    # Daily complication hazard h(t) per 100 patient-days: early post-op peak + late tail
    j_norm = x[3]
    early_peak = (1.6 + 2.8 * j_norm + 1.4 * x[1]) * np.exp(-DAYS / 7.5)
    late_tail = (0.25 + 0.95 * j_norm) * np.exp(-((DAYS - 35.0) / 28.0) ** 2)
    hazard = np.clip((early_peak + late_tail) * (1.0 - 0.35 * p_q), 0.05, 8.0)

    # Functional recovery score (0 - 100, e.g., composite QoL / mobility index)
    baseline_func = 88.0 - 18.0 * x[0] - 20.0 * x[1]
    nadir = 28.0 + 14.0 * (1.0 - x[4])
    functional_score = np.clip(nadir + (baseline_func - nadir) * p_q, 10.0, 99.0)

    # 30-day and 90-day readmission probability
    readmit_30d = float(np.clip(0.04 + 0.16 * (1.0 - p_q[6]) + 0.06 * j_norm, 0.02, 0.45))
    readmit_90d = float(np.clip(readmit_30d + 0.08 * (1.0 - p_q[10]), readmit_30d, 0.60))
    readmit_30d_base = float(np.clip(0.04 + 0.16 * (1.0 - p_q_base[6]) + 0.06 * x_base[3], 0.02, 0.45))

    # Expected length of stay (days)
    proc_info = PROCEDURES.get(procedure, PROCEDURES["stent"])
    los_days = float(proc_info["base_los"] * (0.85 + 0.55 * (1.0 - p_q[3]) + 0.30 * x[1]))

    # Archetype kernel similarities
    arch_sims = []
    for ak, av in ARCHETYPES.items():
        sim = quantum_kernel(x, np.array(av["x"]), gamma=gamma)
        arch_sims.append({"key": ak, "label": av["label"], "similarity": sim, "expected_90d": av["expected_90d"]})
    arch_sims.sort(key=lambda r: r["similarity"], reverse=True)

    # Feature attribution (finite-difference sensitivity of 30d recovery probability to +0.10 perturbation)
    attributions = []
    for idx, fname in enumerate(FEATURE_NAMES):
        xp = x.copy()
        xp[idx] = min(1.0, xp[idx] + 0.10)
        xm = x.copy()
        xm[idx] = max(0.0, xm[idx] - 0.10)
        kp = quantum_kernel_matrix(xp[None, :], model["X_tr"], gamma=gamma)[0]
        km = quantum_kernel_matrix(xm[None, :], model["X_tr"], gamma=gamma)[0]
        dp = float((kp @ model["W_q"])[6] - (km @ model["W_q"])[6])
        attributions.append({
            "feature": fname,
            "label": FEATURE_LABELS[fname],
            "value": float(x[idx]),
            "delta_30d": dp,
        })

    return {
        "days": DAYS.tolist(),
        "p_recovery": p_q.tolist(),
        "p5": p5.tolist(),
        "p95": p95.tolist(),
        "p_classical": p_c.tolist(),
        "p_baseline_physics": p_q_base.tolist(),
        "hazard": hazard.tolist(),
        "functional_score": functional_score.tolist(),
        "features": {FEATURE_NAMES[i]: float(x[i]) for i in range(6)},
        "summary": {
            "recovery_7d": float(p_q[3]),
            "recovery_30d": float(p_q[6]),
            "recovery_90d": float(p_q[10]),
            "recovery_gain_vs_baseline": float(p_q[6] - p_q_base[6]),
            "readmission_30d": readmit_30d,
            "readmission_90d": readmit_90d,
            "readmission_reduction": float(max(0.0, readmit_30d_base - readmit_30d)),
            "expected_los_days": los_days,
            "functional_90d": float(functional_score[10]),
        },
        "archetypes": arch_sims,
        "attributions": attributions,
        "diagnostics": {
            "gamma": gamma,
            "gram_eig_min": model["gram_eig_min"],
            "gram_eig_max": model["gram_eig_max"],
            "gram_trace": model["gram_trace"],
            "effective_rank": model["effective_rank"],
            "auroc_30d": model["auroc_30d"],
            "auroc_90d": model["auroc_90d"],
            "auroc_classical_30d": model["auroc_classical_30d"],
            "brier_30d": model["brier_30d"],
            "brier_classical_30d": model["brier_classical_30d"],
            "mae_90d": model["mae_90d"],
            "n_train": model["n_train"],
            "n_val": model["n_val"],
        },
        "procedure": proc_info["label"],
        "use_optimized": use_optimized,
    }
