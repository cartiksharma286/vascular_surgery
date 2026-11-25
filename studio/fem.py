"""2-D plane-strain finite element model of a stented, plaque-narrowed artery cross-section.

Constant-strain triangles on a polar mesh whose radial spacing is the conformal partition of the
ring (geometric radii, cells square in (ln r, theta)). Loading is a uniform luminal pressure that
represents balloon/stent expansion; the outer boundary is tethered (fixed) or on elastic springs.
Linear small-strain surrogate: it ranks designs; it is not a large-strain stent deployment model.

Verification: homogeneous thick-walled cylinder against the exact Lame solution.
Units: mm, MPa, N per mm of axial depth.
"""

from __future__ import annotations

import math
from typing import Dict, List, Optional

import numpy as np
from scipy.sparse import coo_matrix
from scipy.sparse.linalg import spsolve

from elliptic import conformal_partition, uniform_partition


def build_mesh(r_inner: float, r_outer: float, n_theta: int, graded: bool = True, n_r: Optional[int] = None) -> Dict[str, np.ndarray]:
    part = conformal_partition(r_inner, r_outer, n_theta)
    nr = n_r if n_r is not None else part["n_r"]
    radii = part["radii"] if (graded and n_r is None) else (
        [r_inner * (r_outer / r_inner) ** (j / nr) for j in range(nr + 1)] if graded else uniform_partition(r_inner, r_outer, nr))
    radii = np.array(radii)
    theta = np.linspace(0.0, 2.0 * math.pi, n_theta, endpoint=False)
    R, T = np.meshgrid(radii, theta, indexing="ij")
    nodes = np.column_stack([(R * np.cos(T)).ravel(), (R * np.sin(T)).ravel()])
    tris: List[List[int]] = []
    ecj: List[int] = []
    eci: List[int] = []
    for j in range(nr):
        for i in range(n_theta):
            i1 = (i + 1) % n_theta
            n00, n10, n11, n01 = j * n_theta + i, (j + 1) * n_theta + i, (j + 1) * n_theta + i1, j * n_theta + i1
            tris.append([n00, n10, n11]); ecj.append(j); eci.append(i)
            tris.append([n00, n11, n01]); ecj.append(j); eci.append(i)
    tris_a = np.array(tris)
    cen = nodes[tris_a].mean(axis=1)
    return {"nodes": nodes, "tris": tris_a, "radii": radii, "n_theta": n_theta, "n_r": nr,
            "row": np.array(ecj), "col": np.array(eci), "cr": np.hypot(cen[:, 0], cen[:, 1]),
            "ctheta": np.mod(np.arctan2(cen[:, 1], cen[:, 0]), 2.0 * math.pi)}


def _D(E: np.ndarray, nu: np.ndarray) -> np.ndarray:
    f = E / ((1 + nu) * (1 - 2 * nu))
    D = np.zeros((len(E), 3, 3))
    D[:, 0, 0] = D[:, 1, 1] = f * (1 - nu)
    D[:, 0, 1] = D[:, 1, 0] = f * nu
    D[:, 2, 2] = f * (1 - 2 * nu) / 2
    return D


def _geometry(mesh):
    xy = mesh["nodes"][mesh["tris"]]  # (ne, 3, 2)
    x, y = xy[:, :, 0], xy[:, :, 1]
    b = np.column_stack([y[:, 1] - y[:, 2], y[:, 2] - y[:, 0], y[:, 0] - y[:, 1]])
    c = np.column_stack([x[:, 2] - x[:, 1], x[:, 0] - x[:, 2], x[:, 1] - x[:, 0]])
    area = 0.5 * (x[:, 0] * b[:, 0] + x[:, 1] * b[:, 1] + x[:, 2] * b[:, 2])
    B = np.zeros((len(area), 3, 6))
    for k in range(3):
        B[:, 0, 2 * k] = b[:, k]
        B[:, 1, 2 * k + 1] = c[:, k]
        B[:, 2, 2 * k] = c[:, k]
        B[:, 2, 2 * k + 1] = b[:, k]
    B /= (2.0 * area)[:, None, None]
    return B, area


