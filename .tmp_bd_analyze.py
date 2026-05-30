import json,re,subprocess,pathlib,collections

def run(args):
    p=subprocess.run(args,capture_output=True,text=True)
    return p.returncode,p.stdout,p.stderr

def parse_json_maybe(s):
    t=s.strip()
    if not t:
        return None
    try:
        return json.loads(t)
    except Exception:
        rows=[]
        ok=True
        for ln in t.splitlines():
            ln=ln.strip()
            if not ln:
                continue
            try:
                rows.append(json.loads(ln))
            except Exception:
                ok=False
                break
        if ok and rows:
            return rows
    return None

def unwrap(obj):
    if isinstance(obj,list):
        return obj
    if isinstance(obj,dict):
        for k in ["items","results","data","issues","tasks","tickets"]:
            v=obj.get(k)
            if isinstance(v,list):
                return v
        for v in obj.values():
            if isinstance(v,list):
                return v
    return []

def norm(items):
    out=[]
    for it in items:
        if not isinstance(it,dict):
            continue
        gid=lambda ks: next((it.get(k) for k in ks if it.get(k) is not None),"")
        out.append({
            'id':str(gid(['id','key','issue_id','uid','number'])),
            'title':str(gid(['title','summary','name','text','description'])),
            'status':str(gid(['status','state','workflow_state'])).strip().lower(),
        })
    return out

def is_open(st):
    return not re.search(r'\b(closed|done|resolved|cancelled|canceled)\b', st or '')

def pollution(rows):
    c=collections.Counter()
    titles=collections.Counter()
    pfx=collections.Counter()
    for r in rows:
        idv=r['id'] or ''
        title=(r['title'] or '').strip()
        txt=(idv+' '+title).lower()
        if idv and not re.match(r'^[A-Za-z][A-Za-z0-9_]*-\d+$',idv): c['malformed_id_format']+=1
        if re.search(r'(tmp|temp|import|dummy|sample|test|wip|backup|copy of)',txt): c['temp_or_import_artifact']+=1
        if len(title)<4 or title.lower() in {'tbd','todo','misc','n/a','none','placeholder'}: c['non_actionable_title']+=1
        if re.search(r'(\.csv|\.json|\.xlsx|\.sql|/|\\\\)', title.lower()): c['file_or_path_artifact_in_title']+=1
        if title:
            titles[' '.join(title.lower().split())]+=1
        m=re.match(r'^([A-Za-z][A-Za-z0-9_]*)-',idv)
        if m:
            pfx[m.group(1).lower()]+=1
    c['duplicate_title_items'] += sum(v for v in titles.values() if v>1)
    c['duplicate_prefix_items'] += sum(v for v in pfx.values() if v>=3)
    return c

rc,so,se = run(["bd","list","--json"])
obj=parse_json_maybe(so)
items=norm(unwrap(obj)) if obj is not None else []
open_items=[r for r in items if is_open(r['status'])]
closed_items=[r for r in items if not is_open(r['status'])]

print(f"BD_LIST_JSON_EXIT={rc}")
print(f"JSON_TOTAL_COUNT={len(items)}")
print(f"JSON_OPEN_COUNT_EST={len(open_items)}")
print(f"JSON_CLOSED_COUNT_EST={len(closed_items)}")

for st in ["open","closed"]:
    rc2,so2,se2 = run(["bd","list","--status",st,"--json"])
    obj2=parse_json_maybe(so2)
    rows2=norm(unwrap(obj2)) if obj2 is not None else []
    print(f"BD_LIST_STATUS_{st.upper()}_JSON_EXIT={rc2}")
    print(f"JSON_{st.upper()}_COUNT_DIRECT={len(rows2)}")

issues=pathlib.Path('.beads/issues.jsonl')
if issues.exists():
    lc=sum(1 for _ in issues.open('r',encoding='utf-8',errors='ignore'))
    print("BEADS_ISSUES_JSONL_EXISTS=true")
    print(f"BEADS_ISSUES_JSONL_LINES={lc}")
else:
    print("BEADS_ISSUES_JSONL_EXISTS=false")
    lc=None

print("TOP_POLLUTION_ALL=", pollution(items).most_common(8))
print("TOP_POLLUTION_OPEN=", pollution(open_items).most_common(8))

cands=[]
for k,v in [('JSON_TOTAL_COUNT',len(items)),('JSON_OPEN_COUNT_EST',len(open_items)),('JSON_CLOSED_COUNT_EST',len(closed_items))]:
    if v==689:
        cands.append(k)
if lc==689:
    cands.append('BEADS_ISSUES_JSONL_LINES')
print("LIKELY_689_SOURCE=" + (','.join(cands) if cands else 'none_of_current_counts'))
