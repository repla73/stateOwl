import json,os,subprocess,tempfile,unittest
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from stateowl.r2 import *
from stateowl.r2_memory import MemoryReadProvider
from stateowl.r2_localgit import LocalGitReadProvider

def enc(v):return (json.dumps(v,separators=(',',':'))+'\n').encode()
class R2Tests(unittest.TestCase):
 def setUp(self):
  self.t={'kind':'git','authority':'github.com','resource':'fixture/project','namespace':'refs/heads/state'};self.A='git:sha1:'+'a'*40
  self.router=enc({'schema':'stateowl.router/v1','routes':{'work':{'path':'state/work.json','select':['id','status']}}})
  self.work=enc({'id':'work','status':'working','count':1,'links':{'detail':{'path':'state/detail.txt','format':'text'}}})
  self.p=MemoryReadProvider(self.t,{self.A:{'type':'commit','parents':[],'files':{'.stateowl/router.json':self.router,'state/work.json':self.work,'state/detail.txt':b'detail\n'}}},head=self.A,algorithm='sha1')
 def req(self,at,records,resolver=None):
  r={'protocol':PROTOCOL,'op':'read','target':self.t,'at':at,'records':records}
  if resolver:r['resolver']=resolver
  return r
 def test_exact_zero_resolve_and_batch_file_share(self):
  rd=R2Reader(self.p);res=rd.read(self.req({'snapshot':{'id':self.A}},[{'key':'a','path':'state/work.json','format':'json','select':['status']},{'key':'b','path':'state/work.json','format':'json','select':['count']}]))
  self.assertEqual(res['status'],'ok');self.assertEqual(rd.last_instrumentation.resolve,0);self.assertEqual(rd.last_instrumentation.file,1)
 def test_current_one_resolve_router_expand(self):
  rd=R2Reader(self.p);res=rd.read(self.req({'current':True},[{'key':'work','route':'work','expand':['detail']}],ROUTER_V1))
  self.assertEqual(res['records'][0]['expanded'][0]['value'],'detail\n');self.assertEqual(rd.last_instrumentation.resolve,1);self.assertEqual(rd.last_instrumentation.file,3)
 def test_opaque_non_git(self):
  t={'kind':'fixture','authority':'stateowl.invalid','resource':'fixture/project','namespace':'state'};o='opaque/revision-7';p=MemoryReadProvider(t,{o:{'type':'snapshot','files':{'state/work.json':b'{"status":"working"}\n'}}},head=o)
  r={'protocol':PROTOCOL,'op':'read','target':t,'at':{'snapshot':{'id':o}},'records':[{'key':'x','path':'state/work.json','format':'json','select':['status']}]};rd=R2Reader(p);out=rd.read(r);self.assertEqual(out['snapshot']['id'],o);self.assertEqual(rd.last_instrumentation.resolve,0);self.assertNotIn('object',out['records'][0]['source'])
 def test_annotated_tag_peels_only_current_tag_namespace(self):
  T='git:sha1:'+'f'*40;G='git:sha1:'+'1'*40;p=MemoryReadProvider({**self.t,'namespace':'refs/tags/v1'},{T:{'type':'tag','target':G,'target_type':'tag'},G:{'type':'tag','target':self.A,'target_type':'commit'},self.A:{'type':'commit','parents':[],'files':{'state/work.json':self.work}}},head=T,algorithm='sha1');rd=R2Reader(p);r={'protocol':PROTOCOL,'op':'read','target':{**self.t,'namespace':'refs/tags/v1'},'at':{'current':True},'records':[{'key':'x','path':'state/work.json','format':'json'}]};self.assertEqual(rd.read(r)['status'],'ok');r['at']={'snapshot':{'id':T}};self.assertEqual(rd.read(r)['error']['code'],'INVALID_SOURCE')
 def test_sha256_typed_identity(self):
  oid='git:sha256:'+'a'*64;t=self.t;p=MemoryReadProvider(t,{oid:{'type':'commit','parents':[],'files':{'state/work.json':b'{"status":"working"}\n'}}},head=oid,algorithm='sha256');out=R2Reader(p).read(self.req({'snapshot':{'id':oid}},[{'key':'x','path':'state/work.json','format':'json'}]));self.assertTrue(out['records'][0]['source']['object'].startswith('git:sha256:'))
 def test_whole_json_validation_before_projection(self):
  bad=b'{"status":"ok","hidden":9007199254740993}\n';p=MemoryReadProvider(self.t,{self.A:{'type':'commit','files':{'x.json':bad}}},algorithm='sha1');out=R2Reader(p).read(self.req({'snapshot':{'id':self.A}},[{'key':'x','path':'x.json','format':'json','select':['status']}]));self.assertEqual(out['error']['code'],'NUMBER_UNREPRESENTABLE')

 def test_router_v1_empty_default_projection_is_legal(self):
  router=enc({'schema':'stateowl.router/v1','routes':{'work':{'path':'state/work.json','select':[]}}})
  p=MemoryReadProvider(self.t,{self.A:{'type':'commit','parents':[],'files':{'.stateowl/router.json':router,'state/work.json':self.work}}},head=self.A,algorithm='sha1')
  out=R2Reader(p).read(self.req({'snapshot':{'id':self.A}},[{'key':'work','route':'work'}],ROUTER_V1))
  self.assertEqual(out['records'][0]['value'],{});self.assertEqual(out['records'][0]['select'],[])
 def test_router_v1_empty_link_projection_is_legal(self):
  work=enc({'id':'work','status':'working','links':{'detail':{'path':'state/detail.json','select':[]}}})
  p=MemoryReadProvider(self.t,{self.A:{'type':'commit','parents':[],'files':{'.stateowl/router.json':self.router,'state/work.json':work,'state/detail.json':enc({'x':1})}}},head=self.A,algorithm='sha1')
  out=R2Reader(p).read(self.req({'snapshot':{'id':self.A}},[{'key':'work','route':'work','expand':['detail']}],ROUTER_V1))
  child=out['records'][0]['expanded'][0];self.assertEqual(child['value'],{});self.assertEqual(child['select'],[])
 def test_local_git_and_tag(self):
  with tempfile.TemporaryDirectory() as d:
   subprocess.run(['git','init','-q',d],check=True);subprocess.run(['git','-C',d,'config','user.email','x@y'],check=True);subprocess.run(['git','-C',d,'config','user.name','x'],check=True);Path(d,'state.json').write_text('{"status":"ok"}\n');subprocess.run(['git','-C',d,'add','state.json'],check=True);subprocess.run(['git','-C',d,'commit','-qm','base'],check=True);subprocess.run(['git','-C',d,'tag','-a','v1','-m','v1'],check=True)
   t={'kind':'git','authority':'local','resource':'local/project','namespace':'refs/heads/master'};p=LocalGitReadProvider(d,t);oid=p.resolve(t);r={'protocol':PROTOCOL,'op':'read','target':t,'at':{'snapshot':{'id':oid}},'records':[{'key':'x','path':'state.json','format':'json'}]};rd=R2Reader(p);self.assertEqual(rd.read(r)['status'],'ok');self.assertEqual(rd.last_instrumentation.resolve,0)
   tt={**t,'namespace':'refs/tags/v1'};p2=LocalGitReadProvider(d,tt);r['target']=tt;r['at']={'current':True};self.assertEqual(R2Reader(p2).read(r)['status'],'ok')

 def test_tag_cycle_and_advertised_type_mismatch(self):
  T='git:sha1:'+'f'*40;G='git:sha1:'+'1'*40;tt={**self.t,'namespace':'refs/tags/v1'}
  cyc=MemoryReadProvider(tt,{T:{'type':'tag','target':G,'target_type':'tag'},G:{'type':'tag','target':T,'target_type':'tag'}},head=T,algorithm='sha1')
  req={'protocol':PROTOCOL,'op':'read','target':tt,'at':{'current':True},'records':[{'key':'x','path':'state/work.json','format':'json'}]}
  self.assertEqual(R2Reader(cyc).read(req)['error']['code'],'INVALID_SOURCE')
  mm=MemoryReadProvider(tt,{T:{'type':'tag','target':self.A,'target_type':'blob'},self.A:{'type':'commit','files':{}}},head=T,algorithm='sha1')
  self.assertEqual(R2Reader(mm).read(req)['error']['code'],'INTEGRITY_MISMATCH')
 def test_branch_ref_does_not_peel_tag(self):
  T='git:sha1:'+'f'*40;p=MemoryReadProvider(self.t,{T:{'type':'tag','target':self.A,'target_type':'commit'},self.A:{'type':'commit','files':{}}},head=T,algorithm='sha1')
  req=self.req({'current':True},[{'key':'x','path':'x','format':'json'}])
  self.assertEqual(R2Reader(p).read(req)['error']['code'],'INVALID_SOURCE')

if __name__=='__main__':unittest.main()
