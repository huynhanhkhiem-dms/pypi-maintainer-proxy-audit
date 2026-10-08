# PyPI Maintainer Proxy Audit — Reproducibility Materials

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
  prepare_data.py
  decision_impact.py
  tiebreak_sensitivity.py
  reproduce.py
  derive_account_flags.py
data/
  account_flags.csv.gz
  download_ranks.csv.gz
  hist_metadata_proxy_edges_2024-07-05.csv.gz
  historical_sample_projects_2024-07-05.csv.gz
  projects_analysis.csv.gz
data_encoded/
  metadata_proxy_edges.csv.gz.part*.b64
  roles.csv.gz.part*.b64
  journal_role_events.csv.gz.part*.b64
results/
  decision_impact_results.csv
  tiebreak_sensitivity_results.csv
  figure*.png
environment.yml
SHA256SUMS.txt
```

Three larger pseudonymised tables are stored as Base64 parts so the repository remains compatible with normal GitHub file-transfer limits. The reconstruction script restores the exact original `.csv.gz` bytes and verifies their SHA-256 hashes.

## Environment

Create the pinned Conda environment:

```bash
conda env create -f environment.yml
conda activate pypi-construct-audit
```

## Prepare the larger data tables

Run once after cloning:

```bash
python code/prepare_data.py
```

This reconstructs:

- `data/metadata_proxy_edges.csv.gz`
- `data/roles.csv.gz`
- `data/journal_role_events.csv.gz`

The script stops if any reconstructed file fails its expected SHA-256 checksum.

## Reproduce the main analyses

```bash
python code/decision_impact.py
python code/tiebreak_sensitivity.py
python code/reproduce.py --null-R 1000
```

The null-model run is intentionally computationally heavier than the main decision-impact analyses. A smaller `--null-R` value can be used for a smoke test, but manuscript-level null results should use the stated replication count.

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
- Projects with zero exposure in both graphs remain in the decision universe; they do not affect the reported positive cutoffs.
- Monthly download counts are not the primary tie-break for the manuscript's fixed-budget analysis.
- The public package is intentionally pseudonymised and does not expose undistributed identity mappings.

## Integrity

`SHA256SUMS.txt` records the hashes of the analysis files. The three reconstructed larger tables are checked automatically by `code/prepare_data.py`.
