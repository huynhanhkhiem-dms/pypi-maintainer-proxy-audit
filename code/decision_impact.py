#!/usr/bin/env python3
"""Reproduce decision-impact analyses and manuscript figures from packaged data.

The script uses no network access. Fixed-budget point rankings use exposure as the
primary key and a deterministic SHA-256-derived project key only as a reproducible
within-score tie-break. Monthly downloads are reserved for a separate post-selection
diagnostic. Primary fixed-budget inference additionally reports the exact regret range
over every admissible proxy top-k set at a tied boundary.
"""
import csv, gzip, hashlib
from collections import defaultdict
from pathlib import Path
import numpy as np
from scipy.stats import spearmanr
import matplotlib.pyplot as plt

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
DATA = ROOT / 'data'
OUT = ROOT / 'results'
OUT.mkdir(exist_ok=True)


def read_gz(name):
    with gzip.open(DATA / name, 'rt', encoding='utf-8', newline='') as f:
        yield from csv.DictReader(f)


def get_id(mapping, key):
    if key not in mapping:
        mapping[key] = len(mapping)
    return mapping[key]


# Canonical project universe and organization ownership.
pidx = {}
pnames = []
org_owned = []
for row in read_gz('projects_analysis.csv.gz'):
    c = row['project_id']
    if c in pidx:
        continue
    pidx[c] = len(pidx)
    pnames.append(c)
    org_owned.append(row['organization_owned'] == '1')
N = len(pidx)
org_owned = np.asarray(org_owned, dtype=bool)

# Actor-project graphs.
account_map, proxy_map = {}, {}
A, B = defaultdict(set), defaultdict(set)
for row in read_gz('metadata_proxy_edges.csv.gz'):
    p = pidx.get(row['project_id'])
    if p is not None:
        A[get_id(proxy_map, row['proxy_id'])].add(p)
for row in read_gz('roles.csv.gz'):
    p = pidx.get(row['project_id'])
    if p is not None:
        B[get_id(account_map, row['account_id'])].add(p)

# Reverse neighborhoods and exposure vectors.
pA, pB = defaultdict(list), defaultdict(list)
for a, ps in A.items():
    for p in ps:
        pA[p].append(a)
for a, ps in B.items():
    for p in ps:
        pB[p].append(a)

degA = np.array([len(A[a]) for a in range(len(A))], dtype=np.int64)
degB = np.array([len(B[a]) for a in range(len(B))], dtype=np.int64)
xa = np.zeros(N, dtype=np.int64)
xb = np.zeros(N, dtype=np.int64)
for p, actors in pA.items():
    xa[p] = max(degA[a] for a in actors)
for p, actors in pB.items():
    xb[p] = max(degB[a] for a in actors)
mask = (xa > 0) | (xb > 0)
idx = np.where(mask)[0]
rho = float(spearmanr(xa[mask], xb[mask]).statistic)

rows = []
def add(group, metric, value, detail=''):
    rows.append({'analysis': group, 'metric': metric, 'value': value, 'detail': detail})

add('census', 'unique_canonical_projects', N)
add('agreement', 'spearman_rho', f'{rho:.4f}')

# Top-entity project sets.
topA = sorted(A, key=lambda a: len(A[a]), reverse=True)
topB = sorted(B, key=lambda a: len(B[a]), reverse=True)
for k in [10, 25, 50, 100, 250, 500, 1000, 2500, 5000, 10000]:
    ra, rb = set(), set()
    for a in topA[:k]:
        ra.update(A[a])
    for a in topB[:k]:
        rb.update(B[a])
    inter = len(ra & rb)
    union = len(ra | rb)
    add('top_entity', f'jaccard_k{k}', f'{inter/union:.6f}')
    add('top_entity', f'role_recall_k{k}', f'{inter/len(rb):.6f}')
    add('top_entity', f'role_projects_missed_k{k}', len(rb - ra))

# Boundary-tie sensitivity for the top-entity comparison. Exact-k actor lists are
# retained as the main descriptive convention. If the kth actor is tied in degree,
# this check includes every actor at the boundary and reports the resulting project set.
def tie_aware_actor_project_set(adj, k):
    deg_actor = sorted(((len(ps), a) for a, ps in adj.items()), reverse=True)
    cutoff = deg_actor[k - 1][0]
    actors = [a for d, a in deg_actor if d >= cutoff]
    projects = set()
    for a in actors:
        projects.update(adj[a])
    return cutoff, len(actors), projects

for k in [10, 25, 50, 100]:
    cut_a, n_a, sa = tie_aware_actor_project_set(A, k)
    cut_b, n_b, sb = tie_aware_actor_project_set(B, k)
    inter = len(sa & sb); union = len(sa | sb)
    add('entity_boundary_tie_sensitivity', f'k{k}_graphA_actor_count', n_a)
    add('entity_boundary_tie_sensitivity', f'k{k}_graphB_actor_count', n_b)
    add('entity_boundary_tie_sensitivity', f'k{k}_jaccard', f'{inter/union:.6f}')

