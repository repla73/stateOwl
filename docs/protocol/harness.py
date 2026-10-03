"""Finite, in-memory conformance model. Not a production stateOwl implementation.

No network, real Git, credentials, installation or external effects. Expected
responses are read only by the test driver, never by the provider or model.
"""
from __future__ import annotations
import base64
from collections import Counter
import copy
import json
from pathlib import Path
import re
from typing import Any
from jsonschema import Draft202012Validator
from fixture_codec import (VERSION, Fault, strict, byte_value, unbase64, digest,
    git_blob, identity, request_digest, restricted_jcs, jcs, receipt_message,
    receipt_identity)

HERE=Path(__file__).resolve().parent
SCHEMA=json.loads((HERE/'schema.json').read_text())
VALIDATORS={k:Draft202012Validator({'$defs':SCHEMA['$defs'],'$ref':'#/$defs/'+k}) for k in SCHEMA['$defs']}
ROUTER='urn:stateowl:binding:router-v1:1'
RETRY={c:r for r,cs in {
 'after_correction':'INVALID_REQUEST NOT_FOUND EXACT_SNAPSHOT_REQUIRED INVALID_SOURCE NUMBER_UNREPRESENTABLE LIMIT_EXCEEDED VALIDATION_FAILED',
 'after_refresh':'UNAUTHENTICATED CONFLICT NAMESPACE_DISCONTINUITY TOKEN_INVALID',
 'after_backoff':'RATE_LIMITED PROVIDER_UNAVAILABLE',
 'never':'UNSUPPORTED_VERSION UNSUPPORTED_CAPABILITY FORBIDDEN NOT_FOUND_OR_FORBIDDEN SNAPSHOT_UNAVAILABLE INTEGRITY_MISMATCH NO_CHANGE HISTORY_UNAVAILABLE'
}.items() for c in cs.split()}

def merge(base, patch):
    """RFC 7396 merge patch; fixtures use it only to construct test inputs."""
    if not isinstance(patch,dict): return copy.deepcopy(patch)
    out=copy.deepcopy(base) if isinstance(base,dict) else {}
    for k,v in patch.items():
        if v is None: out.pop(k,None)
        else: out[k]=merge(out.get(k),v)
    return out

def error(code, uncertain=False):
    return {'code':code,'retry':'reconcile' if uncertain else RETRY[code]}

def snap(oid): return {'id':oid}

def path_valid(path): return VALIDATORS['Path'].is_valid(path)

def valid_ref(value):
    if not value.startswith(('refs/heads/','refs/tags/')) or value.endswith(('/', '.')):return False
    if any(ord(c)<33 or ord(c)==127 or c in '~^:?*[\\' for c in value):return False
    if '..' in value or '@{' in value:return False
    return all(p and not p.startswith('.') and not p.endswith('.lock') for p in value.split('/'))

def collision(paths):
    names=set(paths)
    return len(names)!=len(paths) or any('/'.join(p.split('/')[:i]) in names for p in paths for i in range(1,len(p.split('/'))))

class ProviderFailure(Fault):
    def __init__(self,code,dispatched=False):
        super().__init__(code); self.dispatched=dispatched

