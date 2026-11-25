"""Elliptic moduli, conformal moduli and conformal grid partitioning.

Facts used (all exact, all unit-tested):

* The rectangle [-K, K] x [0, K'] is mapped conformally onto the upper half-plane by sn(z, k),
  so its width/height ratio is 2K(k)/K'(k). Hence a rectangle a x b has the elliptic modulus
  k with K'(k)/K(k) = 2b/a, computed explicitly from the nome q = exp(-pi K'/K).
* The ring r_i < |z| < r_o maps by w = ln z onto the rectangle [ln r_i, ln r_o] x [0, 2 pi], so its
  conformal modulus is ln(r_o/r_i)/(2 pi), and cells of constant conformal size are squares in w.
* The eccentric ring (inner circle of radius a with centre offset e inside the circle of radius R)
  is conformally equivalent to a concentric ring with ln(rho) = arccosh((R^2 + a^2 - e^2)/(2 R a)).
"""

from __future__ import annotations

import math
from typing import Dict, List, Tuple


def theta_functions(q: float, terms: int = 60) -> Tuple[float, float, float]:
    """Jacobi theta functions theta_2, theta_3, theta_4 at nome 0 < q < 1."""
    if not (0.0 < q < 1.0):
        raise ValueError("nome must lie in (0, 1)")
    th3 = 1.0 + 2.0 * sum(q ** (n * n) for n in range(1, terms))
    th4 = 1.0 + 2.0 * sum((-1) ** n * q ** (n * n) for n in range(1, terms))
    th2 = 2.0 * sum(q ** ((n + 0.5) ** 2) for n in range(0, terms))
    return th2, th3, th4


def agm(a: float, b: float) -> float:
    for _ in range(60):
        a, b = (a + b) / 2.0, math.sqrt(a * b)
        if abs(a - b) < 1e-16 * a:
            break
    return (a + b) / 2.0


def complete_K(k: float) -> float:
    if not (0.0 <= k < 1.0):
        raise ValueError("modulus must lie in [0, 1)")
    return math.pi / (2.0 * agm(1.0, math.sqrt(1.0 - k * k)))


def complete_K_prime(k: float) -> float:
    return complete_K(math.sqrt(1.0 - k * k))


def ratio_from_modulus(k: float) -> float:
    """K'(k)/K(k)."""
    return complete_K_prime(k) / complete_K(k)


def modulus_from_ratio(ratio: float) -> float:
    """Elliptic modulus k with K'(k)/K(k) = ratio (explicit, via the nome q = exp(-pi ratio))."""
    if not ratio > 0.0:
        raise ValueError("ratio must be positive")
    q = math.exp(-math.pi * ratio)
    th2, th3, _ = theta_functions(q)
    return (th2 / th3) ** 2


def rectangle_modulus(width: float, height: float) -> float:
    """Elliptic modulus of the rectangle width x height under the sn-map (2K/K' = width/height)."""
    if not (width > 0 and height > 0):
        raise ValueError("sides must be positive")
    return modulus_from_ratio(2.0 * height / width)


def rectangle_aspect_from_modulus(k: float) -> float:
    """Width/height = 2K/K' of the rectangle whose sn-map has modulus k."""
    return 2.0 * complete_K(k) / complete_K_prime(k)


def annulus_modulus(r_inner: float, r_outer: float) -> float:
    """Conformal modulus ln(r_o/r_i)/(2 pi) of a concentric ring."""
    if not (0 < r_inner < r_outer):
        raise ValueError("need 0 < r_inner < r_outer")
    return math.log(r_outer / r_inner) / (2.0 * math.pi)


def eccentric_ring_log_ratio(R: float, a: float, e: float) -> float:
    """ln(rho) of the concentric ring conformally equivalent to circle(R) minus offset circle(a, e)."""
    if not (0 < a < R) or e < 0 or e + a >= R:
        raise ValueError("electrode circle must lie strictly inside the outer circle")
    return math.acosh((R * R + a * a - e * e) / (2.0 * R * a))


def conformal_partition(r_inner: float, r_outer: float, n_theta: int) -> Dict[str, object]:
    """Radial count and geometric radii giving conformally square cells in (ln r, theta)."""
    if n_theta < 8:
        raise ValueError("n_theta must be at least 8")
    span = math.log(r_outer / r_inner)
    n_r = max(1, round(n_theta * span / (2.0 * math.pi)))
    radii = [r_inner * (r_outer / r_inner) ** (j / n_r) for j in range(n_r + 1)]
    cell_aspect = (span / n_r) / (2.0 * math.pi / n_theta)
    return {"n_r": n_r, "n_theta": n_theta, "radii": radii, "conformal_aspect": cell_aspect,
            "annulus_modulus": annulus_modulus(r_inner, r_outer)}


def uniform_partition(r_inner: float, r_outer: float, n_r: int) -> List[float]:
    return [r_inner + (r_outer - r_inner) * j / n_r for j in range(n_r + 1)]


def struts_from_modulus(k: float, cell_axial_length: float, vessel_radius: float, minimum: int = 6) -> int:
    """Strut count from the cell aspect a/b = 2K/K': circumferential width b = a K'/(2K), n = 2 pi r / b."""
    b = cell_axial_length * complete_K_prime(k) / (2.0 * complete_K(k))
    return max(minimum, int(round(2.0 * math.pi * vessel_radius / b)))


def modulus_table(ratios=(0.25, 0.5, 1.0, 2.0, 4.0)) -> List[Dict[str, float]]:
    rows = []
    for r in ratios:
        k = modulus_from_ratio(r)
        rows.append({"ratio": r, "k": k, "K": complete_K(k), "K_prime": complete_K_prime(k),
                     "check": ratio_from_modulus(k)})
    return rows


def strut_density_from_modulus(k: float, cell_axial_length: float, vessel_radius: float) -> float:
    """Continuous strut count n(k) = 2 pi r / b with circumferential cell width b = a K'(k) / (2 K(k))."""
    b = cell_axial_length * complete_K_prime(k) / (2.0 * complete_K(k))
    return 2.0 * math.pi * vessel_radius / b
