import math
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import bem
import economics
import ehr
import elliptic
import fem
import optimize


class EllipticTests(unittest.TestCase):
    def test_known_values(self):
        self.assertAlmostEqual(elliptic.modulus_from_ratio(1.0), 1 / math.sqrt(2), places=12)
        self.assertAlmostEqual(elliptic.rectangle_modulus(1, 1), (math.sqrt(2) - 1) ** 2, places=12)
        self.assertAlmostEqual(elliptic.complete_K(1 / math.sqrt(2)), 1.8540746773013719, places=12)

    def test_round_trip_and_inverse_relation(self):
        for k in (0.05, 0.3, 0.7, 0.95):
            self.assertAlmostEqual(elliptic.modulus_from_ratio(elliptic.ratio_from_modulus(k)), k, places=10)
            a = elliptic.rectangle_aspect_from_modulus(k)
            self.assertAlmostEqual(elliptic.rectangle_modulus(a, 1.0), k, places=9)

    def test_ring_moduli(self):
        self.assertAlmostEqual(elliptic.annulus_modulus(1, math.e ** (2 * math.pi)), 1.0, places=12)
        self.assertAlmostEqual(elliptic.eccentric_ring_log_ratio(3.0, 1.0, 0.0), math.log(3.0), places=12)
        self.assertGreater(elliptic.eccentric_ring_log_ratio(3.0, 1.0, 1.0), 0.0)
        self.assertLess(elliptic.eccentric_ring_log_ratio(3.0, 1.0, 1.5), elliptic.eccentric_ring_log_ratio(3.0, 1.0, 0.0))
        with self.assertRaises(ValueError):
            elliptic.eccentric_ring_log_ratio(3.0, 1.0, 2.0)

    def test_conformal_partition_makes_square_cells(self):
        p = elliptic.conformal_partition(1.5, 3.0, 96)
        self.assertAlmostEqual(p["conformal_aspect"], 1.0, delta=0.08)
        self.assertAlmostEqual(p["radii"][0], 1.5)
        self.assertAlmostEqual(p["radii"][-1], 3.0)
        ratios = [p["radii"][i + 1] / p["radii"][i] for i in range(p["n_r"])]
        self.assertAlmostEqual(max(ratios), min(ratios), places=10)

    def test_strut_density_is_monotone_in_k(self):
        vals = [elliptic.strut_density_from_modulus(k, 1.0, 1.5) for k in (0.1, 0.3, 0.5, 0.7, 0.9)]
        self.assertEqual(vals, sorted(vals))


class BemTests(unittest.TestCase):
    def test_concentric_ring_matches_exact_solution(self):
        e = bem.concentric_error()
        self.assertLess(e["max_potential_error"], 1e-3)
        self.assertLess(e["current_relative_error"], 1e-3)

    def test_eccentric_current_matches_conformal_modulus_with_second_order_convergence(self):
        rows = bem.convergence_study(counts=(24, 48, 96))
        self.assertLess(rows[-1]["relative_error"], 5e-4)
        self.assertGreater(rows[-1]["observed_order"], 1.8)
        self.assertGreater(rows[1]["observed_order"], 1.7)

    def test_maximum_principle_and_geometry(self):
        m = bem.field_map(4.0, 1.0, 1.2, grid=40, n_outer=64, n_inner=40)
        u = m["u"][m["inside"]]
        self.assertTrue(((u > -0.02) & (u < 1.02)).all())
        self.assertGreater(m["serosal_exposure"], 0.0)
        with self.assertRaises(ValueError):
            bem.build_boundary(4.0, 1.0, 3.5, 32, 32)

    def test_closer_electrode_raises_serosal_exposure(self):
        far = bem.field_map(4.0, 1.0, 0.0, grid=36, n_outer=48, n_inner=28)["serosal_exposure"]
        near = bem.field_map(4.0, 1.0, 1.8, grid=36, n_outer=48, n_inner=28)["serosal_exposure"]
        self.assertGreater(near, far)


class FemTests(unittest.TestCase):
    def test_lame_convergence_and_grading(self):
        rows = fem.verify_lame(n_thetas=(24, 48, 96))
        self.assertLess(rows[-1]["graded_error"], 5e-3)
        self.assertGreater(rows[-1]["graded_order"], 1.5)
        for r in rows:
            self.assertLessEqual(r["graded_error"], r["uniform_error"])

    def test_pressure_scaling_is_linear(self):
        mesh = fem.build_mesh(1.5, 3.0, 48)
        E, nus, _ = fem.assign_materials(mesh)
        a = fem.solve(mesh, E, nus, 0.01)["mean_lumen_displacement"]
        b = fem.solve(mesh, E, nus, 0.02)["mean_lumen_displacement"]
        self.assertAlmostEqual(b / a, 2.0, places=9)

    def test_stent_hoop_resists_recoil(self):
        none = fem.stent_case(n_struts=0, n_theta=48)
        some = fem.stent_case(n_struts=12, n_theta=48)
        more = fem.stent_case(n_struts=24, n_theta=48)
        self.assertAlmostEqual(none["retained_gain_fraction"], none["plastic_fraction"], places=6)
        self.assertGreater(some["retained_gain_fraction"], none["retained_gain_fraction"] + 0.3)
        self.assertGreater(more["retained_gain_fraction"], some["retained_gain_fraction"])
        self.assertGreater(more["metal_burden"], some["metal_burden"])

    def test_vm_nonnegative_and_plaque_present(self):
        c = fem.stent_case(n_theta=48)
        self.assertTrue((c["vm_scaled"] >= 0).all())
        self.assertTrue((c["tag"] == 1).any() and (c["tag"] == 2).any())
        self.assertGreater(c["plaque_max_vm"], 0.0)


