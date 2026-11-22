import json, math
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 8, "axes.linewidth": 0.8})

# ---- Shared FE setup (synthetic; healthy-carotid material from Table 1) ----
N = 16                      # ring elements
L_SEG = 60.0                # mm
LE = L_SEG / N              # 3.75 mm
Z = np.array([i * LE for i in range(N + 1)])
ZC = 30.0                   # lesion centre (mm)
D_NOM = 6.0                 # mm, nominal vessel diameter
D_MIN = 1.20                # mm, minimum (stenotic) lumen
SIG_G = 1.55                # mm, Gaussian lesion width
H_WALL = 0.60               # mm
MU = 204.0                  # kPa (healthy carotid preset)
ALPHA = 0.25
PHI = 2.5                   # plaque stiffening factor at full stenosis
SIGMA_Y = 600.0             # kPa, plaque yield stress
SOFT = 0.216                # post-yield tangent fraction

def d_ref(z):
    return D_NOM - (D_NOM - D_MIN) * math.exp(-((z - ZC) ** 2) / (2 * SIG_G ** 2))

DREF_N = np.array([d_ref(z) for z in Z])
DREF_E = np.array([(DREF_N[e] + DREF_N[e + 1]) / 2 for e in range(N)])
MU_E = np.array([MU * (1 + (PHI - 1) * (1 - DREF_E[e] / D_NOM)) for e in range(N)])

def mr_stress(lam, mu):
    return mu * ((1 - ALPHA) + ALPHA * lam ** -2) * (lam ** 2 - lam ** -2)

def mr_tangent(lam, mu):
    A = (1 - ALPHA) + ALPHA * lam ** -2
    dA = -2 * ALPHA * lam ** -3
    B = lam ** 2 - lam ** -2
    dB = 2 * lam + 2 * lam ** -3
    return mu * (dA * B + A * dB)

def lam_yield(mu):
    lo, hi = 1.0, 4.0
    for _ in range(80):
        mid = (lo + hi) / 2
        if mr_stress(mid, mu) < SIGMA_Y: lo = mid
        else: hi = mid
    return (lo + hi) / 2

def thomas(a, b, c, d):
    n = len(d)
    cp = np.zeros(n); dp = np.zeros(n)
    cp[0] = c[0] / b[0]; dp[0] = d[0] / b[0]
    for i in range(1, n):
        m = b[i] - a[i] * cp[i - 1]
        cp[i] = c[i] / m if i < n - 1 else 0.0
        dp[i] = (d[i] - a[i] * dp[i - 1]) / m
    x = np.zeros(n); x[-1] = dp[-1]
    for i in range(n - 2, -1, -1):
        x[i] = dp[i] - cp[i] * x[i + 1]
    return x

