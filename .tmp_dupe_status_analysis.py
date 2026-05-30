import json
from pathlib import Path
from collections import Counter, defaultdict

ALL_PATH = Path('.tmp_bd_all.json')
OPEN_PATH = Path('.tmp_bd_open.json')

def load_records(path):
    data = json.loads(path.read_text(encoding='utf-8'))
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for k in ('items','data','results','issues','tickets'):
            v = data.get(k)
            if isinstance(v, list):
                return v
    return []

def pick(row, keys, default=''):
    for k in keys:
        v = row.get(k)
        if v is not None and v != '':
            return str(v)
    return default

def norm_title(t):
    return ' '.join((t or '').strip().lower().split())

all_rows = load_records(ALL_PATH)
open_rows = load_records(OPEN_PATH)

# 1) status distribution for all issues
status_counter = Counter()
for r in all_rows:
    s = pick(r, ('status','state','workflow_status'), 'UNKNOWN').strip() or 'UNKNOWN'
    status_counter[s.upper()] += 1

print('1) STATUS DISTRIBUTION (ALL)')
for status, n in sorted(status_counter.items(), key=lambda kv: (-kv[1], kv[0])):
    print(f'- {status}: {n}')

# 2) duplicate-title groups with per-status counts
by_title = defaultdict(list)
for r in all_rows:
    title = pick(r, ('title','name','summary','subject'), '').strip()
    key = norm_title(title)
    if key:
        by_title[key].append(r)

dup_groups = [(k, v) for k, v in by_title.items() if len(v) > 1]

def row_id(r):
    return pick(r, ('id','issue_id','key','ticket_id','identifier'), '')

def row_status(r):
    return pick(r, ('status','state','workflow_status'), 'UNKNOWN').upper()

print('\n2) DUPLICATE TITLE GROUPS (PER-STATUS)')
if not dup_groups:
    print('- none')
else:
    for key, rows in sorted(dup_groups, key=lambda kv: (-len(kv[1]), kv[0])):
        sc = Counter(row_status(r) for r in rows)
        status_text = ', '.join(f'{s}:{c}' for s, c in sorted(sc.items(), key=lambda kv: (-kv[1], kv[0])))
        sample_ids = ', '.join([row_id(r) for r in rows[:5]])
        print(f'- "{key}" total={len(rows)} statuses=[{status_text}] ids=[{sample_ids}]')

# 3) which duplicate groups include OPEN/READY items
print('\n3) DUPLICATE GROUPS WITH OPEN/READY')
found = 0
for key, rows in sorted(dup_groups, key=lambda kv: kv[0]):
    hot = [r for r in rows if row_status(r) in {'OPEN','READY'}]
    if hot:
        found += 1
        ids = ', '.join(row_id(r) for r in hot)
        counts = Counter(row_status(r) for r in hot)
        ctext = ', '.join(f'{k}:{v}' for k, v in sorted(counts.items()))
        print(f'- "{key}" open_ready=[{ctext}] ids=[{ids}]')
if found == 0:
    print('- none')

# 4) list of OPEN items with id,title,status,priority
print('\n4) OPEN ITEMS (id | title | status | priority)')
if not open_rows:
    # fallback from all_rows in case open snapshot missing
    open_rows = [r for r in all_rows if row_status(r) == 'OPEN']

if not open_rows:
    print('- none')
else:
    for r in open_rows:
        rid = row_id(r)
        title = pick(r, ('title','name','summary','subject'), '').replace('\n', ' ').strip()
        status = row_status(r)
        prio = pick(r, ('priority','severity','rank'), '').upper() or '-'
        print(f'- {rid} | {title} | {status} | {prio}')