class Provider:
    """Scripted provider boundary shared by the model and future adapter drivers."""
    METHODS={'access','resolve','inspect','file','tree','validate','admit','token_check','token_issue'}
    def __init__(self,world):
        self.world=copy.deepcopy(world);self.initial=copy.deepcopy(world);self.calls=[];self.counts=Counter()
        self.dispatches=0;self.admissions=0;self.tokens=copy.deepcopy(world.get('tokens',{}))
        self.used_faults=set()
        events=set()
        for f in self.world.get('faults',[]):
            if set(f)-{'method','at','phase','code','replace','mutate'} or f['method'] not in self.METHODS or f.get('phase','before') not in ('before','after') or type(f.get('at',1)) is not int or f.get('at',1)<1:
                raise ValueError('invalid fault script')
            if 'code' in f and f['code'] not in RETRY: raise ValueError('unknown fault code')
            if not ({'code','replace','mutate'} & set(f)) or ('code' in f and 'replace' in f):raise ValueError('ambiguous/empty fault action')
            key=(f['method'],f.get('at',1),f.get('phase','before'))
            if key in events:raise ValueError('duplicate fault event')
            events.add(key)
    @staticmethod
    def move_head(store,new):
        old=store.get('head')
        if old!=new:
            store.setdefault('ref_updates',[]).append({'old':old,'new':new})
        store['head']=new
    def mutate(self,patch):
        old=self.world.get('head')
        self.world=merge(self.world,patch)
        if 'head' in patch and self.world.get('head')!=old:
            self.world.setdefault('ref_updates',[]).append({'old':old,'new':self.world.get('head')})
    @staticmethod
    def publication_continuity(store):
        status=store.get('continuity','intact')
        if status!='intact': return status
        # This is a trusted test configuration, never inferred from ancestry.
        if store.get('admission_policy')!='single_step': return 'unknown'
        updates=store.get('ref_updates',[])
        if len(updates)>1024: return 'unknown'
        previous=None
        for i,event in enumerate(updates):
            old,new=event['old'],event['new']
            if old is None or new is None or old==new: return 'reset'
            if i and old!=previous: return 'reset'
            obj=store.get('objects',{}).get(new)
            if obj is None: return 'unknown'
            if obj.get('type')!='commit' or obj.get('parents')!=[old]: return 'reset'
            previous=new
        return 'intact'
    def store(self,target):
        if target==self.world['target']: return self.world
        store=self.world.get('external',{}).get(target['resource'])
        if not store or store.get('target')!=target: raise Fault('FORBIDDEN')
        return store
    def call(self,method,**args):
        signatures={'access':{'target','operation'},'resolve':{'target'},'inspect':{'target','snapshot'},'file':{'target','snapshot','path'},'tree':{'target','snapshot'},'validate':{'target','expected','binding','old','candidate'},'admit':{'target','expected','candidate','message'},'token_check':{'token','scope'},'token_issue':{'scope','fingerprint'}}
        if method not in signatures or set(args)!=signatures[method]: raise ValueError('invalid provider call signature')
        self.counts[method]+=1;self.calls.append({'method':method,'args':copy.deepcopy(args)})
        faults=[(i,f) for i,f in enumerate(self.world.get('faults',[])) if f['method']==method and f.get('at',1)==self.counts[method]]
        for i,f in faults:
            if f.get('phase','before')=='before':
                self.used_faults.add(i)
                if 'mutate' in f:self.mutate(f['mutate'])
                if 'code' in f:raise ProviderFailure(f['code'])
                if 'replace' in f:return copy.deepcopy(f['replace'])
        result=self._call(method,**args)
        for i,f in faults:
            if f.get('phase','before')=='after':
                self.used_faults.add(i)
                if 'mutate' in f:self.mutate(f['mutate'])
                if 'code' in f:raise ProviderFailure(f['code'],method=='admit')
                if 'replace' in f:result=copy.deepcopy(f['replace'])
        return result
    def _call(self,method,**a):
        if method in ('token_check','token_issue'):
            if method=='token_check':
                v=self.tokens.get(a['token'])
                if not v or v.get('expired') or v['scope']!=a['scope']:raise Fault('TOKEN_INVALID')
                return copy.deepcopy(v)
            token='test-token:'+digest(restricted_jcs({'scope':a['scope'],'fingerprint':a['fingerprint']}))[7:]
            self.tokens[token]={'scope':a['scope'],'fingerprint':a['fingerprint']}
            return token
        s=self.store(a['target'])
        if method=='access':
            if not s.get('authenticated',True):raise Fault('UNAUTHENTICATED')
            if not s.get('authorized',True):raise Fault('FORBIDDEN')
            result={k:copy.deepcopy(s.get(k,v)) for k,v in {'validation':None,'validator_available':True,'project_authorized':True,'continuity':'intact','auth_scope':'fixture-user'}.items()}
            if a['operation']=='publish': result['continuity']=self.publication_continuity(s)
            return result
        if method=='resolve':
            h=s.get('head')
            if h is None:raise Fault('NOT_FOUND')
            if 'head_after_resolve' in s:self.move_head(s,s['head_after_resolve'])
            return h
        if method in ('inspect','file','tree'):
            oid=a['snapshot'];o=s.get('objects',{}).get(oid)
            if o is None:raise Fault('SNAPSHOT_UNAVAILABLE')
            if method=='inspect':return {'id':oid,**{k:copy.deepcopy(v) for k,v in o.items() if k!='files'}}
            if o['type']!='commit':raise Fault('INVALID_SOURCE')
            if method=='tree':return copy.deepcopy(o['files'])
            item=o['files'].get(a['path'])
            if item is None:raise Fault('NOT_FOUND_OR_FORBIDDEN' if s.get('conceal_absence') else 'NOT_FOUND')
            raw=unbase64(item['base64'])
            result={'base64':item['base64'],'mode':item['mode'],'digest':digest(raw),'integrity':'provider'}
            if s.get('native',True):result['object']=git_blob(raw,s.get('algorithm','sha1'))
            return result
        if method=='validate':
            # A concrete project-owned test rule checks old/candidate, not a supplied verdict.
            protected=s.get('protected_path','state/validation.json')
            if a['old'].get(protected)!=a['candidate'].get(protected) and not s.get('allow_policy_change',False):raise Fault('VALIDATION_FAILED')
            if not s.get('project_authorized',True):raise Fault('FORBIDDEN')
            return True
        if method=='admit':
            self.dispatches+=1
            if s.get('head')!=a['expected']:return {'status':'conflict'}
            oid=s['next_snapshot']
            s['objects'][oid]={'type':'commit','parents':[a['expected']],'message':a['message'],'files':copy.deepcopy(a['candidate'])}
            self.move_head(s,oid);self.admissions+=1
            if 'head_after_admit' in s:self.move_head(s,s['head_after_admit'])
            return {'status':'admitted','snapshot':oid}
        raise ValueError('unimplemented test method')