def assign_materials(mesh, E_wall: float = 1.0, nu: float = 0.40, plaque: Optional[Dict[str, float]] = None,
                     n_struts: int = 0, strut_layers: int = 1, E_strut: float = 5000.0, nu_strut: float = 0.30):
    """Element modulus array and region tags (0 wall, 1 plaque, 2 stent hoop)."""
    ne = len(mesh["tris"])
    E = np.full(ne, E_wall)
    nus = np.full(ne, nu)
    tag = np.zeros(ne, dtype=int)
    r_in = mesh["radii"][0]
    if plaque:
        half = 0.5 * math.radians(plaque["arc_deg"])
        centre = math.radians(plaque.get("center_deg", 90.0))
        dth = np.abs(np.angle(np.exp(1j * (mesh["ctheta"] - centre))))
        inside = (dth <= half) & (mesh["cr"] <= r_in + plaque["thickness"])
        E[inside], tag[inside] = plaque["E"], 1
    if n_struts > 0:
        # Connected stent hoop, smeared around the circumference: effective modulus = E_strut * coverage,
        # where coverage = n_struts / n_theta is the metal fraction of the luminal circumference.
        coverage = min(1.0, n_struts / mesh["n_theta"])
        sel = mesh["row"] < strut_layers
        E[sel], nus[sel], tag[sel] = E_strut * coverage, nu_strut, 2
    return E, nus, tag


def assemble(mesh, E: np.ndarray, nus: np.ndarray, outer_spring: Optional[float] = None):
    """Global stiffness (sparse), element B and D matrices, areas and element dof maps."""
    nodes, tris = mesh["nodes"], mesh["tris"]
    nn = len(nodes)
    B, area = _geometry(mesh)
    D = _D(E, nus)
    Ke = np.einsum("eji,ejk,ekl->eil", B, D, B) * area[:, None, None]
    dof = np.stack([2 * tris[:, 0], 2 * tris[:, 0] + 1, 2 * tris[:, 1], 2 * tris[:, 1] + 1,
                    2 * tris[:, 2], 2 * tris[:, 2] + 1], axis=1)
    rows = np.repeat(dof[:, :, None], 6, axis=2).ravel()
    cols = np.repeat(dof[:, None, :], 6, axis=1).ravel()
    K = coo_matrix((Ke.ravel(), (rows, cols)), shape=(2 * nn, 2 * nn)).tolil()
    nth, nr = mesh["n_theta"], mesh["n_r"]
    outer = np.arange(nr * nth, (nr + 1) * nth)
    if outer_spring is not None:
        trib = 2.0 * math.pi * mesh["radii"][-1] / nth
        for n in outer:
            nvec = nodes[n] / np.hypot(*nodes[n])
            K[2 * n: 2 * n + 2, 2 * n: 2 * n + 2] += outer_spring * trib * np.outer(nvec, nvec)
    return K.tocsc(), B, D, area, dof, outer


def solve_force(K, f: np.ndarray, outer: np.ndarray, outer_spring: Optional[float]) -> np.ndarray:
    nn2 = K.shape[0]
    if outer_spring is None:
        fixed = np.concatenate([2 * outer, 2 * outer + 1])
        free = np.setdiff1d(np.arange(nn2), fixed)
        u = np.zeros(nn2)
        u[free] = spsolve(K[free][:, free].tocsc(), f[free])
        return u
    return spsolve(K, f)


def pressure_load(mesh, pressure: float) -> np.ndarray:
    nodes = mesh["nodes"]
    nth = mesh["n_theta"]
    f = np.zeros(2 * len(nodes))
    for i in range(nth):
        a, b_ = i, (i + 1) % nth
        pa, pb = nodes[a], nodes[b_]
        edge = pb - pa
        length = np.hypot(*edge)
        normal_out = np.array([edge[1], -edge[0]]) / length
        normal_out *= np.sign(np.dot(normal_out, 0.5 * (pa + pb)))
        force = pressure * length * normal_out / 2.0
        f[2 * a: 2 * a + 2] += force
        f[2 * b_: 2 * b_ + 2] += force
    return f


def _vm(stress: np.ndarray, nus: np.ndarray) -> np.ndarray:
    sx, sy, txy = stress[:, 0], stress[:, 1], stress[:, 2]
    sz = nus * (sx + sy)
    return np.sqrt(0.5 * ((sx - sy) ** 2 + (sy - sz) ** 2 + (sz - sx) ** 2) + 3.0 * txy ** 2)