# Download counts and top-15k indicator. This archived table is the exact input used
# in the study; it originates from the Top PyPI Packages monthly dump.
downloads = np.zeros(N, dtype=np.int64)
is_top = np.zeros(N, dtype=bool)
for row in read_gz('download_ranks.csv.gz'):
    p = pidx.get(row['project_id'])
    if p is not None:
        is_top[p] = True
        downloads[p] = int(float(row['download_count']))

# Tie-aware full-census high-exposure tiers. For a nominal percentile q, the score at
# the q-th ranked project defines the cutoff independently in each graph; every project
# tied at that score is included. Set sizes may therefore differ across graphs.
tier_labels, tier_jaccard = [], []
for pct in [0.01, 0.05, 0.10, 0.20]:
    nominal = int(round(len(idx) * pct))
    a_sorted = np.sort(xa[idx])[::-1]
    b_sorted = np.sort(xb[idx])[::-1]
    cut_a = int(a_sorted[nominal - 1])
    cut_b = int(b_sorted[nominal - 1])
    sa = set(idx[xa[idx] >= cut_a])
    sb = set(idx[xb[idx] >= cut_b])
    inter = len(sa & sb)
    union = len(sa | sb)
    jac = inter / union
    label = f'{int(pct*100)}pct'
    add('tier_tie_aware', f'{label}_nominal_projects', nominal)
    add('tier_tie_aware', f'{label}_graphA_cutoff', cut_a)
    add('tier_tie_aware', f'{label}_graphB_cutoff', cut_b)
    add('tier_tie_aware', f'{label}_graphA_set_size', len(sa))
    add('tier_tie_aware', f'{label}_graphB_set_size', len(sb))
    add('tier_tie_aware', f'{label}_jaccard', f'{jac:.6f}')
    add('tier_tie_aware', f'{label}_graphA_only', len(sa - sb))
    add('tier_tie_aware', f'{label}_graphB_only', len(sb - sa))
    add('tier_tie_aware', f'{label}_symmetric_difference', len(sa ^ sb))
    tier_labels.append(f'{int(pct*100)}%')
    tier_jaccard.append(jac)

# Popular-project fixed-budget prioritization. Exposure is the primary key. A stable
# SHA-256-derived key over the reviewer-facing project ID resolves exposure ties in the
# main analysis. This key is independent of download volume, which is reserved for the
# separate popularity diagnostic. Alternative download, canonical-order, and common-
# random tie schemes are evaluated in tiebreak_sensitivity.py.
idxT = np.where(is_top)[0]
stable_hash = np.zeros(N, dtype=np.uint64)
for p in idxT:
    stable_hash[p] = int.from_bytes(hashlib.sha256(pnames[p].encode('utf-8')).digest()[:8], 'big')
rankAT = idxT[np.lexsort((stable_hash[idxT], -xa[idxT]))]
rankBT = idxT[np.lexsort((stable_hash[idxT], -xb[idxT]))]
budgets = [100, 500, 1000, 2500, 5000, 10000]
budget_agreement, budget_capture = [], []
for n0 in budgets:
    n = min(n0, len(idxT))
    sa = set(rankAT[:n])
    sb = set(rankBT[:n])
    inter = len(sa & sb)
    # Reference-construct capture: how much Graph-B exposure is captured by the
    # metadata-selected list relative to the Graph-B-selected list under equal budget.
    capture = float(xb[list(sa)].sum() / xb[list(sb)].sum())
    missed = sb - sa
    missed_download_share = float(downloads[list(missed)].sum() / downloads[list(sb)].sum())
    agreement = inter / n
    add('top15k_budget', f'budget{n}_list_agreement', f'{agreement:.6f}')
    add('top15k_budget', f'budget{n}_role_projects_missed', len(missed))
    add('top15k_budget', f'budget{n}_role_exposure_capture_ratio', f'{capture:.6f}')
    add('top15k_budget', f'budget{n}_missed_download_share', f'{missed_download_share:.6f}')

    # Exact tie-robust construct-substitution regret interval. All projects strictly
    # above the Graph-A cutoff are fixed. The remaining positions are filled from the
    # boundary plateau. Reference utility extrema are obtained by selecting the
    # smallest/largest Graph-B exposures on that plateau.
    a_sorted = np.sort(xa[idxT])[::-1]
    cutoff = int(a_sorted[n - 1])
    fixed = idxT[xa[idxT] > cutoff]
    plateau = idxT[xa[idxT] == cutoff]
    r = n - len(fixed)
    ref_opt = int(np.sort(xb[idxT])[::-1][:n].sum())
    fixed_u = int(xb[fixed].sum())
    plateau_b = np.sort(xb[plateau])
    min_u = fixed_u + int(plateau_b[:r].sum())
    max_u = fixed_u + int(plateau_b[-r:].sum())
    regret_min = 1.0 - (max_u / ref_opt)
    regret_max = 1.0 - (min_u / ref_opt)
    add('top15k_exact_regret', f'budget{n}_proxy_cutoff', cutoff)
    add('top15k_exact_regret', f'budget{n}_boundary_plateau', len(plateau))
    add('top15k_exact_regret', f'budget{n}_positions_on_plateau', r)
    add('top15k_exact_regret', f'budget{n}_regret_min', f'{regret_min:.9f}')
    add('top15k_exact_regret', f'budget{n}_regret_max', f'{regret_max:.9f}')

    budget_agreement.append(agreement)
    budget_capture.append(capture)

