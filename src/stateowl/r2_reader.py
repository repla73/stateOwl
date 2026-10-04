from __future__ import annotations
import copy, json
from collections import Counter
from .r2_types import *

class CounterProvider:
    def __init__(self,p):self.p=p;self.counts=Counter()
    def access(self,t,o):self.counts['access']+=1;return self.p.access(t,o)
    def resolve(self,t):self.counts['resolve']+=1;return self.p.resolve(t)
    def inspect(self,t,s):self.counts['inspect']+=1;return self.p.inspect(t,s)
    def file(self,t,s,p):self.counts['file']+=1;return self.p.file(t,s,p)

DEFAULT_READ_CAPABILITIES={'protocol':PROTOCOL,'operations':['read'],'formats':['json','text','base64'],'features':['routes','expand'],'resolvers':[ROUTER_V1],'limits':{'request_bytes':65536,'record_bytes':16384,'mutation_bytes':32768,'response_bytes':65536,'records':32,'expansions':16,'changes':32,'tag_hops':8,'reconcile_commits':16,'json_depth':64}}

class R2Reader:
    def __init__(self,provider,capabilities=DEFAULT_READ_CAPABILITIES):self.provider=provider;self.cap=copy.deepcopy(capabilities);self.last_instrumentation=ReadInstrumentation()
    def read(self,request):
        try:raw=json.dumps(request,ensure_ascii=False,allow_nan=False,separators=(',',':')).encode()
        except Exception:return fail('INVALID_REQUEST','unknown')
        return self.read_bytes(raw)
    def read_bytes(self,raw):
        cp=CounterProvider(self.provider); s=Session(cp,self.cap)
        try:return s.run(raw)
        finally:self.last_instrumentation=ReadInstrumentation(**{k:cp.counts[k] for k in ('access','resolve','inspect','file')})

from .r2_session_records import Session