def _smooth(mesh, vm: np.ndarray, area: np.ndarray) -> np.ndarray:
    tris = mesh["tris"]
    node_vm, wsum = np.zeros(len(mesh["nodes"])), np.zeros(len(mesh["nodes"]))
    for k in range(3):
        np.add.at(node_vm, tris[:, k], vm * area)
        np.add.at(wsum, tris[:, k], area)
    return node_vm / wsum


def _inner_radial(mesh, u: np.ndarray) -> np.ndarray:
    nth = mesh["n_theta"]
    disp = u.reshape(-1, 2)
    inner = np.arange(nth)
    pts = mesh["nodes"][inner]
    return np.einsum("ij,ij->i", disp[inner], pts) / np.hypot(pts[:, 0], pts[:, 1])


def solve(mesh, E: np.ndarray, nus: np.ndarray, pressure: float = 1.0, outer_spring: Optional[float] = None) -> Dict[str, np.ndarray]:
    K, B, D, area, dof, outer = assemble(mesh, E, nus, outer_spring)
    f = pressure_load(mesh, pressure)
    u = solve_force(K, f, outer, outer_spring)
    strain = np.einsum("eij,ej->ei", B, u[dof])
    stress = np.einsum("eij,ej->ei", D, strain)
    vm = _vm(stress, nus)
    radial = _inner_radial(mesh, u)
    return {"u": u.reshape(-1, 2), "u_flat": u, "vm": vm, "node_vm": _smooth(mesh, vm, area), "area": area,
            "stress": stress, "strain": strain, "inner_radial": radial, "mean_lumen_displacement": float(radial.mean()),
            "energy": 0.5 * float(f @ u), "r_inner": float(mesh["radii"][0]),
            "_K": K, "_B": B, "_D": D, "_dof": dof, "_outer": outer}


def recoil(mesh, E: np.ndarray, nus: np.ndarray, tag: np.ndarray, res: Dict[str, np.ndarray], plastic_fraction: float,
           outer_spring: Optional[float] = None) -> Dict[str, np.ndarray]:
    """Balloon withdrawn: tissue keeps `plastic_fraction` of its deployment strain as permanent set
    (eigenstrain lam*eps), struts keep all of theirs (shape-set). Equilibrium: K u = sum A B^T D eps*."""
    K, B, D, area, dof, outer = res["_K"], res["_B"], res["_D"], res["area"], res["_dof"], res["_outer"]
    eps_dep = res["strain"]
    lam = np.where(tag == 2, 1.0, plastic_fraction)
    eig = eps_dep * lam[:, None]
    f_e = np.einsum("eji,ejk,ek->ei", B, D, eig) * area[:, None]
    f = np.zeros(K.shape[0])
    np.add.at(f, dof.ravel(), f_e.ravel())
    u = solve_force(K, f, outer, outer_spring)
    strain = np.einsum("eij,ej->ei", B, u[dof])
    stress = np.einsum("eij,ej->ei", D, strain - eig)
    vm = _vm(stress, nus)
    radial = _inner_radial(mesh, u)
    return {"u": u.reshape(-1, 2), "vm": vm, "node_vm": _smooth(mesh, vm, area), "inner_radial": radial,
            "mean_lumen_displacement": float(radial.mean())}


def lame_inner_displacement(E: float, nu: float, p: float, ri: float, ro: float) -> float:
    """Exact radial displacement at r_i, plane strain, outer fixed: u = C1 (r_i^2 - r_o^2) / r_i."""
    lam = E * nu / ((1 + nu) * (1 - 2 * nu))
    mu = E / (2 * (1 + nu))
    c1 = -p / (2.0 * ((lam + mu) + mu * ro ** 2 / ri ** 2))
    return c1 * (ri ** 2 - ro ** 2) / ri


def lame_hoop_stress(E: float, nu: float, p: float, ri: float, ro: float, r: float) -> float:
    lam = E * nu / ((1 + nu) * (1 - 2 * nu))
    mu = E / (2 * (1 + nu))
    c1 = -p / (2.0 * ((lam + mu) + mu * ro ** 2 / ri ** 2))
    c2 = -c1 * ro ** 2
    return 2 * (lam + mu) * c1 + 2 * mu * c2 / r ** 2


