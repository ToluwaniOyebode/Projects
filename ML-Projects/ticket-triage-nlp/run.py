"""Command line entry point: python run.py [--quick] [--n 6000] [--seed 5]."""

from __future__ import annotations

import argparse
from pathlib import Path

from ticket_nlp.experiment import run_experiment


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the ticket triage NLP study.")
    parser.add_argument("--n", type=int, default=6000, help="number of synthetic tickets")
    parser.add_argument("--seed", type=int, default=5, help="random seed")
    parser.add_argument("--quick", action="store_true", help="fewer cross-validation folds for a smoke run")
    parser.add_argument("--out", default=str(Path(__file__).parent / "results"), help="output directory")
    args = parser.parse_args()

    results = run_experiment(args.out, n=args.n, seed=args.seed, quick=args.quick)
    print(f"{'Model':<50}{'random F1':>10}{'unseen F1':>10}")
    for name, m in results["models"].items():
        print(f"{name:<50}{m['random_split']['macro_f1']:>10.3f}{m['grouped_split']['macro_f1']:>10.3f}")
    routing = results["routing"]
    print(f"Selected: {results['selected_model']}")
    print(f"Routing at {routing['threshold']:.2f}: {routing['coverage']:.1%} automated at {routing['automated_accuracy']:.1%} accuracy")
    print(f"Best search: {results['best_search']}")
    print(f"Report written to {Path(args.out) / 'REPORT.md'}")


if __name__ == "__main__":
    main()
