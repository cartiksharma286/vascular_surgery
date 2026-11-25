"""Health economics with statistical prisms: valuation and 10-year revenue projections.

Two contexts, six regions (US and Canada; Japan, China, India and Australia for Asia-Pacific). All market
parameters are ILLUSTRATIVE ARCHETYPES chosen to demonstrate the method; they are not sourced market data,
and nothing here is a forecast. Values are USD-equivalent.

Prisms (independent statistical views of the same question):
  1. scenario   : deterministic low / base / high
  2. Monte Carlo: parameter uncertainty -> percentile fan chart and NPV distribution
  3. bootstrap  : residual bootstrap of a log-linear fit to a synthetic 36-month pilot history
  4. Bayesian   : Beta-Binomial posterior for per-site adoption from a synthetic pilot
  5. regression : analytic t-distribution prediction interval for the same history
The physics link converts the finite element and boundary element design gains into a relative reduction in
complication risk, p = p0 (1 + kappa J), to give a payer-side value ratio per procedure.
"""

from __future__ import annotations

import math
from typing import Dict, List

import numpy as np
from scipy import stats

import qml_trajectories

YEARS = 10

REGIONS: Dict[str, Dict[str, object]] = {
    "us": {"cost_index": 1.0, "name": "United States", "context": "us_canada", "price_index": 1.00, "cv_k": 700, "gi_k": 450, "sites": 900,
           "discount": 0.08, "lead": 1.0, "fixed_M": 1.4, "launch_M": 6.0, "wtp_qaly": 100000.0, "readmit_cost": 18500.0},
    "canada": {"cost_index": 0.8, "name": "Canada", "context": "us_canada", "price_index": 0.78, "cv_k": 80, "gi_k": 55, "sites": 120,
               "discount": 0.08, "lead": 1.5, "fixed_M": 0.7, "launch_M": 3.0, "wtp_qaly": 50000.0, "readmit_cost": 14500.0},
    "japan": {"cost_index": 0.65, "name": "Japan", "context": "asia_pacific", "price_index": 0.70, "cv_k": 220, "gi_k": 160, "sites": 400,
              "discount": 0.05, "lead": 2.0, "fixed_M": 1.0, "launch_M": 4.5, "wtp_qaly": 45000.0, "readmit_cost": 12000.0},
    "china": {"cost_index": 0.3, "name": "China", "context": "asia_pacific", "price_index": 0.45, "cv_k": 900, "gi_k": 600, "sites": 1200,
              "discount": 0.10, "lead": 3.0, "fixed_M": 1.1, "launch_M": 4.5, "wtp_qaly": 15000.0, "readmit_cost": 5500.0},
    "india": {"cost_index": 0.15, "name": "India", "context": "asia_pacific", "price_index": 0.25, "cv_k": 500, "gi_k": 300, "sites": 800,
              "discount": 0.12, "lead": 3.0, "fixed_M": 0.6, "launch_M": 2.5, "wtp_qaly": 8000.0, "readmit_cost": 2800.0},
    "australia": {"cost_index": 0.85, "name": "Australia", "context": "asia_pacific", "price_index": 0.82, "cv_k": 70, "gi_k": 45, "sites": 150,
                  "discount": 0.08, "lead": 1.5, "fixed_M": 0.6, "launch_M": 2.8, "wtp_qaly": 35000.0, "readmit_cost": 15000.0},
}
CONTEXTS = {"us_canada": ["us", "canada"], "asia_pacific": ["japan", "china", "india", "australia"]}

LINES = {"cv": {"fee": 220.0, "smax": 0.18, "label": "Cardiovascular stent FE planning"},
         "gi": {"fee": 180.0, "smax": 0.15, "label": "GI surgery BEM planning"},
         "ehr": {"fee": 45000.0, "smax": 0.35, "label": "EHR heuristic platform"},
         "qml": {"fee": 140.0, "smax": 0.22, "label": "QML post-op trajectory suite"}}
