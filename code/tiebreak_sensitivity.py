#!/usr/bin/env python3
"""Sensitivity of fixed-budget results to within-exposure tie resolution."""
from pathlib import Path
import runpy
import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
G = runpy.run_path(str(HERE / "decision_impact.py"))
idxT, xa, xb, downloads, stable_hash = G["idxT"], G["xa"], G["xb"], G["downloads"], G["stable_hash"]
budgets = [100, 500, 1000, 2500, 5000, 10000]

def metrics(rankA, rankB, label):
    out = []
    for n in budgets:
        sa, sb = set(rankA[:n]), set(rankB[:n])
        missed = sb - sa
        capture = float(xb[list(sa)].sum() / xb[list(sb)].sum())
        dshare = float(downloads[list(missed)].sum() / downloads[list(sb)].sum())
        out.append([label, n, len(sa & sb) / n, len(missed), capture, dshare])
    return out

rows = []
rankA = idxT[np.lexsort((stable_hash[idxT], -xa[idxT]))]
rankB = idxT[np.lexsort((stable_hash[idxT], -xb[idxT]))]
rows += metrics(rankA, rankB, "stable_hash_primary")
rankA = idxT[np.lexsort((idxT, -downloads[idxT], -xa[idxT]))]
rankB = idxT[np.lexsort((idxT, -downloads[idxT], -xb[idxT]))]
rows += metrics(rankA, rankB, "downloads_tiebreak")
rankA = idxT[np.lexsort((idxT, -xa[idxT]))]
rankB = idxT[np.lexsort((idxT, -xb[idxT]))]
rows += metrics(rankA, rankB, "canonical_tiebreak")
for seed in range(20):
    rng = np.random.default_rng(20260812 + seed)
    rand = rng.integers(0, np.iinfo(np.uint64).max, size=len(xa), dtype=np.uint64)
    rankA = idxT[np.lexsort((rand[idxT], -xa[idxT]))]
    rankB = idxT[np.lexsort((rand[idxT], -xb[idxT]))]
    rows += metrics(rankA, rankB, f"random_{seed}")

cols = ["scheme", "budget", "agreement", "missed", "capture", "missed_download_share"]
df = pd.DataFrame(rows, columns=cols)
out = ROOT / "results" / "tiebreak_sensitivity_results.csv"
df.to_csv(out, index=False)
print(f"Tie-break sensitivity results: {out}")
print(df.groupby("budget").agg(agreement_min=("agreement","min"), agreement_max=("agreement","max"), capture_min=("capture","min"), capture_max=("capture","max"), missed_download_share_min=("missed_download_share","min"), missed_download_share_max=("missed_download_share","max")).to_string())