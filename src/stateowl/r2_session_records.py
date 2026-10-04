from __future__ import annotations
import copy,re
from .r2_types import *
from .r2_types import _REPO
from .r2_session_io import SessionIO

class Session(SessionIO):
    def legacy_link(self,parent,name,t,oid):
        links=parent.get('links',{})
        if not isinstance(links,dict) or name not in links:raise ReadFault('NOT_FOUND')
        l=links[name]
        if not isinstance(l,dict) or set(l)-{'repository','commit','path','format','select'} or not path_valid(l.get('path')):raise ReadFault('INVALID_SOURCE')
        repo=l.get('repository',t['resource'])
        if not isinstance(repo,str) or not _REPO.fullmatch(repo) or any(x in ('.','..') for x in repo.split('/')):raise ReadFault('INVALID_SOURCE')
        fmt=l.get('format','json')
        if fmt not in ('json','text'):raise ReadFault('INVALID_SOURCE')
        if 'select' in l and (fmt!='json' or not isinstance(l['select'],list) or any(not isinstance(x,str) or not x for x in l['select']) or len(l['select'])!=len(set(l['select']))):raise ReadFault('INVALID_SOURCE')
        other=repo!=t['resource']
        if other and 'commit' not in l:raise ReadFault('EXACT_SNAPSHOT_REQUIRED')
        if 'commit' in l and (not isinstance(l['commit'],str) or not re.fullmatch('[0-9a-f]{40}',l['commit'])):raise ReadFault('INVALID_SOURCE')
        dest={**t,'resource':repo.lower()} if other else t; doid='git:sha1:'+l['commit'] if 'commit' in l else oid
        if other or doid!=oid:self.p.access(dest,'read');self.root(dest,{'snapshot':{'id':doid}})
        return self.found(name,l['path'],fmt,l.get('select'),dest,doid,require_obj='select' in l)[0]
    def read_op(self,r):
        t=r['target'];oid=self.root(t,r['at']);self.root_target=copy.deepcopy(t);self.root_oid=oid
        out={'protocol':PROTOCOL,'op':'read','status':'ok','target':copy.deepcopy(t),'snapshot':{'id':oid},'records':[]}
        for rec in r['records']:
            path=rec.get('path');select=rec.get('select');fmt=rec.get('format','json');routed='route' in rec
            if routed:
                rr,_=self.fetch(t,oid,'.stateowl/router.json',True);router=self.value(rr,'json')
                if not isinstance(router,dict) or set(router)!={'schema','routes'} or router.get('schema')!='stateowl.router/v1' or not isinstance(router.get('routes'),dict) or not router['routes']:raise ReadFault('INVALID_SOURCE')
                if rec['route'] not in router['routes']:raise ReadFault('NOT_FOUND')
                e=router['routes'][rec['route']]
                if not isinstance(e,dict) or set(e)!={'path','select'} or not path_valid(e.get('path')) or not isinstance(e.get('select'),list) or any(not isinstance(x,str) or not x for x in e['select']) or len(e['select'])!=len(set(e['select'])):raise ReadFault('INVALID_SOURCE')
                path=e['path'];select=rec.get('select',e['select']);fmt='json'
            try:record,raw=self.found(rec['key'],path,fmt,select,t,oid,require_obj=routed)
            except ReadFault as e:
                if e.code!='NOT_FOUND' or not rec.get('optional'):raise
                out['records'].append({'key':rec['key'],'status':'absent','path':path});continue
            if rec.get('expand'):
                parent=self.value(raw,'json')
                if not isinstance(parent,dict):raise ReadFault('INVALID_SOURCE')
                self.fetch(t,oid,path,True);record['expanded']=[self.legacy_link(parent,n,t,oid) for n in rec['expand']]
            out['records'].append(record)
        if 'resolver' in r:out['routing']={'binding':r['resolver'],'sources':copy.deepcopy(self.routing)}
        return out
