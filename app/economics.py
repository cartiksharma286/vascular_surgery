"""Health-economics scenario model + statistical ML cross-check (Section 11).
Synthetic assumptions only. Pure numpy. Seed fixed; every number in Tables 6-8
and Figure 5 is printed by this script."""
import json
import numpy as np

rng = np.random.default_rng(20261122)

# ---------- 11.1 Accounting (bottom-up) driver model ----------
LIC = 40_000.0          # annual site licence, USD per site
ROY = 300.0             # royalty per FE-designed-device case, USD
scen = {
    "Conservative": dict(sites=[70, 140, 230], cpm=[15, 18, 21],
                         fee=[660, 700, 750], share=[0.20, 0.30, 0.40]),
    "Scale (central)": dict(sites=[90, 210, 340], cpm=[16, 20, 24],
                            fee=[680, 740, 800], share=[0.25, 0.40, 0.55]),
    "Upside": dict(sites=[110, 280, 460], cpm=[17, 22, 27],
                   fee=[700, 770, 840], share=[0.30, 0.50, 0.65]),
}
VAR = [210, 230, 250]            # variable cost per case, USD, years 1-3
FIXED = [9e6, 16e6, 24e6]        # fixed operating cost, USD

def account(d):
    rows = []
    for y in range(3):
        cases = d["sites"][y] * d["cpm"][y] * 12
        r_case = cases * d["fee"][y]
        r_lic = d["sites"][y] * LIC
        r_roy = cases * d["share"][y] * ROY
        rev = r_case + r_lic + r_roy
        cost = cases * VAR[y] + FIXED[y]
        rows.append(dict(year=y + 1, sites=d["sites"][y], cases=cases,
                         r_case=r_case, r_lic=r_lic, r_roy=r_roy, rev=rev,
                         cost=cost, contrib=rev - cost,
                         margin=(rev - cost) / rev))
    return rows

acct = {k: account(v) for k, v in scen.items()}

# ---------- 11.2 Synthetic site-month panel + ML ----------
NS, NM = 160, 24                       # sites x months = 3,840 rows
lam = rng.gamma(shape=6.0, scale=3.2, size=NS)          # cases / month intensity
tier = rng.integers(0, 3, NS)
fee_site = np.array([660., 750., 840.])[tier]
lic_site = np.array([30_000., 40_000., 50_000.])[tier] / 12.0
share0 = rng.uniform(0.08, 0.30, NS)
site_fx = rng.normal(0, 300, NS)
rows = []
for i in range(NS):
    for m in range(NM):
        cases = rng.poisson(lam[i] * (1 + 0.08 * np.sin(2 * np.pi * m / 12)))
        share = min(0.65, share0[i] + 0.012 * m)
        rev = lic_site[i] + cases * fee_site[i] + cases * share * ROY \
            + site_fx[i] + rng.normal(0, 250)
        rows.append((cases, fee_site[i], share, lic_site[i], rev, m))
P = np.array(rows, float)
cases, fee, share, licm, rev, month = P.T
Xr = np.column_stack([cases, fee, share, cases * fee, cases * share, licm])
Xg = np.column_stack([cases, fee, share, licm])
tr, te = month < 18, month >= 18

def ridge_fit(X, y, lam_):
    mu, sd = X.mean(0), X.std(0) + 1e-12
    Z = (X - mu) / sd
    A = Z.T @ Z + lam_ * np.eye(X.shape[1])
    w = np.linalg.solve(A, Z.T @ (y - y.mean()))
    return (mu, sd, w, y.mean())

def ridge_pred(model, X):
    mu, sd, w, ym = model
    return ym + ((X - mu) / sd) @ w

# 5-fold CV over lambda on training rows (blocked by row order is fine here)
lams = [0.01, 0.1, 1, 10, 100, 1000]
idx = np.where(tr)[0]; rng.shuffle(idx); folds = np.array_split(idx, 5)
best = min(lams, key=lambda L: np.mean([
    np.mean((ridge_pred(ridge_fit(Xr[np.setdiff1d(idx, f)], rev[np.setdiff1d(idx, f)], L),
                        Xr[f]) - rev[f]) ** 2) for f in folds]))
model = ridge_fit(Xr[tr], rev[tr], best)
pred_r = ridge_pred(model, Xr[te])

# Gradient boosting with depth-2 trees, implemented directly
def fit_tree(X, r, depth, min_leaf=60):
    def best_split(Xs, rs, feats):
        b = (np.inf, None, None)
        for j in feats:
            qs = np.quantile(Xs[:, j], np.linspace(.1, .9, 9))
            for q in qs:
                L = Xs[:, j] <= q
                if L.sum() < min_leaf or (~L).sum() < min_leaf: continue
                sse = ((rs[L] - rs[L].mean()) ** 2).sum() + ((rs[~L] - rs[~L].mean()) ** 2).sum()
                if sse < b[0]: b = (sse, j, q)
        return b
    def build(Xs, rs, d):
        node = {"val": rs.mean()}
        if d == 0 or len(rs) < 2 * min_leaf: return node
        sse, j, q = best_split(Xs, rs, range(Xs.shape[1]))
        if j is None: return node
        L = Xs[:, j] <= q
        node.update(j=j, q=q, left=build(Xs[L], rs[L], d - 1),
                    right=build(Xs[~L], rs[~L], d - 1))
        return node
    return build(X, r, depth)