class OptimizeTests(unittest.TestCase):
    def test_golden_section_finds_quadratic_minimum(self):
        x, fx, evals = optimize.golden_section(lambda t: (t - 0.37) ** 2, 0.0, 1.0, tol=1e-6)
        self.assertAlmostEqual(x, 0.37, places=4)
        self.assertLess(evals, 60)

    def test_stent_heuristics_match_exhaustive_search(self):
        r = optimize.optimize_stent()
        ex = r["exhaustive"]
        self.assertLess(r["annealing"]["evaluations"], ex["evaluations"])
        self.assertLessEqual(abs(r["annealing"]["gap_to_exhaustive"]), 0.01)
        self.assertLess(ex["J"], r["baseline"]["J"])
        self.assertGreaterEqual(ex["n_struts"], 6)
        self.assertEqual(len(r["weight_sensitivity"]), 5)

    def test_gi_optimization_respects_window_and_improves_baseline(self):
        r = optimize.optimize_gi()
        best = min(r["exhaustive"]["J"], r["annealing"]["J"])
        self.assertLess(best, r["baseline"]["J"])
        a, e = (r["annealing"]["a"], r["annealing"]["e"]) if r["annealing"]["J"] <= r["exhaustive"]["J"] else (r["exhaustive"]["a"], r["exhaustive"]["e"])
        self.assertTrue(optimize.gi_objective(a, e)[4])


class EhrTests(unittest.TestCase):
    def test_soundex_reference_values(self):
        for name, code in (("Robert", "R163"), ("Rupert", "R163"), ("Tymczak", "T522"), ("Pfister", "P236"), ("Ashcraft", "A261")):
            self.assertEqual(ehr.soundex(name), code)

    def test_jaro_winkler_reference_values(self):
        self.assertAlmostEqual(ehr.jaro_winkler("MARTHA", "MARHTA"), 0.9611, places=4)
        self.assertAlmostEqual(ehr.jaro_winkler("DWAYNE", "DUANE"), 0.84, places=4)
        self.assertAlmostEqual(ehr.jaro_winkler("DIXON", "DICKSONX"), 0.8133, places=4)
        self.assertEqual(ehr.jaro_winkler("abc", "abc"), 1.0)
        self.assertEqual(ehr.jaro_winkler("abc", "xyz"), 0.0)

    def test_linkage_quality_and_blocking_reduction(self):
        recs = ehr.generate_records(300, 0.2, 1)
        r = ehr.link_records(recs)
        self.assertGreater(r["metrics"]["f1"], 0.9)
        self.assertGreater(r["reduction_ratio"], 0.99)
        self.assertEqual(recs, ehr.generate_records(300, 0.2, 1))
        self.assertGreater(r["metrics"]["precision"], 0.9)

    def test_union_find(self):
        uf = ehr.UnionFind(6)
        uf.union(0, 1); uf.union(1, 2); uf.union(4, 5)
        self.assertEqual(uf.find(0), uf.find(2))
        self.assertNotEqual(uf.find(0), uf.find(4))

    def test_annealing_beats_priority_rules(self):
        s = ehr.schedule(ehr.generate_cases(24, 3))
        self.assertLessEqual(s["annealing"], min(s["rules"].values()))
        self.assertGreater(s["improvement_vs_best_rule"], 0.1)
        ends = {}
        for seg in s["segments"]:
            self.assertGreater(seg["end"], seg["start"])
        for room in range(s["rooms"]):
            segs = sorted((x for x in s["segments"] if x["room"] == room), key=lambda x: x["start"])
            for a, b in zip(segs, segs[1:]):
                self.assertLessEqual(a["end"], b["start"] + 1e-9)

    def test_invalid_inputs(self):
        with self.assertRaises(ValueError):
            ehr.generate_records(5, 0.2, 1)


