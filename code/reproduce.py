#!/usr/bin/env python3
"""Reproduce the reported PyPI role-measurement results from the packaged data.

No network access is used. Identifiers for PyPI accounts and metadata identities
are pseudonymized in the distributed tables. Project names are also replaced
with stable reviewer-facing project identifiers; the mapping is not distributed.
"""
import argparse, csv, gzip, os, sys, time
from collections import defaultdict
import numpy as np
from scipy.stats import spearmanr

HERE = os.path.dirname(os.path.abspath(__file__))
DATA_CANDIDATES = (os.path.join(HERE, '..', 'data'), os.path.join(HERE, 'data'), 'data')
DATA = next((os.path.abspath(p) for p in DATA_CANDIDATES if os.path.isdir(p)), None)
if DATA is None:
    sys.exit('Data directory not found.')

KS = (10, 25, 50, 100)
SEED = 20260812
ANCHOR = '2024-07-05'

parser = argparse.ArgumentParser()
parser.add_argument('--null-R', type=int, default=1000, help='Number of null replications (default: 1000)')
parser.add_argument('--null-only', action='store_true', help='Run census + null analysis only')
args = parser.parse_args()
rng = np.random.default_rng(SEED)
t0 = time.time()

def read_gz(name):
    path = os.path.join(DATA, name)
    if not os.path.exists(path):
        sys.exit(f'Missing required file: {path}')
    with gzip.open(path, 'rt', encoding='utf-8', newline='') as fh:
        yield from csv.DictReader(fh)

def adjacency(edges, keep_entity=None, keep_project=None):
    out = defaultdict(set)
    for e, p in edges:
        if keep_entity is not None and not keep_entity[e]:
            continue
        if keep_project is not None and not keep_project[p]:
            continue
        out[e].add(p)
    return out

def top_coverage(adj, k):
    groups = sorted(adj.values(), key=len, reverse=True)[:k]
    return set().union(*groups) if groups else set()

def jaccard(a, b):
    u = len(a | b)
    return len(a & b) / u if u else float('nan')

def overlap(a, b):
    m = min(len(a), len(b))
    return len(a & b) / m if m else float('nan')

def exposure(adj, n):
    x = np.zeros(n, dtype=np.int64)
    for ps in adj.values():
        if not ps:
            continue
        idx = np.fromiter(ps, dtype=np.int64, count=len(ps))
        np.maximum.at(x, idx, len(ps))
    return x

def compare(adj_a, adj_b, n, label, quiet=False):
    js = []
    if not quiet:
        print(f'\n{label}')
        print(f'{"k":>5}{"Jaccard":>11}{"Overlap":>11}{"cover A":>11}{"cover B":>11}')
    for k in KS:
        ca, cb = top_coverage(adj_a, k), top_coverage(adj_b, k)
        js.append(jaccard(ca, cb))
        if not quiet:
            print(f'{k:>5}{jaccard(ca, cb):>11.3f}{overlap(ca, cb):>11.3f}{len(ca):>11,}{len(cb):>11,}')
    xa, xb = exposure(adj_a, n), exposure(adj_b, n)
    mask = (xa > 0) | (xb > 0)
    rho = spearmanr(xa[mask], xb[mask]).statistic
    if not quiet:
        print(f'Spearman rho = {rho:.4f} (n={int(mask.sum()):,})')
    return js, rho, xa, xb, mask

# Project universe. Source rows are preserved in the file; the analysis uses
# the first occurrence of each PEP 503 canonical project name.
pidx, org_owned = {}, []
source_project_rows = 0
for row in read_gz('projects_analysis.csv.gz'):
    source_project_rows += 1
    c = row['project_id']
    if c in pidx:
        continue
    pidx[c] = len(pidx)
    org_owned.append(row['organization_owned'] == '1')
NP = len(pidx)
org_owned = np.asarray(org_owned, dtype=bool)
print('=' * 78)
print('REPRODUCTION FROM PACKAGED PSEUDONYMIZED DATA')
print('=' * 78)
print(f'Successfully retrieved API records : {source_project_rows:,}')
print(f'Unique canonical projects          : {NP:,}')
print(f'Organization-owned projects        : {int(org_owned.sum()):,} ({org_owned.mean():.2%})')

