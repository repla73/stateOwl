from __future__ import annotations
import base64, copy, hashlib, json
from collections import Counter
from pathlib import Path
from stateowl.r2 import ReadFault, digest, git_blob


def merge(base, patch):
    if not isinstance(patch, dict): return copy.deepcopy(patch)
    out=copy.deepcopy(base) if isinstance(base,dict) else {}
    for k,v in patch.items():
        if v is None: out.pop(k,None)
        else: out[k]=merge(out.get(k),v)
    return out

def expand_assets(value,assets,stack=()):
    if len(stack)>64: raise ValueError('asset depth')
    if isinstance(value,dict) and set(value)=={'$fixture'}:
        n=value['$fixture']
        if n not in assets or n in stack: raise ValueError('bad fixture '+n)
        return expand_assets(assets[n],assets,stack+(n,))
    if isinstance(value,dict): return {k:expand_assets(v,assets,stack) for k,v in value.items()}
    if isinstance(value,list): return [expand_assets(v,assets,stack) for v in value]
    return value

class FixtureProvider:
    def __init__(self,world):
        self.world=copy.deepcopy(world);self.counts=Counter();self.calls=[]
    def store(self,t):
        if t==self.world['target']: return self.world
        s=self.world.get('external',{}).get(t['resource'])
        if not s or s.get('target')!=t: raise ReadFault('FORBIDDEN')
        return s
    def _faults(self,method,phase):
        return [f for f in self.world.get('faults',[]) if f['method']==method and f.get('at',1)==self.counts[method] and f.get('phase','before')==phase]
    def _mutate(self,p): self.world=merge(self.world,p)
    def _before(self,m):
        for f in self._faults(m,'before'):
            if 'mutate' in f:self._mutate(f['mutate'])
            if 'code' in f: raise ReadFault(f['code'])
            if 'replace' in f:return copy.deepcopy(f['replace'])
        return None
    def _after(self,m,v):
        for f in self._faults(m,'after'):
            if 'mutate' in f:self._mutate(f['mutate'])
            if 'code' in f: raise ReadFault(f['code'])
            if 'replace' in f:v=copy.deepcopy(f['replace'])
        return v
    def _call(self,m,args,fn):
        self.counts[m]+=1;self.calls.append((m,copy.deepcopy(args)))
        x=self._before(m)
        return self._after(m,x if x is not None else fn())
    def access(self,t,o):
        def run():
            s=self.store(t)
            if not s.get('authenticated',True):raise ReadFault('UNAUTHENTICATED')
            if not s.get('authorized',True):raise ReadFault('FORBIDDEN')
            return {'auth_scope':s.get('auth_scope','fixture-user')}
        return self._call('access',{'target':t,'operation':o},run)
    def resolve(self,t):
        def run():
            s=self.store(t);h=s.get('head')
            if h is None:raise ReadFault('NOT_FOUND')
            if 'head_after_resolve' in s:s['head']=s['head_after_resolve']
            return h
        return self._call('resolve',{'target':t},run)
    def inspect(self,t,snapshot):
        def run():
            s=self.store(t);o=s.get('objects',{}).get(snapshot)
            if o is None:raise ReadFault('SNAPSHOT_UNAVAILABLE')
            return {'id':snapshot,**{k:copy.deepcopy(v) for k,v in o.items() if k!='files'}}
        return self._call('inspect',{'target':t,'snapshot':snapshot},run)
    def file(self,t,snapshot,path):
        def run():
            s=self.store(t);o=s.get('objects',{}).get(snapshot)
            if o is None:raise ReadFault('SNAPSHOT_UNAVAILABLE')
            if o.get('type')!='commit':raise ReadFault('INVALID_SOURCE')
            it=o.get('files',{}).get(path)
            if it is None:raise ReadFault('NOT_FOUND_OR_FORBIDDEN' if s.get('conceal_absence') else 'NOT_FOUND')
            raw=base64.b64decode(it['base64'],validate=True)
            out={'base64':it['base64'],'mode':it['mode'],'digest':digest(raw),'integrity':'provider'}
            if s.get('native',True):out['object']=git_blob(raw,s.get('algorithm','sha1'))
            return out
        return self._call('file',{'target':t,'snapshot':snapshot,'path':path},run)

def load_read_inputs(root:Path):
    proto=root/'docs/protocol'
    if not (proto/'fixtures.json').exists(): proto=root/'.frozen-protocol'
    fp=proto/'fixtures.json'
    if not fp.exists(): fp=proto/'fixtures-read-subset.json'
    packed=json.loads(fp.read_text());assets=packed.pop('assets',{})
    suite=expand_assets(packed,assets)
    cases=expand_assets(json.loads((proto/'read-cases.json').read_text()),assets)
    return suite,cases

def case_inputs(suite,case):
    r=merge(suite['requests'][case['request']],case.get('request_patch',{}))
    raw=base64.b64decode(case['request_bytes'],validate=True) if 'request_bytes' in case else json.dumps(r,ensure_ascii=False,separators=(',',':')).encode()
    w=merge(suite['defaults']['world'],suite.get('worlds',{}).get(case.get('world'),{}));w=merge(w,case.get('world_patch',{}))
    c=merge(suite['defaults']['capabilities'],case.get('cap_patch',{}))
    return raw,w,c
