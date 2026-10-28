import json
import tempfile
import unittest
from pathlib import Path

import numpy as np

from ticket_nlp.data import CATEGORIES, TEMPLATES, corrupt_text, generate_tickets
from ticket_nlp.experiment import run_experiment
from ticket_nlp.models import grouped_split, random_split, unpack
from ticket_nlp.routing import apply_threshold, choose_threshold, routing_curve
from ticket_nlp.search import TicketIndex, evaluate_retrieval


class DataTests(unittest.TestCase):
    def test_reproducible_and_covers_all_categories(self):
        a, b = generate_tickets(n=600, seed=2), generate_tickets(n=600, seed=2)
        self.assertEqual([t.text for t in a], [t.text for t in b])
        self.assertEqual({t.category for t in a}, set(CATEGORIES))

    def test_slots_are_always_filled(self):
        for ticket in generate_tickets(n=800, seed=3, typo_rate=0):
            self.assertNotIn("{", ticket.text)
            self.assertNotIn("}", ticket.text)

    def test_template_ids_point_at_real_templates(self):
        for ticket in generate_tickets(n=300, seed=4):
            category, index = ticket.template_id.split(":")
            self.assertEqual(category, ticket.category)
            self.assertLess(int(index), len(TEMPLATES[category]))
            if ticket.has_secondary_issue:
                other, other_index = ticket.secondary_template_id.split(":")
                self.assertNotEqual(other, ticket.category)
                self.assertLess(int(other_index), len(TEMPLATES[other]))
            else:
                self.assertIsNone(ticket.secondary_template_id)

    def test_corruption_changes_text_only_when_rate_positive(self):
        rng = np.random.default_rng(0)
        text = "please refund the duplicate charge on my invoice"
        self.assertEqual(corrupt_text(text, 0.0, rng), text)
        noisy = corrupt_text(text, 1.0, np.random.default_rng(0))
        self.assertNotEqual(noisy, text)
        self.assertEqual(len(noisy.split(" ")), len(text.split(" ")))

    def test_invalid_arguments_rejected(self):
        with self.assertRaises(ValueError):
            generate_tickets(n=10)
        with self.assertRaises(ValueError):
            generate_tickets(n=600, typo_rate=2)


class SplitTests(unittest.TestCase):
    """The unseen-phrasing split must really be unseen; otherwise the headline numbers are fiction."""

    def setUp(self):
        self.tickets = generate_tickets(n=3000, seed=6)
        self.train, self.test = grouped_split(self.tickets, holdout_per_category=2, seed=6)

    def test_no_overlap_between_train_and_test(self):
        self.assertEqual(set(self.train) & set(self.test), set())

    def test_held_out_phrasings_never_appear_in_training_at_all(self):
        held_out = {self.tickets[i].template_id for i in self.test}
        self.assertEqual(len(held_out), 2 * len(CATEGORIES))
        for i in self.train:
            ticket = self.tickets[i]
            self.assertNotIn(ticket.template_id, held_out)
            self.assertNotIn(ticket.secondary_template_id, held_out)  # the contamination bug

    def test_every_category_appears_in_both_sides(self):
        self.assertEqual({self.tickets[i].category for i in self.train}, set(CATEGORIES))
        self.assertEqual({self.tickets[i].category for i in self.test}, set(CATEGORIES))

    def test_random_split_is_stratified_and_disjoint(self):
        train, test = random_split(self.tickets, seed=6)
        self.assertEqual(set(train) & set(test), set())
        self.assertEqual(len(train) + len(test), len(self.tickets))


