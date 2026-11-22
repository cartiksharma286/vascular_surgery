import math

# Finite element expansion - Thomas solver (Section 10, Table 4, Figure 3)
N, L_SEG = 16, 60.0
LE = L_SEG / N                      # 3.75 mm
ZC, D_NOM, D_MIN, SIG_G = 30.0, 6.0, 1.20, 1.55
H, MU, ALPHA, PHI = 0.60, 204.0, 0.25, 2.5
SIGMA_Y, SOFT = 600.0, 0.216        # kPa; post-yield tangent fraction
Z = [i * LE for i in range(N + 1)]
DREF = [D_NOM - (D_NOM - D_MIN) * math.exp(-((z - ZC) ** 2) / (2 * SIG_G ** 2)) for z in Z]
DE = [(DREF[e] + DREF[e + 1]) / 2 for e in range(N)]
MUE = [MU * (1 + (PHI - 1) * (1 - DE[e] / D_NOM)) for e in range(N)]

def stress(lam, mu):
    return mu * ((1 - ALPHA) + ALPHA * lam ** -2) * (lam ** 2 - lam ** -2)

def tangent(lam, mu):
    A = (1 - ALPHA) + ALPHA * lam ** -2
    return mu * (-2 * ALPHA * lam ** -3 * (lam ** 2 - lam ** -2)
                 + A * (2 * lam + 2 * lam ** -3))

def lam_yield(mu):
    lo, hi = 1.0, 4.0
    for _ in range(80):
        mid = (lo + hi) / 2
        if stress(mid, mu) < SIGMA_Y: lo = mid
        else: hi = mid
    return (lo + hi) / 2

def thomas(a, b, c, d):
    n = len(d); cp = [0.0] * n; dp = [0.0] * n
    cp[0] = c[0] / b[0]; dp[0] = d[0] / b[0]
    for i in range(1, n):
        m = b[i] - a[i] * cp[i - 1]
        cp[i] = c[i] / m if i < n - 1 else 0.0
        dp[i] = (d[i] - a[i] * dp[i - 1]) / m
    x = [0.0] * n; x[-1] = dp[-1]
    for i in range(n - 2, -1, -1):
        x[i] = dp[i] - cp[i] * x[i + 1]
    return x

def expand(p_atm, d_dev, dev_len):
    P = p_atm * 101.325                       # kPa
    loaded = [i for i in range(N + 1) if abs(Z[i] - ZC) <= dev_len / 2]
    cap = {i: max(0.0, (d_dev - DREF[i]) / 2) for i in loaded}
    F = [0.0] * (N + 1)
    for i in loaded: F[i] = P * LE * d_dev    # mN

    def solve(tan):
        ke = [tan[e] * (H / (DE[e] / 2)) * LE for e in range(N)]   # Eq. (17)
        fixed = {0: 0.0, N: 0.0}
        for _ in range(8):                    # active-set contact cap
            a = [0.0] * (N - 1); b = [0.0] * (N - 1); c = [0.0] * (N - 1)
            rhs = F[1:N][:]
            for e in range(N):
                i, j = e, e + 1
                if 1 <= i <= N - 1: b[i - 1] += ke[e]
                if 1 <= j <= N - 1: b[j - 1] += ke[e]
                if 1 <= i <= N - 1 and 1 <= j <= N - 1:
                    c[i - 1] -= ke[e]; a[j - 1] -= ke[e]
                if i in fixed and 1 <= j <= N - 1 and j not in fixed: rhs[j - 1] += ke[e] * fixed[i]
                if j in fixed and 1 <= i <= N - 1 and i not in fixed: rhs[i - 1] += ke[e] * fixed[j]
            for node, val in fixed.items():
                if 1 <= node <= N - 1:
                    k = node - 1; rhs[k] = val; b[k] = 1.0; a[k] = 0.0; c[k] = 0.0
                    if k - 1 >= 0: c[k - 1] = 0.0
                    if k + 1 < N - 1: a[k + 1] = 0.0
            x = thomas(a, b, c, rhs)
            u = [0.0] * (N + 1); u[1:N] = x
            for node, val in fixed.items(): u[node] = val
            u = [max(v, 0.0) for v in u]
            new = [i for i in loaded if i not in fixed and u[i] > cap[i] + 1e-9]
            if not new:
                return u, sorted(i for i in fixed if i in cap)
            for i in new: fixed[i] = cap[i]
        return u, sorted(i for i in fixed if i in cap)

    tan = [tangent(1.0, MUE[e]) for e in range(N)]
    u1, _ = solve(tan)                        # pass 1: elastic
    lam1 = [(DE[e] + u1[e] + u1[e + 1]) / DE[e] for e in range(N)]
    yielded = [e for e in range(N) if stress(lam1[e], MUE[e]) > SIGMA_Y]
    tan = [tangent(max(lam1[e], 1.0), MUE[e]) for e in range(N)]
    for e in yielded: tan[e] = SOFT * tangent(lam_yield(MUE[e]), MUE[e])
    u, contact = solve(tan)                   # pass 2: yielded elements softened
    lam = [(DE[e] + u[e] + u[e + 1]) / DE[e] for e in range(N)]
    sig = [SIGMA_Y + SOFT * tangent(lam_yield(MUE[e]), MUE[e]) * (lam[e] - lam_yield(MUE[e]))
           if e in yielded else stress(lam[e], MUE[e]) for e in range(N)]
    D_after = [DREF[i] + 2 * u[i] for i in range(N + 1)]
    centre = DREF.index(min(DREF))
    spanned = [e for e in range(N) if e in loaded and e + 1 in loaded]
    F_tot = (P / 1000) * math.pi * sum(DE[e] for e in spanned) * LE   # N
    print(f"P={P:.2f} kPa  lumen {min(DREF):.2f} -> {D_after[centre]:.2f} mm  "
          f"max stress {max(sig):.0f} kPa  yielded {len(yielded)}  "
          f"contact {len(contact)}  F={F_tot:.0f} N  passes=2")
    return D_after, sig, u

expand(10.0, 6.0, 15.0)   # balloon:  1013.25 kPa, 1.20 -> 6.00 mm, 629 kPa, 223 N
expand(8.0, 6.5, 24.0)    # stent:     810.60 kPa, 1.20 -> 6.50 mm, 659 kPa, 293 N

# Design variants (Table 5): pressure, diameter and length sweeps
expand(8.0, 6.0, 15.0)    # B2 balloon, lower pressure: 629 kPa, 178 N
expand(10.0, 5.5, 15.0)   # B3 balloon, undersized: 5.50 mm, 607 kPa, 223 N
expand(8.0, 6.5, 15.0)    # S2 stent, short: 659 kPa, 178 N
expand(8.0, 6.0, 24.0)    # S3 stent, nominal diameter: 629 kPa, 293 N
