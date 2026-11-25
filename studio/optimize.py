"""Design optimization: exhaustive search, simulated annealing, and golden-section in an elliptic-modulus coordinate.

Stent (finite element): minimize J = recoil_loss + w_metal * metal_burden + w_over * overstress(deployment).
GI electrosurgery (boundary element): minimize J = serosal_exposure + w_cov * max(0, target - lesion_coverage),
subject to the electrode-tissue impedance window R_e = ln(rho)/(2 pi sigma) in [R_min, R_max].
"""

from __future__ import annotations

import math
import random
from functools import lru_cache
from typing import Callable, Dict, List, Tuple

import bem
import elliptic
import fem

GOLDEN = (math.sqrt(5.0) - 1.0) / 2.0

W_METAL = 0.10
W_OVER = 1.0


@lru_cache(maxsize=4096)
def stent_objective(n_struts: float, layers: int, ri: float = 1.5, ro: float = 3.0, n_theta: int = 48) -> Tuple[float, float, float, float]:
    c = fem.stent_case(ri=ri, ro=ro, n_struts=n_struts, strut_layers=layers, n_theta=n_theta)
    j = c["recoil_loss"] + W_METAL * c["metal_burden"] + W_OVER * c["overstress_fraction"]
    return j, c["recoil_loss"], c["metal_burden"], c["overstress_fraction"]


def golden_section(f: Callable[[float], float], lo: float, hi: float, tol: float = 1e-3, max_iter: int = 40) -> Tuple[float, float, int]:
    a, b = lo, hi
    c, d = b - GOLDEN * (b - a), a + GOLDEN * (b - a)
    fc, fd, evals = f(c), f(d), 2
    for _ in range(max_iter):
        if abs(b - a) < tol:
            break
        if fc < fd:
            b, d, fd = d, c, fc
            c = b - GOLDEN * (b - a)
            fc = f(c)
        else:
            a, c, fc = c, d, fd
            d = a + GOLDEN * (b - a)
            fd = f(d)
        evals += 1
    x = 0.5 * (a + b)
    return x, f(x), evals + 1


def optimize_stent(ri: float = 1.5, ro: float = 3.0, seed: int = 7, n_theta: int = 48, sa_steps: int = 30) -> Dict[str, object]:
    ns_range = list(range(6, 31, 2))
    layers_range = [1, 2, 3]

    # 1. exhaustive search on the discrete grid
    best = (math.inf, None)
    grid_rows: List[Dict[str, float]] = []
    for layers in layers_range:
        for n in ns_range:
            j, loss, burden, over = stent_objective(float(n), layers, ri, ro, n_theta)
            grid_rows.append({"n": n, "layers": layers, "J": j, "recoil_loss": loss, "metal_burden": burden, "overstress": over})
            if j < best[0]:
                best = (j, (n, layers))
    exhaustive = {"J": best[0], "n_struts": best[1][0], "layers": best[1][1], "evaluations": len(ns_range) * len(layers_range)}

    # 2. simulated annealing on the same discrete space
    rng = random.Random(seed)
    cur = (rng.choice(ns_range), rng.choice(layers_range))
    cur_j = stent_objective(float(cur[0]), cur[1], ri, ro, n_theta)[0]
    best_sa, best_j = cur, cur_j
    seen = {cur}
    trace = [cur_j]
    temp0 = 0.05
    for step in range(sa_steps):
        temp = temp0 * (1 - step / sa_steps) + 1e-4
        n = min(30, max(6, cur[0] + rng.choice([-4, -2, 2, 4])))
        layers = cur[1] if rng.random() < 0.7 else rng.choice(layers_range)
        cand = (n, layers)
        seen.add(cand)
        j = stent_objective(float(n), layers, ri, ro, n_theta)[0]
        if j < cur_j or rng.random() < math.exp(-(j - cur_j) / temp):
            cur, cur_j = cand, j
        if cur_j < best_j:
            best_sa, best_j = cur, cur_j
        trace.append(best_j)
    annealing = {"J": best_j, "n_struts": best_sa[0], "layers": best_sa[1], "evaluations": len(seen), "trace": trace,
                 "gap_to_exhaustive": best_j - exhaustive["J"]}

    # 3. golden-section in the elliptic-modulus coordinate k, thickness layers from the exhaustive optimum
    layers_opt = exhaustive["layers"]

    def j_of_k(k: float) -> float:
        n = elliptic.strut_density_from_modulus(k, 1.0, ri)
        return stent_objective(round(n, 3), layers_opt, ri, ro, n_theta)[0]

    k_star, j_star, evals = golden_section(j_of_k, 0.05, 0.98)
    n_star = elliptic.strut_density_from_modulus(k_star, 1.0, ri)
    modulus = {"J": j_star, "k": k_star, "n_struts_continuous": n_star, "n_struts_rounded": round(n_star),
               "ratio_Kp_over_K": elliptic.ratio_from_modulus(k_star), "layers": layers_opt, "evaluations": evals}

    sensitivity = []
    for wm in (0.02, 0.05, 0.10, 0.25, 0.50):
        row = min(grid_rows, key=lambda r: r["recoil_loss"] + wm * r["metal_burden"] + W_OVER * r["overstress"])
        sensitivity.append({"w_metal": wm, "n_struts": row["n"], "layers": row["layers"],
                            "recoil_loss": row["recoil_loss"], "metal_burden": row["metal_burden"]})
    baseline_n, baseline_layers = 12, 1
    b = stent_objective(float(baseline_n), baseline_layers, ri, ro, n_theta)
    return {"exhaustive": exhaustive, "annealing": annealing, "elliptic_modulus": modulus,
            "baseline": {"n_struts": baseline_n, "layers": baseline_layers, "J": b[0], "recoil_loss": b[1], "metal_burden": b[2], "overstress": b[3]},
            "grid": grid_rows, "weights": {"metal": W_METAL, "overstress": W_OVER}, "weight_sensitivity": sensitivity}


