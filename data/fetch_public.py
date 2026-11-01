"""Probe candidate public data sources without presenting them as purifier evidence."""

from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
SOURCES = {
    "NASA_CMAPSS_catalog": "https://catalog.data.gov/dataset/c-mapss-aircraft-engine-simulator-data",
    "NASA_CMAPSS_archive": "https://phm-datasets.s3.amazonaws.com/NASA/6.+Turbofan+Engine+Degradation+Simulation+Data+Set.zip",
    "CGWB_quality_catalog": "https://www.nwdp.nwic.gov.in/dataset/ground-water-quality-manual-chemical-parameters-cgwb-f-gfg",
    "RO_fouling_candidate": "https://www.mdpi.com/2673-4117/6/5/98",
}


def probe() -> dict:
    results: dict[str, dict[str, object]] = {}
    report: dict[str, object] = {"checked_on": date.today().isoformat(), "results": results}
    for name, url in SOURCES.items():
        try:
            request = Request(
                url, headers={"User-Agent": "FilterTwin-data-probe/1.0", "Range": "bytes=0-0"}
            )
            with urlopen(request, timeout=12) as response:
                results[name] = {
                    "url": url,
                    "http_status": response.status,
                    "final_url": response.geturl(),
                    "content_type": response.headers.get("content-type"),
                    "content_length": response.headers.get("content-length"),
                    "license": "not verified",
                    "downloaded": False,
                    "probe": "HTTP range/header reachability only; no dataset file imported",
                }
        except HTTPError as exc:
            results[name] = {
                "url": url,
                "http_status": exc.code,
                "final_url": exc.geturl(),
                "error": str(exc),
                "license": "not verified",
                "downloaded": False,
            }
        except (URLError, TimeoutError, OSError) as exc:
            results[name] = {
                "url": url,
                "status": "unavailable in this run",
                "error": str(exc),
                "license": "not verified",
                "downloaded": False,
            }
    target = ROOT / "results" / "public_fetch.json"
    target.parent.mkdir(exist_ok=True)
    target.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--probe", action="store_true", help="check source reachability without importing data"
    )
    args = parser.parse_args()
    if args.probe:
        print(json.dumps(probe(), indent=2))
    else:
        parser.error("pass --probe; data import requires manual license and schema review")


if __name__ == "__main__":
    main()