def tree_pred(node, X):
    if "j" not in node: return np.full(len(X), node["val"])
    L = X[:, node["j"]] <= node["q"]
    out = np.empty(len(X)); out[L] = tree_pred(node["left"], X[L])
    out[~L] = tree_pred(node["right"], X[~L]); return out

base = rev[tr].mean(); pred_tr = np.full(tr.sum(), base); trees = []
for _ in range(200):
    t = fit_tree(Xg[tr], rev[tr] - pred_tr, depth=2)
    trees.append(t); pred_tr += 0.1 * tree_pred(t, Xg[tr])
pred_g = np.full(te.sum(), base)
for t in trees: pred_g += 0.1 * tree_pred(t, Xg[te])

def metrics(y, p):
    ss = 1 - ((y - p) ** 2).sum() / ((y - y.mean()) ** 2).sum()
    return float(ss), float(np.sqrt(np.mean((y - p) ** 2)))
r2_r, rmse_r = metrics(rev[te], pred_r)
r2_g, rmse_g = metrics(rev[te], pred_g)
mu_, sd_, w_, ym_ = model
coef_raw = w_ / sd_          # back-transformed ridge coefficients

# ---------- 11.3 Apply ridge to planned drivers (scale scenario) ----------
d = scen["Scale (central)"]
ml_rows = []
for y in range(3):
    x = np.array([[d["cpm"][y], d["fee"][y], d["share"][y],
                   d["cpm"][y] * d["fee"][y], d["cpm"][y] * d["share"][y],
                   LIC / 12.0]])
    monthly = float(ridge_pred(model, x)[0])
    ml_rows.append(dict(year=y + 1, monthly_per_site=monthly,
                        annual=monthly * d["sites"][y] * 12))
# bootstrap coefficient uncertainty for Year-3 ML revenue
boots = []
ti = np.where(tr)[0]
for _ in range(200):
    bi = rng.choice(ti, len(ti), replace=True)
    bm = ridge_fit(Xr[bi], rev[bi], best)
    x3 = np.array([[d["cpm"][2], d["fee"][2], d["share"][2],
                    d["cpm"][2] * d["fee"][2], d["cpm"][2] * d["share"][2],
                    LIC / 12.0]])
    boots.append(float(ridge_pred(bm, x3)[0]) * d["sites"][2] * 12)
pi = np.percentile(boots, [10, 90])

out = dict(acct={k: v for k, v in acct.items()},
           ml=dict(n=int(len(P)), n_train=int(tr.sum()), n_test=int(te.sum()),
                   lam=float(best), r2_ridge=r2_r, rmse_ridge=rmse_r,
                   r2_gbm=r2_g, rmse_gbm=rmse_g,
                   coef_cases_fee=float(coef_raw[3]),
                   coef_cases_share=float(coef_raw[4]),
                   coef_lic=float(coef_raw[5]),
                   forecast=ml_rows, pi_y3=[float(pi[0]), float(pi[1])]))
print(json.dumps(out, indent=1))
json.dump(out, open("econ_results.json", "w"), indent=1)

# ---------- Figure 5 ----------
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
cen = acct["Scale (central)"]
yrs = [1, 2, 3]
fig, ax = plt.subplots(figsize=(7.4, 3.4))
ax.bar(yrs, [r["r_case"] / 1e6 for r in cen], .55, label="Per-case software fees", color="#7a1f1f")
ax.bar(yrs, [r["r_lic"] / 1e6 for r in cen], .55,
       bottom=[r["r_case"] / 1e6 for r in cen], label="Annual site licences", color="#c98a3a")
ax.bar(yrs, [r["r_roy"] / 1e6 for r in cen], .55,
       bottom=[(r["r_case"] + r["r_lic"]) / 1e6 for r in cen],
       label="FE-design royalties", color="#3a6ea5")
ax.axhline(100, color="k", ls="--", lw=1)
ax.text(2.45, 103.5, "USD 100M", fontsize=8, ha="center")
ax.plot(yrs, [r["annual"] / 1e6 for r in ml_rows], "ko", ms=6,
        label="Ridge ML prediction")
for r in cen:
    ax.text(r["year"], r["rev"] / 1e6 + 3, f'{r["rev"]/1e6:.1f}M', ha="center", fontsize=9)
ax.set_xticks(yrs); ax.set_xticklabels(["Year 1", "Year 2", "Year 3"])
ax.set_ylabel("Revenue (USD millions)"); ax.set_ylim(0, 125)
ax.legend(fontsize=7.5, loc="upper left"); ax.grid(axis="y", alpha=.3)
fig.tight_layout(); fig.savefig("fig_econ.png", dpi=300)
print("saved fig_econ.png")