class EconomicsTests(unittest.TestCase):
    LINK = {"cv": {"baseline_risk": 0.126, "optimized_risk": 0.106, "relative_risk_reduction": 0.157, "J_baseline": 0.058, "J_optimized": 0.033},
            "gi": {"baseline_risk": 0.077, "optimized_risk": 0.064, "relative_risk_reduction": 0.175, "J_baseline": 1.1, "J_optimized": 0.24}}

    def test_adoption_is_zero_before_launch_lead_and_monotone(self):
        import numpy as np
        t = np.arange(1, 11)
        a = economics.adoption(t, 0.2, 3.0)
        self.assertTrue((a[:3] == 0).all())
        self.assertTrue((np.diff(a[3:]) >= 0).all())
        self.assertLessEqual(a.max(), 0.2 + 1e-12)

    def test_physics_link_reduces_risk(self):
        link = economics.physics_link(0.058, 0.033, 1.1, 0.24)
        for line in ("cv", "gi"):
            self.assertGreater(link[line]["relative_risk_reduction"], 0.0)
            self.assertLess(link[line]["optimized_risk"], link[line]["baseline_risk"])

    def test_full_run_is_consistent(self):
        r = economics.run_all(self.LINK, n_mc=800)
        for key, v in r["regions"].items():
            self.assertAlmostEqual(sum(v["revenue"]), v["cumulative_revenue"], places=3)
            for ln in ("cv", "gi", "ehr"):
                pass
            total = [sum(v["revenue_by_line"][ln][i] for ln in ("cv", "gi", "ehr")) for i in range(10)]
            for a, b in zip(total, v["revenue"]):
                self.assertAlmostEqual(a, b, places=3)
            fan = v["monte_carlo"]["revenue_fan"]
            for i in range(10):
                self.assertLessEqual(fan["p5"][i], fan["p50"][i] + 1e-6)
                self.assertLessEqual(fan["p50"][i], fan["p95"][i] + 1e-6)
            self.assertLessEqual(v["bootstrap"]["p5"], v["bootstrap"]["p95"])
            self.assertLessEqual(v["regression"]["p5"], v["regression"]["point"])
            self.assertLessEqual(v["bayes"]["cri_low"], v["bayes"]["posterior_mean"])
            self.assertLessEqual(v["bayes"]["posterior_mean"], v["bayes"]["cri_high"])
        c = r["contexts"]["asia_pacific"]
        self.assertAlmostEqual(c["cumulative_revenue"], sum(r["regions"][k]["cumulative_revenue"] for k in c["members"]), places=3)
        self.assertEqual(set(r["contexts"]), {"us_canada", "asia_pacific"})

    def test_reproducible_and_high_scenario_exceeds_low(self):
        a = economics.run_all(self.LINK, n_mc=400, seed=5)
        b = economics.run_all(self.LINK, n_mc=400, seed=5)
        self.assertEqual(a["regions"]["us"]["monte_carlo"]["npv"], b["regions"]["us"]["monte_carlo"]["npv"])
        s = a["regions"]["us"]["scenarios"]
        self.assertGreater(s["high"]["revenue_10y"], s["base"]["revenue_10y"])
        self.assertGreater(s["base"]["revenue_10y"], s["low"]["revenue_10y"])

    def test_value_ratio_varies_with_regional_cost(self):
        v = economics.value_ratios(economics.physics_link(0.058, 0.033, 1.1, 0.24))
        self.assertGreater(v["us"]["cv"]["value_ratio"], v["india"]["cv"]["value_ratio"])


class ApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import app as studio
        cls.client = studio.app.test_client()

    def test_health_and_index(self):
        self.assertEqual(self.client.get("/api/health").status_code, 200)
        r = self.client.get("/")
        self.assertEqual(r.status_code, 200)
        r.close()

    def test_bem_and_validation(self):
        r = self.client.post("/api/bem", json={"R": 4.0, "a": 1.0, "e": 1.0})
        self.assertEqual(r.status_code, 200)
        d = r.get_json()
        self.assertEqual(len(d["u"]), d["grid"])
        self.assertLess(abs(d["metrics"]["current"] - d["metrics"]["exact_current"]) / d["metrics"]["exact_current"], 0.01)
        bad = self.client.post("/api/bem", json={"R": 4.0, "a": 1.0, "e": 3.0})
        self.assertEqual(bad.status_code, 400)
        self.assertFalse(bad.get_json()["success"])
        self.assertEqual(self.client.post("/api/bem", json={"R": "x"}).status_code, 400)

    def test_fem_and_elliptic_and_ehr(self):
        f = self.client.post("/api/fem", json={"n_struts": 12, "layers": 1}).get_json()
        self.assertTrue(f["success"])
        self.assertEqual(len(f["vm_deploy"]), len(f["tris"]))
        self.assertGreater(f["metrics"]["retained_gain_fraction"], 0.5)
        self.assertEqual(self.client.post("/api/fem", json={"n_struts": 999}).status_code, 400)
        e = self.client.post("/api/elliptic", json={"k": 0.5}).get_json()
        self.assertAlmostEqual(e["current"]["ratio"], 1.279262, places=5)
        h = self.client.post("/api/ehr", json={"n": 120, "seed": 2}).get_json()
        self.assertTrue(h["success"])
        self.assertGreater(h["reduction_ratio"], 0.9)
        self.assertEqual(self.client.post("/api/ehr", json={"n": 5}).status_code, 400)


if __name__ == "__main__":
    unittest.main()
