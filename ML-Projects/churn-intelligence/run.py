"""Command line entry point: python run.py [--quick] [--n 12000] [--seed 7]."""

from __future__ import annotations

import argparse
from pathlib import Path

from churn_intel.experiment import run_experiment


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the churn intelligence experiment.")
    parser.add_argument("--n", type=int, default=12000, help="number of synthetic customers")
    parser.add_argument("--seed", type=int, default=7, help="random seed")
    parser.add_argument("--quick", action="store_true", help="smaller models for a fast smoke run")
    parser.add_argument("--out", default=str(Path(__file__).parent / "results"), help="output directory")
    args = parser.parse_args()

    results = run_experiment(args.out, n=args.n, seed=args.seed, quick=args.quick)
    selected = results["selected_model"]
    print(f"Selected model: {selected}")
    print(f"Calibrated test ROC AUC: {results['calibrated_test_metrics']['roc_auc']:.3f}")
    for name, value in results["campaign_profit_test"].items():
        print(f"  {name:<36} ${value:>10,.0f}")
    print(f"Report written to {Path(args.out) / 'REPORT.md'}")


if __name__ == "__main__":
    main()