GROWTH, STEEPNESS, MIDPOINT, COGS, TERMINAL_G = 0.03, 0.9, 3.0, 0.25, 0.02

# complication model: p = p0 (1 + kappa J); cost per complication in USD (index-scaled)
CLINICAL = {"cv": {"p0": 0.08, "cost": 22000.0, "kappa": 10.0}, "gi": {"p0": 0.06, "cost": 30000.0, "kappa": 0.25}}


def adoption(t: np.ndarray, smax, lead, steep=STEEPNESS, mid=MIDPOINT) -> np.ndarray:
    eff = t - lead
    share = smax / (1.0 + np.exp(-steep * np.clip(eff - mid, -30.0, 30.0)))
    share = np.where(eff > 0, share, 0.0)
    return np.where(share < 1e-9, 0.0, share)  # flush subnormals: they slow later array operations by ~100x


def revenue_lines(p: Dict[str, object], t: np.ndarray, smax_mult=1.0, price_mult=1.0, lead_shift=0.0, growth=GROWTH,
                  steep=STEEPNESS) -> Dict[str, np.ndarray]:
    lead = p["lead"] + lead_shift
    pi = p["price_index"] * price_mult
    out = {}
    for line, base in (("cv", p["cv_k"] * 1000.0), ("gi", p["gi_k"] * 1000.0)):
        vol = base * (1.0 + growth) ** (t - 1)
        out[line] = vol * adoption(t, LINES[line]["smax"] * smax_mult, lead, steep) * LINES[line]["fee"] * pi
    out["ehr"] = p["sites"] * adoption(t, LINES["ehr"]["smax"] * smax_mult, lead, steep) * LINES["ehr"]["fee"] * pi
    total_proc = (p["cv_k"] + p["gi_k"]) * 1000.0 * (1.0 + growth) ** (t - 1)
    out["qml"] = total_proc * adoption(t, LINES["qml"]["smax"] * smax_mult, lead, steep) * LINES["qml"]["fee"] * pi
    return out


def cash_and_value(p: Dict[str, object], total: np.ndarray, discount=None) -> Dict[str, np.ndarray]:
    """Operating cash flows, NPV and enterprise value (Gordon terminal value). `total` has trailing axis = years."""
    d = p["discount"] if discount is None else discount
    t = np.arange(1, YEARS + 1)
    cf = total * (1.0 - COGS) - p["fixed_M"] * 1e6
    df = (1.0 + d) ** (-t)
    pv = np.sum(cf * df, axis=-1)
    npv = pv - p["launch_M"] * 1e6
    tv = np.maximum(cf[..., -1], 0.0) * (1.0 + TERMINAL_G) / np.maximum(d - TERMINAL_G, 1e-6)
    ev = npv + tv * (1.0 + d) ** (-YEARS)
    return {"cf": cf, "npv": npv, "ev": ev}


def payback_year(cf: np.ndarray, launch: float) -> int | None:
    cum = -launch + np.cumsum(cf)
    idx = np.where(cum >= 0)[0]
    return int(idx[0] + 1) if len(idx) else None


def physics_link(stent_baseline_J: float, stent_opt_J: float, gi_baseline_J: float, gi_opt_J: float) -> Dict[str, Dict[str, float]]:
    out = {}
    for line, jb, jo in (("cv", stent_baseline_J, stent_opt_J), ("gi", gi_baseline_J, gi_opt_J)):
        c = CLINICAL[line]
        rb, ro = c["p0"] * (1 + c["kappa"] * jb), c["p0"] * (1 + c["kappa"] * jo)
        out[line] = {"baseline_risk": rb, "optimized_risk": ro, "relative_risk_reduction": 1.0 - ro / rb,
                     "J_baseline": jb, "J_optimized": jo}
    return out


