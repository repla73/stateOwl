from __future__ import annotations
import copy,json,struct,sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from stateowl.r2 import PROTOCOL,R2Reader
from stateowl.r2_jcs import jcs_bytes
from stateowl.r2_memory import MemoryReadProvider
from stateowl.r2_reader import DEFAULT_READ_CAPABILITIES
class AuditCorrectionTests(unittest.TestCase):
 def _f02(self,limit):
  t={'kind':'memory','authority':'fixture.local','resource':'audit-f02','namespace':'state'};o='opaque:audit:f02';raw=(json.dumps({'n':1e-7,'pad':'x'*606},separators=(',',':'))+'\n').encode();p=MemoryReadProvider(t,{o:{'type':'snapshot','files':{'state.json':raw}}},head=o);r={'protocol':PROTOCOL,'op':'read','target':t,'at':{'current':True},'records':[{'key':'x','path':'state.json','format':'json'}]};c=copy.deepcopy(DEFAULT_READ_CAPABILITIES);c['limits']['response_bytes']=limit;rd=R2Reader(p,c);return rd,p,rd.read(r)
 def test_f02_audited_1e7_exact_boundary_succeeds(self):
  rd,_,r=self._f02(1024);self.assertEqual(r['status'],'ok');self.assertEqual(len(jcs_bytes(r)),1024);ordinary=json.dumps(r,ensure_ascii=False,separators=(',',':')).encode();self.assertEqual(len(ordinary),1025);self.assertIn(b'1e-7',jcs_bytes(r));self.assertIn(b'1e-07',ordinary);self.assertEqual(rd.last_instrumentation.resolve,1)
 def test_f02_one_byte_below_required_limit_fails(self):
  _,_,r=self._f02(1023);self.assertEqual(r['error']['code'],'LIMIT_EXCEEDED')
 def test_f02_rfc8785_negative_zero_is_zero(self):
  v=struct.unpack('>d',bytes.fromhex('8000000000000000'))[0];self.assertEqual(jcs_bytes(v),b'0')
 def test_f02_rfc8785_exponent_plain_boundaries(self):
  vs={'3eb0c6f7a0b5ed8c':b'9.999999999999997e-7','3eb0c6f7a0b5ed8d':b'0.000001','444b1ae4d6e2ef4e':b'999999999999999700000','444b1ae4d6e2ef4f':b'999999999999999900000','444b1ae4d6e2ef50':b'1e+21','44b52d02c7e14af5':b'9.999999999999997e+22','44b52d02c7e14af6':b'1e+23','44b52d02c7e14af7':b'1.0000000000000001e+23'}
  for b,e in vs.items():
   with self.subTest(bits=b):self.assertEqual(jcs_bytes(struct.unpack('>d',bytes.fromhex(b))[0]),e)
 def test_f02_rfc8785_rounding_vectors(self):
  vs={'0000000000000001':b'5e-324','7fefffffffffffff':b'1.7976931348623157e+308','41b3de4355555553':b'333333333.3333332','41b3de4355555554':b'333333333.33333325','41b3de4355555555':b'333333333.3333333','41b3de4355555556':b'333333333.3333334','41b3de4355555557':b'333333333.33333343','becbf647612f3696':b'-0.0000033333333333333333','43143ff3c1cb0959':b'1424953923781206.2'}
  for b,e in vs.items():
   with self.subTest(bits=b):self.assertEqual(jcs_bytes(struct.unpack('>d',bytes.fromhex(b))[0]),e)
 def test_f07_empty_assert_snapshot_rejected_before_provider_access(self):
  t={'kind':'memory','authority':'fixture.local','resource':'audit-f07','namespace':'state'};o='opaque:audit:f07';p=MemoryReadProvider(t,{o:{'type':'snapshot','files':{'state.json':b'{}\n'}}},head=o);r={'protocol':PROTOCOL,'op':'read','target':t,'at':{'current':True,'assert_snapshot':{'id':''}},'records':[{'key':'x','path':'state.json','format':'json'}]};rd=R2Reader(p);res=rd.read(r);self.assertEqual(res['error']['code'],'INVALID_REQUEST');self.assertEqual((rd.last_instrumentation.access,rd.last_instrumentation.resolve,rd.last_instrumentation.inspect,rd.last_instrumentation.file),(0,0,0,0));self.assertEqual(sum(p.calls.values()),0)
if __name__=='__main__':unittest.main()
