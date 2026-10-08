#!/usr/bin/env python3
"""Document the account-type heuristics applied before pseudonymization.

This script is supplied for methodological transparency. The public replication package
contains pseudonymous account IDs rather than raw PyPI usernames, so the archived
account_flags.csv.gz is the derived table used by reproduce.py. Given the original
public role table with columns project_id,user_normalized and the project table
with project_id,organization, this script regenerates the two Boolean flags.
"""
import argparse, csv, gzip, re
from collections import defaultdict

BOT = re.compile(r'(^|[-_.])(bot|ci|actions?|automation|robot|deploy|release[-_]?bot)([-_.]|$)|bot$', re.I)

p = argparse.ArgumentParser()
p.add_argument('--roles', required=True, help='Gzipped CSV with project_id,user_normalized')
p.add_argument('--projects', required=True, help='Gzipped CSV with project_id,organization')
p.add_argument('--output', required=True, help='Output gzipped CSV keyed by user_normalized')
args = p.parse_args()

org_projects = set()
with gzip.open(args.projects, 'rt', encoding='utf-8', newline='') as f:
    for r in csv.DictReader(f):
        if (r.get('organization') or '').strip():
            org_projects.add(r['project_id'])

users = set()
has_org = defaultdict(bool)
with gzip.open(args.roles, 'rt', encoding='utf-8', newline='') as f:
    for r in csv.DictReader(f):
        u = (r.get('user_normalized') or '').strip()
        if not u:
            continue
        users.add(u)
        if r['project_id'] in org_projects:
            has_org[u] = True

with gzip.open(args.output, 'wt', encoding='utf-8', newline='') as f:
    w = csv.writer(f)
    w.writerow(['user_normalized', 'is_bot_automation', 'is_organization_associated'])
    for u in sorted(users):
        w.writerow([u, int(bool(BOT.search(u))), int(has_org[u])])