def value_ratios(link: Dict[str, Dict[str, float]]) -> Dict[str, Dict[str, Dict[str, float]]]:
    out: Dict[str, Dict[str, Dict[str, float]]] = {}
    for key, p in REGIONS.items():
        out[key] = {}
        for line in ("cv", "gi"):
            c = CLINICAL[line]
            savings = (link[line]["baseline_risk"] - link[line]["optimized_risk"]) * c["cost"] * p["cost_index"]
            fee = LINES[line]["fee"] * p["price_index"]
            out[key][line] = {"savings_per_procedure": savings, "fee": fee, "value_ratio": savings / fee}
    return out


# ------------------------------------------------------------------------- prisms

def monte_carlo(p: Dict[str, object], n: int, rng: np.random.Generator) -> Dict[str, np.ndarray]:
    t = np.arange(1, YEARS + 1)[None, :]
    # adoption ceilings ~ Beta around the base value, price ~ lognormal, lead and growth and discount uncertain
    k_conc = 20.0
    totals = np.zeros((n, YEARS))
    parts = {}
    price = rng.lognormal(0.0, 0.15, n)[:, None]
    lead = rng.uniform(-0.5, 1.0, n)[:, None]
    growth = rng.normal(GROWTH, 0.01, n)[:, None]
    disc = rng.triangular(p["discount"] - 0.01, p["discount"], p["discount"] + 0.02, n)
    for line, base in (("cv", p["cv_k"] * 1000.0), ("gi", p["gi_k"] * 1000.0), ("ehr", p["sites"]), ("qml", (p["cv_k"] + p["gi_k"]) * 1000.0)):
        smax_base = LINES[line]["smax"]
        a, b = smax_base * k_conc, (1 - smax_base) * k_conc
        smax = rng.beta(a, b, n)[:, None]
        vol = base * ((1.0 + growth) ** (t - 1) if line != "ehr" else 1.0)
        rev = vol * adoption(t, smax, p["lead"] + lead) * LINES[line]["fee"] * p["price_index"] * price
        parts[line] = rev
        totals += rev
    d = cash_and_value(p, totals, disc[:, None])
    return {"total": totals, "npv": d["npv"], "ev": d["ev"], "lines": parts}


def pilot_history(p: Dict[str, object], seed: int, months: int = 36) -> np.ndarray:
    rng = np.random.default_rng(seed)
    m = np.arange(1, months + 1)
    base = max(5.0, 0.0006 * (p["cv_k"] + p["gi_k"]) * 1000.0 / 12.0)
    return base * np.exp(0.045 * m) * rng.lognormal(0.0, 0.12, months)


def bootstrap_prism(p: Dict[str, object], seed: int, n_boot: int = 600, horizon_month: int = 48) -> Dict[str, float]:
    y = pilot_history(p, seed)
    m = np.arange(1, len(y) + 1, dtype=float)
    X = np.column_stack([np.ones_like(m), m])
    beta, *_ = np.linalg.lstsq(X, np.log(y), rcond=None)
    res = np.log(y) - X @ beta
    rng = np.random.default_rng(seed + 1)
    xnew = np.array([1.0, float(horizon_month)])
    preds = np.empty(n_boot)
    for b in range(n_boot):
        yb = X @ beta + rng.choice(res, size=len(res), replace=True)
        bb, *_ = np.linalg.lstsq(X, yb, rcond=None)
        preds[b] = np.exp(xnew @ bb + rng.choice(res))
    return {"point": float(np.exp(xnew @ beta)), "p5": float(np.percentile(preds, 5)), "p50": float(np.percentile(preds, 50)),
            "p95": float(np.percentile(preds, 95)), "horizon_month": horizon_month}


def regression_prism(p: Dict[str, object], seed: int, horizon_month: int = 48) -> Dict[str, float]:
    y = pilot_history(p, seed)
    m = np.arange(1, len(y) + 1, dtype=float)
    X = np.column_stack([np.ones_like(m), m])
    beta, *_ = np.linalg.lstsq(X, np.log(y), rcond=None)
    res = np.log(y) - X @ beta
    dof = len(y) - 2
    s2 = float(res @ res) / dof
    xnew = np.array([1.0, float(horizon_month)])
    se = math.sqrt(s2 * (1.0 + xnew @ np.linalg.inv(X.T @ X) @ xnew))
    tcrit = stats.t.ppf(0.95, dof)
    mu = float(xnew @ beta)
    return {"point": math.exp(mu), "p5": math.exp(mu - tcrit * se), "p95": math.exp(mu + tcrit * se), "dof": dof,
            "residual_sd": math.sqrt(s2), "horizon_month": horizon_month}


