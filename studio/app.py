"""Vascular & GI Surgery Simulation Studio: Flask API and static front end.

Run:  python3 app.py            (serves http://127.0.0.1:5050/)
Needs: flask, numpy, scipy. The preprint additionally needs matplotlib and reportlab.

Educational finite-mathematics models on synthetic data. Not a clinical or surgical-planning tool.
"""

from __future__ import annotations

import math
import subprocess
import sys
import threading
from functools import lru_cache
from pathlib import Path

import numpy as np
from flask import Flask, jsonify, request, send_file, send_from_directory

import bem
import economics
import ehr
import elliptic
import fem
import optimize
import qml_trajectories

HERE = Path(__file__).resolve().parent
PREPRINT = HERE / "Nature_Vascular_GI_BEM_FEM_Elliptic_Economics_Preprint.pdf"
app = Flask(__name__, static_folder=str(HERE / "static"), static_url_path="/static")


def clean(a, nd: int = 4):
    """Round and convert NaN to None for JSON."""
    arr = np.asarray(a, dtype=float)
    out = np.round(arr, nd).astype(object)
    out[~np.isfinite(arr)] = None
    return out.tolist()


def num(payload, key, default, lo, hi, cast=float):
    try:
        v = cast(payload.get(key, default))
    except (TypeError, ValueError):
        raise ValueError(f"{key} must be a number")
    if not (lo <= v <= hi):
        raise ValueError(f"{key} must be between {lo} and {hi}")
    return v


@app.errorhandler(ValueError)
def bad_request(exc):
    return jsonify({"success": False, "error": str(exc)}), 400


@app.route("/")
def index():
    return send_from_directory(app.static_folder, "index.html")


@app.route("/api/health")
def health():
    return jsonify({"success": True, "service": "vascular-gi-studio"})


# ---------------------------------------------------------------- elliptic moduli

@app.route("/api/elliptic", methods=["POST", "GET"])
def api_elliptic():
    payload = request.get_json(silent=True) or {}
    ri = num(payload, "ri", 1.5, 0.5, 5.0)
    ro = num(payload, "ro", 3.0, 1.0, 12.0)
    if ro <= ri * 1.05:
        raise ValueError("ro must exceed ri by at least 5%")
    n_theta = num(payload, "n_theta", 48, 12, 96, int)
    part = elliptic.conformal_partition(ri, ro, n_theta)
    nr = part["n_r"]
    ks = [0.02 + 0.97 * i / 59 for i in range(60)]
    k_now = num(payload, "k", 0.5, 0.02, 0.99)
    return jsonify({
        "success": True, "ri": ri, "ro": ro, "n_theta": n_theta, "n_r": nr,
        "conformal_radii": clean(part["radii"], 5), "uniform_radii": clean(elliptic.uniform_partition(ri, ro, nr), 5),
        "conformal_aspect": part["conformal_aspect"], "annulus_modulus": part["annulus_modulus"],
        "table": elliptic.modulus_table(),
        "curve": {"k": clean(ks, 4), "ratio": clean([elliptic.ratio_from_modulus(k) for k in ks], 5),
                  "struts": clean([elliptic.strut_density_from_modulus(k, 1.0, ri) for k in ks], 3)},
        "current": {"k": k_now, "ratio": elliptic.ratio_from_modulus(k_now), "K": elliptic.complete_K(k_now),
                    "K_prime": elliptic.complete_K_prime(k_now), "aspect": elliptic.rectangle_aspect_from_modulus(k_now),
                    "struts": elliptic.strut_density_from_modulus(k_now, 1.0, ri)},
        "square_modulus": elliptic.rectangle_modulus(1.0, 1.0),
    })


# ---------------------------------------------------------------------------- BEM

@lru_cache(maxsize=64)
def _bem_cached(R: float, a: float, e: float, frac: float):
    return bem.field_map(R, a, e, heat_fraction=frac, lesion=optimize.LESION)


@app.route("/api/bem", methods=["POST"])
def api_bem():
    payload = request.get_json(silent=True) or {}
    R = num(payload, "R", 4.0, 2.0, 8.0)
    a = num(payload, "a", 1.0, 0.3, 2.5)
    e = round(num(payload, "e", 1.0, 0.0, 5.0), 3)
    frac = round(num(payload, "heat_fraction", 0.2, 0.02, 0.8), 3)
    if e + a >= R - 0.4:
        raise ValueError("electrode must stay at least 0.4 mm from the outer boundary")
    m = _bem_cached(R, a, e, frac)
    return jsonify({
        "success": True, "R": R, "a": a, "e": e, "grid": m["grid"], "heat_fraction": frac,
        "u": clean(m["u"], 4), "heat": clean(m["heat"], 4),
        "boundary": clean(m["boundary"], 3), "lesion": optimize.LESION,
        "metrics": {k: m[k] for k in ("zone_area", "zone_fraction", "serosal_exposure", "current", "exact_current", "log_rho",
                                       "resistance", "n_elements", "min_gap", "lesion_coverage")},
        "impedance_window": [optimize.R_MIN, optimize.R_MAX],
        "within_window": optimize.R_MIN <= m["resistance"] <= optimize.R_MAX,
    })


