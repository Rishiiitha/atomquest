"""Run the local API server."""

import uvicorn


def main() -> None:
    uvicorn.run("api.app:app", host="127.0.0.1", port=8000, reload=False, log_level="warning")


if __name__ == "__main__":
    main()