# Project-ownership coverage of the registry user-role relation. This analysis is fully
# reproducible from projects_analysis.csv.gz and roles.csv.gz and does not require any
# heuristic account classification.
has_role = np.zeros(N, dtype=bool)
for _, ps in B.items():
    for p in ps:
        has_role[p] = True
for label, keep in [('organization_owned', org_owned), ('individually_owned', ~org_owned)]:
    n = int(keep.sum())
    no_role = int((keep & ~has_role).sum())
    add('role_coverage', f'{label}_projects', n)
    add('role_coverage', f'{label}_no_individual_role', no_role)
    add('role_coverage', f'{label}_no_individual_role_share', f'{no_role/n:.6f}')

# Optional account-type strata retained for robustness. Flags are derived before
# pseudonymization with the documented heuristic in derive_account_flags.py.
flagraw = {}
for row in read_gz('account_flags.csv.gz'):
    flagraw[row['account_id']] = (
        row['is_bot_automation'] == '1',
        row['is_organization_associated'] == '1'
    )
inv_account = {v: k for k, v in account_map.items()}
cat_counts = defaultdict(lambda: [0, 0, 0, 0])
for p in idx:
    actors = pB.get(int(p), [])
    if not actors:
        cat = 'no-role'
    else:
        maxd = max(degB[a] for a in actors)
        tops = [a for a in actors if degB[a] == maxd]
        flags = [flagraw.get(inv_account[a], (False, False)) for a in tops]
        if any(b for b, o in flags):
            cat = 'bot/automation'
        elif any(o for b, o in flags):
            cat = 'organization-associated'
        else:
            cat = 'individual'
    d = int(xa[p]) - int(xb[p])
    rec = cat_counts[cat]
    rec[0] += 1
    if d < 0:
        rec[1] += 1
    elif d > 0:
        rec[2] += 1
    if d <= -100:
        rec[3] += 1
for cat in ['individual', 'organization-associated', 'bot/automation', 'no-role']:
    n, under, over, severe = cat_counts[cat]
    add('exploratory_account_strata', f'{cat}_projects', n)
    if n:
        add('exploratory_account_strata', f'{cat}_metadata_lower_share', f'{under/n:.6f}')
        add('exploratory_account_strata', f'{cat}_metadata_higher_share', f'{over/n:.6f}')
        add('exploratory_account_strata', f'{cat}_underestimate_ge100_share', f'{severe/n:.6f}')

# Machine-readable results.
out_csv = OUT / 'decision_impact_results.csv'
with out_csv.open('w', newline='', encoding='utf-8') as f:
    w = csv.DictWriter(f, fieldnames=['analysis', 'metric', 'value', 'detail'])
    w.writeheader()
    w.writerows(rows)

# Manuscript figures.
plt.figure(figsize=(7.2, 4.5))
plt.plot(budgets, budget_agreement, marker='o', label='List agreement')
plt.plot(budgets, budget_capture, marker='s', label='Role-exposure capture ratio')
plt.xscale('log')
plt.ylim(0.5, 1.02)
plt.xlabel('Project audit budget N (top 15 000 by downloads)')
plt.ylabel('Proportion')
plt.legend()
plt.tight_layout()
plt.savefig(OUT / 'figure1_audit_budget_top15k.png', dpi=300)
plt.close()

plt.figure(figsize=(7.2, 4.5))
bars = plt.bar(tier_labels, tier_jaccard)
plt.ylim(0.45, 0.95)
plt.xlabel('Nominal high-exposure tier')
plt.ylabel('Tie-aware Jaccard agreement')
for b, v in zip(bars, tier_jaccard):
    plt.text(b.get_x() + b.get_width()/2, v + 0.008, f'{v:.3f}', ha='center')
plt.tight_layout()
plt.savefig(OUT / 'figure2_tie_aware_exposure_tiers.png', dpi=300)
plt.close()

labels = ['Individually owned', 'Organization owned']
shares = [float(((~org_owned) & ~has_role).sum() / (~org_owned).sum()),
          float((org_owned & ~has_role).sum() / org_owned.sum())]
plt.figure(figsize=(7.2, 4.5))
bars = plt.bar(labels, shares)
plt.ylim(0, 0.65)
plt.ylabel('Projects with no individual user role')
for b, v in zip(bars, shares):
    plt.text(b.get_x() + b.get_width()/2, v + 0.015, f'{v:.1%}', ha='center')
plt.tight_layout()
plt.savefig(OUT / 'figure3_role_coverage_by_ownership.png', dpi=300)
plt.close()

print(f'Unique canonical projects: {N}')
print(f'Spearman rho: {rho:.4f}')
print(f'Decision-impact results: {out_csv}')
print(f'Figures: {OUT}')