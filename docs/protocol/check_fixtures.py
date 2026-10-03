#!/usr/bin/env python3
"""Run offline protocol schemas, finite fault model, codecs and actual legacy cases."""
from __future__ import annotations
import argparse
import atexit
import base64
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import queue
import re
import threading
import sys
from jsonschema import Draft202012Validator
from fixture_codec import (Fault, strict, unbase64, digest, git_blob, identity,
    request_digest, restricted_jcs, jcs, byte_value, receipt_identity)
from harness import HERE, SCHEMA, VALIDATORS, Provider, Model, merge
ROOT=HERE.parents[1]

def require(ok,message):
    if not ok:raise AssertionError(message)

def read_json(path):return strict(path.read_bytes())

def expand_assets(value,assets,stack=()):
    if len(stack)>64:raise ValueError('fixture asset depth')
    if isinstance(value,dict) and set(value)=={'$fixture'}:
        name=value['$fixture']
        if name not in assets or name in stack:raise ValueError('unknown/cyclic fixture asset')
        return expand_assets(assets[name],assets,stack+(name,))
    if isinstance(value,dict):return {k:expand_assets(v,assets,stack) for k,v in value.items()}
    if isinstance(value,list):return [expand_assets(v,assets,stack) for v in value]
    return value

def case_inputs(suite,case):
    request=merge(suite['requests'][case['request']],case.get('request_patch',{}))
    raw=unbase64(case['request_bytes']) if 'request_bytes' in case else json.dumps(request,ensure_ascii=False,separators=(',',':')).encode()
    world=merge(suite['defaults']['world'],suite['worlds'].get(case.get('world'),{}))
    world=merge(world,case.get('world_patch',{}))
    cap=merge(suite['defaults']['capabilities'],case.get('cap_patch',{}))
    return raw,world,cap

def check_trace(case,p,result,raw):
    trace=case.get('trace',{})
    for k,n in trace.items():
        if k=='ref_updates':
            require(p.world.get('ref_updates',[])==n,case['id']+': actual ref transitions')
        elif k=='final_modes':
            files=p.world['objects'][p.world['head']]['files']
            require({path:files[path]['mode'] for path in n}==n,case['id']+': final modes')
        else:
            actual=p.dispatches if k=='dispatches' else p.admissions if k=='admissions' else p.counts[k]
            require(actual==n,case['id']+': trace '+k+' '+str((actual,n)))
    if result['op'] in ('read','observe'):
        require(p.dispatches==0 and p.counts['tree']==0 and p.counts['validate']==0,case['id']+': read/observe effect')
    if result['op']=='read' and result.get('status')=='ok':
        request=json.loads(raw)
        require(p.counts['resolve']==(1 if request['at'].get('current') else 0),case['id']+': mutable resolution count')
        require([r['key'] for r in result['records']]==[r['key'] for r in request['records']],case['id']+': record cardinality/order')
        files=[x['args'] for x in p.calls if x['method']=='file']
        keys=[json.dumps(x,sort_keys=True) for x in files]
        require(len(keys)==len(set(keys)),case['id']+': duplicate exact file fetch')
        allowed=set()
        def source_key(source):
            origin=source.get('origin',{'target':request['target'],'snapshot':result['snapshot']})
            return json.dumps({'target':origin['target'],'snapshot':origin['snapshot']['id'],'path':source['path']},sort_keys=True)
        for record in result['records']:
            if record['status']=='absent':allowed.add(source_key({'path':record['path']}))
            else:
                allowed.add(source_key(record['source']))
                for child in record.get('expanded',[]):allowed.add(source_key(child['source']))
        for source in result.get('routing',{}).get('sources',[]):allowed.add(source_key(source))
        require(set(keys)==allowed,case['id']+': missing or unrelated exact file read')
    try:r=json.loads(raw)
    except ValueError:return
    if r.get('op')=='publish':
        require(p.dispatches<=1 and p.admissions<=1,case['id']+': repeated admission')
        if r.get('mode')=='reconcile':require(p.dispatches==0,case['id']+': reconciliation dispatched')
        for call in (c for c in p.calls if c['method']=='admit'):
            a=call['args'];old=p.initial['objects'][r['expected']['id']]['files'];wanted=copy.deepcopy(old)
            for change in r['changes']:
                path=change['path']
                if 'delete' in change:wanted.pop(path)
                else:wanted[path]={'base64':base64.b64encode(byte_value(change['put'])).decode(),'mode':old.get(path,{}).get('mode','100644')}
            require(a['expected']==r['expected']['id'] and a['candidate']==wanted,case['id']+': admission candidate changed extra bytes/modes')
            require(receipt_identity(a['message'],VALIDATORS['PublicationIdentity'].is_valid)==identity(r),case['id']+': admission receipt mismatch')