# Current actor-project rows.
account_index, proxy_index = {}, {}
def get_id(mapping, key):
    if key not in mapping:
        mapping[key] = len(mapping)
    return mapping[key]

roles_owner, roles_maint, meta_all, meta_email = [], [], [], []
role_rows = meta_rows = 0
for row in read_gz('roles.csv.gz'):
    p = pidx.get(row['project_id'])
    if p is None:
        continue
    a = get_id(account_index, row['account_id'])
    role_rows += 1
    (roles_owner if row['role'] == 'Owner' else roles_maint).append((a, p))
for row in read_gz('metadata_proxy_edges.csv.gz'):
    p = pidx.get(row['project_id'])
    if p is None:
        continue
    a = get_id(proxy_index, row['proxy_id'])
    meta_rows += 1
    meta_all.append((a, p))
    if row['identity_type'] == 'email':
        meta_email.append((a, p))
roles_all = roles_owner + roles_maint

# Account flags are distributed instead of raw usernames.
flag_by_id = {}
for row in read_gz('account_flags.csv.gz'):
    flag_by_id[row['account_id']] = (row['is_bot_automation'] == '1', row['is_organization_associated'] == '1')
is_bot = np.zeros(len(account_index), dtype=bool)
is_org_assoc = np.zeros(len(account_index), dtype=bool)
for aid, idx in account_index.items():
    b, o = flag_by_id.get(aid, (False, False))
    is_bot[idx], is_org_assoc[idx] = b, o

# Download stratum.
is_top = np.zeros(NP, dtype=bool)
for row in read_gz('download_ranks.csv.gz'):
    p = pidx.get(row['project_id'])
    if p is not None:
        is_top[p] = True

adj_a = adjacency(meta_all)
adj_b = adjacency(roles_all)
print(f'Graph A source rows / identities   : {meta_rows:,} / {len(proxy_index):,}')
print(f'Graph B source rows / accounts     : {role_rows:,} / {len(account_index):,}')
print(f'Graph A distinct edges             : {sum(map(len, adj_a.values())):,}')
print(f'Graph B distinct edges             : {sum(map(len, adj_b.values())):,}')

print('\n' + '=' * 78)
print('CENSUS-LEVEL AGREEMENT')
print('=' * 78)
obs_j, rho, xa, xb, mask = compare(adj_a, adj_b, NP, 'Full census')
print(f'Largest actor-project degree: A={int(xa.max()):,}; B={int(xb.max()):,}')
diff = np.abs(xa[mask] - xb[mask])
print(f'Absolute exposure difference >= 10  : {(diff >= 10).sum():,} ({(diff >= 10).mean():.1%})')
print(f'Absolute exposure difference >= 100 : {(diff >= 100).sum():,} ({(diff >= 100).mean():.1%})')
print(f'Non-zero exposure on exactly one side: {((xa[mask] == 0) | (xb[mask] == 0)).sum():,} ({((xa[mask] == 0) | (xb[mask] == 0)).mean():.1%})')

# Null model: preserve source-row entity stubs and globally permute project
# endpoints. Parallel matches can collapse when evaluated as set-valued
# neighborhoods, so this is intentionally not described as exact simple-graph
# degree preservation.
print('\n' + '=' * 78)
print(f'STUB-PRESERVING CONFIGURATION NULL (R={args.null_R})')
print('=' * 78)
arr = np.asarray(roles_all, dtype=np.int64)
order = np.argsort(arr[:, 0], kind='stable')
entities, projects = arr[:, 0][order], arr[:, 1][order]
unique_entities, starts = np.unique(entities, return_index=True)
ends = np.append(starts[1:], len(entities))
deg = ends - starts
top_positions = {}
for k in KS:
    top_groups = np.argsort(deg)[::-1][:k]
    top_positions[k] = np.concatenate([np.arange(starts[t], ends[t], dtype=np.int64) for t in top_groups])
