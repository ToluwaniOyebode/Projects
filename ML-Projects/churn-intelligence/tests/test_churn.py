import json
import tempfile
import unittest
from pathlib import Path

import numpy as np

from churn_intel.business import RetentionEconomics, best_threshold, campaign_profit, lift_table
from churn_intel.data import FEATURES, ID_COLUMN, TARGET, generate_customers, split_features_target
from churn_intel.experiment import run_experiment
from churn_intel.modeling import expected_calibration_error, model_zoo


class DataTests(unittest.TestCase):
    def test_same_seed_gives_identical_data(self):
        a = generate_customers(n=500, seed=3)
        b = generate_customers(n=500, seed=3)
        self.assertTrue(a.equals(b))
        self.assertFalse(a.equals(generate_customers(n=500, seed=4)))

    def test_churn_rate_matches_target(self):
        frame = generate_customers(n=6000, seed=1, target_rate=0.26)
        self.assertAlmostEqual(frame[TARGET].mean(), 0.26, delta=0.03)

    def test_label_and_id_are_never_model_inputs(self):
        frame = generate_customers(n=300, seed=2)
        X, y = split_features_target(frame)
        self.assertNotIn(TARGET, X.columns)
        self.assertNotIn(ID_COLUMN, X.columns)
        self.assertEqual(list(X.columns), FEATURES)
        self.assertEqual(len(X), len(y))

    def test_ids_unique_and_missing_values_present(self):
        frame = generate_customers(n=2000, seed=5)
        self.assertTrue(frame[ID_COLUMN].is_unique)
        self.assertGreater(frame["avg_usage_gb"].isna().sum(), 0)

    def test_rejects_invalid_arguments(self):
        with self.assertRaises(ValueError):
            generate_customers(n=10)
        with self.assertRaises(ValueError):
            generate_customers(n=500, target_rate=1.5)


class BusinessTests(unittest.TestCase):
    def setUp(self):
        self.eco = RetentionEconomics(contact_cost=25, save_rate=0.5, customer_value=200)

    def test_breakeven_probability(self):
        self.assertAlmostEqual(self.eco.breakeven_probability, 0.25)

    def test_campaign_profit_arithmetic(self):
        y = [1, 0, 1, 0]
        contacted = [True, True, False, False]
        # churner gains 0.5*200-25=75, non-churner loses 25 -> 50
        self.assertAlmostEqual(campaign_profit(y, contacted, self.eco), 50.0)
        self.assertEqual(campaign_profit(y, [False] * 4, self.eco), 0.0)

    def test_perfect_scores_contact_only_churners(self):
        y = np.array([1, 1, 0, 0, 0, 0])
        threshold, profit = best_threshold(y, y.astype(float), self.eco)
        self.assertAlmostEqual(profit, 2 * 75.0)
        self.assertGreater(threshold, 0.0)

    def test_lift_table_properties(self):
        rng = np.random.default_rng(0)
        scores = rng.random(2000)
        y = (rng.random(2000) < scores).astype(int)
        table = lift_table(y, scores, bins=10)
        self.assertEqual(sum(row["customers"] for row in table), 2000)
        self.assertGreater(table[0]["lift"], 1.0)
        self.assertLess(table[-1]["lift"], 1.0)
        capture = [row["cumulative_capture"] for row in table]
        self.assertEqual(capture, sorted(capture))
        self.assertAlmostEqual(capture[-1], 1.0)

    def test_invalid_economics_rejected(self):
        with self.assertRaises(ValueError):
            RetentionEconomics(save_rate=0)
        with self.assertRaises(ValueError):
            RetentionEconomics(customer_value=-5)


class ModelingTests(unittest.TestCase):
    def test_calibration_error_is_low_for_calibrated_scores(self):
        rng = np.random.default_rng(0)
        p = rng.random(20000)
        y = (rng.random(20000) < p).astype(int)
        self.assertLess(expected_calibration_error(y, p), 0.02)
        self.assertGreater(expected_calibration_error(y, np.clip(p * 0.3, 0, 1)), 0.1)

    def test_every_pipeline_fits_and_handles_unseen_category(self):
        frame = generate_customers(n=800, seed=9)
        X, y = split_features_target(frame)
        X_new = X.head(5).copy()
        X_new["region"] = "atlantis"
        for name, pipeline in model_zoo(quick=True).items():
            pipeline.fit(X, y)
            proba = pipeline.predict_proba(X_new)
            self.assertEqual(proba.shape, (5, 2), name)
            self.assertTrue(np.allclose(proba.sum(axis=1), 1.0), name)


class EndToEndTests(unittest.TestCase):
    def test_quick_run_writes_all_artifacts(self):
        with tempfile.TemporaryDirectory() as tmp:
            results = run_experiment(tmp, n=2500, seed=11, quick=True)
            for name in ("metrics.json", "REPORT.md", "roc_pr.png", "calibration.png",
                         "lift_gains.png", "profit_curve.png", "feature_importance.png"):
                self.assertTrue((Path(tmp) / name).exists(), name)
            saved = json.loads((Path(tmp) / "metrics.json").read_text())
            self.assertEqual(saved["selected_model"], results["selected_model"])
            self.assertGreater(results["calibrated_test_metrics"]["roc_auc"], 0.65)
            profits = results["campaign_profit_test"]
            self.assertGreater(profits["Model, break-even rule"], profits["Contact nobody"])


if __name__ == "__main__":
    unittest.main()