# ----------------------------------------------------------------------------- GI (BEM)

R_MIN, R_MAX = 0.12, 0.30          # normalized impedance window R_e = ln(rho)/(2 pi)
LESION = {"x": 2.8, "y": 0.0, "r": 0.5}
COVERAGE_TARGET = 0.9


@lru_cache(maxsize=2048)
def gi_objective(a: float, e: float, R: float = 4.0) -> Tuple[float, float, float, float, bool]:
    m = bem.field_map(R, a, e, n_outer=48, n_inner=28, grid=36, lesion=LESION)
    resistance = m["resistance"]
    feasible = R_MIN <= resistance <= R_MAX
    deficit = max(0.0, COVERAGE_TARGET - m["lesion_coverage"])
    j = m["serosal_exposure"] + 5.0 * deficit + (0.0 if feasible else 5.0)
    return j, m["serosal_exposure"], m["lesion_coverage"], resistance, feasible


def optimize_gi(R: float = 4.0, seed: int = 11, sa_steps: int = 30) -> Dict[str, object]:
    a_grid = [0.6, 0.9, 1.2, 1.4, 1.6]
    e_max = lambda a: R - a - 0.8
    cands = []
    for a in a_grid:
        for i in range(7):
            e = round(i / 6 * e_max(a), 3)
            cands.append((a, e))
    best = (math.inf, None)
    rows = []
    for a, e in cands:
        j, sero, cov, res, feas = gi_objective(a, e, R)
        rows.append({"a": a, "e": e, "J": j, "serosal": sero, "coverage": cov, "resistance": res, "feasible": feas})
        if j < best[0]:
            best = (j, (a, e))
    exhaustive = {"J": best[0], "a": best[1][0], "e": best[1][1], "evaluations": len(cands)}

    rng = random.Random(seed)
    cur = rng.choice(cands)
    cur_j = gi_objective(cur[0], cur[1], R)[0]
    best_sa, best_j = cur, cur_j
    seen = {cur}
    trace = [cur_j]
    for step in range(sa_steps):
        temp = 0.3 * (1 - step / sa_steps) + 1e-3
        a = min(1.6, max(0.6, round(cur[0] + rng.choice([-0.2, 0.0, 0.2]), 2)))
        e = min(e_max(a), max(0.0, round(cur[1] + rng.uniform(-0.5, 0.5), 3)))
        cand = (a, e)
        seen.add(cand)
        j = gi_objective(a, e, R)[0]
        if j < cur_j or rng.random() < math.exp(-(j - cur_j) / temp):
            cur, cur_j = cand, j
        if cur_j < best_j:
            best_sa, best_j = cur, cur_j
        trace.append(best_j)
    annealing = {"J": best_j, "a": best_sa[0], "e": best_sa[1], "evaluations": len(seen), "trace": trace,
                 "gap_to_exhaustive": best_j - exhaustive["J"]}
    base = gi_objective(1.0, 0.0, R)
    return {"exhaustive": exhaustive, "annealing": annealing, "grid": rows,
            "baseline": {"a": 1.0, "e": 0.0, "J": base[0], "serosal": base[1], "coverage": base[2], "resistance": base[3], "feasible": base[4]},
            "impedance_window": [R_MIN, R_MAX], "lesion": LESION, "coverage_target": COVERAGE_TARGET}
