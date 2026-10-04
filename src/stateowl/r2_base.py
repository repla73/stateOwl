from __future__ import annotations
import hashlib,re
from dataclasses import dataclass
from typing import Any,Mapping,Protocol

PROTOCOL='stateowl/0.2-draft.3'; ROUTER_V1='urn:stateowl:binding:router-v1:1'; MAX_SAFE=9007199254740991
RETRY={}
for r,cs in {'after_correction':'INVALID_REQUEST NOT_FOUND EXACT_SNAPSHOT_REQUIRED INVALID_SOURCE NUMBER_UNREPRESENTABLE LIMIT_EXCEEDED VALIDATION_FAILED','after_refresh':'UNAUTHENTICATED CONFLICT NAMESPACE_DISCONTINUITY TOKEN_INVALID','after_backoff':'RATE_LIMITED PROVIDER_UNAVAILABLE','never':'UNSUPPORTED_VERSION UNSUPPORTED_CAPABILITY FORBIDDEN NOT_FOUND_OR_FORBIDDEN SNAPSHOT_UNAVAILABLE INTEGRITY_MISMATCH NO_CHANGE HISTORY_UNAVAILABLE'}.items():
    for c in cs.split(): RETRY[c]=r
_GIT=re.compile(r'git:(sha1):([0-9a-f]{40})|git:(sha256):([0-9a-f]{64})')
_REPO=re.compile(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+')

class ReadFault(ValueError):
    def __init__(self,code:str,msg:str|None=None): self.code=code; super().__init__(msg or code)
class ReadProvider(Protocol):
    def access(self,target:Mapping[str,Any],operation:str)->Mapping[str,Any]: ...
    def resolve(self,target:Mapping[str,Any])->str: ...
    def inspect(self,target:Mapping[str,Any],snapshot:str)->Mapping[str,Any]: ...
    def file(self,target:Mapping[str,Any],snapshot:str,path:str)->Mapping[str,Any]: ...
@dataclass(frozen=True)
class ReadInstrumentation: access:int=0; resolve:int=0; inspect:int=0; file:int=0

def fail(code,op='read'): return {'protocol':PROTOCOL,'op':op,'status':'error','error':{'code':code,'retry':RETRY[code]}}
def digest(raw:bytes): return 'sha256:'+hashlib.sha256(raw).hexdigest()
def git_blob(raw:bytes,alg:str): return f'git:{alg}:'+hashlib.new(alg,b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()
def parse_git(value:Any):
    if not isinstance(value,str): return None
    m=_GIT.fullmatch(value)
    return ('sha1',m.group(2)) if m and m.group(1) else ('sha256',m.group(4)) if m else None
def typed_git(raw:str):
    if re.fullmatch('[0-9a-f]{40}',raw): return 'git:sha1:'+raw
    if re.fullmatch('[0-9a-f]{64}',raw): return 'git:sha256:'+raw
    raise ReadFault('INVALID_SOURCE')
def raw_git(value:str):
    p=parse_git(value)
    if not p: raise ReadFault('INVALID_SOURCE')
    return p[1]
def path_valid(v):
    return isinstance(v,str) and bool(v) and not v.startswith('/') and not v.endswith('/') and '\\' not in v and all(ord(c)>=32 and ord(c)!=127 for c in v) and all(p not in ('','.','..') for p in v.split('/'))
def ref_valid(v):
    if not isinstance(v,str) or not v.startswith(('refs/heads/','refs/tags/')) or v.endswith(('/','.')) or '..' in v or '@{' in v:return False
    if any(ord(c)<33 or ord(c)==127 or c in '~^:?*[\\' for c in v):return False
    return all(p and not p.startswith('.') and not p.endswith('.lock') for p in v.split('/'))
