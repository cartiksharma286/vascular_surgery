"""Parametric CAD, GD&T dimensioning, and Generative AI recommendation engine
for cardiovascular stents, GI instrumentation, and electrocautery devices.

Exports valid ASCII .DXF, .STL, and .OBJ files to disk under cad_exports/.
Educational finite-mathematics & CAD teaching module. Not for clinical manufacturing.
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np

import elliptic

HERE = Path(__file__).resolve().parent
EXPORT_DIR = HERE / "cad_exports"
EXPORT_DIR.mkdir(parents=True, exist_ok=True)

DEVICE_DB: Dict[str, Dict[str, object]] = {
    # --- Stent-Based Repair ---
    "coronary_des": {
        "id": "coronary_des",
        "category": "stent",
        "category_label": "Stent-Based Repair",
        "name": "Coronary Closed-Cell DES",
        "material": "CoCr L605 / NiTi",
        "diameter_mm": 3.0,
        "length_mm": 18.0,
        "wall_mm": 0.085,
        "n_struts": 12,
        "n_rings": 6,
        "tip_radius_mm": 0.15,
        "indication": "Focal coronary stenosis & ostial scaffold",
        "surface_ra_um": 0.4,
    },
    "iliac_self_expand": {
        "id": "iliac_self_expand",
        "category": "stent",
        "category_label": "Stent-Based Repair",
        "name": "Iliac Self-Expanding Nitinol Stent",
        "material": "Nitinol (NiTi 55/45)",
        "diameter_mm": 8.0,
        "length_mm": 40.0,
        "wall_mm": 0.180,
        "n_struts": 16,
        "n_rings": 8,
        "tip_radius_mm": 0.25,
        "indication": "Aortoiliac occlusive & aneurysmal repair",
        "surface_ra_um": 0.6,
    },
    "carotid_tapered": {
        "id": "carotid_tapered",
        "category": "stent",
        "category_label": "Stent-Based Repair",
        "name": "Carotid Tapered Open-Cell Stent",
        "material": "Nitinol (Superelastic)",
        "diameter_mm": 6.5,
        "length_mm": 30.0,
        "wall_mm": 0.140,
        "n_struts": 14,
        "n_rings": 7,
        "tip_radius_mm": 0.20,
        "indication": "Carotid bifurcation plaque stabilization",
        "surface_ra_um": 0.4,
    },
    # --- GI Instrumentation ---
    "lap_grasper_jaw": {
        "id": "lap_grasper_jaw",
        "category": "gi_instrument",
        "category_label": "GI Instrumentation",
        "name": "Laparoscopic Atraumatic Grasper Jaw",
        "material": "316LVM Stainless Steel",
        "diameter_mm": 5.0,
        "length_mm": 22.0,
        "wall_mm": 0.80,
        "n_struts": 8,
        "n_rings": 5,
        "tip_radius_mm": 0.60,
        "indication": "Bowel & mesentery atraumatic traction",
        "surface_ra_um": 0.8,
    },
    "eea_stapler_anvil": {
        "id": "eea_stapler_anvil",
        "category": "gi_instrument",
        "category_label": "GI Instrumentation",
        "name": "Circular EEA Anastomosis Stapler Ring",
        "material": "17-4PH Stainless / Ti-6Al-4V",
        "diameter_mm": 28.0,
        "length_mm": 14.0,
        "wall_mm": 4.20,
        "n_struts": 24,
        "n_rings": 2,
        "tip_radius_mm": 0.35,
        "indication": "Colorectal end-to-end stapled anastomosis",
        "surface_ra_um": 0.5,
    },
    # --- Electrocautery ---
    "monopolar_hook": {
        "id": "monopolar_hook",
        "category": "electrocautery",
        "category_label": "Electrocautery",
        "name": "Monopolar L-Hook Dissection Electrode",
        "material": "Tungsten / PTFE Shaft",
        "diameter_mm": 2.4,
        "length_mm": 24.0,
        "wall_mm": 0.45,
        "n_struts": 10,
        "n_rings": 4,
        "tip_radius_mm": 0.30,
        "indication": "Submucosal & serosal-sparing GI dissection",
        "surface_ra_um": 0.2,
    },
    "bipolar_forceps_tip": {
        "id": "bipolar_forceps_tip",
        "category": "electrocautery",
        "category_label": "Electrocautery",
        "name": "Bipolar Coagulation Forceps Tip",
        "material": "Cu-Be / TiN Non-Stick",
        "diameter_mm": 3.2,
        "length_mm": 20.0,
        "wall_mm": 0.60,
        "n_struts": 8,
        "n_rings": 3,
        "tip_radius_mm": 0.25,
        "indication": "Focused mesenteric vessel hemostasis",
        "surface_ra_um": 0.2,
    },
}


def list_database() -> Dict[str, object]:
    devices = list(DEVICE_DB.values())
    saved = sorted(
        [
            {"name": p.name, "size_bytes": p.stat().st_size, "ext": p.suffix.lower()}
            for p in EXPORT_DIR.iterdir()
            if p.is_file() and p.suffix.lower() in {".dxf", ".stl", ".obj"}
        ],
        key=lambda x: x["name"],
    )
    return {"devices": devices, "saved_files": saved}


def recommend_design(
    device_id: str = "coronary_des",
    target_diameter_mm: float = 3.2,
    target_length_mm: float = 20.0,
    stiffness_factor: float = 0.5,
    priority: str = "balanced",
) -> Dict[str, object]:
    """Generative AI latent-manifold recommendation engine for parametric CAD synthesis."""
    base = DEVICE_DB.get(device_id, DEVICE_DB["coronary_des"])
    cat = base["category"]

    weights = {
        "balanced": (0.40, 0.35, 0.25),
        "high_radial": (0.65, 0.15, 0.20),
        "low_metal": (0.20, 0.60, 0.20),
    }.get(priority, (0.40, 0.35, 0.25))
    w_rad, w_burd, w_conf = weights

    # Generate candidate latent-space variants around the target clinical envelope
    candidates: List[Dict[str, object]] = []
    if cat == "stent":
        strut_grid = [8, 10, 12, 14, 16, 18, 20]
        wall_mults = [0.85, 1.0, 1.15]
        for ns in strut_grid:
            for wm in wall_mults:
                wall = round(base["wall_mm"] * wm * (1.0 + 0.18 * (stiffness_factor - 0.5)), 4)
                rings = max(3, int(round(target_length_mm / 3.2)))
                # Elliptic modulus conformal score
                k_est = float(np.clip(0.18 + 0.032 * ns, 0.08, 0.94))
                ratio_k = elliptic.ratio_from_modulus(k_est)
                radial_score = 1.0 - math.exp(-0.14 * ns * (wall / base["wall_mm"]))
                metal_burden = (ns * wall) / (math.pi * target_diameter_mm)
                burden_score = max(0.0, 1.0 - 1.6 * metal_burden)
                conformal_score = math.exp(-((ratio_k - 1.25) ** 2) / 0.35)
                gen_score = w_rad * radial_score + w_burd * burden_score + w_conf * conformal_score
                candidates.append({
                    "n_struts": ns,
                    "n_rings": rings,
                    "wall_mm": wall,
                    "diameter_mm": round(target_diameter_mm, 3),
                    "length_mm": round(target_length_mm, 3),
                    "elliptic_k": round(k_est, 4),
                    "radial_score": round(radial_score, 4),
                    "metal_burden": round(metal_burden, 4),
                    "gen_score": round(gen_score, 4),
                })
    else:
        # GI instrumentation & electrocautery generative synthesis
        rib_grid = [6, 8, 10, 12, 14]
        wall_mults = [0.85, 1.0, 1.15]
        for ns in rib_grid:
            for wm in wall_mults:
                wall = round(base["wall_mm"] * wm, 3)
                rings = max(2, int(round(target_length_mm / 5.0)))
                k_est = float(np.clip(0.22 + 0.04 * ns, 0.10, 0.92))
                ergonomic_score = math.exp(-((ns - base["n_struts"]) ** 2) / 18.0)
                thermal_or_grip = 1.0 - math.exp(-0.22 * ns * (1.0 + 0.4 * stiffness_factor))
                mass_penalty = 0.12 * wm
                gen_score = w_rad * thermal_or_grip + w_burd * (1.0 - mass_penalty) + w_conf * ergonomic_score
                candidates.append({
                    "n_struts": ns,
                    "n_rings": rings,
                    "wall_mm": wall,
                    "diameter_mm": round(target_diameter_mm, 3),
                    "length_mm": round(target_length_mm, 3),
                    "elliptic_k": round(k_est, 4),
                    "radial_score": round(thermal_or_grip, 4),
                    "metal_burden": round(wall / max(target_diameter_mm, 0.5), 4),
                    "gen_score": round(gen_score, 4),
                })

    candidates.sort(key=lambda c: c["gen_score"], reverse=True)
    best = candidates[0]
    return {
        "base_device": base,
        "recommended": best,
        "alternatives": candidates[1:4],
        "priority": priority,
        "confidence": round(float(np.clip(0.78 + 0.20 * best["gen_score"], 0.70, 0.98)), 3),
    }


# ------------------------------------------------------------------ 3D Mesh Gen

def _box_tris(p0: np.ndarray, p1: np.ndarray, w: float, h: float) -> Tuple[np.ndarray, np.ndarray]:
    """Generate 12 triangles (8 vertices) for a 3D strut segment from p0 to p1."""
    d = p1 - p0
    L = float(np.linalg.norm(d))
    if L < 1e-8:
        return np.zeros((0, 3)), np.zeros((0, 3), dtype=int)
    t = d / L
    # Radial-ish normal perpendicular to t
    ref = np.array([0.0, 0.0, 1.0]) if abs(t[2]) < 0.9 else np.array([1.0, 0.0, 0.0])
    u = np.cross(t, ref)
    u /= np.linalg.norm(u)
    v = np.cross(t, u)
    hw, hh = 0.5 * w, 0.5 * h
    verts = np.array([
        p0 - hw * u - hh * v, p0 + hw * u - hh * v, p0 + hw * u + hh * v, p0 - hw * u + hh * v,
        p1 - hw * u - hh * v, p1 + hw * u - hh * v, p1 + hw * u + hh * v, p1 - hw * u + hh * v,
    ])
    faces = np.array([
        [0, 2, 1], [0, 3, 2],
        [4, 5, 6], [4, 6, 7],
        [0, 1, 5], [0, 5, 4],
        [1, 2, 6], [1, 6, 5],
        [2, 3, 7], [2, 7, 6],
        [3, 0, 4], [3, 4, 7],
    ], dtype=int)
    return verts, faces


def build_3d_mesh(device: Dict[str, object], spec: Dict[str, object]) -> Tuple[np.ndarray, np.ndarray]:
    """Build parametric 3D triangle mesh (vertices in mm, faces)."""
    cat = device["category"]
    D = float(spec["diameter_mm"])
    L = float(spec["length_mm"])
    R = 0.5 * D
    wall = float(spec["wall_mm"])
    ns = int(spec["n_struts"])
    nr = int(spec["n_rings"])

    all_v: List[np.ndarray] = []
    all_f: List[np.ndarray] = []
    v_off = 0

    def add_seg(p0, p1, w, h):
        nonlocal v_off
        vs, fs = _box_tris(p0, p1, w, h)
        if len(vs):
            all_v.append(vs)
            all_f.append(fs + v_off)
            v_off += len(vs)

    if cat == "stent":
        # Closed-cell sinusoidal crown rings + longitudinal connectors
        pts_per_ring = max(24, ns * 2)
        ring_z = np.linspace(-0.45 * L, 0.45 * L, nr)
        amp = min(0.85, 0.40 * L / max(nr, 1))
        for rz in ring_z:
            ring_pts = []
            for i in range(pts_per_ring):
                th = 2.0 * math.pi * i / pts_per_ring
                z = rz + amp * math.sin(ns * th)
                ring_pts.append(np.array([R * math.cos(th), R * math.sin(th), z]))
            for i in range(pts_per_ring):
                add_seg(ring_pts[i], ring_pts[(i + 1) % pts_per_ring], wall, wall * 1.15)
        # Longitudinal bridges between adjacent rings
        for r_idx in range(nr - 1):
            for s in range(0, ns, 2):
                th = 2.0 * math.pi * s / ns
                p0 = np.array([R * math.cos(th), R * math.sin(th), ring_z[r_idx]])
                p1 = np.array([R * math.cos(th), R * math.sin(th), ring_z[r_idx + 1]])
                add_seg(p0, p1, wall * 0.9, wall)

    elif cat == "gi_instrument":
        # Cylindrical shaft + fenestrated jaw / stapler ring with ribs
        n_seg = max(16, ns * 2)
        z_shaft_end = -0.05 * L
        for i in range(n_seg):
            th0 = 2.0 * math.pi * i / n_seg
            th1 = 2.0 * math.pi * (i + 1) / n_seg
            p0 = np.array([R * math.cos(th0), R * math.sin(th0), -0.5 * L])
            p1 = np.array([R * math.cos(th0), R * math.sin(th0), z_shaft_end])
            add_seg(p0, p1, wall * 0.8, wall * 0.8)
            q0 = np.array([R * math.cos(th0), R * math.sin(th0), z_shaft_end])
            q1 = np.array([R * math.cos(th1), R * math.sin(th1), z_shaft_end])
            add_seg(q0, q1, wall * 0.8, wall * 0.8)
        # Working jaw / staple crown
        for i in range(ns):
            th = 2.0 * math.pi * i / ns
            r_tip = R * (0.65 if device["id"] == "lap_grasper_jaw" else 1.0)
            p0 = np.array([R * math.cos(th), R * math.sin(th), z_shaft_end])
            p1 = np.array([r_tip * math.cos(th), r_tip * math.sin(th), 0.5 * L])
            add_seg(p0, p1, wall * 0.75, wall * 0.75)
            # Serration / staple slot cross-bars
            for k in range(1, nr + 1):
                frac = k / (nr + 1)
                c_pt = p0 * (1 - frac) + p1 * frac
                th_n = 2.0 * math.pi * (i + 1) / ns
                n_pt = np.array([R * math.cos(th_n), R * math.sin(th_n), z_shaft_end]) * (1 - frac) + np.array([r_tip * math.cos(th_n), r_tip * math.sin(th_n), 0.5 * L]) * frac
                add_seg(c_pt, n_pt, wall * 0.55, wall * 0.55)

    else:
        # Electrocautery: insulated cylindrical shaft + active L-hook / bipolar prongs
        n_seg = 16
        for i in range(n_seg):
            th0 = 2.0 * math.pi * i / n_seg
            th1 = 2.0 * math.pi * (i + 1) / n_seg
            p0 = np.array([R * math.cos(th0), R * math.sin(th0), -0.5 * L])
            p1 = np.array([R * math.cos(th0), R * math.sin(th0), 0.15 * L])
            add_seg(p0, p1, wall * 0.7, wall * 0.7)
            add_seg(
                np.array([R * math.cos(th0), R * math.sin(th0), 0.15 * L]),
                np.array([R * math.cos(th1), R * math.sin(th1), 0.15 * L]),
                wall * 0.7, wall * 0.7,
            )
        if device["id"] == "monopolar_hook":
            add_seg(np.array([0.0, 0.0, 0.15 * L]), np.array([0.0, 0.0, 0.45 * L]), wall * 0.9, wall * 0.9)
            add_seg(np.array([0.0, 0.0, 0.45 * L]), np.array([1.2 * R, 0.0, 0.45 * L]), wall * 0.8, wall * 0.8)
            add_seg(np.array([1.2 * R, 0.0, 0.45 * L]), np.array([1.2 * R, 0.0, 0.34 * L]), wall * 0.7, wall * 0.7)
        else:
            # Bipolar dual prongs
            for sgn in (-1.0, 1.0):
                add_seg(np.array([sgn * 0.45 * R, 0.0, 0.15 * L]), np.array([sgn * 0.28 * R, 0.0, 0.50 * L]), wall * 0.65, wall * 0.65)

    V = np.vstack(all_v) if all_v else np.zeros((0, 3))
    F = np.vstack(all_f) if all_f else np.zeros((0, 3), dtype=int)
    return V, F


# ------------------------------------------------------------ GD&T Dimensioning

def build_gdt_spec(device: Dict[str, object], spec: Dict[str, object]) -> Dict[str, object]:
    """Generate ASME Y14.5 / ISO 1101 GD&T feature control frames and tolerances."""
    D = float(spec["diameter_mm"])
    L = float(spec["length_mm"])
    w = float(spec["wall_mm"])
    tol_d = round(max(0.01, 0.006 * D), 3)
    tol_l = round(max(0.03, 0.003 * L), 3)
    tol_w = round(max(0.004, 0.05 * w), 4)

    frames = [
        {"symbol": "⌭", "characteristic": "Cylindricity (Outer Envelope)", "tolerance": f"{tol_d:.3f} mm", "datums": "—", "feature": "Primary OD"},
        {"symbol": "⌖", "characteristic": "True Position (Struts / Slots)", "tolerance": f"Ø {tol_d * 1.2:.3f} Ⓜ", "datums": "A | B | C", "feature": f"{spec['n_struts']}× Radial Features"},
        {"symbol": "◎", "characteristic": "Concentricity (ID to OD)", "tolerance": f"Ø {tol_d * 0.9:.3f}", "datums": "A", "feature": "Lumen / Shaft Axis"},
        {"symbol": "⌓", "characteristic": "Profile of a Surface", "tolerance": f"{tol_w * 2:.3f} mm", "datums": "A | B", "feature": "Active Working Surface"},
        {"symbol": "⊥", "characteristic": "Perpendicularity (End Face)", "tolerance": f"{tol_l * 0.5:.3f} mm", "datums": "A", "feature": "Proximal Datum Face"},
    ]
    dimensions = [
        {"label": "Nominal OD", "value": f"Ø {D:.2f} ± {tol_d:.3f} mm"},
        {"label": "Overall Length", "value": f"{L:.2f} ± {tol_l:.2f} mm"},
        {"label": "Wall / Strut Thickness", "value": f"{w:.3f} ± {tol_w:.4f} mm"},
        {"label": "Surface Finish", "value": f"Ra {device['surface_ra_um']} μm (Electropolished)"},
        {"label": "Material", "value": device["material"]},
    ]
    return {"frames": frames, "dimensions": dimensions, "datums": ["A (Primary Axis)", "B (Proximal Face)", "C (Crown 0°)"]}


# ----------------------------------------------------------- Disk CAD Exporters

def export_stl(path: Path, V: np.ndarray, F: np.ndarray, solid_name: str) -> int:
    lines = [f"solid {solid_name}"]
    for tri in F:
        p0, p1, p2 = V[tri[0]], V[tri[1]], V[tri[2]]
        n = np.cross(p1 - p0, p2 - p0)
        norm = float(np.linalg.norm(n))
        if norm > 1e-12:
            n = n / norm
        else:
            n = np.array([0.0, 0.0, 1.0])
        lines.append(f"  facet normal {n[0]:.6f} {n[1]:.6f} {n[2]:.6f}")
        lines.append("    outer loop")
        for p in (p0, p1, p2):
            lines.append(f"      vertex {p[0]:.6f} {p[1]:.6f} {p[2]:.6f}")
        lines.append("    endloop")
        lines.append("  endfacet")
    lines.append(f"endsolid {solid_name}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path.stat().st_size


def export_obj(path: Path, V: np.ndarray, F: np.ndarray, obj_name: str) -> int:
    lines = [f"# Vascular & GI Simulation Studio CAD Export: {obj_name}", f"o {obj_name}"]
    for v in V:
        lines.append(f"v {v[0]:.6f} {v[1]:.6f} {v[2]:.6f}")
    for tri in F:
        lines.append(f"f {tri[0] + 1} {tri[1] + 1} {tri[2] + 1}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path.stat().st_size


def export_dxf(path: Path, V: np.ndarray, F: np.ndarray, spec: Dict[str, object]) -> int:
    """Write valid ASCII DXF (R12/R2000 compatible) with 3DFACE entities + 2D GD&T callouts."""
    lines = [
        "0", "SECTION",
        "2", "HEADER",
        "9", "$INSUNITS",
        "70", "4",  # millimeters
        "0", "ENDSEC",
        "0", "SECTION",
        "2", "ENTITIES",
    ]
    # 3DFACE entities for full 3D CAD geometry
    for tri in F:
        p0, p1, p2 = V[tri[0]], V[tri[1]], V[tri[2]]
        lines.extend([
            "0", "3DFACE",
            "8", "MODEL_3D",
            "10", f"{p0[0]:.5f}", "20", f"{p0[1]:.5f}", "30", f"{p0[2]:.5f}",
            "11", f"{p1[0]:.5f}", "21", f"{p1[1]:.5f}", "31", f"{p1[2]:.5f}",
            "12", f"{p2[0]:.5f}", "22", f"{p2[1]:.5f}", "32", f"{p2[2]:.5f}",
            "13", f"{p2[0]:.5f}", "23", f"{p2[1]:.5f}", "33", f"{p2[2]:.5f}",
        ])
    # Add GD&T centerline & overall length annotation text on layer GDT_ANNO
    L = float(spec["length_mm"])
    D = float(spec["diameter_mm"])
    lines.extend([
        "0", "LINE", "8", "GDT_CENTERLINE",
        "10", "0.0", "20", "0.0", "30", f"{-0.6 * L:.4f}",
        "11", "0.0", "21", "0.0", "31", f"{0.6 * L:.4f}",
        "0", "TEXT", "8", "GDT_ANNO",
        "10", f"{D:.4f}", "20", "0.0", "30", "0.0",
        "40", "0.8",
        "1", f"OD {D:.2f}mm | L {L:.2f}mm | t {spec['wall_mm']:.3f}mm | DATUM A-B-C",
    ])
    lines.extend(["0", "ENDSEC", "0", "EOF"])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path.stat().st_size


def generate_and_export_cad(
    device_id: str = "coronary_des",
    target_diameter_mm: float = 3.2,
    target_length_mm: float = 20.0,
    stiffness_factor: float = 0.5,
    priority: str = "balanced",
) -> Dict[str, object]:
    """Run generative AI recommendation, synthesize 3D CAD & GD&T, and write .dxf/.stl/.obj to disk."""
    rec = recommend_design(device_id, target_diameter_mm, target_length_mm, stiffness_factor, priority)
    device = rec["base_device"]
    spec = rec["recommended"]
    V, F = build_3d_mesh(device, spec)
    gdt = build_gdt_spec(device, spec)

    stem = f"{device['id']}_D{spec['diameter_mm']:.1f}_L{spec['length_mm']:.0f}_n{spec['n_struts']}"
    stl_path = EXPORT_DIR / f"{stem}.stl"
    obj_path = EXPORT_DIR / f"{stem}.obj"
    dxf_path = EXPORT_DIR / f"{stem}.dxf"

    stl_bytes = export_stl(stl_path, V, F, stem)
    obj_bytes = export_obj(obj_path, V, F, stem)
    dxf_bytes = export_dxf(dxf_path, V, F, spec)

    # Decimate wireframe edges for fast browser 3D preview if large
    step = max(1, len(F) // 1800)
    preview_faces = F[::step].tolist()

    return {
        "device": device,
        "recommended": spec,
        "alternatives": rec["alternatives"],
        "confidence": rec["confidence"],
        "gdt": gdt,
        "mesh": {
            "n_vertices": int(len(V)),
            "n_triangles": int(len(F)),
            "vertices": np.round(V, 4).tolist(),
            "faces": preview_faces,
        },
        "exports": [
            {"format": "DXF", "filename": dxf_path.name, "path": str(dxf_path), "size_bytes": dxf_bytes, "url": f"/api/cad/download/{dxf_path.name}"},
            {"format": "STL", "filename": stl_path.name, "path": str(stl_path), "size_bytes": stl_bytes, "url": f"/api/cad/download/{stl_path.name}"},
            {"format": "OBJ", "filename": obj_path.name, "path": str(obj_path), "size_bytes": obj_bytes, "url": f"/api/cad/download/{obj_path.name}"},
        ],
    }
