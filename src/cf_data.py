"""Read the SEC Crowdfunding Offerings quarterly zips into pandas tables."""
from __future__ import annotations

import warnings
import zipfile
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
CF_DIR = ROOT / "data" / "raw" / "crowdfunding"

TABLES = [
    "SUBMISSION",
    "DISCLOSURE",
    "ISSUER_INFORMATION",
    "ISSUER_JURISDICTIONS",
    "COISSUER_INFORMATION",
    "ISSUER_SIGNATURE",
    "SIGNATURE",
]


def read_table(name: str, cf_dir: Path = CF_DIR) -> pd.DataFrame:
    """Stack table ``FORM_C_<name>`` across all quarters, everything as str.

    A ``QUARTER`` column (e.g. ``2021q3``) records the source file. Values are
    left as strings: date formats differ across quarters and are parsed later.
    Quarters whose zip lacks the table (COISSUER_INFORMATION before 2021) are
    skipped with a warning.
    """
    frames, missing = [], []
    for path in sorted(cf_dir.glob("*_cf.zip")):
        with zipfile.ZipFile(path) as z:
            member = next((m for m in z.namelist() if m.endswith(f"FORM_C_{name}.tsv")), None)
            if member is None:
                missing.append(path.name[:6])
                continue
            with z.open(member) as f:
                df = pd.read_csv(f, sep="\t", dtype=str, keep_default_na=False,
                                 na_values=[""], quoting=3, encoding="utf-8")
        df["QUARTER"] = path.name[:6]
        frames.append(df)
    return _stack(frames, missing, f"FORM_C_{name}")


def _stack(frames: list[pd.DataFrame], missing: list[str], name: str) -> pd.DataFrame:
    """Concatenate per-quarter frames, warning about quarters without the table."""
    if not frames:
        raise FileNotFoundError(f"{name}.tsv is in none of the zips")
    if missing:
        warnings.warn(f"{name}.tsv absent from {len(missing)} quarter(s): {', '.join(missing)}",
                      stacklevel=3)
    return pd.concat(frames, ignore_index=True)


def parse_dates(s: pd.Series) -> pd.Series:
    """Parse the mixed date formats found in the data (YYYYMMDD, YYYY-MM-DD, MM-DD-YYYY...)."""
    s = s.astype("string").str.strip()
    out = pd.to_datetime(s, format="%Y%m%d", errors="coerce")
    for fmt in ("%Y-%m-%d", "%m-%d-%Y", "%m/%d/%Y", "%d-%b-%Y", "%Y-%m-%d %H:%M:%S"):
        miss = out.isna() & s.notna()
        if not miss.any():
            break
        out[miss] = pd.to_datetime(s[miss], format=fmt, errors="coerce")
    return out


def base_type(t: pd.Series) -> pd.Series:
    """Strip the withdrawal suffix: ``C-U-W`` -> ``C-U``."""
    return t.str.replace(r"-W$", "", regex=True)
