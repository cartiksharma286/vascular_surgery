"""Part II model: Sunnybrook Odette 10-year scenario (2027-2036).
Deterministic, real 2026 CAD. All effect sizes are HYPOTHETICAL planning
assumptions for the Section 4 trial, not observed results.
Anchors: 12,000 new patients/yr and 300,000 visits/yr (Sunnybrook /
Odette public pages); Ontario incidence +25.4% 2020-2030 (Ontario
Cancer Statistics 2020, Ch. 3) -> g = 1.254^(1/10)-1 = 2.29%/yr;
discount rate 1.5% (Canada's Drug Agency pharmacoeconomic guidance).
"""
import json
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

N0, VIS0 = 12000, 300000
g = 1.254 ** 0.1 - 1
R_DISC = 0.015
ADOPT = [0.10, 0.25, 0.45, 0.65, 0.80, 0.90, 0.90, 0.92, 0.95, 0.95]
ELIG, PI_POS = 0.35, 0.40
TEST_COST, STAFF_VAR, TEST_FUND = 850, 310, 950
FIXED = 2_400_000
TRIAL_REV, TRIAL_COST, ENROL_RATE = 18000, 13500, 0.12
GRANT0 = 600_000

def surv(median_m, t_m):
    return 0.5 ** (t_m / median_m)

def dqaly(pfs_w, os_w, u_pf=0.80, u_pd=0.60):
    def q(pw, ow):
        tot = 0.0
        for m in range(60):
            d = 1 / ((1 + R_DISC) ** (m / 12))
            pfs = sum(w * surv(md, m) for w, md in pw)
            os_ = sum(w * surv(md, m) for w, md in ow)
            tot += (u_pf * pfs + u_pd * max(os_ - pfs, 0)) * d / 12
        return tot
    return q(pfs_w, os_w) - q([(1, 9)], [(1, 20)])

DQ = {"conservative": dqaly([(0.4, 11), (0.6, 8)], [(0.4, 24), (0.6, 19)]),
      "base": dqaly([(0.4, 14), (0.6, 8)], [(0.4, 30), (0.6, 19)]),
      "optimistic": dqaly([(0.4, 17), (0.6, 8)], [(0.4, 36), (0.6, 19)])}

def annual():
    rows, cum_h, cum_s, cum_hd = [], 0.0, 0.0, 0.0
    for t in range(10):
        new = round(N0 * (1 + g) ** (t + 1))
        tested = round(new * ELIG * ADOPT[t])
        enrol = round(tested * ENROL_RATE)
        funding = tested * TEST_FUND + enrol * TRIAL_REV + GRANT0 * 1.03 ** t
        hcost = tested * (TEST_COST + STAFF_VAR) + enrol * TRIAL_COST + FIXED
        per = (TEST_COST + STAFF_VAR + PI_POS * 6000) - (0.6 * 0.50 * (22000 + 2800))
        sysc = per * tested + FIXED
        cum_h += funding - hcost
        d = 1 / ((1 + R_DISC) ** (t + 1))
        cum_s += sysc * d
        cum_hd += (funding - hcost) * d
        rows.append(dict(year=2027 + t, new=new,
                         visits=round(VIS0 * (1 + g) ** (t + 1)),
                         tested=tested, enrol=enrol,
                         funding_M=round(funding / 1e6, 2),
                         hcost_M=round(hcost / 1e6, 2),
                         hnet_M=round((funding - hcost) / 1e6, 2),
                         hcum_M=round(cum_h / 1e6, 2),
                         sys_M=round(sysc / 1e6, 2),
                         qaly=round(DQ["base"] * tested)))
    return rows, cum_s, cum_hd

def scenario(change, avoided, dq):
    tc = tq = 0.0
    for t in range(10):
        tested = N0 * (1 + g) ** (t + 1) * ELIG * ADOPT[t]
        per = (TEST_COST + STAFF_VAR + PI_POS * 6000) - (0.6 * change * (avoided + 2800))
        d = 1 / ((1 + R_DISC) ** (t + 1))
        tc += (per * tested + FIXED) * d
        tq += dq * tested * d
    return round(tc / 1e6, 1), round(tq), (round(tc / tq) if tc > 0 else "Dominant")


def sensitivity():
    def run(test=850, fixed=FIXED, avoided=22000, adopt_scale=1.0):
        tc = tq = 0.0
        for t in range(10):
            tested = N0 * (1 + g) ** (t + 1) * ELIG * min(ADOPT[t] * adopt_scale, 1.0)
            per = (test + STAFF_VAR + PI_POS * 6000) - (0.6 * 0.50 * (avoided + 2800))
            d = 1 / ((1 + R_DISC) ** (t + 1))
            tc += (per * tested + fixed) * d
            tq += DQ["base"] * tested * d
        return dict(cost_disc_M=round(tc / 1e6, 1), qaly=round(tq),
                    icer=("Dominant" if tc < 0 else round(tc / tq)))
    return {"test_cost_x2": run(test=1700), "fixed_x2": run(fixed=4_800_000),
            "avoided_halved": run(avoided=11000), "adoption_halved": run(adopt_scale=0.5)}

