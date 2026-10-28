"""Build the campaign-success target from Form C-U progress updates.

The data sets have no "amount raised" field. A C-U's PROGRESSUPDATE is a free
text of at most 256 characters, usually stating the amount closed on
("At the close of the offering, the issuer closed on $52,410 and 11,254
securities") or a percentage of the target ("100% of target amount").
"""
from __future__ import annotations

import re

import numpy as np
import pandas as pd

_NUM = r"\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?"
_MONEY = re.compile(
    rf"(?P<dollar>\$|USD\s?)?\s?(?<![A-Za-z\d.,])(?P<num>{_NUM})\s?(?P<mult>million|mm|m\b|k\b|thousand)?",
    flags=re.I,
)
_PCT = re.compile(rf"(?P<num>{_NUM})\s?%")
_MONTHS = r"(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?"
# A number followed by one of these words is a count or a unit price, not the amount raised.
_NOT_MONEY_AFTER = re.compile(
    r"^\s*(?:number of\s+)?(?:securit|share|unit|note|investor|token|day|per\b|each\b|%)", re.I)

# Statements of outcome without a number. Failure patterns are checked first,
# because "unsuccessfully" contains "successfully".
_FAIL = re.compile(
    r"unsuccess|not (?:been )?(?:met|reach|achiev|successful)|did not|didn't|failed|fail to"
    r"|not able to (?:meet|reach)|cancel|terminat|refund|returned to (?:the )?investors"
    r"|be(?:ing)? returned|no (?:funds|investments) (?:were )?raised",
    re.I)
_SUCCESS = re.compile(
    r"(?:reached|met|achieved|exceeded|surpassed|hit|reach|raised) (?:its |the |our )?(?:minimum|target|maximum|goal)"
    r"|(?:target|minimum|goal)(?: offering)?(?: amount)? (?:was |has been )?(?:met|reached|achieved|exceeded)"
    r"|closed successfully|successfully (?:closed|completed|funded|reach)",
    re.I)
_MULT = {"million": 1e6, "mm": 1e6, "m": 1e6, "k": 1e3, "thousand": 1e3}


def _is_date_part(text: str, start: int, end: int) -> bool:
    before, after = text[max(0, start - 12):start], text[end:end + 1]
    if after == "/" or before.endswith("/") or before.endswith("-"):
        return True
    if re.search(rf"{_MONTHS}\s*$", before, flags=re.I):  # "April 24"
        return True
    if re.search(rf"{_MONTHS}\s*\d{{1,2}},\s*$", before, flags=re.I):  # "April 24, 2021"
        return True
    return False


def parse_amount(text: str | float) -> float:
    """Dollar amount stated in a progress update, NaN if none.

    Picks the first number written with a ``$`` sign; otherwise the first
    number that is not part of a date, a percentage or a count of securities.
    """
    if not isinstance(text, str):
        return np.nan
    plain = None
    for m in _MONEY.finditer(text):
        if _is_date_part(text, m.start("num"), m.end("num")):
            continue
        if _NOT_MONEY_AFTER.match(text[m.end():]):
            continue
        value = float(m["num"].replace(",", ""))
        if m["mult"]:
            value *= _MULT[m["mult"].lower()]
        if m["dollar"]:
            return value
        if plain is None:
            plain = value
    return np.nan if plain is None else plain


def parse_percent(text: str | float) -> float:
    """Highest percentage of the target stated in a progress update, NaN if none.

    The highest, because one update often reports both thresholds
    ("50% and 100% of target amount reached").
    """
    if not isinstance(text, str):
        return np.nan
    found = [float(m["num"].replace(",", "")) for m in _PCT.finditer(text)]
    return max(found) if found else np.nan


def parse_outcome(text: str | float) -> float:
    """1 / 0 when the text states success / failure in words, NaN otherwise."""
    if not isinstance(text, str):
        return np.nan
    if _FAIL.search(text):
        return 0.0
    if _SUCCESS.search(text):
        return 1.0
    return np.nan


