#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, subprocess, sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"src"))
from stateowl.r2 import PROTOCOL, DEFAULT_READ_CAPABILITIES, R2Reader
from stateowl.r2_jcs import jcs_bytes
from stateowl.r2_memory import MemoryReadProvider

A="git:sha1:"+"a"*40
TARGET={"kind":"git","authority":"github.com","resource":"fixture/project","namespace":"refs/heads/state"}
SCALES=(0,10,100,1000)

def enc(v): return (json.dumps(v,separators=(",",":"))+"\n").encode()
WORK=enc({"id":"work","status":"working","count":1,"noise":"omit"})

def world(scale=0,growing=False):
    routes={"work":{"path":"state/work.json","select":["id","status"]}}
    files={"state/work.json":WORK}
    for i in range(scale):
        files[f"unrelated/{i}.json"]=b"{}\n"
        if growing: routes[f"unused-{i}"]={"path":f"unrelated/{i}.json","select":[]}
    files[".stateowl/router.json"]=enc({"schema":"stateowl.router/v1","routes":routes})
    return files

def request(mode,batch=False,routed=False):
    if batch:
        records=[{"key":f"r{i}","path":"state/work.json","format":"json","select":["count" if i%2 else "status"]} for i in range(5)]
    elif routed:
        records=[{"key":"work","route":"work"}]
    else:
        records=[{"key":"work","path":"state/work.json","format":"json","select":["status"]}]
    out={"protocol":PROTOCOL,"op":"read","target":TARGET,"at":{"snapshot":{"id":A}} if mode=="exact" else {"current":True},"records":records}
    if routed: out["resolver"]="urn:stateowl:binding:router-v1:1"
    return out

def run_case(name,files,req):
    p=MemoryReadProvider(TARGET,{A:{"type":"commit","parents":[],"message":"base\n","files":files}},head=A,algorithm="sha1")
    r=R2Reader(p,DEFAULT_READ_CAPABILITIES); out=r.read(req); inst=r.last_instrumentation
    return {"case":name,"mutable_ref_resolutions":inst.resolve,"provider_operations":inst.access+inst.resolve+inst.inspect+inst.file,"file_reads":inst.file,"model_visible_bytes":len(jcs_bytes(out)),"provider_returned_bytes":p.returned_bytes}

def baseline(compact=False):
    p=MemoryReadProvider(TARGET,{A:{"type":"commit","parents":[],"message":"base\n","files":world()}},head=A,algorithm="sha1")
    p.access(TARGET,"read"); f=p.file(TARGET,A,"state/work.json"); v=json.loads(WORK)
    out=[({"count":v["count"]} if i%2 else {"status":v["status"]}) for i in range(5)] if compact else {"status":v["status"]}
    return {"case":"compact_batch_baseline" if compact else "direct_pinned_file_baseline","mutable_ref_resolutions":0,"provider_operations":2,"file_reads":1,"model_visible_bytes":len(json.dumps(out,separators=(",",":")).encode()),"provider_returned_bytes":p.returned_bytes}

def python_results():
    cases=[run_case("exact",world(),request("exact")),run_case("current",world(),request("current")),run_case("batch5",world(),request("current",batch=True)),baseline(),baseline(True)]
    for n in SCALES: cases.append({**run_case(f"fixed_router_{n}",world(n,False),request("current",routed=True)),"scale":n})
    for n in SCALES: cases.append({**run_case(f"growing_router_{n}",world(n,True),request("current",routed=True)),"scale":n})
    return cases

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--output",type=Path,required=True); a=ap.parse_args()
    py=python_results()
    runner=ROOT/"typescript"/"dist"/"benchmarks"/"r2-common-runner.js"
    if not runner.exists(): raise SystemExit("build TypeScript first: npm --prefix typescript run build")
    ts=json.loads(subprocess.check_output(["node",str(runner)],cwd=ROOT,text=True))
    by_py={x["case"]:x for x in py}; by_ts={x["case"]:x for x in ts}
    fields=("mutable_ref_resolutions","provider_operations","file_reads","model_visible_bytes","provider_returned_bytes")
    mismatches=[]
    for k in sorted(set(by_py)|set(by_ts)):
        if k not in by_py or k not in by_ts: mismatches.append({"case":k,"reason":"missing"})
        else:
            diff={f:[by_py[k][f],by_ts[k][f]] for f in fields if by_py[k][f]!=by_ts[k][f]}
            if diff: mismatches.append({"case":k,"fields":diff})
    result={"schema":"stateowl.r2-common-interoperability/v1","basis":"05278c225eb302697e8b31406d06f98022ab7d3c","evidence_type":"deterministic in-memory qualification; not live GitHub performance","scales":list(SCALES),"python":py,"typescript":ts,"cross_language_comparable":not mismatches,"mismatches":mismatches}
    a.output.parent.mkdir(parents=True,exist_ok=True); a.output.write_text(json.dumps(result,indent=2,sort_keys=True)+"\n")
    print(json.dumps(result,indent=2,sort_keys=True))
    raise SystemExit(0 if not mismatches else 1)
if __name__=="__main__": main()
