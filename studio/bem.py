"""2-D boundary element method (BEM) for Laplace's equation in a bowel-wall cross-section.

Model: tissue between an outer circle (radius R, the serosal return, u = 0) and an electrode circle
(radius a, centre offset e, u = V). The conduction problem div(sigma grad u) = 0 with sigma = 1 has
Joule heating density q = sigma |grad u|^2. Constant elements, midpoint collocation, direct BEM:

    c_i u_i + sum_j H_ij u_j = sum_j G_ij q_j,  with  u* = -(1/2pi) ln r,  q* = du*/dn.

Exact reference: total current per unit depth I = 2 pi sigma V / ln(rho) with
cosh(ln rho) = (R^2 + a^2 - e^2)/(2 R a), the conformal modulus of the eccentric ring.
An idealized 2-D conduction model for teaching; not a validated surgical-planning tool.
"""

from __future__ import annotations

import math
from typing import Dict, List, Tuple

import numpy as np

from elliptic import eccentric_ring_log_ratio

_GAUSS = {n: np.polynomial.legendre.leggauss(n) for n in (6, 8, 12)}


def _circle(center: Tuple[float, float], radius: float, n: int, clockwise: bool) -> np.ndarray:
    ang = np.linspace(0.0, 2.0 * math.pi, n, endpoint=False)
    if clockwise:
        ang = -ang
    return np.column_stack([center[0] + radius * np.cos(ang), center[1] + radius * np.sin(ang)])


def build_boundary(R: float, a: float, e: float, n_outer: int, n_inner: int) -> Dict[str, np.ndarray]:
    """Boundary nodes (outer CCW, electrode CW so that (dy, -dx)/L is the outward normal of the domain)."""
    if not (0 < a < R) or e < 0 or e + a >= R:
        raise ValueError("electrode circle must lie strictly inside the outer circle")
    outer = _circle((0.0, 0.0), R, n_outer, clockwise=False)
    inner = _circle((e, 0.0), a, n_inner, clockwise=True)
    nodes = np.vstack([outer, inner])
    starts = np.vstack([outer, inner])
    ends = np.vstack([np.roll(outer, -1, axis=0), np.roll(inner, -1, axis=0)])
    d = ends - starts
    length = np.hypot(d[:, 0], d[:, 1])
    normal = np.column_stack([d[:, 1], -d[:, 0]]) / length[:, None]
    mid = 0.5 * (starts + ends)
    return {"nodes": nodes, "start": starts, "end": ends, "length": length, "normal": normal, "mid": mid,
            "is_outer": np.arange(n_outer + n_inner) < n_outer}


def _kernels(points: np.ndarray, b: Dict[str, np.ndarray], order: int = 12) -> Tuple[np.ndarray, np.ndarray]:
    """G[p, j] = int u* dGamma_j and H[p, j] = int q* dGamma_j for field points (excluding the singular case)."""
    gx, gw = _GAUSS[order]
    s = 0.5 * (gx + 1.0)
    w = 0.5 * gw
    start, end, L, nrm = b["start"], b["end"], b["length"], b["normal"]
    qx = start[:, 0, None] + (end[:, 0] - start[:, 0])[:, None] * s[None, :]      # (E, G)
    qy = start[:, 1, None] + (end[:, 1] - start[:, 1])[:, None] * s[None, :]
    rx = qx[None, :, :] - points[:, 0, None, None]                                 # (P, E, G)
    ry = qy[None, :, :] - points[:, 1, None, None]
    r2 = np.maximum(rx * rx + ry * ry, 1e-30)
    ustar = np.log(r2) * (-0.25 / math.pi)
    qstar = (rx * nrm[None, :, 0, None] + ry * nrm[None, :, 1, None]) / r2 * (-0.5 / math.pi)
    G = (ustar @ w) * L[None, :]
    H = (qstar @ w) * L[None, :]
    return G, H


def solve_potential(R: float, a: float, e: float, V: float = 1.0, n_outer: int = 160, n_inner: int = 96) -> Dict[str, object]:
    b = build_boundary(R, a, e, n_outer, n_inner)
    n = len(b["length"])
    G, H = _kernels(b["mid"], b)
    L = b["length"]
    G[np.arange(n), np.arange(n)] = L / (2.0 * math.pi) * (1.0 - np.log(L / 2.0))
    H[np.arange(n), np.arange(n)] = 0.0
    u = np.where(b["is_outer"], 0.0, V)
    q = np.linalg.solve(G, H @ u + 0.5 * u)
    return {"b": b, "u": u, "q": q}


def total_current(sol: Dict[str, object], sigma: float = 1.0) -> float:
    """Current entering the tissue per unit depth: sigma * sum q L over the electrode (q = du/dn, n out of the domain)."""
    b, q = sol["b"], sol["q"]
    inner = ~b["is_outer"]
    return float(sigma * np.sum(q[inner] * b["length"][inner]))


