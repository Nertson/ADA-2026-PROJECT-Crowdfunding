"""Read the SEC Form D quarterly zips into pandas tables."""
from __future__ import annotations

import zipfile
from pathlib import Path

import pandas as pd

from src.cf_data import parse_dates

ROOT = Path(__file__).resolve().parents[1]
FORMD_DIR = ROOT / "data" / "raw" / "form_d"


def read_table(name: str, usecols: list[str] | None = None,
               formd_dir: Path = FORMD_DIR) -> pd.DataFrame:
    """Stack Form D table ``<name>.tsv`` (e.g. ``ISSUERS``) across all quarters, as str."""
    frames = []
    for path in sorted(formd_dir.glob("*_d*.zip")):
        with zipfile.ZipFile(path) as z:
            member = next(m for m in z.namelist() if m.endswith(f"/{name}.tsv"))
            with z.open(member) as f:
                df = pd.read_csv(f, sep="\t", dtype=str, keep_default_na=False, na_values=[""],
                                 quoting=3, encoding="utf-8", encoding_errors="replace",
                                 usecols=usecols)
        df["QUARTER"] = path.name[:6]
        frames.append(df)
    return pd.concat(frames, ignore_index=True)


def filings_by_cik() -> pd.DataFrame:
    """One row per (Form D filing, issuer CIK): accession, CIK, type, filing date.

    All issuers of a filing are kept (primary and co-issuers). Test filings are dropped.
    """
    sub = read_table("FORMDSUBMISSION",
                     ["ACCESSIONNUMBER", "FILING_DATE", "SUBMISSIONTYPE", "TESTORLIVE"])
    sub = sub[sub.TESTORLIVE.fillna("LIVE").str.upper() == "LIVE"]
    iss = read_table("ISSUERS", ["ACCESSIONNUMBER", "CIK", "IS_PRIMARYISSUER_FLAG"])
    out = iss.merge(sub.drop(columns="QUARTER"), on="ACCESSIONNUMBER")
    out["DATE"] = parse_dates(out.FILING_DATE.str.strip())
    out["CIK"] = out.CIK.str.strip().str.zfill(10)
    return out.drop_duplicates(["ACCESSIONNUMBER", "CIK"])