def run_case(name, p_atm, d_dev, dev_len):
    P_kPa = p_atm * 101.325
    P = P_kPa / 1000.0  # N/mm^2
    loaded_nodes = [i for i in range(N + 1) if abs(Z[i] - ZC) <= dev_len / 2 + 1e-9]
    cap = {i: max(0.0, (d_dev - DREF_N[i]) / 2) for i in loaded_nodes}
    F = np.zeros(N + 1)
    for i in loaded_nodes:
        F[i] = P_kPa * LE * d_dev  # mN (kPa = mN/mm^2; tributary area LE x D_dev)

    def solve_pass(tangents):
        # Assemble K (free nodes 1..N-1) with element stiffness Eq. (17):
        # k_e = (dsigma/dlambda)_e * (h/r)_e * L_e  [mN/mm]
        n = N - 1
        a0 = np.zeros(n); b0 = np.zeros(n); c0 = np.zeros(n)
        for e in range(N):
            ke = tangents[e] * (H_WALL / (DREF_E[e] / 2)) * LE
            i, j = e, e + 1
            if 1 <= i <= N - 1: b0[i - 1] += ke
            if 1 <= j <= N - 1: b0[j - 1] += ke
            if 1 <= i <= N - 1 and 1 <= j <= N - 1:
                c0[i - 1] -= ke; a0[j - 1] -= ke
        fixed = {0: 0.0, N: 0.0}   # segment ends fixed
        contact = []
        for _ in range(8):  # active-set iterations for the contact cap
            a = a0.copy(); b = b0.copy(); c = c0.copy(); rhs = F[1:N].copy()
            for node, val in fixed.items():
                if 1 <= node <= N - 1:
                    k = node - 1
                    rhs[k] = val; b[k] = 1.0; a[k] = 0.0; c[k] = 0.0
                    if k - 1 >= 0: rhs[k - 1] -= a0[k - 1] * 0.0  # neighbour coupling handled below
            # Dirichlet neighbours: subtract coupling * fixed value from adjacent rhs
            rhs = F[1:N].copy()
            for node, val in fixed.items():
                if 1 <= node <= N - 1:
                    rhs[node - 1] = val
                # element coupling from a fixed node enters neighbour equations
            # rebuild rhs properly: rhs_i = F_i - sum over fixed neighbours K_ij * val_j
            rhs = F[1:N].copy()
            for e in range(N):
                ke = tangents[e] * (H_WALL / (DREF_E[e] / 2)) * LE
                i, j = e, e + 1
                if i in fixed and 1 <= j <= N - 1 and j not in fixed:
                    rhs[j - 1] += ke * fixed[i]
                if j in fixed and 1 <= i <= N - 1 and i not in fixed:
                    rhs[i - 1] += ke * fixed[j]
            for node, val in fixed.items():
                if 1 <= node <= N - 1:
                    k = node - 1; rhs[k] = val; b[k] = 1.0; a[k] = 0.0; c[k] = 0.0
                    if k - 1 >= 0: c[k - 1] = 0.0
                    if k + 1 < n: a[k + 1] = 0.0
            x = thomas(a, b, c, rhs)
            u = np.zeros(N + 1); u[1:N] = x
            for node, val in fixed.items(): u[node] = val
            u = np.maximum(u, 0.0)
            new = [i for i in loaded_nodes if i not in fixed and u[i] > cap[i] + 1e-9]
            if not new:
                contact = sorted(i for i in fixed if i in cap)
                return u, contact
            for i in new:
                fixed[i] = cap[i]
        contact = sorted(i for i in fixed if i in cap)
        return u, contact

    # Pass 1: elastic tangents at reference stretch
    tan1 = np.array([mr_tangent(1.0, MU_E[e]) for e in range(N)])
    u1, _ = solve_pass(tan1)
    lam1 = np.array([(DREF_E[e] + (u1[e] + u1[e + 1])) / DREF_E[e] for e in range(N)])
    sig_el1 = np.array([mr_stress(lam1[e], MU_E[e]) for e in range(N)])
    yielded = [e for e in range(N) if sig_el1[e] > SIGMA_Y]

    # Pass 2: yielded elements softened; others tangent at pass-1 stretch
    tan2 = np.array([mr_tangent(max(lam1[e], 1.0), MU_E[e]) for e in range(N)])
    for e in yielded:
        tan2[e] = SOFT * mr_tangent(lam_yield(MU_E[e]), MU_E[e])
    u, contact = solve_pass(tan2)
    lam = np.array([(DREF_E[e] + (u[e] + u[e + 1])) / DREF_E[e] for e in range(N)])
    sigma = np.zeros(N)
    for e in range(N):
        if e in yielded:
            ly = lam_yield(MU_E[e])
            sigma[e] = SIGMA_Y + SOFT * mr_tangent(ly, MU_E[e]) * (lam[e] - ly)
        else:
            sigma[e] = mr_stress(lam[e], MU_E[e])
    D_after = DREF_N + 2 * u
    loaded_el = [e for e in range(N) if e in loaded_nodes and (e + 1) in loaded_nodes]
    F_tot = P * math.pi * sum(DREF_E[e] for e in loaded_el) * LE  # N
    return dict(name=name, p_atm=p_atm, P_kPa=P_kPa, d_dev=d_dev, dev_len=dev_len,
                loaded_nodes=loaded_nodes, loaded_elements=loaded_el,
                min_before=float(DREF_N.min()), min_after=float(D_after[int(DREF_N.argmin())]),
                gain=float(D_after[int(DREF_N.argmin())] - DREF_N.min()),
                resid_pct=float(max(0.0, (1 - D_after[int(DREF_N.argmin())] / D_NOM)) * 100),
                max_stress=float(sigma.max()), max_stress_e=int(sigma.argmax()),
                yielded=yielded, yield_zone_mm=float(len(yielded) * LE),
                contact=contact, n_contact=len(contact), F_tot=float(F_tot),
                passes=2, u=u.tolist(), D_after=D_after.tolist(),
                lam=lam.tolist(), sigma=sigma.tolist(),
                lam1=lam1.tolist(), sig_el1=sig_el1.tolist())

