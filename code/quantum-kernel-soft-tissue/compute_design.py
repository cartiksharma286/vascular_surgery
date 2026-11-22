import json
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 8, "axes.linewidth": 0.8})

import compute_fe as fe  # reuses the verified generator (reruns Table 4 cases)

VARIANTS = [
    ("B1 balloon, nominal",        10.0, 6.0, 15.0),
    ("B2 balloon, lower pressure",  8.0, 6.0, 15.0),
    ("B3 balloon, undersized",     10.0, 5.5, 15.0),
    ("S1 stent, oversized",         8.0, 6.5, 24.0),
    ("S2 stent, short",             8.0, 6.5, 15.0),
    ("S3 stent, nominal diameter",  8.0, 6.0, 24.0),
]
rows = []
for label, p_atm, d_dev, dev_len in VARIANTS:
    r = fe.run_case(label, p_atm, d_dev, dev_len)
    rows.append(dict(label=label, p_atm=p_atm, d_dev=d_dev, dev_len=dev_len,
                     min_after=r["min_after"], gain=r["gain"], resid_pct=r["resid_pct"],
                     max_stress=r["max_stress"], n_yielded=len(r["yielded"]),
                     yield_zone_mm=r["yield_zone_mm"], n_contact=r["n_contact"], F_tot=r["F_tot"]))
    print(label, "| after", round(r["min_after"], 2), "| gain", round(r["gain"], 2),
          "| resid%", round(r["resid_pct"], 1), "| stress", round(r["max_stress"], 0),
          "| yielded", len(r["yielded"]), "| contact", r["n_contact"], "| F", round(r["F_tot"], 0))

json.dump(rows, open("design_results.json", "w"), indent=2)

labels = [r["label"].split(" ")[0] for r in rows]
fig, axes = plt.subplots(1, 2, figsize=(7.2, 2.4))
x = np.arange(len(rows))
cols = ["#b45309" if l.startswith("B") else "#0f766e" for l in labels]
axes[0].bar(x, [r["max_stress"] for r in rows], color=cols, width=0.62)
axes[0].axhline(600, color="#b91c1c", ls="--", lw=0.9)
axes[0].text(5.45, 612, "Yield 600 kPa", fontsize=6.5, color="#b91c1c", ha="right")
axes[0].set_xticks(x); axes[0].set_xticklabels(labels)
axes[0].set_ylabel("Max hoop stress (kPa)"); axes[0].set_title("a  Peak stress by design variant")
axes[0].set_ylim(0, 760); axes[0].grid(axis="y", alpha=0.25)
axes[1].bar(x - 0.19, [r["gain"] for r in rows], width=0.38, color="#2563eb", label="Lumen gain (mm, left)")
ax1b = axes[1].twinx()
ax1b.bar(x + 0.19, [r["F_tot"] for r in rows], width=0.38, color="#7c3aed", label="Total device force (N, right)")
axes[1].set_xticks(x); axes[1].set_xticklabels(labels)
axes[1].set_ylabel("Lumen gain (mm)", color="#2563eb"); ax1b.set_ylabel("Total force (N)", color="#7c3aed")
ax1b.tick_params(axis="y", labelcolor="#7c3aed"); axes[1].tick_params(axis="y", labelcolor="#2563eb")
axes[1].set_title("b  Lumen gain and device force")
axes[1].set_ylim(0, 6.4); ax1b.set_ylim(0, 360); axes[1].grid(axis="y", alpha=0.25)
h1, l1 = axes[1].get_legend_handles_labels(); h2, l2 = ax1b.get_legend_handles_labels()
axes[1].legend(h1 + h2, l1 + l2, fontsize=6.3, frameon=False, loc="upper left")
plt.tight_layout(); plt.savefig("fig_fe_design.png", dpi=300); plt.close()
print("design figure done")
