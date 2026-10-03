from __future__ import annotations
import json,math
from decimal import Decimal
from .r2_base import *

def strict_json(raw:bytes,*,source:bool,depth:int):
    bad='INVALID_SOURCE' if source else 'INVALID_REQUEST'; numeric='NUMBER_UNREPRESENTABLE' if source else bad
    try:
        if raw.startswith(b'\xef\xbb\xbf'): raise ReadFault(bad)
        text=raw.decode(); n=0; q=False; esc=False
        for c in text:
            if q:
                if esc: esc=False
                elif c=='\\':esc=True
                elif c=='"':q=False
            elif c=='"':q=True
            elif c in '[{':
                n+=1
                if n>depth:raise ReadFault('LIMIT_EXCEEDED')
            elif c in ']}':n-=1
        def pairs(items):
            out={}
            for k,v in items:
                if k in out: raise ReadFault(bad)
                out[k]=v
            return out
        def const(_): raise ReadFault(bad)
        val=json.loads(text,object_pairs_hook=pairs,parse_int=Decimal,parse_float=Decimal,parse_constant=const)
        def check(v):
            if isinstance(v,str):v.encode()
            elif isinstance(v,Decimal):
                if not v.is_finite():raise ReadFault(numeric)
                if v.is_zero() and v.is_signed():raise ReadFault(bad)
                if v==v.to_integral_value():
                    if abs(v)>MAX_SAFE:raise ReadFault(numeric)
                else:
                    f=float(v)
                    if not math.isfinite(f) or Decimal(repr(f))!=v:raise ReadFault(numeric)
            elif isinstance(v,dict):
                for k,x in v.items():check(k);check(x)
            elif isinstance(v,list):
                for x in v:check(x)
        check(val)
        def conv(v):
            if isinstance(v,Decimal):return int(v) if v==v.to_integral_value() else float(v)
            if isinstance(v,dict):return {k:conv(x) for k,x in v.items()}
            if isinstance(v,list):return [conv(x) for x in v]
            return v
        return conv(val)
    except ReadFault:raise
    except (ValueError,UnicodeError,OverflowError,RecursionError):raise ReadFault(bad) from None

def request_valid(r):
    if not isinstance(r,dict) or set(r)-{'protocol','op','target','at','records','resolver'} or set(r)<{'protocol','op','target','at','records'}:return False
    t=r['target']
    if r['op']!='read' or not isinstance(t,dict) or set(t)!={'kind','authority','resource','namespace'} or any(not isinstance(t[k],str) or not t[k] for k in t):return False
    a=r['at']
    if not isinstance(a,dict):return False
    if 'snapshot' in a:
        if set(a)!={'snapshot'} or not isinstance(a['snapshot'],dict) or set(a['snapshot'])!={'id'} or not isinstance(a['snapshot']['id'],str) or not a['snapshot']['id']:return False
    elif a.get('current') is True:
        if set(a)-{'current','assert_snapshot'}:return False
        if 'assert_snapshot' in a and (not isinstance(a['assert_snapshot'],dict) or set(a['assert_snapshot'])!={'id'} or not isinstance(a['assert_snapshot']['id'],str)):return False
    else:return False
    recs=r['records']
    if not isinstance(recs,list) or not recs:return False
    need=False
    for x in recs:
        if not isinstance(x,dict) or not isinstance(x.get('key'),str) or not x['key']:return False
        if 'optional' in x and type(x['optional']) is not bool:return False
        if 'expand' in x:
            if not isinstance(x['expand'],list) or any(not isinstance(v,str) or not v for v in x['expand']) or len(x['expand'])!=len(set(x['expand'])):return False
            need|=bool(x['expand'])
        if 'select' in x and (not isinstance(x['select'],list) or any(not isinstance(v,str) for v in x['select']) or len(x['select'])!=len(set(x['select']))):return False
        if 'path' in x:
            if set(x)-{'key','path','format','select','optional','expand'} or 'route' in x or 'format' not in x or not path_valid(x['path']) or x['format'] not in ('json','text','base64'):return False
            if 'select' in x and x['format']!='json':return False
        elif 'route' in x:
            need=True
            if set(x)-{'key','route','select','optional','expand'} or not isinstance(x['route'],str) or not x['route']:return False
        else:return False
    if need:
        if not isinstance(r.get('resolver'),str) or not r['resolver'] or len(r['resolver'])>256 or any(ord(c)<33 or ord(c)>126 for c in r['resolver']):return False
    elif 'resolver' in r:return False
    return True