def bayes_prism(p: Dict[str, object], seed: int, n_sites: int = 24, draws: int = 4000) -> Dict[str, float]:
    rng = np.random.default_rng(seed)
    p_true = min(0.9, LINES["ehr"]["smax"] * 1.6)
    k = int(rng.binomial(n_sites, p_true))
    a, b = 1 + k, 1 + n_sites - k
    post = rng.beta(a, b, draws)
    rev = p["sites"] * post * LINES["ehr"]["fee"] * p["price_index"]
    base = p["sites"] * LINES["ehr"]["smax"] * LINES["ehr"]["fee"] * p["price_index"]
    return {"pilot_sites": n_sites, "adopters": k, "alpha": a, "beta": b, "posterior_mean": a / (a + b),
            "cri_low": float(stats.beta.ppf(0.05, a, b)), "cri_high": float(stats.beta.ppf(0.95, a, b)),
            "mature_revenue_p5": float(np.percentile(rev, 5)), "mature_revenue_p50": float(np.percentile(rev, 50)),
            "mature_revenue_p95": float(np.percentile(rev, 95)), "assumed_revenue": float(base)}


def q(a: np.ndarray, lo=5, hi=95, axis=0):
    return {"p5": np.percentile(a, lo, axis=axis).tolist(), "p50": np.percentile(a, 50, axis=axis).tolist(),
            "p95": np.percentile(a, hi, axis=axis).tolist()}


def qml_clinical_value() -> Dict[str, Dict[str, float]]:
    """Quantify 30-day readmission reduction and QALY gain from QML-guided postoperative stratification."""
    out: Dict[str, Dict[str, float]] = {}
    for line, proc in (("cv", "stent"), ("gi", "gi")):
        t_opt = qml_trajectories.predict_trajectory(procedure=proc, use_optimized=True)
        t_base = qml_trajectories.predict_trajectory(procedure=proc, use_optimized=False)
        red_readmit = max(0.0, t_base["summary"]["readmission_30d"] - t_opt["summary"]["readmission_30d"])
        # 5-year discounted QALY increment from improved 90-day recovery & functional status
        delta_rec90 = max(0.0, t_opt["summary"]["recovery_90d"] - t_base["summary"]["recovery_90d"])
        delta_func = max(0.0, t_opt["summary"]["functional_90d"] - t_base["summary"]["functional_90d"]) / 100.0
        qaly_per_case = 0.045 * delta_rec90 + 0.035 * delta_func + 0.020 * red_readmit * 10.0
        out[line] = {
            "readmission_30d_baseline": t_base["summary"]["readmission_30d"],
            "readmission_30d_optimized": t_opt["summary"]["readmission_30d"],
            "readmission_reduction": red_readmit,
            "recovery_90d_gain": delta_rec90,
            "qaly_per_case": float(max(0.008, qaly_per_case)),
            "auroc_30d": t_opt["diagnostics"]["auroc_30d"],
        }
    return out


