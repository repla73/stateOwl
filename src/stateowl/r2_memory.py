from __future__ import annotations
import base64, copy
from collections import Counter
from .r2 import ReadFault,digest,git_blob
class MemoryReadProvider:
 def __init__(self,target,objects,head=None,algorithm=None):self.target=copy.deepcopy(target);self.objects=copy.deepcopy(objects);self.head=head;self.algorithm=algorithm;self.calls=Counter();self.returned_bytes=0
 def chk(self,t):
  if dict(t)!=self.target:raise ReadFault('FORBIDDEN')
 def access(self,t,o):self.calls['access']+=1;self.chk(t);return {'auth_scope':'memory-read'} if o in ('read','observe') else (_ for _ in()).throw(ReadFault('UNSUPPORTED_CAPABILITY'))
 def resolve(self,t):
  self.calls['resolve']+=1;self.chk(t)
  if self.head is None:raise ReadFault('NOT_FOUND')
  return self.head
 def inspect(self,t,s):
  self.calls['inspect']+=1;self.chk(t);o=self.objects.get(s)
  if o is None:raise ReadFault('SNAPSHOT_UNAVAILABLE')
  return {'id':s,**{k:copy.deepcopy(v) for k,v in o.items() if k!='files'}}
 def file(self,t,s,p):
  self.calls['file']+=1;self.chk(t);o=self.objects.get(s)
  if o is None:raise ReadFault('SNAPSHOT_UNAVAILABLE')
  item=o.get('files',{}).get(p)
  if item is None:raise ReadFault('NOT_FOUND')
  raw=item if isinstance(item,bytes) else item['content'];mode='100644' if isinstance(item,bytes) else item.get('mode','100644')
  out={'base64':base64.b64encode(raw).decode(),'mode':mode,'digest':digest(raw),'integrity':'provider'}
  if self.algorithm:out['object']=git_blob(raw,self.algorithm)
  self.returned_bytes+=len(raw);return out
