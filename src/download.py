"""Download every raw input of the project. Filters nothing.

Sources
-------
1. SEC Crowdfunding Offerings Data Sets (Reg CF, 2016Q2 onwards), public domain.
2. SEC Form D Data Sets (2008 onwards), public domain. File names vary
   (``_0`` suffix, two URL prefixes), so links are scraped from the index page.
3. FRED series (CSV). Some are copyrighted (NASDAQCOM, UMCSENT): they are
   downloaded into data/raw/, which is gitignored, and never committed.

Files already on disk are skipped, so the script can be re-run safely.

Usage (from the repo root)::

    python -m src.download                # everything
    python -m src.download --only cf      # one source: cf | formd | fred
"""
from __future__ import annotations

import argparse
import re
import time
from datetime import date
from pathlib import Path
from urllib.parse import urljoin

import requests

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"

# The SEC requires a declared User-Agent and at most 10 requests per second.
SEC_HEADERS = {"User-Agent": "Arthur Pillet arthur.pillet@unil.ch"}
SEC_PAUSE = 0.15

CF_URL = "https://www.sec.gov/files/dera/data/crowdfunding-offerings-data-sets/{year}q{q}_cf.zip"
CF_FIRST = (2016, 2)
FORMD_INDEX = "https://www.sec.gov/dera/data/form-d"

FRED_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv?id={series}"
FRED_SERIES = ["CPIAUCSL", "FEDFUNDS", "NASDAQCOM", "UMCSENT", "BABATOTALSAUS", "VIXCLS"]


def _quarters(first: tuple[int, int], today: date) -> list[tuple[int, int]]:
    """All quarters from ``first`` to the last fully completed quarter."""
    last_year, last_q = today.year, (today.month - 1) // 3  # previous quarter
    if last_q == 0:
        last_year, last_q = last_year - 1, 4
    out, (y, q) = [], first
    while (y, q) <= (last_year, last_q):
        out.append((y, q))
        y, q = (y + 1, 1) if q == 4 else (y, q + 1)
    return out


def _fetch(url: str, dest: Path, headers: dict | None = None) -> bool:
    """Download ``url`` to ``dest`` unless it exists. Returns True if written."""
    if dest.exists() and dest.stat().st_size > 0:
        return False
    r = requests.get(url, headers=headers, timeout=120)
    if r.status_code == 404:
        print(f"  not published yet: {url}")
        return False
    r.raise_for_status()
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".part")
    tmp.write_bytes(r.content)
    tmp.rename(dest)
    print(f"  {dest.relative_to(ROOT)} ({len(r.content) / 1e6:.1f} MB)")
    return True


def download_crowdfunding(today: date | None = None) -> None:
    print("SEC Crowdfunding Offerings Data Sets")
    for y, q in _quarters(CF_FIRST, today or date.today()):
        url = CF_URL.format(year=y, q=q)
        if _fetch(url, RAW / "crowdfunding" / f"{y}q{q}_cf.zip", SEC_HEADERS):
            time.sleep(SEC_PAUSE)


def formd_links() -> list[str]:
    """Absolute URLs of every quarterly Form D zip listed on the SEC page."""
    html = requests.get(FORMD_INDEX, headers=SEC_HEADERS, timeout=60).text
    hrefs = re.findall(r'href="([^"]+?\d{4}q\d_d(?:_0)?\.zip)"', html, flags=re.I)
    return sorted({urljoin(FORMD_INDEX, h) for h in hrefs})


def download_formd() -> None:
    print("SEC Form D Data Sets")
    for url in formd_links():
        if _fetch(url, RAW / "form_d" / url.rsplit("/", 1)[-1], SEC_HEADERS):
            time.sleep(SEC_PAUSE)


def download_fred() -> None:
    print("FRED")
    for s in FRED_SERIES:
        _fetch(FRED_URL.format(series=s), RAW / "fred" / f"{s}.csv")


SOURCES = {"cf": download_crowdfunding, "formd": download_formd, "fred": download_fred}

if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--only", choices=SOURCES, help="download a single source")
    args = p.parse_args()
    for name, fn in SOURCES.items():
        if args.only in (None, name):
            fn()
