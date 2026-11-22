import json, math, numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
plt.rcParams.update({"font.family":"DejaVu Sans","font.size":8,"axes.linewidth":0.8})
MMHG=0.133322 # kPa per mmHg
def mr_stress(lam,mu,alpha):
    return mu*((1-alpha)+alpha*lam**-2)*(lam**2-lam**-2)
def pressure_kpa(lam,mu,alpha,H_R):
    return H_R * lam**-2 * mr_stress(lam,mu,alpha)
def lam_at_pressure(PmmHg,mu,alpha,H_R):
    target=PmmHg*MMHG
    lo,hi=1.0,3.0
    # pressure monotonic increasing to asymptote mu*H_R*(1-alpha) approx; check
    if pressure_kpa(hi,mu,alpha,H_R) < target: return float("nan")
    for _ in range(80):
        mid=(lo+hi)/2
        if pressure_kpa(mid,mu,alpha,H_R) < target: lo=mid
        else: hi=mid
    return (lo+hi)/2

presets={
 "Healthy carotid": dict(D0=6.0,H=0.60,mu=204.0,alpha=0.25),
 "AAA wall": dict(D0=42.0,H=1.80,mu=420.0,alpha=0.30),
 "Stiff / calcified": dict(D0=5.5,H=0.80,mu=650.0,alpha=0.20),
 "Vein graft": dict(D0=4.0,H=0.40,mu=180.0,alpha=0.25),
 "Synthetic graft": dict(D0=6.0,H=0.50,mu=900.0,alpha=0.10),
}
rows=[]
for name,p in presets.items():
    H_R=p["H"]/(p["D0"]/2)
    ld=lam_at_pressure(80,p["mu"],p["alpha"],H_R); ls=lam_at_pressure(120,p["mu"],p["alpha"],H_R)
    Dd=p["D0"]*ld; Ds=p["D0"]*ls
    dP=40.0
    strain=(Ds-Dd)/Dd
    compliance=(Ds-Dd)/dP
    distens=(Ds-Dd)/(Dd*dP)*1000  # per 1000 mmHg? keep fractional per mmHg below
    Ep=dP/strain if strain else float("nan")  # mmHg
    beta=math.log(120/80)/strain if strain else float("nan")
    Ps_kPa=120*MMHG; rs=Ds/2; hs=p["H"]/ls
    sigma=Ps_kPa*rs/hs  # kPa Laplace
    tension=Ps_kPa*rs  # N/mm? kPa*mm = mN/mm -> report N/m: kPa*mm = N/m
    # strain energy at systolic (MR): I1, I2
    lam=ls; I1=lam**2+1+lam**-2; I2=lam**-2+1+lam**2  # for lambda_z=1, I2 = lam^2+1+lam^-2 same? actually I2 = lam^2*1 + ... compute: principal: l1=lam,l2=1,l3=1/lam; I2=l1^2 l2^2 + l2^2 l3^2 + l3^2 l1^2 = lam^2 + lam^-2 +1 = I1. So W:
    C10=p["mu"]*(1-p["alpha"])/2; C01=p["mu"]*p["alpha"]/2
    W=C10*(I1-3)+C01*(I2-3)
    rows.append(dict(name=name,**p,H_R=H_R,lam_d=ld,lam_s=ls,Dd=Dd,Ds=Ds,strain_pct=strain*100,
        compliance=compliance,distens_per_mmHg=strain/dP,Ep_mmHg=Ep,beta=beta,sigma_s_kPa=sigma,tension_N_per_m=tension,W_s=W,
        stress_s=mr_stress(ls,p["mu"],p["alpha"])))
    print(rows[-1])

# Quantum kernel
def qk(f,g):
    d=(np.pi/2)*(np.array(f)-np.array(g))
    return float(np.prod(np.cos(d/2)**2))
def rbf(f,g,gamma=2.0):
    d=np.array(f)-np.array(g); return float(np.exp(-gamma*np.sum(d*d)))
pL=[0.15,0.30,0.20,0.0,0.0,0.20]; pH=[0.85,0.75,0.80,1.0,1.0,0.80]
cases={
 "A - low burden": [0.20,0.35,0.25,0,0,0.20],
 "B - moderate": [0.45,0.55,0.40,0,1,0.40],
 "C - high burden": [0.80,0.70,0.75,1,1,0.60],
 "D - older, diabetic": [0.65,0.85,0.55,1,0,0.80],
 "E - focal severe": [0.90,0.45,0.30,0,0,0.20],
 "F - diffuse severe": [0.85,0.80,0.85,1,1,1.00],
}
krows=[]
for n,f in cases.items():
    kl, kh = qk(f,pL), qk(f,pH)
    krows.append(dict(name=n,features=f,k_low=kl,k_high=kh,score=kh-kl,
        rbf_low=rbf(f,pL),rbf_high=rbf(f,pH),label="higher" if kh>kl else "lower"))
    print(krows[-1])