ROWS, CUM_SYS_DISC, CUM_HOSP_DISC = annual()
SENS = sensitivity()
SCEN = {"conservative": scenario(0.25, 15000, DQ["conservative"]),
        "base": scenario(0.50, 22000, DQ["base"]),
        "optimistic": scenario(0.65, 28000, DQ["optimistic"])}
TRAJ = {tm: dict(pfs_std=round(100 * surv(9, tm), 1),
                 pfs_gui=round(100 * (0.4 * surv(14, tm) + 0.6 * surv(8, tm)), 1),
                 os_std=round(100 * surv(20, tm), 1),
                 os_gui=round(100 * (0.4 * surv(30, tm) + 0.6 * surv(19, tm)), 1))
        for tm in (12, 36, 60)}
OUT = dict(growth_pct=round(100 * g, 2), dqaly={k: round(v, 3) for k, v in DQ.items()},
           rows=ROWS, scenarios={k: dict(cost_disc_M=v[0], qaly=v[1], icer=v[2]) for k, v in SCEN.items()},
           cum_sys_disc_M=round(CUM_SYS_DISC / 1e6, 1), cum_hosp_disc_M=round(CUM_HOSP_DISC / 1e6, 1), sensitivity=SENS, traj=TRAJ,
           totals=dict(tested=sum(x["tested"] for x in ROWS), enrol=sum(x["enrol"] for x in ROWS),
                       qaly=sum(x["qaly"] for x in ROWS),
                       funding_M=round(sum(x["funding_M"] for x in ROWS), 1),
                       hcost_M=round(sum(x["hcost_M"] for x in ROWS), 1),
                       hnet_M=round(sum(x["hnet_M"] for x in ROWS), 1),
                       sys_M=round(sum(x["sys_M"] for x in ROWS), 1)))
with open(".src/data/economics_model.json", "w") as f:
    json.dump(OUT, f, indent=1)
print(json.dumps(OUT, indent=1))

# ---- Figures ----
NAVY, RUST, GREY = "#1f3a5f", "#8a1a1a", "#888888"
yrs = [x["year"] for x in ROWS]
fig, ax = plt.subplots(1, 2, figsize=(7.4, 2.7))
ax[0].bar(yrs, [x["tested"] for x in ROWS], color=NAVY, width=0.7)
ax[0].set_title("A. Patients signature-tested per year", fontsize=8)
ax[0].set_ylabel("Patients", fontsize=8); ax[0].tick_params(labelsize=7)
cum_sys, s = [], 0.0
for i, x in enumerate(ROWS):
    s += x["sys_M"] / ((1 + R_DISC) ** (i + 1)); cum_sys.append(s)
cum_hosp_d, sh = [], 0.0
for i, x in enumerate(ROWS):
    sh += x["hnet_M"] / ((1 + R_DISC) ** (i + 1)); cum_hosp_d.append(sh)
ax[1].plot(yrs, cum_sys, color=RUST, marker="o", ms=3, label="System (payer) cum. net cost, discounted")
ax[1].plot(yrs, cum_hosp_d, color=NAVY, marker="s", ms=3, label="Hospital cum. net funding, discounted")
ax[1].axhline(0, color=GREY, lw=0.7)
ax[1].set_title("B. Cumulative net position, CAD M", fontsize=8)
ax[1].set_ylabel("CAD millions", fontsize=8); ax[1].tick_params(labelsize=7)
ax[1].legend(fontsize=6.5, loc="lower left")
fig.tight_layout(); fig.savefig(".src/media/fig-economics.png", dpi=220); plt.close(fig)

m = np.arange(0, 61)
fig, ax = plt.subplots(figsize=(7.4, 2.8))
ax.plot(m, 100 * surv(20, m), color=GREY, ls="--", label="Overall survival - standard")
ax.plot(m, 100 * (0.4 * surv(30, m) + 0.6 * surv(19, m)), color=NAVY, label="Overall survival - signature-guided (hypothetical)")
ax.plot(m, 100 * surv(9, m), color=GREY, ls=":", label="Progression-free - standard")
ax.plot(m, 100 * (0.4 * surv(14, m) + 0.6 * surv(8, m)), color=RUST, label="Progression-free - signature-guided (hypothetical)")
ax.set_xlabel("Months from treatment start", fontsize=8); ax.set_ylabel("% of cohort", fontsize=8)
ax.set_title("Partitioned-survival trajectories, tested cohort (assumption set, Table 5)", fontsize=8.5)
ax.tick_params(labelsize=7); ax.legend(fontsize=6.5, loc="upper right"); ax.set_ylim(0, 102)
fig.tight_layout(); fig.savefig(".src/media/fig-trajectories.png", dpi=220); plt.close(fig)
print("figures written")