obs_masks = {}
obs_sizes = {}
for k in KS:
    s = top_coverage(adj_a, k)
    m = np.zeros(NP, dtype=bool)
    if s:
        m[np.fromiter(s, dtype=np.int64, count=len(s))] = True
    obs_masks[k], obs_sizes[k] = m, len(s)
# For the union of the top-k entities, a global random permutation of all
# project-endpoint stubs is distributionally equivalent to drawing the needed
# endpoint stubs without replacement. We therefore sample only as many stubs as
# the top-100 entities require instead of materializing a 940k-element
# permutation in every replication. The k-specific samples are nested prefixes
# of the same draw, matching the joint distribution induced by one permutation.
# This optimization changes runtime, not the null model.
ordered_top_groups = np.argsort(deg)[::-1][:max(KS)]
cum_stub_counts = np.cumsum(deg[ordered_top_groups])
m_by_k = {k: int(cum_stub_counts[k - 1]) for k in KS}
max_m = m_by_k[max(KS)]
null = {k: np.empty(args.null_R, dtype=float) for k in KS}
N_STUBS = len(projects)
for r in range(args.null_R):
    draw_idx = rng.choice(N_STUBS, size=max_m, replace=False, shuffle=False)
    sampled_projects = projects[draw_idx]
    # One unique operation is enough for all nested k values. The first index at
    # which a project appears determines whether it belongs to each prefix.
    uniq_projects, first_idx = np.unique(sampled_projects, return_index=True)
    for k in KS:
        sel = first_idx < m_by_k[k]
        cover = uniq_projects[sel]
        inter = int(obs_masks[k][cover].sum())
        union = obs_sizes[k] + len(cover) - inter
        null[k][r] = inter / union if union else float('nan')
print(f'{"k":>5}{"Observed":>11}{"Null mean":>12}{"Null SD":>10}{"Null 95% CI":>24}{"Ratio":>9}')
for i, k in enumerate(KS):
    a = null[k]; lo, hi = np.percentile(a, [2.5, 97.5])
    print(f'{k:>5}{obs_j[i]:>11.3f}{a.mean():>12.4f}{a.std():>10.4f}   [{lo:.4f}, {hi:.4f}]{obs_j[i] / a.mean():>8.1f}x')

if args.null_only:
    print(f'\nElapsed: {time.time() - t0:.1f} seconds')
    raise SystemExit(0)

print('\n' + '=' * 78)
print('ROBUSTNESS')
print('=' * 78)
checks = [
    ('Owner only', adj_a, adjacency(roles_owner)),
    ('Owner + Maintainer', adj_a, adj_b),
    ('Metadata email only', adjacency(meta_email), adj_b),
    ('Metadata email + name fallback', adj_a, adj_b),
    ('Top-15,000 download stratum', adjacency(meta_all, keep_project=is_top), adjacency(roles_all, keep_project=is_top)),
    ('Long tail', adjacency(meta_all, keep_project=~is_top), adjacency(roles_all, keep_project=~is_top)),
    ('Excluding bot/automation accounts', adj_a, adjacency(roles_all, keep_entity=~is_bot)),
    ('Excluding organization-associated accounts', adj_a, adjacency(roles_all, keep_entity=~is_org_assoc)),
    ('Individual accounts only', adj_a, adjacency(roles_all, keep_entity=(~is_bot & ~is_org_assoc))),
    ('Excluding organization-owned projects', adjacency(meta_all, keep_project=~org_owned), adjacency(roles_all, keep_project=~org_owned)),
]
for label, aa, bb in checks:
    j, rr, *_ = compare(aa, bb, NP, label, quiet=True)
    print(f'{label:<42} Jaccard {min(j):.3f}-{max(j):.3f}; rho={rr:.4f}')
jm, rm, *_ = compare(adj_a, adjacency(roles_maint), NP, 'Maintainer only', quiet=True)
print(f'Maintainer-only [degenerate]             Jaccard {min(jm):.3f}-{max(jm):.3f}; rho={rm:.4f}; source rows={len(roles_maint):,}')

print('\n' + '=' * 78)
print('USER-ROLE COVERAGE')
print('=' * 78)
has_role = np.zeros(NP, dtype=bool)
for _, p in roles_all:
    has_role[p] = True
