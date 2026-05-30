import json, re
from collections import defaultdict
from pathlib import Path

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

def get_id(row):
    for k in ('id','issue_id','key','ticket_id','identifier'):
        v = row.get(k)
        if v:
            return str(v)
    return ''

def get_title(row):
    for k in ('title','name','summary','subject'):
        v = row.get(k)
        if v:
            return str(v)
    return ''

all_rows = load_records(ALL_PATH)
open_rows = load_records(OPEN_PATH)

kw_re = re.compile(r'\b(temp|archive|ingest|snapshot|export|mirror|pack|zip)\b', re.IGNORECASE)

bucket_ids = defaultdict(list)

title_to_ids = defaultdict(list)
for r in all_rows:
    rid = get_id(r)
    title = get_title(r)
    title_to_ids[title.strip().lower()].append(rid)

for r in all_rows:
    rid = get_id(r)
    title = get_title(r)

    if rid and re.search(r'^[A-Za-z]+\.', rid):
        bucket_ids['id_nonstandard_separator'].append(rid)

    if title and kw_re.search(title):
        bucket_ids['title_keyword'].append(rid)

for t, ids in title_to_ids.items():
    if t and len(ids) > 1:
        bucket_ids['duplicate_title'].extend(ids)

print(f'ALL_COUNT={len(all_rows)}')
print(f'OPEN_COUNT={len(open_rows)}')
for b in sorted(bucket_ids):
    ids = bucket_ids[b]
    # preserve order, dedupe
    seen = set()
    uniq = []
    for i in ids:
        if i not in seen:
            seen.add(i)
            uniq.append(i)
    sample = ', '.join(uniq[:5]) if uniq else '-'
    print(f'{b}: count={len(uniq)} sample_ids=[{sample}]')