def cost_effectiveness(link: Dict[str, Dict[str, float]], qml_val: Dict[str, Dict[str, float]],
                       region_lines: Dict[str, Dict[str, np.ndarray]]) -> Dict[str, Dict[str, float]]:
    """Compute 10-year payer savings (complication + readmission), QALYs, ICER, NMB, and payer ROI per region."""
    t = np.arange(1, YEARS + 1)
    out: Dict[str, Dict[str, float]] = {}
    for key, p in REGIONS.items():
        pi = p["price_index"]
        ci = p["cost_index"]
        comp_sav_10y = 0.0
        readmit_sav_10y = 0.0
        qalys_10y = 0.0
        for line, base_k in (("cv", p["cv_k"]), ("gi", p["gi_k"])):
            vol = base_k * 1000.0 * (1.0 + GROWTH) ** (t - 1)
            adopted = vol * adoption(t, LINES[line]["smax"], p["lead"])
            total_cases = float(adopted.sum())
            comp_sav_per = (link[line]["baseline_risk"] - link[line]["optimized_risk"]) * CLINICAL[line]["cost"] * ci
            readmit_sav_per = qml_val[line]["readmission_reduction"] * p["readmit_cost"]
            comp_sav_10y += total_cases * comp_sav_per
            readmit_sav_10y += total_cases * readmit_sav_per
            qalys_10y += total_cases * qml_val[line]["qaly_per_case"]
        total_fees_10y = float(
            region_lines[key]["cv"].sum()
            + region_lines[key]["gi"].sum()
            + region_lines[key]["qml"].sum()
        )
        total_payer_savings = comp_sav_10y + readmit_sav_10y
        net_cost = total_fees_10y - total_payer_savings
        icer = net_cost / max(qalys_10y, 1e-6)
        nmb = p["wtp_qaly"] * qalys_10y - net_cost
        out[key] = {
            "complication_savings_10y": float(comp_sav_10y),
            "readmission_savings_10y": float(readmit_sav_10y),
            "total_payer_savings_10y": float(total_payer_savings),
            "total_software_fees_10y": float(total_fees_10y),
            "net_payer_cost_10y": float(net_cost),
            "qalys_gained_10y": float(qalys_10y),
            "icer": float(icer),
            "dominant": bool(net_cost < 0.0),
            "wtp_qaly": float(p["wtp_qaly"]),
            "nmb_10y": float(nmb),
            "payer_roi": float(total_payer_savings / max(total_fees_10y, 1.0)),
        }
    return out


