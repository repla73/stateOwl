from __future__ import annotations
import base64,hashlib,subprocess
from collections import Counter
from pathlib import Path
from .r2 import ReadFault,digest,raw_git,typed_git
class LocalGitReadProvider:
 def __init__(self,path,target):self.path=Path(path);self.target=dict(target);self.calls=Counter();self.process_calls=0;self.returned_bytes=0;self.alg=None
 def chk(self,t):
  if dict(t)!=self.target or t.get('kind')!='git':raise ReadFault('FORBIDDEN')
 def git(self,*a,missing='SNAPSHOT_UNAVAILABLE'):
  self.process_calls+=1;p=subprocess.run(['git','-C',str(self.path),*a],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
  if p.returncode:raise ReadFault(missing)
  self.returned_bytes+=len(p.stdout);return p.stdout
 def algorithm(self):
  if self.alg is None:self.alg=self.git('rev-parse','--show-object-format',missing='PROVIDER_UNAVAILABLE').decode().strip()
  if self.alg not in ('sha1','sha256'):raise ReadFault('INVALID_SOURCE')
  return self.alg
 def access(self,t,o):self.calls['access']+=1;self.chk(t);self.git('rev-parse','--git-dir',missing='PROVIDER_UNAVAILABLE');return {'auth_scope':'local-git'}
 def resolve(self,t):self.calls['resolve']+=1;self.chk(t);return typed_git(self.git('rev-parse','--verify',t['namespace'],missing='NOT_FOUND').decode().strip())
 def inspect(self,t,s):
  self.calls['inspect']+=1;self.chk(t);oid=raw_git(s);kind=self.git('cat-file','-t',oid).decode().strip();body=self.git('cat-file','-p',oid)
  if kind=='commit':
   lines=body.decode(errors='replace').splitlines();parents=[typed_git(x[7:]) for x in lines if x.startswith('parent ')];tree=next((typed_git(x[5:]) for x in lines if x.startswith('tree ')),None)
   if not tree:raise ReadFault('INVALID_SOURCE')
   return {'id':s,'type':'commit','parents':parents,'tree':tree}
  if kind=='tag':
   lines=body.split(b'\n\n',1)[0].decode(errors='replace').splitlines();obj=next((x[7:] for x in lines if x.startswith('object ')),None);typ=next((x[5:] for x in lines if x.startswith('type ')),None)
   if not obj or typ not in ('tag','commit','tree','blob'):raise ReadFault('INVALID_SOURCE')
   return {'id':s,'type':'tag','target':typed_git(obj),'target_type':typ}
  return {'id':s,'type':kind}
 def file(self,t,s,path):
  self.calls['file']+=1;self.chk(t);commit=raw_git(s);data=self.git('ls-tree','--full-tree','-z',commit,'--',path)
  es=[x for x in data.split(b'\0') if x]
  if not es:raise ReadFault('NOT_FOUND')
  try:meta,actual=es[0].split(b'\t',1);mode,kind,oid=meta.decode().split(' ',2);actual=actual.decode()
  except Exception:raise ReadFault('INVALID_SOURCE') from None
  if actual!=path:raise ReadFault('NOT_FOUND')
  if kind!='blob':raise ReadFault('INVALID_SOURCE')
  raw=self.git('cat-file','blob',oid);alg=self.algorithm();observed=hashlib.new(alg,b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()
  if observed!=oid:raise ReadFault('INTEGRITY_MISMATCH')
  return {'base64':base64.b64encode(raw).decode(),'mode':mode,'digest':digest(raw),'integrity':'provider','object':typed_git(oid)}
