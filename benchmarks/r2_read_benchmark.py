#!/usr/bin/env python3
from __future__ import annotations
import argparse,json,math,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from stateowl.r2 import *
from stateowl.r2_memory import MemoryReadProvider

def enc(v):return (json.dumps(v,separators=(',',':'))+'\n').encode()
def visible(v):return len(json.dumps(v,ensure_ascii=False,separators=(',',':')).encode())
def toks(n):return math.ceil(n/4)
def fixture(n,growing=False):
 t={'kind':'git','authority':'github.com','resource':'bench/project','namespace':'refs/heads/state'};A='git:sha1:'+'a'*40
 routes={'target':{'path':'state/target.json','select':['id','status']}}
 if growing:
  for i in range(n):routes[f'u{i}']={'path':f'state/u{i}.json','select':['id']}
 files={'.stateowl/router.json':enc({'schema':'stateowl.router/v1','routes':routes}),'state/target.json':enc({'id':'target','status':'working','noise':'x'*2048})}
 if not growing:
  for i in range(n):files[f'state/u{i}.json']=enc({'id':i,'noise':'u'*256})
 return t,A,files
def run(n,kind,growing=False,batch=False):
 t,A,files=fixture(n,growing);p=MemoryReadProvider(t,{A:{'type':'commit','files':files}},head=A,algorithm='sha1');rd=R2Reader(p);recs=[{'key':'target','route':'target'}]
 if batch:recs+=[{'key':'status','path':'state/target.json','format':'json','select':['status']}]
 at={'snapshot':{'id':A}} if kind=='exact' else {'current':True};req={'protocol':PROTOCOL,'op':'read','target':t,'at':at,'records':recs,'resolver':ROUTER_V1};start=time.perf_counter_ns();out=rd.read(req);elapsed=time.perf_counter_ns()-start;b=visible(out)
 return {'case':kind+('-growing-router' if growing else '-fixed-router')+('-batch' if batch else ''),'unrelated':n,'logical_operations':len(recs),'provider_operations':sum(vars(rd.last_instrumentation).values()),'ref_resolutions':rd.last_instrumentation.resolve,'file_fetches':rd.last_instrumentation.file,'returned_bytes':p.returned_bytes,'model_visible_bytes':b,'model_visible_tokens_approx':toks(b),'runtime_ns':elapsed,'evidence':'simulated'}
def baseline():
 t,A,files=fixture(0);p=MemoryReadProvider(t,{A:{'type':'commit','files':files}},head=A,algorithm='sha1');start=time.perf_counter_ns();item=p.file(t,A,'state/target.json');elapsed=time.perf_counter_ns()-start;b=len(item['base64'])
 return {'case':'direct-pinned-file','unrelated':0,'logical_operations':1,'provider_operations':1,'ref_resolutions':0,'file_fetches':1,'returned_bytes':p.returned_bytes,'model_visible_bytes':b,'model_visible_tokens_approx':toks(b),'runtime_ns':elapsed,'evidence':'simulated'}
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--output',type=Path,required=True);a=ap.parse_args();cases=[baseline()]
 for n in (0,100,1000):cases += [run(n,'exact'),run(n,'current')]
 for n in (0,100,250):cases.append(run(n,'exact',True))
 cases.append(run(1000,'current',False,True));result={'schema':'stateowl.r2-python-benchmark/v1','token_estimate':'ceil(serialized model-visible UTF-8 bytes / 4); approximation, not a tokenizer','network_latency_claimed':False,'cases':cases};a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(result,indent=2,sort_keys=True)+'\n');print(json.dumps(result,indent=2))
if __name__=='__main__':main()
