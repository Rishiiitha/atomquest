"""Standalone deterministic cohort generation command."""

import argparse

from twin.simulator import ROOT, generate_cohort


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--quick", action="store_true")
    parser.add_argument("--full", action="store_true")
    args = parser.parse_args()
    cohorts = generate_cohort(quick=args.quick, full=args.full, out_dir=ROOT / "data" / "generated")
    print(
        {
            name: {"units": int(frame.unit_id.nunique()), "rows": len(frame)}
            for name, frame in cohorts.items()
        }
    )


if __name__ == "__main__":
    main()
