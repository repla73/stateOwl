from __future__ import annotations
import base64,copy,json
from .r2_types import *
from .r2_session_base import SessionBase

class SessionIO(SessionBase):
    def fetch(self,t,oid,path,routing=False):
        k=(json.dumps(t,sort_keys=True,separators=(',',':')),oid,path)
        if k in self.absent:raise ReadFault('NOT_FOUND')
        if k not in self.cache:
            try:item=self.p.file(t,oid,path)
            except ReadFault as e:
                if e.code=='NOT_FOUND':self.absent.add(k)
                raise
            try:raw=base64.b64decode(item['base64'],validate=True)
            except Exception:raise ReadFault('INVALID_SOURCE') from None
            if base64.b64encode(raw).decode()!=item['base64']:raise ReadFault('INVALID_SOURCE')
            if len(raw)>self.limit('record_bytes'):raise ReadFault('LIMIT_EXCEEDED')
            if item.get('digest')!=digest(raw):raise ReadFault('INTEGRITY_MISMATCH')
            obj=item.get('object')
            if obj is not None:
                p=parse_git(obj)
                if not p or git_blob(raw,p[0])!=obj:raise ReadFault('INTEGRITY_MISMATCH')
            if item.get('mode') not in ('100644','100755') or item.get('integrity') not in ('provider','object_chain'):raise ReadFault('INVALID_SOURCE')
            src={'path':path,'digest':digest(raw),'integrity':item['integrity']}
            if obj is not None:src['object']=obj
            if t!=self.root_target or oid!=self.root_oid:src['origin']={'target':copy.deepcopy(t),'snapshot':{'id':oid}}
            self.cache[k]=(raw,src)
        raw,src=self.cache[k]
        if routing and src not in self.routing:self.routing.append(copy.deepcopy(src))
        return raw,copy.deepcopy(src)
    def value(self,raw,fmt):
        if fmt=='json':return strict_json(raw,source=True,depth=self.limit('json_depth'))
        if fmt=='base64':return base64.b64encode(raw).decode()
        try:return raw.decode()
        except UnicodeError:raise ReadFault('INVALID_SOURCE') from None
    def found(self,key,path,fmt,select,t,oid,require_obj=False):
        raw,src=self.fetch(t,oid,path);v=self.value(raw,fmt)
        if require_obj and not isinstance(v,dict):raise ReadFault('INVALID_SOURCE')
        out={'key':key,'status':'found','format':fmt,'value':v,'source':src}
        if select is not None:
            if not isinstance(v,dict):raise ReadFault('INVALID_REQUEST')
            out['value']={k:v[k] for k in select if k in v};out['select']=list(select);out['missing']=[k for k in select if k not in v]
        return out,raw