@lru_cache(maxsize=1)
def _bem_verify():
    return {"concentric": bem.concentric_error(), "convergence": bem.convergence_study()}


@app.route("/api/bem/verify")
def api_bem_verify():
    return jsonify({"success": True, **_bem_verify()})


@lru_cache(maxsize=1)
def _gi_opt():
    return optimize.optimize_gi()


@app.route("/api/bem/optimize")
def api_bem_optimize():
    return jsonify({"success": True, **_gi_opt()})


# ---------------------------------------------------------------------------- FEM

@lru_cache(maxsize=96)
def _fem_cached(n_struts, layers, gain, arc, plaque_E, plastic, limit, thickness):
    plaque = {"arc_deg": arc, "thickness": thickness, "E": plaque_E, "center_deg": 90.0} if arc > 0 else None
    return fem.stent_case(n_struts=n_struts, strut_layers=layers, target_gain=gain, plaque=plaque,
                          plastic_fraction=plastic, stress_limit=limit)


@app.route("/api/fem", methods=["POST"])
def api_fem():
    payload = request.get_json(silent=True) or {}
    n_struts = num(payload, "n_struts", 12, 0, 40, int)
    layers = num(payload, "layers", 1, 1, 3, int)
    gain = round(num(payload, "target_gain", 0.10, 0.02, 0.2), 3)
    arc = num(payload, "plaque_arc", 120, 0, 240, float)
    plaque_E = num(payload, "plaque_E", 2.5, 1.0, 20.0)
    plastic = round(num(payload, "plastic_fraction", 0.55, 0.1, 0.9), 3)
    limit = round(num(payload, "stress_limit", 0.25, 0.05, 1.0), 3)
    thickness = round(num(payload, "plaque_thickness", 0.45, 0.1, 1.0), 3)
    c = _fem_cached(n_struts, layers, gain, arc, plaque_E, plastic, limit, thickness)
    mesh = c["mesh"]
    return jsonify({
        "success": True, "ri": c["ri"], "ro": c["ro"], "n_theta": mesh["n_theta"], "n_r": mesh["n_r"],
        "nodes": clean(mesh["nodes"], 4), "tris": mesh["tris"].tolist(), "tag": c["tag"].tolist(),
        "vm_deploy": clean(c["vm_scaled"], 4), "vm_after": clean(c["vm_after"], 4),
        "u_deploy": clean(c["u_scaled"], 5), "u_after": clean(c["u_after"], 5),
        "metrics": {k: c[k] for k in ("max_vm_tissue", "max_vm_after", "overstress_fraction", "overstress_after", "metal_coverage",
                                      "metal_burden", "retained_gain_fraction", "recoil_loss", "lumen_area_retained", "lumen_area_gain",
                                      "target_displacement", "stress_limit", "plastic_fraction", "plaque_max_vm", "n_struts", "strut_layers")},
        "baseline_recoil_loss": 1.0 - plastic,
    })


@lru_cache(maxsize=1)
def _fem_verify():
    rows = fem.verify_lame()
    return {"lame": rows}


@app.route("/api/fem/verify")
def api_fem_verify():
    return jsonify({"success": True, **_fem_verify()})


@lru_cache(maxsize=1)
def _stent_opt():
    return optimize.optimize_stent()


@app.route("/api/fem/optimize")
def api_fem_optimize():
    return jsonify({"success": True, **_stent_opt()})


# ---------------------------------------------------------------------------- EHR

@lru_cache(maxsize=32)
def _ehr_cached(n, dup, th, seed):
    recs = ehr.generate_records(n, dup, seed)
    res = ehr.link_records(recs, th)
    return res, ehr.schedule(ehr.generate_cases(24, seed + 2), 3, seed)


@app.route("/api/ehr", methods=["POST"])
def api_ehr():
    payload = request.get_json(silent=True) or {}
    n = num(payload, "n", 300, 40, 1200, int)
    dup = round(num(payload, "dup_rate", 0.2, 0.02, 0.5), 3)
    th = round(num(payload, "threshold", 0.86, 0.5, 0.99), 3)
    seed = num(payload, "seed", 1, 1, 999, int)
    res, sched = _ehr_cached(n, dup, th, seed)
    shown = [e for e in res["edges"]][:600]
    involved = sorted({x for e in shown for x in (e["a"], e["b"])})
    recs = {r["rid"]: r for r in res["records"]}
    nodes = [{"id": i, "entity": recs[i]["entity"], "cluster": res["assignment"][i], "label": f"{recs[i]['first']} {recs[i]['last']}"} for i in involved]
    return jsonify({
        "success": True, "n_records": res["n_records"], "total_pairs": res["total_pairs"], "candidate_pairs": res["candidate_pairs"],
        "reduction_ratio": res["reduction_ratio"], "metrics": res["metrics"], "curve": res["curve"], "clusters": res["clusters"],
        "entities": res["entities"], "predicted_entities": res["predicted_entities"], "edges": shown, "nodes": nodes,
        "schedule": {k: sched[k] for k in ("rules", "best_rule", "annealing", "improvement_vs_best_rule", "trace", "segments", "rooms")},
    })


