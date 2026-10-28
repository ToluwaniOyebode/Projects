import json
import tempfile
import unittest
from pathlib import Path

import numpy as np

from forecast_lab import metrics
from forecast_lab.backtest import rolling_origins, run_backtest
from forecast_lab.data import generate_panel, holiday_codes
from forecast_lab.experiment import run_experiment
from forecast_lab.features import MIN_ORIGIN, build_features
from forecast_lab.models import GlobalBoosting, HoltWinters, SeasonalAverage, SeasonalNaive
import pandas as pd


class DataTests(unittest.TestCase):
    def test_panel_is_reproducible_and_well_formed(self):
        a, b = generate_panel(n_series=3, days=500, seed=4), generate_panel(n_series=3, days=500, seed=4)
        self.assertTrue(np.array_equal(a.units, b.units))
        self.assertEqual(a.units.shape, (3, 500))
        self.assertTrue((a.units >= 0).all())
        self.assertEqual(len(a.to_frame()), 3 * 500)
        self.assertGreater(a.promo.sum(), 0)

    def test_holiday_codes_find_known_dates(self):
        dates = pd.to_datetime(["2023-01-01", "2023-11-24", "2023-12-25", "2023-06-15"])
        self.assertEqual(list(holiday_codes(dates)), [1, 3, 5, 0])  # Black Friday 2023 is Nov 24

    def test_rejects_bad_arguments(self):
        with self.assertRaises(ValueError):
            generate_panel(n_series=0)
        with self.assertRaises(ValueError):
            generate_panel(days=100)


class LeakageTests(unittest.TestCase):
    """The most important tests in the project: features may never see the future."""

    def setUp(self):
        self.panel = generate_panel(n_series=3, days=600, seed=2)
        self.origin = 450
        self.horizon = 14

    def test_features_ignore_sales_after_the_origin(self):
        history = self.panel.units[:, : self.origin + 1]
        clean, _, scale_clean = build_features(history, self.panel, [self.origin], self.horizon, with_target=False)

        # Rewrite every sale after the origin in the full panel; the features must not change.
        tampered_units = self.panel.units.copy()
        tampered_units[:, self.origin + 1 :] = 9999.0
        tampered_history = tampered_units[:, : self.origin + 1]
        tampered, _, scale_tampered = build_features(tampered_history, self.panel, [self.origin], self.horizon, with_target=False)

        pd.testing.assert_frame_equal(clean, tampered)
        self.assertTrue(np.array_equal(scale_clean, scale_tampered))

    def test_changing_a_recent_sale_does_change_features(self):
        history = self.panel.units[:, : self.origin + 1].copy()
        base, _, _ = build_features(history, self.panel, [self.origin], self.horizon, with_target=False)
        history[:, self.origin] += 50
        changed, _, _ = build_features(history, self.panel, [self.origin], self.horizon, with_target=False)
        self.assertFalse(base["last_value"].equals(changed["last_value"]))

    def test_target_is_the_future_ratio(self):
        history = self.panel.units[:, : self.origin + 1]
        X, y, scale = build_features(history, self.panel, [self.origin - 14], self.horizon, with_target=True)
        first_row = 0  # series 0, horizon 1
        expected = self.panel.units[0, self.origin - 14 + 1] / scale[first_row]
        self.assertAlmostEqual(y[first_row], expected)
        self.assertEqual(len(X), 3 * self.horizon)

    def test_origin_bounds_are_enforced(self):
        history = self.panel.units[:, : self.origin + 1]
        with self.assertRaises(ValueError):
            build_features(history, self.panel, [MIN_ORIGIN - 1], self.horizon, with_target=False)
        with self.assertRaises(ValueError):
            build_features(history, self.panel, [self.origin], self.horizon, with_target=True)


