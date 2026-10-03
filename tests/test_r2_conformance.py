from __future__ import annotations
import base64,json,sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from stateowl.r2 import R2Reader,ReadFault,git_blob
from stateowl.r2_legacy import R2LegacyReader,LegacyCompatibilityError
from r2_fixture_support import FixtureProvider,load_read_inputs,case_inputs

class NormativeReadConformance(unittest.TestCase):
 def test_all_normative_read_cases(self):
  suite,cases=load_read_inputs(ROOT);self.assertEqual(len(cases),90)
  for case in cases:
   with self.subTest(case=case['id']):
    raw,w,c=case_inputs(suite,case);p=FixtureProvider(w);out=R2Reader(p,c).read_bytes(raw)
    self.assertEqual(out,case['expected'])
    for k,n in case.get('trace',{}).items():
     if k in ('access','resolve','inspect','file'):self.assertEqual(p.counts[k],n)
    if out.get('op')=='read' and out.get('status')=='ok':
     req=json.loads(raw);self.assertEqual(p.counts['resolve'],1 if req['at'].get('current') else 0)
     file_args=[json.dumps(a,sort_keys=True) for m,a in p.calls if m=='file'];self.assertEqual(len(file_args),len(set(file_args)))

class LegacyProvider:
 def __init__(self,suite,case):
  self.target={'kind':'git','authority':'github.com','resource':suite['repository'],'namespace':'refs/heads/main'};self.case=case;self.i=0;self.paths=[]
  self.files={**suite['files'],**case['overrides']}
 def access(self,t,o):
  if t!=self.target:raise ReadFault('FORBIDDEN')
  return {'auth_scope':'legacy'}
 def resolve(self,t):
  h=self.case['heads'][self.i];self.i+=1;return 'git:sha1:'+h
 def inspect(self,t,s):return {'id':s,'type':'commit','parents':[]}
 def file(self,t,s,p):
  self.paths.append(p);it=self.files.get(p)
  if it is None:raise ReadFault('NOT_FOUND')
  raw=base64.b64decode(it['base64'],validate=True)
  return {'base64':it['base64'],'mode':'100644','digest':'sha256:'+__import__('hashlib').sha256(raw).hexdigest(),'integrity':'provider','object':'git:sha1:'+it['blob']}

class LegacyConformance(unittest.TestCase):
 def test_all_normative_legacy_cases_through_r2(self):
  p=ROOT/'docs/protocol/legacy-v0.1.0.json'
  if not p.exists():p=ROOT/'.frozen-protocol/legacy-v0.1.0.json'
  suite=json.loads(p.read_text());self.assertEqual(len(suite['cases']),6)
  for case in suite['cases']:
   with self.subTest(case=case['id']):
    provider=LegacyProvider(suite,case);reader=R2LegacyReader(provider);actual=[]
    for req in case['requests']:
     try:actual.append({'result':reader.read(**req)})
     except LegacyCompatibilityError as e:actual.append({'error':e.code})
    self.assertEqual(actual,case['responses']);self.assertEqual(provider.paths,case['file_paths'])

if __name__=='__main__':unittest.main()
