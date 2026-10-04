from __future__ import annotations
import base64,hashlib,json,os
from collections import Counter,OrderedDict
from urllib.error import HTTPError,URLError
from urllib.parse import quote
from urllib.request import Request,urlopen
from .r2 import ReadFault,digest,raw_git,typed_git
class GitHubReadProvider:
 def __init__(self,token=None,api_base='https://api.github.com',timeout=15.0):self.token=token if token is not None else os.getenv('GITHUB_TOKEN');self.api_base=api_base.rstrip('/');self.timeout=timeout;self.calls=Counter();self.http_requests=0;self.wire_bytes=0;self.types={};self.meta={};self.trees={};self.blobs={}
 def repo(self,t):
  if t.get('kind')!='git' or t.get('authority')!='github.com':raise ReadFault('FORBIDDEN')
  r=t.get('resource','')
  if r.lower()!=r or r.count('/')!=1 or r.endswith('.git'):raise ReadFault('FORBIDDEN')
  return r.split('/',1)
 def req(self,t,suffix,missing):
  o,r=self.repo(t);url=f'{self.api_base}/repos/{quote(o,safe="")}/{quote(r,safe="")}/{suffix}'.rstrip('/');h={'Accept':'application/vnd.github+json','User-Agent':'stateowl/r2-python-reader','X-GitHub-Api-Version':'2022-11-28'}
  if self.token:h['Authorization']='Bearer '+self.token
  self.http_requests+=1
  try:
   with urlopen(Request(url,headers=h),timeout=self.timeout) as resp:raw=resp.read()
  except HTTPError as e:
   if e.code==404:
    if missing is None:return None
    raise ReadFault(missing)
   if e.code==401:raise ReadFault('UNAUTHENTICATED')
   if e.code==403:raise ReadFault('FORBIDDEN')
   raise ReadFault('PROVIDER_UNAVAILABLE')
  except URLError:raise ReadFault('PROVIDER_UNAVAILABLE')
  self.wire_bytes+=len(raw)
  try:return json.loads(raw)
  except Exception:raise ReadFault('INVALID_SOURCE') from None
 def access(self,t,o):self.calls['access']+=1;self.req(t,'','NOT_FOUND_OR_FORBIDDEN');return {'auth_scope':'github-read'}
 def resolve(self,t):
  self.calls['resolve']+=1;ns=t['namespace'].removeprefix('refs/');v=self.req(t,'git/ref/'+quote(ns,safe='/'),'NOT_FOUND');obj=v.get('object',{});oid=typed_git(obj.get('sha',''));typ=obj.get('type')
  if typ not in ('commit','tag','tree','blob'):raise ReadFault('INVALID_SOURCE')
  self.types[(t['resource'],oid)]=typ;return oid
 def probe(self,t,s):
  k=(t['resource'],s)
  if k in self.meta:return self.meta[k]
  oid=raw_git(s);hint=self.types.get(k);order=([hint] if hint else [])+[x for x in ('commit','tag','blob','tree') if x!=hint]
  for typ in order:
   v=self.req(t,{'commit':'git/commits/','tag':'git/tags/','blob':'git/blobs/','tree':'git/trees/'}[typ]+oid,None)
   if v is not None:break
  else:raise ReadFault('SNAPSHOT_UNAVAILABLE')
  if typ=='commit':m={'id':s,'type':'commit','parents':[typed_git(x['sha']) for x in v.get('parents',[])],'tree':typed_git(v['tree']['sha'])}
  elif typ=='tag':
   obj=v.get('object',{});tt=obj.get('type')
   if tt not in ('commit','tag','tree','blob'):raise ReadFault('INVALID_SOURCE')
   target=typed_git(obj['sha']);self.types[(t['resource'],target)]=tt;m={'id':s,'type':'tag','target':target,'target_type':tt}
  else:m={'id':s,'type':typ}
  self.meta[k]=m;return m
 def inspect(self,t,s):self.calls['inspect']+=1;return dict(self.probe(t,s))
 def tree(self,t,oid):
  k=(t['resource'],oid)
  if k not in self.trees:
   v=self.req(t,'git/trees/'+oid,'SNAPSHOT_UNAVAILABLE')
   if v.get('truncated'):raise ReadFault('LIMIT_EXCEEDED')
   self.trees[k]=v.get('tree',[])
  return self.trees[k]
 def blob(self,t,oid):
  k=(t['resource'],oid)
  if k not in self.blobs:
   v=self.req(t,'git/blobs/'+oid,'NOT_FOUND')
   try:raw=base64.b64decode(''.join(v['content'].split()),validate=True)
   except Exception:raise ReadFault('INVALID_SOURCE') from None
   alg='sha1' if len(oid)==40 else 'sha256' if len(oid)==64 else None
   if not alg or hashlib.new(alg,b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()!=oid:raise ReadFault('INTEGRITY_MISMATCH')
   self.blobs[k]=raw
  return self.blobs[k]
 def file(self,t,s,path):
  self.calls['file']+=1;m=self.probe(t,s)
  if m.get('type')!='commit':raise ReadFault('INVALID_SOURCE')
  tree=raw_git(m['tree']);entry=None
  for i,part in enumerate(path.split('/')):
   found=[e for e in self.tree(t,tree) if e.get('path')==part]
   if len(found)!=1:raise ReadFault('NOT_FOUND')
   entry=found[0]
   if i<len(path.split('/'))-1:
    if entry.get('type')!='tree':raise ReadFault('NOT_FOUND')
    tree=entry['sha']
  if entry.get('type')!='blob':raise ReadFault('INVALID_SOURCE')
  raw=self.blob(t,entry['sha']);return {'base64':base64.b64encode(raw).decode(),'mode':entry['mode'],'digest':digest(raw),'integrity':'provider','object':typed_git(entry['sha'])}