org_missing = int((org_owned & ~has_role).sum())
ind_missing = int((~org_owned & ~has_role).sum())
print(f'Organization-owned projects: {int(org_owned.sum()):,}; without individual role: {org_missing:,} ({org_missing / org_owned.sum():.1%})')
print(f'Individually owned projects: {int((~org_owned).sum()):,}; without individual role: {ind_missing:,} ({ind_missing / (~org_owned).sum():.1%})')

print('\n' + '=' * 78)
print('TWO-TIME-POINT HISTORICAL SENSITIVITY')
print('=' * 78)
# Restrict historical replay to the archived stratified sample. This is
# algebraically equivalent to constructing the full 843k-project state and then
# subsetting it, but avoids allocating hundreds of thousands of empty Python sets.
sample = []
for row in read_gz('historical_sample_projects_2024-07-05.csv.gz'):
    c = row['project_id']
    if c in pidx:
        sample.append(c)
sample = list(dict.fromkeys(sample))
sidx = {c: i for i, c in enumerate(sample)}
NS = len(sample)

account_name = [None] * len(account_index)
for key, value in account_index.items():
    account_name[value] = key
project_name = [None] * NP
for c, i in pidx.items():
    project_name[i] = c

# Current accepted role state only for sample projects.
current_state = {c: set() for c in sample}
for a, p in roles_owner:
    c = project_name[p]
    if c in sidx:
        current_state[c].add(('Owner', account_name[a]))
for a, p in roles_maint:
    c = project_name[p]
    if c in sidx:
        current_state[c].add(('Maintainer', account_name[a]))
historical_state = {c: set(v) for c, v in current_state.items()}

# Retain only replay events that can affect the archived sample, while still
# counting events that reference projects outside the current census.
missing_events = 0
events = []
for row in read_gz('journal_role_events.csv.gz'):
    c = row['project_id']
    if c not in pidx:
        missing_events += 1
        continue
    if c in sidx and row['timestamp_utc'][:10] >= ANCHOR:
        events.append((int(row['serial']), row))
events.sort(key=lambda x: -x[0])
for _, row in events:
    state = historical_state[row['project_id']]
    et, aid = row['event_type'], row['account_id']
    rb, ra = row['role_before'], row['role_after']
    if et in ('add', 'accepted'):
        state.discard((ra, aid))
    elif et == 'remove':
        state.add((rb, aid))
    elif et == 'change':
        state.discard((ra, aid))
        state.add((rb, aid))
    # invite/revoke_invite do not change accepted role state.
print(f'Journal events referencing projects outside current census: {missing_events:,}')

# Historical proxy edges.
hist_proxy_index = {}
hist_a = []
for row in read_gz('hist_metadata_proxy_edges_2024-07-05.csv.gz'):
    if row['project_id'] not in sidx:
        continue
    a = get_id(hist_proxy_index, row['proxy_id'])
    hist_a.append((a, sidx[row['project_id']]))
# Historical user-role edges.
hist_account_index = {}
hist_b = []
for c in sample:
    for _, aid in historical_state[c]:
        a = get_id(hist_account_index, aid)
        hist_b.append((a, sidx[c]))
# Current same-sample proxy and role edges.
cur_a = []
cur_proxy_index = {}
for a, p in meta_all:
    c = project_name[p]
    if c in sidx:
        aid = get_id(cur_proxy_index, a)
        cur_a.append((aid, sidx[c]))
cur_b = []
cur_account_index = {}
for a, p in roles_all:
    c = project_name[p]
    if c in sidx:
        aid = get_id(cur_account_index, a)
        cur_b.append((aid, sidx[c]))
for label, ea, eb in ((ANCHOR, hist_a, hist_b), ('2026-08-12', cur_a, cur_b)):
    j, rr, *_ = compare(adjacency(ea), adjacency(eb), NS, label, quiet=True)
    print(f'{label}: mean Jaccard={np.mean(j):.3f}; Spearman rho={rr:.4f}; n projects={NS:,}')

print(f'\nElapsed: {time.time() - t0:.1f} seconds')