class AdapterSession:
    """Bounded JSONL test transport, with a fresh isolated world per start event."""
    def __init__(self,command):
        self.proc=subprocess.Popen(command,stdin=subprocess.PIPE,stdout=subprocess.PIPE,text=True,encoding='utf-8')
        self.inbox=queue.Queue(maxsize=2)
        def collect():
            try:
                while True:
                    line=self.proc.stdout.readline(1048577)
                    self.inbox.put(line)
                    if not line:return
            except Exception as e:self.inbox.put(e)
        threading.Thread(target=collect,daemon=True).start()
        atexit.register(self.close)
    def close(self):
        if self.proc.poll() is None:
            self.proc.stdin.close()
            try:self.proc.wait(timeout=2)
            except subprocess.TimeoutExpired:self.proc.kill();self.proc.wait()
    def send(self,value):
        self.proc.stdin.write(json.dumps(value)+'\n');self.proc.stdin.flush()
    def run(self,raw,p,cap):
        self.send({'type':'start','request_base64':base64.b64encode(raw).decode(),'capabilities':cap})
        seen=set()
        for _ in range(1024):
            try:line=self.inbox.get(timeout=10)
            except queue.Empty:raise ValueError('adapter event timeout') from None
            if isinstance(line,Exception):raise line
            if len(line)>1048576 or (line and not line.endswith('\n')):raise ValueError('adapter event byte bound')
            if not line:raise ValueError('adapter exited without result')
            event=strict(line.encode())
            if event.get('type')=='result' and set(event)=={'type','response'}:return event['response']
            require(set(event)=={'type','id','method','args'} and event['type']=='call','invalid adapter event')
            require(type(event['id']) is int and event['id']>=0 and event['id'] not in seen,'duplicate/noninteger call ID');seen.add(event['id'])
            try:reply={'type':'return','id':event['id'],'value':p.call(event['method'],**event['args'])}
            except Fault as e:reply={'type':'return','id':event['id'],'fault':{'code':e.code,'dispatched':getattr(e,'dispatched',False)}}
            self.send(reply)
        raise ValueError('adapter call budget exceeded')

def check_legacy():
    suite=read_json(HERE/'legacy-v0.1.0.json');source=ROOT/suite['baseline']['source']
    raw=source.read_bytes();blob=git_blob(raw).split(':')[-1]
    require(blob==suite['baseline']['blob'],'legacy source differs from pinned baseline')
    spec=importlib.util.spec_from_file_location('stateowl_legacy_fixture_core',source)
    module=importlib.util.module_from_spec(spec);sys.modules[spec.name]=module;spec.loader.exec_module(module)
    def decoded(data):
        out={}
        for path,item in data.items():
            raw=unbase64(item['base64']);require(git_blob(raw).split(':')[-1]==item['blob'],'legacy blob: '+path);out[path]=raw
        return out
    for case in suite['cases']:
        files={**decoded(suite['files']),**decoded(case['overrides'])}
        class Store:
            def __init__(self):self.resolves=0;self.paths=[]
            def resolve_ref(self,repository,ref):
                require(repository==suite['repository'] and ref=='refs/heads/main','legacy target')
                h=case['heads'][self.resolves];self.resolves+=1;return h
            def read_file(self,repository,commit,path):
                require(repository==suite['repository'] and commit==suite['snapshot'],'legacy snapshot')
                self.paths.append(path);raw=files[path];return module.FileObject(git_blob(raw).split(':')[-1],raw)
        store=Store();reader=module.Reader(store);actual=[]
        for r in case['requests']:
            try:actual.append({'result':reader.read(**r)})
            except module.StateOwlError as e:actual.append({'error':e.code})
        require(actual==case['responses'],'legacy output '+case['id'])
        require(store.paths==case['file_paths'] and store.resolves==len(case['heads']),'legacy trace '+case['id'])
    return len(suite['cases'])

