"""Training entry point; full orchestration is shared with evaluation for reproducibility."""

from data.pipeline import run_pipeline


def main() -> None:
    run_pipeline(quick=True)


if __name__ == "__main__":
    main()
