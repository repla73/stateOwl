#!/usr/bin/env python3
from __future__ import annotations
import argparse, copy, json, subprocess, sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"src"))
from stateowl.r2 import PROTOCOL, DEFAULT_READ_CAPABILITIES, R2Reader
from stateowl.r2_jcs import jcs_bytes
from stateowl.r2_memory import MemoryReadProvider

A="git:sha1:"+"a"*40
TARGET={"kind":"git","authority":"github.com","resource":"fixture/project","namespace":"refs/heads/state"}
SCALES=(0,10,100,1000)
BENCHMARK_RECORD_BYTES=1048576
BENCHMARK_RESPONSE_BYTES=1048576
BENCHMARK_CAPABILITIES=copy.deepcopy(DEFAULT_READ_CAPABILITIES)
BENCHMARK_CAPABILITIES["limits"]["record_bytes"]=BENCHMARK_RECORD_BYTES
BENCHMARK_CAPABILITIES["limits"]["response_bytes"]=BENCHMARK_RESPONSE_BYTES
METRIC_FIELDS=("stateowl_read","read_success","mutable_ref_resolutions","provider_operations","file_reads","model_visible_bytes","provider_returned_bytes")

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
    r=R2Reader(p,BENCHMARK_CAPABILITIES); out=r.read(req)
    if not isinstance(out,dict) or out.get("status")!="ok":
        return {"case":name,"stateowl_read":True,"read_success":False,"error":out}
    inst=r.last_instrumentation
    return {"case":name,"stateowl_read":True,"read_success":True,"mutable_ref_resolutions":inst.resolve,"provider_operations":inst.access+inst.resolve+inst.inspect+inst.file,"file_reads":inst.file,"model_visible_bytes":len(jcs_bytes(out)),"provider_returned_bytes":p.returned_bytes}

def baseline(compact=False):
    p=MemoryReadProvider(TARGET,{A:{"type":"commit","parents":[],"message":"base\n","files":world()}},head=A,algorithm="sha1")
    p.access(TARGET,"read"); p.file(TARGET,A,"state/work.json"); v=json.loads(WORK)
    out=[({"count":v["count"]} if i%2 else {"status":v["status"]}) for i in range(5)] if compact else {"status":v["status"]}
    return {"case":"compact_batch_baseline" if compact else "direct_pinned_file_baseline","stateowl_read":False,"mutable_ref_resolutions":0,"provider_operations":2,"file_reads":1,"model_visible_bytes":len(json.dumps(out,separators=(",",":")).encode()),"provider_returned_bytes":p.returned_bytes}

def python_results():
    cases=[run_case("exact",world(),request("exact")),run_case("current",world(),request("current")),run_case("batch5",world(),request("current",batch=True)),baseline(),baseline(True)]
    for n in SCALES: cases.append({**run_case(f"fixed_router_{n}",world(n,False),request("current",routed=True)),"scale":n})
    for n in SCALES: cases.append({**run_case(f"growing_router_{n}",world(n,True),request("current",routed=True)),"scale":n})
    return cases

def implementation_checks(cases):
    by={x["case"]:x for x in cases}
    stateowl=[x for x in cases if x.get("stateowl_read")]
    fixed=[by[f"fixed_router_{n}"] for n in SCALES]
    growing=[by[f"growing_router_{n}"] for n in SCALES]
    successful=all(x.get("read_success") is True for x in stateowl)
    fixed_ok=(
        all(x.get("read_success") is True for x in fixed)
        and len({x["model_visible_bytes"] for x in fixed})==1
        and {x["mutable_ref_resolutions"] for x in fixed}=={1}
        and len({x["provider_operations"] for x in fixed})==1
        and {x["file_reads"] for x in fixed}=={2}
    )
    growing_bytes=[x.get("provider_returned_bytes") for x in growing]
    growing_ok=(
        all(x.get("read_success") is True for x in growing)
        and len({x["model_visible_bytes"] for x in growing})==1
        and {x["mutable_ref_resolutions"] for x in growing}=={1}
        and len({x["provider_operations"] for x in growing})==1
        and {x["file_reads"] for x in growing}=={2}
        and all(isinstance(v,int) for v in growing_bytes)
        and growing_bytes[-1]>growing_bytes[0]
    )
    return {"successful_focused_reads":successful,"fixed_router_invariant":fixed_ok,"growing_router_invariant":growing_ok}

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--output",type=Path,required=True); a=ap.parse_args()
    py=python_results()
    runner=ROOT/"typescript"/"dist"/"benchmarks"/"r2-common-runner.js"
    if not runner.exists(): raise SystemExit("build TypeScript first: npm --prefix typescript run build")
    ts=json.loads(subprocess.check_output(["node",str(runner)],cwd=ROOT,text=True))
    by_py={x["case"]:x for x in py}; by_ts={x["case"]:x for x in ts}
    mismatches=[]
    for k in sorted(set(by_py)|set(by_ts)):
        if k not in by_py or k not in by_ts: mismatches.append({"case":k,"reason":"missing"})
        else:
            diff={f:[by_py[k].get(f),by_ts[k].get(f)] for f in METRIC_FIELDS if by_py[k].get(f)!=by_ts[k].get(f)}
            if diff: mismatches.append({"case":k,"fields":diff})
    py_checks=implementation_checks(py);ts_checks=implementation_checks(ts)
    cross_language_comparable=not mismatches
    successful_focused_reads=py_checks["successful_focused_reads"] and ts_checks["successful_focused_reads"]
    fixed_router_invariant=py_checks["fixed_router_invariant"] and ts_checks["fixed_router_invariant"]
    growing_router_invariant=py_checks["growing_router_invariant"] and ts_checks["growing_router_invariant"]
    qualification_pass=cross_language_comparable and successful_focused_reads and fixed_router_invariant and growing_router_invariant
    result={"schema":"stateowl.r2-common-interoperability/v1","basis":"05278c225eb302697e8b31406d06f98022ab7d3c","evidence_type":"deterministic in-memory qualification; not live GitHub performance","benchmark_limits":{"record_bytes":BENCHMARK_RECORD_BYTES,"response_bytes":BENCHMARK_RESPONSE_BYTES},"scales":list(SCALES),"python":py,"typescript":ts,"python_checks":py_checks,"typescript_checks":ts_checks,"cross_language_comparable":cross_language_comparable,"successful_focused_reads":successful_focused_reads,"fixed_router_invariant":fixed_router_invariant,"growing_router_invariant":growing_router_invariant,"qualification_pass":qualification_pass,"mismatches":mismatches}
    a.output.parent.mkdir(parents=True,exist_ok=True); a.output.write_text(json.dumps(result,indent=2,sort_keys=True)+"\n")
    print(json.dumps(result,indent=2,sort_keys=True))
    raise SystemExit(0 if qualification_pass else 1)
if __name__=="__main__": main()