def harness_self_checks(suite):
    count=0
    for f in [{'method':'unknown'}, {'method':'admit','at':0}, {'method':'file','phase':'later'}, {'method':'file','code':'INVENTED'}]:
        try:Provider(merge(suite['defaults']['world'],{'faults':[f]}))
        except (ValueError,KeyError):count+=1;continue
        raise AssertionError('invalid fault script accepted')
    p=Provider(suite['defaults']['world'])
    for method,args in [('unknown',{}),('resolve',{'target':p.world['target'],'unexpected':True})]:
        try:p.call(method,**args)
        except ValueError:count+=1;continue
        raise AssertionError('bad provider call accepted')
    for assets in [{'a':{'$fixture':'a'}},{'a':{'$fixture':'missing'}}]:
        try:expand_assets({'$fixture':'a'},assets)
        except ValueError:count+=1;continue
        raise AssertionError('invalid asset graph accepted')
    # Input-only model API has no parameter for the expected response.
    raw,world,cap=case_inputs(suite,{'request':'exact'})
    actual=Model(Provider(world),cap).run(raw);bad=copy.deepcopy(actual);bad['records'].reverse();bad['records'].append(copy.deepcopy(bad['records'][0]))
    require(actual!=bad,'cardinality mutation not detected');count+=1
    altered=copy.deepcopy(actual);altered['records'][0]['source']['digest']='sha256:'+'0'*64
    require(actual!=altered,'provenance mutation not detected');count+=1
    return count

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--adapter',nargs=argparse.REMAINDER)
    args=parser.parse_args();packed=read_json(HERE/'fixtures.json');assets=packed.pop('assets',{});suite=expand_assets(packed,assets)
    Draft202012Validator.check_schema(SCHEMA)
    hs=read_json(HERE/'harness.schema.json');Draft202012Validator.check_schema(hs)
    hv={n:Draft202012Validator({'$defs':hs['$defs'],'$ref':'#/$defs/'+n}) for n in hs['$defs']}
    rules=set()
    for name in ('PROTOCOL.md','git-binding-v2.md','router-v1.md'):
        rules.update(re.findall(r'(?:\*\*|## )([A-Z][0-9]+)\.',(HERE/name).read_text()))
    for case in suite['schema_cases']:require(VALIDATORS[case['definition']].is_valid(case['instance'])==case['valid'],'structural '+case['id'])
    for case in suite['serialization']:
        try:actual=strict(unbase64(case['base64']),source=True);code=None
        except Fault as e:code=e.code
        require(code==case['error'],'serialization '+case['id']+' '+str((code,case['error'])))
    for case in suite['base64_cases']:
        try:unbase64(case['text']);valid=True
        except Fault:valid=False
        require(valid==case['valid'],'base64 vector '+repr(case['text']))
    for case in suite['receipt_message_cases']:
        try:
            actual_identity=receipt_identity(case['message'],VALIDATORS['PublicationIdentity'].is_valid);code=None
        except Fault as exc:
            actual_identity=None;code=exc.code
        require(code==case['error'] and actual_identity==case['expected_identity'],'receipt grammar '+case['id'])
    identity_checks=0
    for vec in suite['identity_vectors']:
        VALIDATORS['PublicationIdentity'].validate(vec['identity'])
        require(identity(vec['request'])==vec['identity'],'identity preimage')
        can=restricted_jcs(vec['identity']);require(can.decode()==vec['canonical'] and digest(can)==vec['digest'],'canonical golden')
        require(jcs(vec['identity'])==can,'independent ECMAScript canonicalization');identity_checks+=1
        r=copy.deepcopy(vec['request']);r['changes'].reverse()
        require(request_digest(r)==vec['digest'],'change order affected identity');identity_checks+=1
        r['mode']='reconcile';require(request_digest(r)==vec['digest'],'mode affected identity');identity_checks+=1
        for c in r['changes']:
            if 'put' in c:c['put']={'encoding':'base64','data':base64.b64encode(byte_value(c['put'])).decode()}
        require(request_digest(r)==vec['digest'],'equivalent byte encoding changed identity');identity_checks+=1
        for field,value in [('validation','urn:fixture:validation:2'),('expected',{'id':'other'}),('target',{**r['target'],'namespace':'other'})]:
            changed={**r,field:value};require(request_digest(changed)!=vec['digest'],'binding/context identity ignored');identity_checks+=1
    for vec in suite['jcs_vectors']:require(jcs(vec['value']).decode()==vec['canonical'],'general JCS vector '+vec['id'])
    for vec in suite['git_blob_vectors']:require(git_blob(unbase64(vec['base64']),vec['algorithm'])==vec['object'],'Git blob vector')
    counts={};ids=set();adapter=AdapterSession(args.adapter) if args.adapter else None
    for file in suite['scenario_files']:
        cases=expand_assets(read_json(HERE/file),assets)
        for case in cases:
            require(case['id'] not in ids,'duplicate scenario ID');ids.add(case['id'])
            hv['Case'].validate(case)
            require(set(case['rules'])<=rules,'unknown normative rule: '+case['id'])
            raw,world,cap=case_inputs(suite,case)
            hv['World'].validate(world)
            VALIDATORS['Capabilities'].validate(cap)
            p=Provider(world)
            actual=adapter.run(raw,p,cap) if adapter else Model(p,cap).run(raw)
            try:
                Draft202012Validator(SCHEMA).validate(actual)
                require(actual==case['expected'],case['id']+'\nACTUAL '+json.dumps(actual,ensure_ascii=False)+'\nEXPECTED '+json.dumps(case['expected'],ensure_ascii=False))
                check_trace(case,p,actual,raw)
            except Exception as e:raise AssertionError(file+': '+str(e)) from e
        counts[file.split('-')[0]]=len(cases)
    if adapter:adapter.close()
    checks=harness_self_checks(suite)
    legacy=check_legacy()
    print(json.dumps({'status':'passed','draft':suite['protocol'],'schemas':2,'structural':len(suite['schema_cases']),**counts,'strict_json':len(suite['serialization']),'canonical_base64':len(suite['base64_cases']),'receipt_message_vectors':len(suite['receipt_message_cases']),'identity_checks':identity_checks,'general_jcs':len(suite['jcs_vectors']),'git_object_vectors':len(suite['git_blob_vectors']),'fault_harness_self_checks':checks,'simulated_scenarios':sum(counts.values()),'legacy_reader_cases':legacy,'external_adapter_executed':bool(args.adapter),'real_provider_executions':0},indent=2))

if __name__=='__main__':
    try:main()
    except Exception as e:print(str(e),file=sys.stderr);sys.exit(1)
