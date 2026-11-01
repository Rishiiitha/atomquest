"""Evaluation entry point; generates and validates frozen pipeline outputs."""

from data.pipeline import run_pipeline


def main() -> None:
    run_pipeline(full=True)


if __name__ == "__main__":
    main()
