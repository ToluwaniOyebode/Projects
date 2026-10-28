"""Command line entry point: python run.py [--quick] [--folds 8] [--seed 11]."""

from __future__ import annotations

import argparse
from pathlib import Path

from forecast_lab.experiment import run_experiment


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the demand forecasting benchmark.")
    parser.add_argument("--folds", type=int, default=8, help="number of rolling-origin folds")
    parser.add_argument("--horizon", type=int, default=14, help="forecast horizon in days")
    parser.add_argument("--seed", type=int, default=11, help="random seed")
    parser.add_argument("--quick", action="store_true", help="smaller boosting models for a smoke run")
    parser.add_argument("--out", default=str(Path(__file__).parent / "results"), help="output directory")
    args = parser.parse_args()

    results = run_experiment(args.out, folds=args.folds, horizon=args.horizon, seed=args.seed, quick=args.quick)
    print(f"{'Model':<28}{'WAPE':>8}{'Bias':>9}{'MASE':>7}")
    for name, m in results["models"].items():
        print(f"{name:<28}{m['wape']:>8.1%}{m['bias']:>+9.1%}{m['mase']:>7.2f}")
    print(f"Improvement over seasonal naive: {results['improvement_over_naive']:.1%}")
    print(f"Interval coverage (nominal 80%): {results['intervals']['coverage']:.1%}")
    print(f"Report written to {Path(args.out) / 'REPORT.md'}")


if __name__ == "__main__":
    main()