def success_from_update(text: pd.Series, target: pd.Series) -> pd.DataFrame:
    """Amount, percentage and success flag (1/0/NaN) for each progress update.

    Success = stated amount >= target, else stated percentage >= 100, else an
    explicit statement in words. NaN when the text gives none of these.
    ``SOURCE`` records which rule decided.
    """
    amount = text.map(parse_amount)
    pct = text.map(parse_percent)
    words = text.map(parse_outcome)
    ratio = amount / target.astype(float)
    success = pd.Series(np.nan, index=text.index)
    source = pd.Series(pd.NA, index=text.index, dtype="string")
    for name, flag in [("amount", ratio >= 1), ("percent", pct >= 100), ("words", words == 1)]:
        known = {"amount": ratio, "percent": pct, "words": words}[name].notna()
        fill = success.isna() & known
        success[fill] = flag[fill].astype(float)
        source[fill] = name
    return pd.DataFrame({"AMOUNT_STATED": amount, "PCT_STATED": pct, "OUTCOME_WORDS": words,
                         "RATIO_TO_TARGET": ratio, "SUCCESS_CU": success, "SOURCE": source})


# Plausibility bounds for offering terms. Targets under $1,000 are typos
# (e.g. $0.01, $1); campaigns can be extended by amendment, but beyond three
# years the deadline is a typo (e.g. 2032 for 2023).
MIN_TARGET = 1_000
MAX_CAMPAIGN_DAYS = 3 * 365


def build_offerings(sub: pd.DataFrame, dis: pd.DataFrame, iss: pd.DataFrame) -> pd.DataFrame:
    """One row per Reg CF offering (FILE_NUMBER) with its terms and success flag.

    Inputs are the stacked SUBMISSION, DISCLOSURE and ISSUER_INFORMATION tables
    from ``src.cf_data.read_table``. Terms (target, deadline) come from the
    latest C or C/A. ``Y_SUCCESS`` is 1 if any C-U reports the target reached;
    0 if the last *final* C-U (filed on/after the deadline, or stating $0 or a
    failure in words) reports less, or if the Form C was withdrawn (C-W);
    NaN otherwise. ``Y_SOURCE`` says which.

    Implausible terms are flagged, not dropped (dropping is a cleaning
    decision): ``TARGET_SUSPECT`` (target below MIN_TARGET or missing) and
    ``DEADLINE_SUSPECT`` (deadline missing, before the Form C, or more than
    MAX_CAMPAIGN_DAYS after it). A suspect target is not used to judge success.
    """
    from src.cf_data import parse_dates

    f = sub.assign(DATE=parse_dates(sub.FILING_DATE))
    f = f.merge(dis[["ACCESSION_NUMBER", "OFFERINGAMOUNT", "DEADLINEDATE"]],
                on="ACCESSION_NUMBER", how="left")
    f = f.merge(iss[["ACCESSION_NUMBER", "PROGRESSUPDATE"]], on="ACCESSION_NUMBER", how="left")
    f["DEADLINE"] = parse_dates(f.DEADLINEDATE)
    f["OFFERINGAMOUNT"] = pd.to_numeric(f.OFFERINGAMOUNT, errors="coerce")
    f = f.sort_values(["FILE_NUMBER", "DATE", "ACCESSION_NUMBER"])

    terms = (f[f.SUBMISSION_TYPE.isin(["C", "C/A"])].groupby("FILE_NUMBER")
             .agg(TARGET=("OFFERINGAMOUNT", "last"), DEADLINE=("DEADLINE", "last")))
    off = (f[f.SUBMISSION_TYPE == "C"].drop_duplicates("FILE_NUMBER")
           .set_index("FILE_NUMBER")[["CIK", "ACCESSION_NUMBER", "DATE"]]
           .rename(columns={"DATE": "C_DATE"}).join(terms))
    off["CIK"] = off.CIK.str.zfill(10)
    off["WITHDRAWN"] = off.index.isin(f.loc[f.SUBMISSION_TYPE == "C-W", "FILE_NUMBER"])
    days = (off.DEADLINE - off.C_DATE).dt.days
    off["TARGET_SUSPECT"] = ~(off.TARGET >= MIN_TARGET)
    off["DEADLINE_SUSPECT"] = ~days.between(0, MAX_CAMPAIGN_DAYS)

    cu = f[f.SUBMISSION_TYPE == "C-U"][["FILE_NUMBER", "DATE", "PROGRESSUPDATE"]]
    cu = cu.join(off[["TARGET", "DEADLINE"]], on="FILE_NUMBER")
    usable_target = cu.TARGET.where(cu.TARGET >= MIN_TARGET)
    cu = pd.concat([cu, success_from_update(cu.PROGRESSUPDATE, usable_target).set_index(cu.index)], axis=1)
    cu["FINAL"] = (cu.DATE >= cu.DEADLINE) | (cu.OUTCOME_WORDS == 0) | (cu.AMOUNT_STATED == 0)

    off["N_CU"] = cu.groupby("FILE_NUMBER").size().reindex(off.index, fill_value=0)
    any_success = cu.groupby("FILE_NUMBER").SUCCESS_CU.max().reindex(off.index)
    last_final = cu[cu.FINAL].dropna(subset=["SUCCESS_CU"]).groupby("FILE_NUMBER").SUCCESS_CU.last()
    last_final = last_final.reindex(off.index)
    off["AMOUNT_RAISED"] = cu.dropna(subset=["AMOUNT_STATED"]).groupby("FILE_NUMBER").AMOUNT_STATED.last()

    off["Y_SUCCESS"] = np.nan
    off["Y_SOURCE"] = pd.Series(pd.NA, index=off.index, dtype="string")
    rules = [("C-U success", any_success == 1), ("C-U final failure", last_final == 0),
             ("withdrawn", off.WITHDRAWN)]
    for name, mask in rules:
        fill = off.Y_SUCCESS.isna() & mask
        off.loc[fill, "Y_SUCCESS"] = 0.0 if name != "C-U success" else 1.0
        off.loc[fill, "Y_SOURCE"] = name
    return off