# -------------------------------------------------------- QML trajectories

@lru_cache(maxsize=64)
def _qml_cached(proc: str, age: float, comorb: float, burden: float, opt: bool, delay: float, gamma: float):
    return qml_trajectories.predict_trajectory(
        procedure=proc, age=age, comorbidity=comorb, burden=burden,
        use_optimized=opt, ehr_delay=delay, gamma=gamma,
    )


@app.route("/api/qml", methods=["POST", "GET"])
def api_qml():
    payload = request.get_json(silent=True) or {}
    proc = str(payload.get("procedure", "stent"))
    if proc not in qml_trajectories.PROCEDURES:
        raise ValueError(f"procedure must be one of {list(qml_trajectories.PROCEDURES)}")
    age = round(num(payload, "age", 64.0, 35.0, 90.0), 1)
    comorb = round(num(payload, "comorbidity", 0.35, 0.0, 1.0), 3)
    burden = round(num(payload, "burden", 0.50, 0.0, 1.0), 3)
    opt = bool(payload.get("use_optimized", True))
    delay = round(num(payload, "ehr_delay", 0.25, 0.0, 1.0), 3)
    gamma = round(num(payload, "gamma", 0.25, 0.0, 1.5), 3)
    res = _qml_cached(proc, age, comorb, burden, opt, delay, gamma)
    return jsonify({"success": True, **res})


# --------------------------------------------------------------------- economics

@lru_cache(maxsize=1)
def _economics():
    s, g = _stent_opt(), _gi_opt()
    link = economics.physics_link(s["baseline"]["J"], s["exhaustive"]["J"], g["baseline"]["J"],
                                  min(g["exhaustive"]["J"], g["annealing"]["J"]))
    return economics.run_all(link)


@app.route("/api/economics")
def api_economics():
    return jsonify({"success": True, **_economics()})


@app.route("/api/summary")
def api_summary():
    v, f, s, g, e = _bem_verify(), _fem_verify(), _stent_opt(), _gi_opt(), _economics()
    res, sched = _ehr_cached(300, 0.2, 0.86, 1)
    q = _qml_cached("stent", 64.0, 0.35, 0.50, True, 0.25, 0.25)
    rows = v["convergence"]
    return jsonify({
        "success": True,
        "bem": {"final_error": rows[-1]["relative_error"], "order": rows[-1].get("observed_order"), "concentric": v["concentric"]},
        "fem": {"final_error": f["lame"][-2]["graded_error"], "graded_vs_uniform": f["lame"][-2]["uniform_error"] / f["lame"][-2]["graded_error"]},
        "stent": {"exhaustive": s["exhaustive"], "annealing_evals": s["annealing"]["evaluations"], "baseline_J": s["baseline"]["J"]},
        "gi": {"best_J": min(g["exhaustive"]["J"], g["annealing"]["J"]), "baseline_J": g["baseline"]["J"]},
        "ehr": {"f1": res["metrics"]["f1"], "reduction": res["reduction_ratio"], "schedule_gain": sched["improvement_vs_best_rule"]},
        "qml": {"recovery_90d": q["summary"]["recovery_90d"], "auroc_30d": q["diagnostics"]["auroc_30d"], "readmission_30d": q["summary"]["readmission_30d"]},
        "contexts": {k: {"cumulative": c["cumulative_revenue"], "npv": c["npv"], "ev": c["ev"], "nmb": c["nmb_10y"]} for k, c in e["contexts"].items()},
    })


# ----------------------------------------------------------------------- preprint

def _ensure_preprint():
    if not PREPRINT.exists():
        subprocess.run([sys.executable, str(HERE / "make_preprint.py")], check=True, cwd=str(HERE))


@app.route("/preprint/view")
def preprint_view():
    _ensure_preprint()
    return send_file(PREPRINT, mimetype="application/pdf")


@app.route("/preprint/download")
def preprint_download():
    _ensure_preprint()
    return send_file(PREPRINT, as_attachment=True, download_name=PREPRINT.name)


def _warm():
    try:
        _bem_verify(); _fem_verify(); _stent_opt(); _gi_opt(); _economics(); _ehr_cached(300, 0.2, 0.86, 1)
        _qml_cached("stent", 64.0, 0.35, 0.50, True, 0.25, 0.25)
    except Exception as exc:  # pragma: no cover - warm-up is best effort
        print("warm-up failed:", exc)


if __name__ == "__main__":
    threading.Thread(target=_warm, daemon=True).start()
    app.run(host="127.0.0.1", port=5095, debug=False, threaded=True)
