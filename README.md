# PyPI Maintainer Proxy Audit - Reproducibility Materials

This repository contains pseudonymised processed data and Python code for a decision-aware construct audit of PyPI maintainer proxies.

## Scope

The package supports analyses of:

- agreement between metadata-derived maintainer proxies and public PyPI Owner/Maintainer roles;
- fixed-budget project prioritisation under alternative constructs;
- construct-substitution regret and exact tie-robust regret intervals;
- sensitivity to deterministic, download-based, canonical-order and random tie resolution;
- ownership coverage, historical robustness and null-model checks.

The distributed tables use reviewer-facing pseudonymous project, account and metadata-identity identifiers. No mapping back to canonical project names or PyPI account names is included.

## Repository structure

```text
code/
  assemble_large_data.py
  decision_impact.py
  tiebreak_sensitivity.py
  reproduce.py
  derive_account_flags.py
data/
  account_flags.csv.gz
  download_ranks.csv.gz
  hist_metadata_proxy_edges_2024-07-05.csv.gz
  historical_sample_projects_2024-07-05.csv.gz
  journal_role_events.csv.gz
  projects_analysis.csv.gz
  metadata_proxy_edges.csv.gz.part000 ... part006
  roles.csv.gz.part000 ... part006
results/
  decision_impact_results.csv
  tiebreak_sensitivity_results.csv
  figure1_audit_budget_top15k.png
  figure2_tie_aware_exposure_tiers.png
  figure3_role_coverage_by_ownership.png
environment.yml
SHA256SUMS.txt
```

Two larger pseudonymised tables are stored in binary parts to avoid oversized single-file transfers. The assembly helper restores the exact original `.csv.gz` byte streams before analysis.

## Environment

```bash
conda env create -f environment.yml
conda activate pypi-construct-audit
```

## Assemble the larger data tables

Run once after cloning:

```bash
python code/assemble_large_data.py
```

This reconstructs:

- `data/metadata_proxy_edges.csv.gz`
- `data/roles.csv.gz`

## Reproduce the main analyses

```bash
python code/decision_impact.py
python code/tiebreak_sensitivity.py
python code/reproduce.py --null-R 1000
```

The null-model run is intentionally more computationally demanding than the main decision-impact analyses. A smaller `--null-R` value can be used for a smoke test.

## Expected exact regret intervals

| Audit budget k | Minimum regret | Maximum regret |
|---:|---:|---:|
| 100 | 0.347222005 | 0.347222005 |
| 500 | 0.109132780 | 0.109132780 |
| 1,000 | 0.176591528 | 0.178246738 |
| 2,500 | 0.178273612 | 0.178482070 |
| 5,000 | 0.132083710 | 0.134179464 |
| 10,000 | 0.083131654 | 0.095204941 |

## Data notes

- The popularity analysis uses 14,999 census-matched projects from an archived top-packages snapshot.
- Projects with zero exposure in both graphs remain in the decision universe.
- Monthly download counts are not the primary tie-break for the manuscript's fixed-budget analysis.
- The public package is intentionally pseudonymised and does not expose undistributed identity mappings.

## Integrity

`SHA256SUMS.txt` records hashes for the analysis files. After assembly, the reconstructed large tables should match those checksums.