def add_annual_reports(off: pd.DataFrame, sub: pd.DataFrame, months: int = 18) -> pd.DataFrame:
    """Flag ``AR_AFTER``: the issuer filed a C-AR within ``months`` after the deadline.

    A C-AR is filed by the issuer, not for one offering, so this is a proxy.
    Offerings without a deadline use the Form C date + 120 days.
    """
    from src.cf_data import parse_dates

    ar = sub[sub.SUBMISSION_TYPE.isin(["C-AR", "C-AR/A"])]
    ar = pd.DataFrame({"CIK": ar.CIK.str.zfill(10), "AR_DATE": parse_dates(ar.FILING_DATE)})
    end = off.DEADLINE.fillna(off.C_DATE + pd.Timedelta(days=120))
    m = pd.DataFrame({"FILE_NUMBER": off.index, "CIK": off.CIK.values, "END": end.values}).merge(ar, on="CIK")
    hit = (m.AR_DATE > m.END) & (m.AR_DATE <= m.END + pd.DateOffset(months=months))
    return off.assign(AR_AFTER=off.index.isin(m.loc[hit, "FILE_NUMBER"]))


def add_formd(off: pd.DataFrame, formd: pd.DataFrame, months: int = 24) -> pd.DataFrame:
    """Flag Form D filings (new notices, type D) by the same CIK relative to the campaign.

    ``FD_BEFORE``: filed before the Form C; ``FD_DURING``: between the Form C and the
    deadline (parallel offering, not follow-on); ``Y_FORMD``: within ``months`` after
    the deadline. ``FD_WINDOW_COMPLETE`` is False when the window extends past the data.
    """
    fd = formd[formd.SUBMISSIONTYPE == "D"][["CIK", "DATE"]]
    end = off.DEADLINE.fillna(off.C_DATE + pd.Timedelta(days=120))
    m = pd.DataFrame({"FILE_NUMBER": off.index, "CIK": off.CIK.values,
                      "START": off.C_DATE.values, "END": end.values}).merge(fd, on="CIK")
    flags = {
        "FD_BEFORE": m.DATE < m.START,
        "FD_DURING": (m.DATE >= m.START) & (m.DATE <= m.END),
        "Y_FORMD": (m.DATE > m.END) & (m.DATE <= m.END + pd.DateOffset(months=months)),
    }
    off = off.assign(**{k: off.index.isin(m.loc[v, "FILE_NUMBER"]) for k, v in flags.items()})
    off["FD_WINDOW_COMPLETE"] = end + pd.DateOffset(months=months) <= formd.DATE.max()
    return off