class Model:
    """Bounded specification oracle over Provider, not an installable adapter."""
    def __init__(self,provider,capabilities):
        self.p=provider;self.cap=capabilities;self.lim=capabilities['limits']
        self.cache={};self.absent=set();self.routing=[];self.dependencies=[];self.root_target=None;self.root_snapshot=None
        self.admitted=None;self.was_dispatched=False;self.req=None
    def fail_result(self,code,stage='operation'):
        r=self.req
        if stage=='request' or not r:
            return {'protocol':VERSION,'op':'unknown','status':'error','error':error(code)}
        if r['op']!='publish':return {'protocol':VERSION,'op':r['op'],'status':'error','error':error(code)}
        outcome='verification_pending' if self.admitted else 'indeterminate' if self.was_dispatched or r['mode']=='reconcile' else 'not_committed'
        out={'protocol':VERSION,'op':'publish','outcome':outcome,'request_digest':request_digest(r),'error':error(code,outcome in ('indeterminate','verification_pending'))}
        if self.admitted:out['snapshot']=snap(self.admitted)
        return out
    def precheck(self,raw):
        if len(raw)>self.lim['request_bytes']:raise Fault('LIMIT_EXCEEDED')
        r=strict(raw,depth=self.lim['json_depth'])
        if not isinstance(r,dict) or not isinstance(r.get('protocol'),str):raise Fault('INVALID_REQUEST')
        if r['protocol']!=VERSION:raise Fault('UNSUPPORTED_VERSION')
        name={'read':'ReadRequest','publish':'PublishRequest','observe':'ObserveRequest'}.get(r.get('op'))
        if not name or not VALIDATORS[name].is_valid(r):raise Fault('INVALID_REQUEST')
        if r['target']['kind']=='git' and not valid_ref(r['target']['namespace']):raise Fault('INVALID_REQUEST')
        records=r.get('records',[])
        if len({x['key'] for x in records})!=len(records):raise Fault('INVALID_REQUEST')
        changes=r.get('changes',[])
        if collision([c['path'] for c in changes]):raise Fault('INVALID_REQUEST')
        decoded=[byte_value(c['put']) for c in changes if 'put' in c]
        if len(records)>self.lim['records'] or sum(len(x.get('expand',[])) for x in records)>self.lim['expansions'] or len(changes)>self.lim['changes'] or sum(map(len,decoded))>self.lim['mutation_bytes'] or any(len(v)>self.lim['record_bytes'] for v in decoded):raise Fault('LIMIT_EXCEEDED')
        return r
    def run(self,raw):
        try:self.req=self.precheck(raw)
        except Fault as e:return self.fail_result(e.code,'request')
        r=self.req
        try:
            if r['op'] not in self.cap['operations']:raise Fault('UNSUPPORTED_CAPABILITY')
            for rec in r.get('records',[]):
                if rec.get('format','json') not in self.cap['formats']:raise Fault('UNSUPPORTED_CAPABILITY')
            if any('route' in x for x in r.get('records',[])) and 'routes' not in self.cap['features']:raise Fault('UNSUPPORTED_CAPABILITY')
            if any(x.get('expand') for x in r.get('records',[])) and 'expand' not in self.cap['features']:raise Fault('UNSUPPORTED_CAPABILITY')
            if 'resolver' in r and r['resolver'] not in self.cap['resolvers']:raise Fault('UNSUPPORTED_CAPABILITY')
            access=self.p.call('access',target=r['target'],operation=r['op'])
            self.access=access
            if r['op']=='publish':result=self.publish(r)
            elif r['op']=='read':result=self.read(r)
            else:result=self.observe(r)
            if len(jcs(result))>self.lim['response_bytes']:raise Fault('LIMIT_EXCEEDED')
            return result
        except ProviderFailure as e:
            self.was_dispatched |= e.dispatched
            return self.fail_result(e.code)
        except Fault as e:return self.fail_result(e.code)
    def inspect(self,target,oid):
        if target['kind']=='git' and not re.fullmatch(r'git:(?:sha1:[0-9a-f]{40}|sha256:[0-9a-f]{64})',oid):raise Fault('INVALID_SOURCE')
        meta=self.p.call('inspect',target=target,snapshot=oid)
        if len(jcs(meta))>self.lim['record_bytes']:raise Fault('LIMIT_EXCEEDED')
        if meta.get('id')!=oid:raise Fault('INTEGRITY_MISMATCH')
        return meta
    def root(self,target,at):
        exact='snapshot' in at
        oid=at['snapshot']['id'] if exact else self.p.call('resolve',target=target)
        seen=set();hops=0;expected_type=None
        while True:
            m=self.inspect(target,oid)
            if expected_type is not None and m.get('type')!=expected_type:raise Fault('INTEGRITY_MISMATCH')
            if oid in seen:raise Fault('INVALID_SOURCE')
            seen.add(oid)
            if m.get('type')=='commit':break
            if exact or m.get('type')!='tag' or (target['kind']=='git' and not target['namespace'].startswith('refs/tags/')):raise Fault('INVALID_SOURCE')
            if hops>=self.lim['tag_hops']:raise Fault('LIMIT_EXCEEDED')
            if not isinstance(m.get('target'),str) or not m['target']:raise Fault('INVALID_SOURCE')
            expected_type=m.get('target_type')
            if expected_type is not None and expected_type not in ('tag','commit','tree','blob'):raise Fault('INVALID_SOURCE')
            oid=m['target'];hops+=1
        if 'assert_snapshot' in at and at['assert_snapshot']!=snap(oid):raise Fault('CONFLICT')
        return oid
    def fetch(self,target,oid,path,routing=False):
        key=(restricted_jcs(target),oid,path)
        if key in self.absent:raise Fault('NOT_FOUND')
        if key not in self.cache:
            try:item=self.p.call('file',target=target,snapshot=oid,path=path)
            except Fault as e:
                if e.code=='NOT_FOUND':
                    self.absent.add(key);self.dependencies.append({'target':target,'path':path,'absent':True})
                raise
            try:raw=unbase64(item['base64'])
            except (Fault,KeyError):raise Fault('INVALID_SOURCE') from None
            if len(raw)>self.lim['record_bytes']:raise Fault('LIMIT_EXCEEDED')
            if item.get('digest')!=digest(raw):raise Fault('INTEGRITY_MISMATCH')
            if 'object' in item:
                algorithm='sha256' if item['object'].startswith('git:sha256:') else 'sha1'
                if git_blob(raw,algorithm)!=item['object']:raise Fault('INTEGRITY_MISMATCH')
            if item.get('mode') not in ('100644','100755'):raise Fault('INVALID_SOURCE')
            source={'path':path,'digest':digest(raw),'integrity':item['integrity']}
            if 'object' in item:source['object']=item['object']
            if target!=self.root_target or oid!=self.root_snapshot:source['origin']={'target':target,'snapshot':snap(oid)}
            self.cache[key]=(raw,source)
            self.dependencies.append({'target':target,'path':path,'digest':digest(raw),'mode':item['mode'],**({'snapshot':snap(oid)} if target!=self.root_target or oid!=self.root_snapshot else {})})
        raw,source=self.cache[key]
        if routing and source not in self.routing:self.routing.append(source)
        return raw,source
    def value(self,raw,fmt):
        if fmt=='json':return strict(raw,source=True,depth=self.lim['json_depth'])
        if fmt=='base64':return base64.b64encode(raw).decode()
        try:return raw.decode('utf-8')
        except UnicodeError:raise Fault('INVALID_SOURCE') from None
    def found(self,key,path,fmt,select,target,oid,require_object=False):
        raw,source=self.fetch(target,oid,path);v=self.value(raw,fmt)
        if require_object and not isinstance(v,dict):raise Fault('INVALID_SOURCE')
        out={'key':key,'status':'found','format':fmt,'value':v,'source':source}
        if select is not None:
            if not isinstance(v,dict):raise Fault('INVALID_REQUEST')
            out.update(value={k:v[k] for k in select if k in v},select=select,missing=[k for k in select if k not in v])
        return out,raw
    def link(self,parent,name,target,oid):
        links=parent.get('links',{})
        if not isinstance(links,dict):raise Fault('INVALID_SOURCE')
        if name not in links:raise Fault('NOT_FOUND')
        l=links[name]
        if not isinstance(l,dict) or set(l)-{'repository','commit','path','format','select'}:raise Fault('INVALID_SOURCE')
        repo=l.get('repository',target['resource'])
        if not isinstance(repo,str) or not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+',repo) or any(x in ('.','..') for x in repo.split('/')):raise Fault('INVALID_SOURCE')
        other=repo!=target['resource']
        if other and 'commit' not in l:raise Fault('EXACT_SNAPSHOT_REQUIRED')
        if 'commit' in l and (not isinstance(l['commit'],str) or not re.fullmatch('[0-9a-f]{40}',l['commit'])):raise Fault('INVALID_SOURCE')
        if not VALIDATORS['LegacyLink'].is_valid(l):raise Fault('INVALID_SOURCE')
        dest={**target,'resource':repo.lower()} if other else target
        dest_oid='git:sha1:'+l['commit'] if 'commit' in l else oid
        if other or dest_oid!=oid:
            self.p.call('access',target=dest,operation='read')
            self.root(dest,{'snapshot':snap(dest_oid)})
        out,raw=self.found(name,l['path'],l.get('format','json'),l.get('select'),dest,dest_oid,'select' in l)
        return out
    def read(self,r):
        t=r['target'];oid=self.root(t,r['at']);self.root_target=t;self.root_snapshot=oid
        out={'protocol':VERSION,'op':'read','status':'ok','target':t,'snapshot':snap(oid),'records':[]}
        for rec in r['records']:
            select=rec.get('select');fmt=rec.get('format','json');path=rec.get('path')
            if 'route' in rec:
                raw,_=self.fetch(t,oid,'.stateowl/router.json',True)
                router=self.value(raw,'json')
                if not VALIDATORS['LegacyRouter'].is_valid(router):raise Fault('INVALID_SOURCE')
                if rec['route'] not in router['routes']:raise Fault('NOT_FOUND')
                entry=router['routes'][rec['route']]
                if not VALIDATORS['LegacyRoute'].is_valid(entry):raise Fault('INVALID_SOURCE')
                path=entry['path'];select=rec.get('select',entry['select'])
            try:record,raw=self.found(rec['key'],path,fmt,select,t,oid,'route' in rec)
            except Fault as e:
                if e.code!='NOT_FOUND' or not rec.get('optional'):raise
                out['records'].append({'key':rec['key'],'status':'absent','path':path});continue
            if 'route' in rec and not isinstance(self.value(raw,'json'),dict):raise Fault('INVALID_SOURCE')
            if rec.get('expand'):
                parent=self.value(raw,'json')
                if not isinstance(parent,dict):raise Fault('INVALID_SOURCE')
                self.fetch(t,oid,path,True)
                record['expanded']=[self.link(parent,name,t,oid) for name in rec['expand']]
            out['records'].append(record)
        if 'resolver' in r:out['routing']={'binding':r['resolver'],'sources':self.routing}
        return out
    def candidate(self,r,old):
        new=copy.deepcopy(old)
        for c in sorted(r['changes'],key=lambda x:x['path'].encode()):
            p=c['path'];existing=old.get(p)
            if existing and existing['mode'] not in ('100644','100755'):raise Fault('INVALID_SOURCE')
            if 'delete' in c:
                if existing is None:raise Fault('NOT_FOUND')
                del new[p]
            else:new[p]={'base64':base64.b64encode(byte_value(c['put'])).decode(),'mode':existing['mode'] if existing else '100644'}
        if collision(list(new)):raise Fault('INVALID_SOURCE')
        if old==new:raise Fault('NO_CHANGE')
        return new
    def result(self,r,oid,head):
        return {'protocol':VERSION,'op':'publish','outcome':'committed','request_digest':request_digest(r),'snapshot':snap(oid),'observed_head':snap(head)}
    def verify(self,r,oid,head=None):
        t=r['target'];m=self.inspect(t,oid)
        if m.get('type')!='commit' or m.get('parents')!=[r['expected']['id']]:raise Fault('INTEGRITY_MISMATCH')
        if receipt_identity(m.get('message',''),VALIDATORS['PublicationIdentity'].is_valid)!=identity(r):raise Fault('INTEGRITY_MISMATCH')
        old=self.p.call('tree',target=t,snapshot=r['expected']['id'])
        wanted=self.candidate(r,old);actual=self.p.call('tree',target=t,snapshot=oid)
        if wanted!=actual:raise Fault('INTEGRITY_MISMATCH')
        if head is None:
            head=self.p.call('resolve',target=t)
            if self.p.call('access',target=t,operation='publish')['continuity']!='intact':raise Fault('NAMESPACE_DISCONTINUITY')
            if head!=oid:self.walk(t,head,oid,ancestor_only=True)
        return self.result(r,oid,head)
    def walk(self,t,head,expected,ancestor_only=False):
        oid=head;seen=set()
        for _ in range(self.lim['reconcile_commits']):
            if oid==expected:return None
            if oid in seen:raise Fault('NAMESPACE_DISCONTINUITY')
            seen.add(oid)
            try:m=self.inspect(t,oid)
            except Fault as e:
                if e.code=='SNAPSHOT_UNAVAILABLE':raise Fault('HISTORY_UNAVAILABLE') from None
                raise
            if m.get('type')!='commit' or len(m.get('parents',[]))!=1:raise Fault('NAMESPACE_DISCONTINUITY')
            parent=m['parents'][0]
            if parent==expected:return None if ancestor_only else (oid,m)
            oid=parent
        raise Fault('HISTORY_UNAVAILABLE')
    def reconcile(self,r):
        self.was_dispatched=True  # Outcome unresolved, not an actual new dispatch.
        t=r['target'];head=self.p.call('resolve',target=t)
        # Recheck trusted policy after resolution: a CAS race may have exposed
        # a ref jump that was not known at the initial access check.
        if self.p.call('access',target=t,operation='publish')['continuity']!='intact':raise Fault('NAMESPACE_DISCONTINUITY')
        if head==r['expected']['id']:raise Fault('PROVIDER_UNAVAILABLE')
        match=self.walk(t,head,r['expected']['id'])
        if match is None:raise Fault('PROVIDER_UNAVAILABLE')
        oid,m=match
        # A breach exposed during the walk also invalidates ancestry evidence.
        if self.p.call('access',target=t,operation='publish')['continuity']!='intact':raise Fault('NAMESPACE_DISCONTINUITY')
        receipt=receipt_identity(m.get('message',''),VALIDATORS['PublicationIdentity'].is_valid)
        if receipt!=identity(r):
            return {'protocol':VERSION,'op':'publish','outcome':'not_committed','request_digest':request_digest(r),'error':error('CONFLICT')}
        self.admitted=oid
        return self.verify(r,oid,head)
    def publish(self,r):
        t=r['target'];a=self.access
        if t['kind']=='git' and not t['namespace'].startswith('refs/heads/'):raise Fault('UNSUPPORTED_CAPABILITY')
        if a['continuity']!='intact':raise Fault('NAMESPACE_DISCONTINUITY')
        if r['mode']=='reconcile':return self.reconcile(r)
        self.root(t,{'snapshot':r['expected']})
        if r['validation']!=a['validation']:raise Fault('VALIDATION_FAILED')
        if r['validation'] and not a['validator_available']:raise Fault('UNSUPPORTED_CAPABILITY')
        if not a['project_authorized']:raise Fault('FORBIDDEN')
        old=self.p.call('tree',target=t,snapshot=r['expected']['id']);new=self.candidate(r,old)
        if r['validation']:self.p.call('validate',target=t,expected=r['expected']['id'],binding=r['validation'],old=old,candidate=new)
        ack=self.p.call('admit',target=t,expected=r['expected']['id'],candidate=new,message=receipt_message(r))
        if ack['status']=='conflict':return self.reconcile(r)
        self.admitted=ack['snapshot'];self.was_dispatched=True
        return self.verify(r,self.admitted)
    def observe(self,r):
        scope={'target':r['target'],'records':copy.deepcopy(r.get('records',[])),'auth_scope':self.access['auth_scope']}
        if 'resolver' in r:scope['resolver']=r['resolver']
        # Fill only semantically neutral omitted defaults; retain selection order.
        for rec in scope['records']:
            rec.setdefault('optional',False);rec.setdefault('expand',[])
        prior=self.p.call('token_check',token=r['token'],scope=scope) if 'token' in r else None
        if self.access['continuity']!='intact':raise Fault('NAMESPACE_DISCONTINUITY')
        if 'records' in r:
            read={k:v for k,v in r.items() if k!='token'};read.update(op='read',at={'current':True})
            response=self.read(read);oid=response['snapshot']['id'];fingerprint=digest(restricted_jcs(self.dependencies))
        else:oid=self.root(r['target'],{'current':True});fingerprint=oid
        status='baseline' if prior is None else 'unchanged' if prior['fingerprint']==fingerprint else 'changed'
        token=self.p.call('token_issue',scope=scope,fingerprint=fingerprint)
        return {'protocol':VERSION,'op':'observe','status':status,'target':r['target'],'snapshot':snap(oid),'token':token}
