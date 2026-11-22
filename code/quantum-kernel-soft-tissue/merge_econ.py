import base64, re

html = open("index.html").read()
assert html.count("All results are synthetic, experimental and not for clinical decisions.</p></div>") == 1

# --- page 1 updates ---
html = html.replace(
    "Independent preprint &bull; Version 1.1 &bull; 22 November 2026 (adds Section 10, Tables 4-5, Figures 3-4 and Appendix C)",
    "Independent preprint &bull; Version 1.2 &bull; 22 November 2026 (adds Section 11, Tables 6-8, Figure 5 and Appendix D; Section 10 added in v1.1)", 1)
html = html.replace(
    "All results are synthetic, experimental and not for clinical decisions.</p></div>",
    "Version 1.2 adds a health-economics scenario model (Section 11): a three-component revenue identity, a payer break-even condition, and a ridge / gradient-boosting machine-learning cross-check fitted on a synthetic site-month panel. In the central scale scenario (340 sites, 97,920 cases in Year 3) revenue reaches USD 108.09M in Year 3 (USD 108.89M by the fitted model), above USD 100M, while a conservative scenario reaches only USD 59.63M; the trajectory is a scenario, not a forecast, and at the stated prices the platform remains a net cost to payers below a 5.97-percentage-point break-even effect. All results are synthetic, experimental and not for clinical decisions.</p></div>", 1)
html = html.replace(
    "finite mathematics; finite element method; catheter design</p>",
    "finite mathematics; finite element method; catheter design; health economics; revenue projection; ridge regression; gradient boosting</p>", 1)
html = html.replace(
    "Section 10 (Version 1.1) adds a finite element model of intraoperative device expansion and derives catheter design implications from it.</p>",
    "Section 10 (Version 1.1) adds a finite element model of intraoperative device expansion and derives catheter design implications from it. Section 11 (Version 1.2) adds a health-economics cost and revenue model with a statistical machine-learning cross-check over a three-year trajectory.</p>", 1)

# --- split into sections; renumber old pages 15-20 to 21-26 ---
parts = html.split('<section class="page">')
assert len(parts) == 21, len(parts)
for i in range(15, 21):
    old = i
    parts[i] = parts[i].replace(f'<div class="pnum">{old}</div>',
                                f'<div class="pnum">{old + 6}</div>', 1)
    assert f'<div class="pnum">{old + 6}</div>' in parts[i]

# --- references + data availability on old page 15 (now 21) ---
refs_add = ('<p>11. Drummond, M. F., Sculpher, M. J., Claxton, K., Stoddart, G. L. &amp; Torrance, G. W. '
            '<i>Methods for the Economic Evaluation of Health Care Programmes</i> 4th edn (Oxford Univ. Press, 2015).</p>\n'
            '<p>12. Hoerl, A. E. &amp; Kennard, R. W. Ridge regression: biased estimation for nonorthogonal problems. '
            '<i>Technometrics</i> 12, 55-67 (1970).</p>\n'
            '<p>13. Friedman, J. H. Greedy function approximation: a gradient boosting machine. '
            '<i>Ann. Stat.</i> 29, 1189-1232 (2001).</p>\n</div>')
parts[15] = parts[15].replace(
    'network. Watson Scientific Computing Laboratory Report (Columbia University, 1949).</p>\n</div>',
    'network. Watson Scientific Computing Laboratory Report (Columbia University, 1949).</p>\n' + refs_add, 1)
assert 'Friedman, J. H.' in parts[15]
parts[15] = parts[15].replace(
    "The generating code is reproduced in Appendices A and B, and the finite element generator of Section 10 in Appendix C;",
    "The generating code is reproduced in Appendices A and B, the finite element generator of Section 10 in Appendix C, and the health-economics and machine-learning generator of Section 11 in Appendix D;", 1)

# --- new sections with figure embedded ---
fig_b64 = base64.b64encode(open("fig_econ.png", "rb").read()).decode()
new = []
for f in ["econ_p15.html", "econ_p16.html", "econ_p17.html",
          "econ_p18.html", "econ_p19.html", "econ_p20.html"]:
    new.append(open(f).read().replace(
        "__FIG_ECON__", "data:image/png;base64," + fig_b64))
out = '<section class="page">'.join(parts[:15] + new + parts[15:])
open("index.html", "w").write(out)
print("sections now:", out.count('<section class="page">'))
print("pnums:", re.findall(r'pnum">(\d+)<', out))