def run_all(link: Dict[str, Dict[str, float]], n_mc: int = 3000, seed: int = 2026) -> Dict[str, object]:
    t = np.arange(1, YEARS + 1)
    regions: Dict[str, object] = {}
    mc_by_region: Dict[str, Dict[str, np.ndarray]] = {}
    base_total: Dict[str, np.ndarray] = {}
    region_lines_map: Dict[str, Dict[str, np.ndarray]] = {}
    for idx, (key, p) in enumerate(REGIONS.items()):
        lines = revenue_lines(p, t)
        region_lines_map[key] = lines
        total = lines["cv"] + lines["gi"] + lines["ehr"] + lines["qml"]
        base_total[key] = total
        cv = cash_and_value(p, total)
        scen = {}
        for name, (sm, pm, ls) in {"low": (0.6, 0.85, 1.0), "base": (1.0, 1.0, 0.0), "high": (1.4, 1.1, -0.5)}.items():
            tl = revenue_lines(p, t, sm, pm, ls)
            tt = tl["cv"] + tl["gi"] + tl["ehr"] + tl["qml"]
            c2 = cash_and_value(p, tt)
            scen[name] = {"revenue_10y": float(tt.sum()), "npv": float(c2["npv"]), "year10_revenue": float(tt[-1])}
        mc = monte_carlo(p, n_mc, np.random.default_rng(seed + idx))
        mc_by_region[key] = mc
        cum_rev = float(total.sum())
        ebitda_sum = float(cv["cf"].sum())
        regions[key] = {
            "name": p["name"], "context": p["context"], "discount": p["discount"], "lead": p["lead"],
            "revenue_by_line": {k: v.tolist() for k, v in lines.items()},
            "line_totals": {k: float(v.sum()) for k, v in lines.items()},
            "revenue": total.tolist(),
            "ebitda": cv["cf"].tolist(),
            "ebitda_10y": ebitda_sum,
            "ebitda_margin": float(ebitda_sum / max(cum_rev, 1.0)),
            "cumulative_cf": (-p["launch_M"] * 1e6 + np.cumsum(cv["cf"])).tolist(),
            "cumulative_revenue": cum_rev, "npv": float(cv["npv"]), "ev": float(cv["ev"]),
            "payback_year": payback_year(cv["cf"], p["launch_M"] * 1e6),
            "scenarios": scen,
            "monte_carlo": {"revenue_fan": q(mc["total"]), "npv": {"p5": float(np.percentile(mc["npv"], 5)), "p50": float(np.percentile(mc["npv"], 50)),
                                                               "p95": float(np.percentile(mc["npv"], 95)), "prob_positive": float(np.mean(mc["npv"] > 0))},
                            "cumulative_revenue": {"p5": float(np.percentile(mc["total"].sum(1), 5)), "p50": float(np.percentile(mc["total"].sum(1), 50)),
                                                   "p95": float(np.percentile(mc["total"].sum(1), 95))},
                            "ev": {"p5": float(np.percentile(mc["ev"], 5)), "p50": float(np.percentile(mc["ev"], 50)), "p95": float(np.percentile(mc["ev"], 95))}},
            "bootstrap": bootstrap_prism(p, seed + 100 + idx), "regression": regression_prism(p, seed + 100 + idx),
            "bayes": bayes_prism(p, seed + 200 + idx),
        }
    qml_val = qml_clinical_value()
    cea = cost_effectiveness(link, qml_val, region_lines_map)
    contexts: Dict[str, object] = {}
    for cname, members in CONTEXTS.items():
        tot = np.sum([base_total[k] for k in members], axis=0)
        ebitda_ctx = np.sum([np.array(regions[k]["ebitda"]) for k in members], axis=0)
        line_by_year = {ln: np.sum([np.array(regions[k]["revenue_by_line"][ln]) for k in members], axis=0).tolist()
                        for ln in LINES}
        mc_tot = np.sum([mc_by_region[k]["total"] for k in members], axis=0)
        mc_npv = np.sum([mc_by_region[k]["npv"] for k in members], axis=0)
        mc_ev = np.sum([mc_by_region[k]["ev"] for k in members], axis=0)
        contexts[cname] = {
            "members": members, "revenue": tot.tolist(), "cumulative_revenue": float(tot.sum()),
            "ebitda": ebitda_ctx.tolist(),
            "ebitda_10y": float(ebitda_ctx.sum()),
            "line_by_year": line_by_year,
            "line_totals": {ln: float(sum(line_by_year[ln])) for ln in LINES},
            "qalys_gained_10y": float(sum(cea[k]["qalys_gained_10y"] for k in members)),
            "total_payer_savings_10y": float(sum(cea[k]["total_payer_savings_10y"] for k in members)),
            "nmb_10y": float(sum(cea[k]["nmb_10y"] for k in members)),
            "npv": float(sum(regions[k]["npv"] for k in members)), "ev": float(sum(regions[k]["ev"] for k in members)),
            "revenue_fan": q(mc_tot), "npv_quantiles": {"p5": float(np.percentile(mc_npv, 5)), "p50": float(np.percentile(mc_npv, 50)), "p95": float(np.percentile(mc_npv, 95)),
                                                         "prob_positive": float(np.mean(mc_npv > 0))},
            "ev_quantiles": {"p5": float(np.percentile(mc_ev, 5)), "p50": float(np.percentile(mc_ev, 50)), "p95": float(np.percentile(mc_ev, 95))},
            "cumulative_quantiles": {"p5": float(np.percentile(mc_tot.sum(1), 5)), "p50": float(np.percentile(mc_tot.sum(1), 50)), "p95": float(np.percentile(mc_tot.sum(1), 95))},
        }
    return {"regions": regions, "contexts": contexts, "lines": LINES, "assumptions": {
        "growth": GROWTH, "steepness": STEEPNESS, "midpoint": MIDPOINT, "cogs": COGS, "terminal_growth": TERMINAL_G, "years": YEARS,
        "mc_draws": n_mc}, "physics_link": link, "value_ratios": value_ratios(link), "clinical": CLINICAL,
        "qml_value": qml_val, "cea": cea}