# Gram matrix check PSD
F=np.array(list(cases.values())); G=np.array([[qk(a,b) for b in F] for a in F])
eig=np.linalg.eigvalsh(G); print("Gram eigenvalues", eig)

json.dump(dict(tissues=rows,kernel=krows,gram_eig_min=float(eig.min()),gram_eig=list(map(float,eig))), open("results.json","w"), indent=2)

# Figures
colors={"Healthy carotid":"#0f766e","AAA wall":"#b45309","Stiff / calcified":"#7c3aed","Vein graft":"#2563eb","Synthetic graft":"#475569"}
fig,axes=plt.subplots(1,2,figsize=(7.2,2.9))
lam=np.linspace(1.01,1.45,200)
for n,p in presets.items():
    axes[0].plot(lam,[mr_stress(x,p["mu"],p["alpha"])/1000 for x in lam],label=n,color=colors[n],lw=1.6)
axes[0].set_xlabel("Circumferential stretch  lambda"); axes[0].set_ylabel("Hoop stress (MPa)"); axes[0].set_title("a  Stress - stretch (Mooney-Rivlin)"); axes[0].legend(fontsize=6.5,frameon=False); axes[0].grid(alpha=0.25)
P=np.linspace(20,160,200)
for n,p in presets.items():
    H_R=p["H"]/(p["D0"]/2)
    vals=[]
    for pp in P:
        vals.append(lam_at_pressure(pp,p["mu"],p["alpha"],H_R))
    axes[1].plot(P,vals,label=n,color=colors[n],lw=1.6)
axes[1].axvline(80,color="grey",ls="--",lw=0.8); axes[1].axvline(120,color="grey",ls="--",lw=0.8)
axes[1].text(81,1.02,"D 80",fontsize=6.5); axes[1].text(121,1.02,"S 120",fontsize=6.5)
axes[1].set_xlabel("Pressure (mmHg)"); axes[1].set_ylabel("Stretch  lambda = D / D0"); axes[1].set_title("b  Pressure - stretch (Laplace inflation)"); axes[1].grid(alpha=0.25)
plt.tight_layout(); plt.savefig("fig_mechanics.png",dpi=300); plt.close()

fig,axes=plt.subplots(1,2,figsize=(7.2,2.9),gridspec_kw={"width_ratios":[1.25,1]})
names=[r["name"] for r in krows]; x=np.arange(len(names))
axes[0].bar(x-0.2,[r["k_low"] for r in krows],width=0.4,label="k to lower-risk prototype",color="#0f766e")
axes[0].bar(x+0.2,[r["k_high"] for r in krows],width=0.4,label="k to higher-risk prototype",color="#b45309")
axes[0].set_xticks(x); axes[0].set_xticklabels([n.split(" - ")[0] for n in names]); axes[0].set_ylabel("Quantum kernel  k(x, p)"); axes[0].set_title("a  Kernel similarity to prototypes"); axes[0].legend(fontsize=6.5,frameon=False); axes[0].grid(axis="y",alpha=0.25); axes[0].set_ylim(0,1.05)
# heartbeat
t=np.linspace(0,1,200); beat=0.5-0.5*np.cos(2*np.pi*t); beat=np.clip(beat,0,1)**1.2
Pbeat=80+40*beat
for n in ["Healthy carotid","AAA wall"]:
    p=presets[n]; H_R=p["H"]/(p["D0"]/2)
    D=[p["D0"]*lam_at_pressure(pp,p["mu"],p["alpha"],H_R) for pp in Pbeat]
    axes[1].plot(t,np.array(D)/p["D0"],label=n,color=colors[n],lw=1.6)
axes[1].set_xlabel("Cardiac cycle (normalised)"); axes[1].set_ylabel("D / D0"); axes[1].set_title("b  Synthetic single heartbeat"); axes[1].legend(fontsize=6.5,frameon=False); axes[1].grid(alpha=0.25)
plt.tight_layout(); plt.savefig("fig_kernel_beat.png",dpi=300); plt.close()
print("done")