balloon = run_case("Balloon angioplasty", 10.0, 6.0, 15.0)
stent = run_case("Stent (self-expanding, oversized)", 8.0, 6.5, 24.0)
for r in (balloon, stent):
    print(r["name"], "| P kPa", round(r["P_kPa"], 2), "| min", round(r["min_before"], 2), "->", round(r["min_after"], 2),
          "| gain", round(r["gain"], 2), "| resid%", round(r["resid_pct"], 2),
          "| maxsig", round(r["max_stress"], 1), "elem", r["max_stress_e"],
          "| yielded", r["yielded"], "zone", r["yield_zone_mm"],
          "| contact", r["n_contact"], r["contact"], "| Ftot", round(r["F_tot"], 1), "| passes", r["passes"])
    print("  D_after", [round(x, 2) for x in r["D_after"]])
    print("  sigma  ", [round(x, 0) for x in r["sigma"]])
    print("  u      ", [round(x, 3) for x in r["u"]])

json.dump(dict(setup=dict(N=N, LE=LE, D_nom=D_NOM, D_min=D_MIN, sig_g=SIG_G, H=H_WALL,
                          mu=MU, alpha=ALPHA, phi=PHI, sigma_y=SIGMA_Y, soft=SOFT,
                          Dref_nodes=DREF_N.tolist(), Dref_elems=DREF_E.tolist(), mu_elems=MU_E.tolist()),
               balloon=balloon, stent=stent),
          open("fe_results.json", "w"), indent=2)

# ---- Figure 3 ----
fig, axes = plt.subplots(1, 2, figsize=(7.2, 2.9))
axes[0].plot(Z, DREF_N, "o-", ms=3, lw=1.4, color="#475569", label="Lumen before (reference)")
axes[0].plot(Z, balloon["D_after"], "o-", ms=3, lw=1.6, color="#b45309", label="After balloon (6.0 mm, 10 atm)")
axes[0].plot(Z, stent["D_after"], "s-", ms=3, lw=1.4, color="#0f766e", label="After stent (6.5 mm, 8 atm)")
axes[0].axhline(6.0, color="#b45309", ls="--", lw=0.8)
axes[0].text(1, 6.14, "Balloon cap 6.0 mm", fontsize=6.5, color="#b45309")
axes[0].axhline(6.5, color="#0f766e", ls=":", lw=0.8)
axes[0].text(1, 6.64, "Stent cap 6.5 mm", fontsize=6.5, color="#0f766e")
axes[0].set_xlabel("Axial position z (mm)"); axes[0].set_ylabel("Lumen diameter (mm)")
axes[0].set_title("a  Lumen before and after expansion"); axes[0].legend(fontsize=6.3, frameon=False); axes[0].grid(alpha=0.25)
axes[0].set_ylim(0, 7.4)
zc_e = np.array([(Z[e] + Z[e + 1]) / 2 for e in range(N)])
ax2 = axes[1]
ax2.plot(zc_e, balloon["sigma"], "o-", ms=3, lw=1.6, color="#7c3aed", label="Hoop stress, balloon (left)")
ax2.axhline(SIGMA_Y, color="#b91c1c", ls="--", lw=0.9)
ax2.text(31, SIGMA_Y + 30, "Yield stress 600 kPa", fontsize=6.5, color="#b91c1c")
ax2.set_xlabel("Axial position z (mm)"); ax2.set_ylabel("Hoop stress (kPa)")
ax2.set_title("b  Hoop stress and displacement (balloon)")
ax2b = ax2.twinx()
ax2b.plot(Z, balloon["u"], "s-", ms=3, lw=1.3, color="#2563eb", label="Radial displacement (right)")
ax2b.set_ylabel("Displacement u (mm)", color="#2563eb"); ax2b.tick_params(axis="y", labelcolor="#2563eb")
h1, l1 = ax2.get_legend_handles_labels(); h2, l2 = ax2b.get_legend_handles_labels()
ax2.legend(h1 + h2, l1 + l2, fontsize=6.3, frameon=False, loc="upper left")
ax2.grid(alpha=0.25)
plt.tight_layout(); plt.savefig("fig_fe.png", dpi=300); plt.close()
print("figure done")