def analytic_current(R: float, a: float, e: float, V: float = 1.0, sigma: float = 1.0) -> float:
    return 2.0 * math.pi * sigma * V / eccentric_ring_log_ratio(R, a, e)


def potential_at(sol: Dict[str, object], pts: np.ndarray) -> np.ndarray:
    """u(x) = sum G q - sum H u for interior points."""
    out = np.empty(len(pts))
    for lo in range(0, len(pts), 800):
        G, H = _kernels(pts[lo:lo + 800], sol["b"], order=8)
        out[lo:lo + 800] = G @ sol["q"] - H @ sol["u"]
    return out


def concentric_error(R: float = 4.0, a: float = 1.0, n_outer: int = 160, n_inner: int = 96) -> Dict[str, float]:
    """Max error of u(r) vs V ln(R/r)/ln(R/a) and relative current error, concentric case."""
    sol = solve_potential(R, a, 0.0, 1.0, n_outer, n_inner)
    r = np.linspace(a * 1.25, R * 0.8, 24)
    pts = np.column_stack([r, np.zeros_like(r)])
    u = potential_at(sol, pts)
    exact = np.log(R / r) / math.log(R / a)
    cur = total_current(sol)
    ex = analytic_current(R, a, 0.0)
    return {"max_potential_error": float(np.max(np.abs(u - exact))), "current_relative_error": abs(cur - ex) / ex}


def convergence_study(R: float = 4.0, a: float = 1.0, e: float = 1.6, counts=(24, 48, 96, 192)) -> List[Dict[str, float]]:
    rows = []
    for n in counts:
        sol = solve_potential(R, a, e, 1.0, n_outer=2 * n, n_inner=n)
        cur, ex = total_current(sol), analytic_current(R, a, e)
        rows.append({"n_inner": n, "n_outer": 2 * n, "current": cur, "exact": ex, "relative_error": abs(cur - ex) / ex})
    for i in range(1, len(rows)):
        rows[i]["observed_order"] = math.log(rows[i - 1]["relative_error"] / rows[i]["relative_error"]) / math.log(2.0)
    return rows


def field_map(R: float, a: float, e: float, n_outer: int = 112, n_inner: int = 72, grid: int = 84,
              heat_fraction: float = 0.2, lesion: Dict[str, float] | None = None) -> Dict[str, object]:
    """Potential and Joule-heating maps on a square grid plus surgical safety metrics."""
    sol = solve_potential(R, a, e, 1.0, n_outer, n_inner)
    xs = np.linspace(-R, R, grid)
    X, Y = np.meshgrid(xs, xs)
    rho_o = np.hypot(X, Y)
    rho_i = np.hypot(X - e, Y)
    h = xs[1] - xs[0]
    inside = (rho_o < R - 0.5 * h) & (rho_i > a + 0.5 * h)
    pts = np.column_stack([X[inside], Y[inside]])
    u_grid = np.full(X.shape, np.nan)
    u_grid[inside] = potential_at(sol, pts)
    gy, gx = np.gradient(u_grid, h)
    heat = gx ** 2 + gy ** 2
    peak = float(np.nanmax(heat))
    zone = heat >= heat_fraction * peak
    area = float(np.nansum(zone & inside) * h * h)
    wall_area = float(math.pi * (R ** 2 - a ** 2))
    near_outer = inside & (rho_o > R - 2.5 * h * 2)
    serosal_ratio = float(np.nanmax(np.where(near_outer, heat, np.nan)) / peak) if np.any(near_outer) else 0.0
    out = {
        "R": R, "a": a, "e": e, "grid": grid, "extent": [-R, R],
        "u": np.where(inside, u_grid, np.nan), "heat": np.where(inside, heat / peak, np.nan),
        "inside": inside, "zone_area": area, "zone_fraction": area / wall_area,
        "serosal_exposure": serosal_ratio, "current": total_current(sol), "exact_current": analytic_current(R, a, e),
        "log_rho": eccentric_ring_log_ratio(R, a, e), "resistance": eccentric_ring_log_ratio(R, a, e) / (2.0 * math.pi),
        "boundary": sol["b"]["mid"], "n_elements": int(len(sol["u"])), "peak_heat_raw": peak,
        "min_gap": R - a - e,
    }
    if lesion is not None:
        lx, ly, lr = float(lesion["x"]), float(lesion.get("y", 0.0)), float(lesion["r"])
        mask = ((X - lx) ** 2 + (Y - ly) ** 2 <= lr ** 2) & inside
        out["lesion_coverage"] = float(np.nanmean(zone[mask])) if mask.any() else 0.0
    return out
