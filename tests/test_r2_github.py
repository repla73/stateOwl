import base64,hashlib,json,sys,unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from stateowl.r2 import *
from stateowl.r2_github import GitHubReadProvider
class Resp:
 def __init__(self,v):self.raw=json.dumps(v).encode()
 def __enter__(self):return self
 def __exit__(self,*a):return False
 def read(self):return self.raw
class Tests(unittest.TestCase):
 def test_current_request_ref_once_and_immutable_cache(self):
  raw=b'{"status":"ok"}\n';bh=hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest();commit='a'*40;tree='b'*40
  counts={}
  def fake(req,timeout):
   u=req.full_url;counts[u]=counts.get(u,0)+1
   if u.endswith('/repos/acme/project'):return Resp({'id':1})
   if '/git/ref/heads/state' in u:return Resp({'object':{'sha':commit,'type':'commit'}})
   if '/git/commits/'+commit in u:return Resp({'sha':commit,'parents':[],'tree':{'sha':tree}})
   if '/git/trees/'+tree in u:return Resp({'tree':[{'path':'state.json','type':'blob','mode':'100644','sha':bh}],'truncated':False})
   if '/git/blobs/'+bh in u:return Resp({'sha':bh,'encoding':'base64','content':base64.b64encode(raw).decode(),'size':len(raw)})
   raise AssertionError(u)
  t={'kind':'git','authority':'github.com','resource':'acme/project','namespace':'refs/heads/state'};req={'protocol':PROTOCOL,'op':'read','target':t,'at':{'current':True},'records':[{'key':'a','path':'state.json','format':'json'},{'key':'b','path':'state.json','format':'json','select':['status']}]}
  p=GitHubReadProvider(token='x')
  with patch('stateowl.r2_github.urlopen',fake):
   rd=R2Reader(p);out=rd.read(req)
  self.assertEqual(out['status'],'ok');self.assertEqual(rd.last_instrumentation.resolve,1);self.assertEqual(rd.last_instrumentation.file,1);self.assertEqual(p.http_requests,5)
if __name__=='__main__':unittest.main()