def verify_lame(ri: float = 1.5, ro: float = 3.0, E: float = 1.0, nu: float = 0.4, p: float = 0.02,
                n_thetas=(24, 48, 96, 192)) -> List[Dict[str, float]]:
    exact = lame_inner_displacement(E, nu, p, ri, ro)
    rows = []
    for n in n_thetas:
        row: Dict[str, float] = {"n_theta": n}
        for graded in (True, False):
            mesh = build_mesh(ri, ro, n, graded=graded, n_r=None if graded else build_mesh(ri, ro, n)["n_r"])
            Ev, nv, _ = assign_materials(mesh, E, nu)
            res = solve(mesh, Ev, nv, p)
            key = "graded" if graded else "uniform"
            row[key + "_error"] = abs(res["mean_lumen_displacement"] - exact) / exact
            row[key + "_dof"] = 2 * len(mesh["nodes"])
        rows.append(row)
    for i in range(1, len(rows)):
        rows[i]["graded_order"] = math.log(rows[i - 1]["graded_error"] / rows[i]["graded_error"]) / math.log(2.0)
    return rows


DEFAULT_TISSUE = {"E_wall": 1.0, "nu": 0.40, "stress_limit": 0.25, "plastic_fraction": 0.55}
DEFAULT_PLAQUE = {"arc_deg": 120.0, "thickness": 0.45, "E": 2.5, "center_deg": 90.0}


def stent_case(ri: float = 1.5, ro: float = 3.0, n_struts: float = 12, strut_layers: int = 1, target_gain: float = 0.10,
               n_theta: int = 96, plaque: Optional[Dict[str, float]] = DEFAULT_PLAQUE, E_strut: float = 5000.0,
               outer_spring: Optional[float] = None, stress_limit: float = DEFAULT_TISSUE["stress_limit"],
               E_wall: float = DEFAULT_TISSUE["E_wall"], nu: float = DEFAULT_TISSUE["nu"],
               plastic_fraction: float = DEFAULT_TISSUE["plastic_fraction"]) -> Dict[str, object]:
    """Deploy to a target mean lumen gain (linear scaling of the unit-pressure solution), then release the
    balloon and let the tissue recoil against the struts (eigenstrain model)."""
    mesh = build_mesh(ri, ro, n_theta)
    E, nus, tag = assign_materials(mesh, E_wall, nu, plaque, n_struts, strut_layers, E_strut)
    res = solve(mesh, E, nus, 1.0, outer_spring)
    target = target_gain * ri
    p_star = target / res["mean_lumen_displacement"]
    rec = recoil(mesh, E, nus, tag, res, plastic_fraction, outer_spring)
    vm = res["vm"] * p_star
    vm_after = rec["vm"] * p_star
    tissue = tag != 2
    area = res["area"]
    total_area = np.sum(area[tissue])
    over = float(np.sum(area[tissue & (vm > stress_limit)]) / total_area)
    over_after = float(np.sum(area[tissue & (vm_after > stress_limit)]) / total_area)
    nth = mesh["n_theta"]
    metal_cov = 0.0 if n_struts == 0 else min(1.0, n_struts / nth)
    metal_burden = metal_cov * strut_layers
    retained = float(rec["mean_lumen_displacement"] * p_star / target)
    return {
        "mesh": mesh, "tag": tag, "E": E, "result": res, "p_star": float(p_star), "vm_scaled": vm, "vm_after": vm_after,
        "node_vm_scaled": res["node_vm"] * p_star, "node_vm_after": rec["node_vm"] * p_star,
        "u_scaled": res["u"] * p_star, "u_after": rec["u"] * p_star,
        "max_vm_tissue": float(vm[tissue].max()), "max_vm_after": float(vm_after[tissue].max()),
        "overstress_fraction": over, "overstress_after": over_after, "metal_coverage": metal_cov, "metal_burden": metal_burden,
        "retained_gain_fraction": retained, "recoil_loss": 1.0 - retained,
        "lumen_area_retained": float(math.pi * ((ri + retained * target) ** 2 - ri ** 2)),
        "lumen_area_gain": float(math.pi * ((ri + target) ** 2 - ri ** 2)), "target_displacement": float(target),
        "stress_limit": stress_limit, "plastic_fraction": plastic_fraction,
        "plaque_max_vm": float(vm[tag == 1].max()) if np.any(tag == 1) else 0.0,
        "n_struts": n_struts, "strut_layers": strut_layers, "ri": ri, "ro": ro,
    }