class RoutingTests(unittest.TestCase):
    def test_curve_trades_coverage_for_accuracy(self):
        y_true = np.array(["a"] * 6 + ["b"] * 4)
        y_pred = np.array(["a"] * 5 + ["b"] + ["b"] * 3 + ["a"])
        confidence = np.array([0.99, 0.95, 0.9, 0.9, 0.85, 0.4, 0.99, 0.9, 0.8, 0.3])
        thresholds, coverage, accuracy = routing_curve(y_true, y_pred, confidence)
        self.assertTrue(np.all(np.diff(coverage) <= 1e-12))
        valid = ~np.isnan(accuracy)
        self.assertGreater(accuracy[valid][-1], accuracy[0])

    def test_apply_threshold_hand_calculation(self):
        y_true = np.array(["a", "a", "b", "b"])
        y_pred = np.array(["a", "b", "b", "a"])
        outcome = apply_threshold(y_true, y_pred, np.array([0.9, 0.6, 0.95, 0.5]), threshold=0.8)
        self.assertAlmostEqual(outcome["coverage"], 0.5)
        self.assertAlmostEqual(outcome["automated_accuracy"], 1.0)
        self.assertEqual(outcome["escalated"], 2)
        self.assertAlmostEqual(outcome["overall_accuracy_all_automated"], 0.5)

    def test_choose_threshold_meets_target_or_falls_back(self):
        y_true = np.array([1, 1, 1, 0, 0, 0])
        y_pred = np.array([1, 1, 0, 0, 1, 1])
        confidence = np.array([0.95, 0.9, 0.5, 0.92, 0.4, 0.45])
        threshold = choose_threshold(y_true, y_pred, confidence, target_accuracy=1.0)
        outcome = apply_threshold(y_true, y_pred, confidence, threshold)
        self.assertEqual(outcome["automated_accuracy"], 1.0)
        impossible = choose_threshold(y_true, 1 - y_true, confidence, target_accuracy=0.99)
        self.assertAlmostEqual(impossible, 0.99)


class SearchTests(unittest.TestCase):
    def setUp(self):
        self.texts = [
            "refund my duplicate charge on the invoice",
            "invoice shows wrong amount charged twice",
            "cannot log in password reset email missing",
            "locked out of my account password does not work",
            "package delivery late tracking not updating",
            "parcel courier delivery damaged order",
        ] * 4
        self.labels = np.array(["billing", "billing", "access", "access", "shipping", "shipping"] * 4)

    def test_nearest_neighbour_of_a_known_text_is_itself(self):
        index = TicketIndex().fit(self.texts)
        top, scores = index.search([self.texts[2]], k=3)
        self.assertEqual(self.labels[top[0][0]], "access")
        self.assertAlmostEqual(scores[0][0], 1.0, places=5)
        self.assertTrue(np.all(np.diff(scores[0]) <= 1e-9))

    def test_search_before_fit_raises(self):
        with self.assertRaises(RuntimeError):
            TicketIndex().search(["hello"])

    def test_lsa_index_and_metrics(self):
        index = TicketIndex(components=5).fit(self.texts)
        metrics = evaluate_retrieval(index, ["charged twice on my invoice", "my parcel has not been delivered"],
                                     ["billing", "shipping"], self.labels)
        self.assertGreater(metrics["precision_at_1"], 0.5)
        self.assertGreater(metrics["mrr"], 0.5)
        self.assertLessEqual(metrics["precision_at_5"], 1.0)


class EndToEndTests(unittest.TestCase):
    def test_quick_run_writes_all_artifacts(self):
        with tempfile.TemporaryDirectory() as tmp:
            results = run_experiment(tmp, n=2400, seed=8, quick=True)
            for name in ("metrics.json", "REPORT.md", "split_comparison.png", "confusion_matrix.png",
                         "typo_robustness.png", "routing_tradeoff.png", "top_terms.png", "retrieval.png"):
                self.assertTrue((Path(tmp) / name).exists(), name)
            saved = json.loads((Path(tmp) / "metrics.json").read_text())
            self.assertEqual(saved["selected_model"], results["selected_model"])
            selected = results["models"][results["selected_model"]]
            self.assertGreater(selected["grouped_split"]["macro_f1"], 1 / len(CATEGORIES))  # beats chance
            self.assertGreater(selected["random_split"]["macro_f1"], selected["grouped_split"]["macro_f1"])


if __name__ == "__main__":
    unittest.main()
