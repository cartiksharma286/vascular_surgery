import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from scipy.special import ellipk
plt.rcParams.update({"font.family":"DejaVu Sans","font.size":9})
fig, axes = plt.subplots(1,2, figsize=(10,3.6), gridspec_kw={"width_ratios":[1.25,1]})
fams=["A\nBalloon","B\nAblation","C\nDiagnostic","D\nGuiding"]
base=[16.80,16.74,17.33,18.11]; mod=[10.03,14.23,11.75,13.05]; qk=[10.01,14.15,11.65,13.06]
x=np.arange(4); w=0.26
axes[0].bar(x-w,base,w,label="Trailing mean",color="#6b7280")
axes[0].bar(x,mod,w,label="Elliptic-modular",color="#0f766e")
axes[0].bar(x+w,qk,w,label="Quantum-kernel emulation",color="#b45309")
axes[0].set_xticks(x); axes[0].set_xticklabels(fams, fontsize=8)
axes[0].set_ylabel("Test MAPE (%)"); axes[0].set_title("a  Forecast error by catheter family (synthetic)"); axes[0].legend(frameon=False,fontsize=7.5); axes[0].set_ylim(0,21); axes[0].spines[["top","right"]].set_visible(False)
k=np.linspace(0,0.99,200)
axes[1].plot(k, ellipk(k*k), color="#0f766e", lw=2)
axes[1].axhline(np.pi/2, color="#6b7280", ls="--", lw=1)
axes[1].plot([0.7],[ellipk(0.49)],"o",color="#b45309")
axes[1].annotate("k = 0.70, K = 1.846", xy=(0.7,1.846), xytext=(0.35,2.6), arrowprops=dict(arrowstyle="->",color="#374151"), fontsize=8)
axes[1].set_xlabel("Elliptic modulus k"); axes[1].set_ylabel("K(k)"); axes[1].set_title("b  Complete elliptic integral of the first kind"); axes[1].spines[["top","right"]].set_visible(False)
fig.tight_layout()
fig.savefig("chart.png", dpi=300, bbox_inches="tight")
print("saved")
