from __future__ import annotations
import json
from .r2_types import *
from .r2_jcs import jcs_bytes

class SessionBase:
    def __init__(self,p,cap):self.p=p;self.cap=cap;self.lim=cap.get('limits',{});self.cache={};self.absent=set();self.routing=[];self.root_target=None;self.root_oid=None
    def limit(self,k):
        v=self.lim.get(k)
        if type(v) is not int or v<=0:raise ReadFault('UNSUPPORTED_CAPABILITY')
        return v
    def run(self,raw):
        try:
            if len(raw)>self.limit('request_bytes'):raise ReadFault('LIMIT_EXCEEDED')
            r=strict_json(raw,source=False,depth=self.limit('json_depth'))
            if not isinstance(r,dict) or not isinstance(r.get('protocol'),str):raise ReadFault('INVALID_REQUEST')
            if r['protocol']!=PROTOCOL:raise ReadFault('UNSUPPORTED_VERSION')
            if not request_valid(r):raise ReadFault('INVALID_REQUEST')
            if r['target']['kind']=='git' and not ref_valid(r['target']['namespace']):raise ReadFault('INVALID_REQUEST')
            if len({x['key'] for x in r['records']})!=len(r['records']):raise ReadFault('INVALID_REQUEST')
            if len(r['records'])>self.limit('records') or sum(len(x.get('expand',[])) for x in r['records'])>self.limit('expansions'):raise ReadFault('LIMIT_EXCEEDED')
        except ReadFault as e:return fail(e.code,'unknown')
        try:
            if 'read' not in self.cap.get('operations',[]):raise ReadFault('UNSUPPORTED_CAPABILITY')
            if any(x.get('format','json') not in self.cap.get('formats',[]) for x in r['records']):raise ReadFault('UNSUPPORTED_CAPABILITY')
            if any('route' in x for x in r['records']) and 'routes' not in self.cap.get('features',[]):raise ReadFault('UNSUPPORTED_CAPABILITY')
            if any(x.get('expand') for x in r['records']) and 'expand' not in self.cap.get('features',[]):raise ReadFault('UNSUPPORTED_CAPABILITY')
            if 'resolver' in r and r['resolver'] not in self.cap.get('resolvers',[]):raise ReadFault('UNSUPPORTED_CAPABILITY')
            self.p.access(r['target'],'read')
            out=self.read_op(r)
            if len(jcs_bytes(out))>self.limit('response_bytes'):raise ReadFault('LIMIT_EXCEEDED')
            return out
        except ReadFault as e:return fail(e.code)
    def inspect(self,t,oid):
        if t['kind']=='git' and not parse_git(oid):raise ReadFault('INVALID_SOURCE')
        m=self.p.inspect(t,oid)
        if m.get('id')!=oid:raise ReadFault('INTEGRITY_MISMATCH')
        if len(json.dumps(m,ensure_ascii=False,separators=(',',':')).encode())>self.limit('record_bytes'):raise ReadFault('LIMIT_EXCEEDED')
        return m
    def root(self,t,at):
        exact='snapshot' in at; oid=at['snapshot']['id'] if exact else self.p.resolve(t); seen=set(); hops=0; expected=None
        while True:
            m=self.inspect(t,oid)
            if expected is not None and m.get('type')!=expected:raise ReadFault('INTEGRITY_MISMATCH')
            if oid in seen:raise ReadFault('INVALID_SOURCE')
            seen.add(oid)
            if m.get('type')=='commit' or (t['kind']!='git' and m.get('type')=='snapshot'):break
            if exact or t['kind']!='git' or m.get('type')!='tag' or not t['namespace'].startswith('refs/tags/'):raise ReadFault('INVALID_SOURCE')
            if hops>=self.limit('tag_hops'):raise ReadFault('LIMIT_EXCEEDED')
            oid=m.get('target'); expected=m.get('target_type')
            if not isinstance(oid,str) or not oid or (expected is not None and expected not in ('tag','commit','tree','blob')):raise ReadFault('INVALID_SOURCE')
            hops+=1
        if 'assert_snapshot' in at and at['assert_snapshot']!={'id':oid}:raise ReadFault('CONFLICT')
        return oid
