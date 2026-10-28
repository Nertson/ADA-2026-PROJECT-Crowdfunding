# AI usage log

Used to write the paper's appendix (tool declaration). One line per task.

| Date | Tool | Task | Files |
|---|---|---|---|
| 2026-10-24 | Claude Code (Claude Opus 5.5) | Repo skeleton, `src/download.py`, `src/cf_data.py`, feasibility checks script | `.gitignore`, `requirements.txt`, `src/`, `reports/feasibility.md` |
| 2026-10-24 | Claude Code (Claude Opus 5.5) | C-U text parser and target construction (`src/targets.py`), Form D reader, feasibility notebook, README, proposal draft | `src/targets.py`, `src/formd_data.py`, `notebooks/00_feasibility.ipynb`, `README.md`, `reports/proposal_draft.md` |
| 2026-10-28 | Claude Code (Claude Opus 5.5) | Fix readers for quarters missing a table, plausibility flags on targets/deadlines, `02_clean` notebook persisting the offering table, protect the manual-check file | `src/cf_data.py`, `src/formd_data.py`, `src/targets.py`, `notebooks/02_clean.ipynb`, `notebooks/00_feasibility.ipynb` |
| 2026-10-28 | Claude Code (Claude Opus 5.5) | Notebooks locate the repo root robustly (ModuleNotFoundError on src) | `notebooks/00_feasibility.ipynb`, `notebooks/02_clean.ipynb` |
