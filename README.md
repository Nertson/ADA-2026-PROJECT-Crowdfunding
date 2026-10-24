# Equity crowdfunding as a pipeline to institutional capital

Advanced Data Analytics, HEC Lausanne, autumn 2026 — Arthur Pillet.

Do the financials and terms disclosed in a U.S. Regulation Crowdfunding (Reg CF)
offering predict (1) whether the campaign reaches its target and (2) whether the
issuer raises a Regulation D round (Form D) within 24 months?

## Repository layout

| Path | Step |
|---|---|
| `src/download.py` | Downloads every raw input into `data/raw/` (filters nothing) |
| `src/cf_data.py`, `src/formd_data.py` | Read the SEC quarterly zips |
| `src/targets.py` | Builds the success and Form D targets |
| `notebooks/00_feasibility.ipynb` | Checks the data can support the research question |
| `data/processed/` | Small derived files |
| `paper/` | Paper (SIAM style) |

## Reproduce

```bash
pip install -r requirements.txt
python -m src.download          # ~210 MB, a few minutes
```

Then run the notebooks in order, each top to bottom in a fresh kernel.
`00_feasibility` takes about 1–2 minutes and under 4 GB of RAM.

## Data and licences

Raw data are not committed (size, licences); `src/download.py` fetches them.

- **SEC Crowdfunding Offerings Data Sets**, 2016Q2 onwards — <https://www.sec.gov/dera/data/crowdfunding-offerings-data-sets>. Public domain.
- **SEC Form D Data Sets**, 2008 onwards — <https://www.sec.gov/dera/data/form-d>. Public domain.
- **FRED** (Federal Reserve Bank of St. Louis) — CPIAUCSL, FEDFUNDS, BABATOTALSAUS (public domain); NASDAQCOM (© Nasdaq), UMCSENT (© University of Michigan), VIXCLS (© Cboe). Copyrighted series are downloaded for private use only and never committed.

SEC requests carry a declared User-Agent and stay under 10 requests per second, as the SEC requires.