class BacktestTests(unittest.TestCase):
    def test_origins_do_not_overlap_and_are_ordered(self):
        origins = rolling_origins(1461, horizon=14, folds=8, step=28)
        self.assertEqual(origins, sorted(origins))
        self.assertTrue(all(b - a >= 14 for a, b in zip(origins, origins[1:])))
        self.assertEqual(origins[-1] + 14, 1460)
        with self.assertRaises(ValueError):
            rolling_origins(1461, horizon=14, folds=8, step=7)

    def test_baselines_against_hand_calculation(self):
        panel = generate_panel(n_series=2, days=500, seed=5)
        history = panel.units[:, :450]
        naive = SeasonalNaive().forecast(history, panel, 14).mean
        origin = 449  # last observed index of a 450-day history
        # h=1 targets origin+1 = 450, whose weekday last occurred at index 443
        self.assertTrue(np.array_equal(naive[:, 0], history[:, origin + 1 - 7]))
        # h=8 targets the following same weekday, so it reuses the same reference day
        self.assertTrue(np.array_equal(naive[:, 7], naive[:, 0]))
        # h=7 targets origin+7, whose last same weekday is the origin itself
        self.assertTrue(np.array_equal(naive[:, 6], history[:, origin]))
        average = SeasonalAverage(weeks=2).forecast(history, panel, 14).mean
        self.assertTrue(np.allclose(average[:, 0], (history[:, 443] + history[:, 436]) / 2))

    def test_every_model_runs_on_truncated_history(self):
        panel = generate_panel(n_series=2, days=520, seed=6)
        models = [SeasonalNaive(), SeasonalAverage(), HoltWinters(), GlobalBoosting(quick=True, origin_step=7)]
        results = run_backtest(panel, models, horizon=14, origins=[470])
        for name, folds in results.items():
            forecast = folds[0]
            self.assertEqual(forecast["mean"].shape, (2, 14), name)
            self.assertTrue(np.isfinite(forecast["mean"]).all(), name)
            self.assertTrue((forecast["mean"] >= 0).all(), name)
        boosting = results[GlobalBoosting.name][0]
        self.assertTrue((boosting["lower"] <= boosting["mean"] + 1e-9).all())
        self.assertTrue((boosting["upper"] >= boosting["mean"] - 1e-9).all())


class MetricTests(unittest.TestCase):
    def test_wape_bias_mae(self):
        actual, forecast = np.array([10.0, 20.0, 0.0]), np.array([12.0, 15.0, 3.0])
        self.assertAlmostEqual(metrics.wape(actual, forecast), 10 / 30)
        self.assertAlmostEqual(metrics.bias(actual, forecast), 0 / 30)
        self.assertAlmostEqual(metrics.mae(actual, forecast), 10 / 3)

    def test_mase_scales_error_by_in_sample_seasonal_naive(self):
        # Every value is 2 higher than the same weekday last week, so the naive scale is exactly 2.
        history = (np.arange(70) // 7 * 2.0)[None, :]
        actual, forecast = np.array([[5.0, 5.0]]), np.array([[4.0, 4.0]])  # mean absolute error 1
        self.assertAlmostEqual(metrics.mase(actual, forecast, history), 0.5)

    def test_interval_and_service_metrics(self):
        actual = np.array([5.0, 10.0, 15.0])
        self.assertAlmostEqual(metrics.interval_coverage(actual, actual - 1, actual + 1), 1.0)
        self.assertAlmostEqual(metrics.interval_coverage(actual, actual + 1, actual + 2), 0.0)
        service = metrics.service_metrics(actual, np.array([5.0, 5.0, 20.0]))
        self.assertAlmostEqual(service["fill_rate"], (5 + 5 + 15) / 30)
        self.assertAlmostEqual(service["excess_stock"], 5 / 30)


class EndToEndTests(unittest.TestCase):
    def test_quick_run_beats_naive_and_writes_artifacts(self):
        with tempfile.TemporaryDirectory() as tmp:
            results = run_experiment(tmp, folds=3, quick=True)
            for name in ("metrics.json", "REPORT.md", "data_overview.png", "model_comparison.png",
                         "horizon_error.png", "forecast_grid.png", "promo_effect.png"):
                self.assertTrue((Path(tmp) / name).exists(), name)
            saved = json.loads((Path(tmp) / "metrics.json").read_text())
            self.assertEqual(saved["best_model"], results["best_model"])
            self.assertGreater(results["improvement_over_naive"], 0.0)
            self.assertGreater(results["intervals"]["coverage"], 0.5)


if __name__ == "__main__":
    unittest.main()
