#!/usr/bin/env python3
"""Loopback test client for HARNESS.md; shares the model, is NOT independent."""
import json
import sys
from fixture_codec import strict, unbase64
from harness import Model, ProviderFailure

class Proxy:
    def __init__(self): self.sequence=0
    def call(self,method,**args):
        self.sequence+=1
        print(json.dumps({'type':'call','id':self.sequence,'method':method,'args':args}),flush=True)
        reply=strict(sys.stdin.buffer.readline(1048577))
        if reply.get('type')!='return' or reply.get('id')!=self.sequence:
            raise ValueError('mismatched harness reply')
        if 'fault' in reply:
            f=reply['fault'];raise ProviderFailure(f['code'],f['dispatched'])
        return reply['value']

if __name__=='__main__':
    while True:
        line=sys.stdin.buffer.readline(1048577)
        if not line:break
        start=strict(line)
        if set(start)!={'type','request_base64','capabilities'} or start['type']!='start':
            raise ValueError('invalid harness start')
        # A new provider universe: no state or object cache carries across cases.
        response=Model(Proxy(),start['capabilities']).run(unbase64(start['request_base64']))
        print(json.dumps({'type':'result','response':response},ensure_ascii=True),flush=True)
