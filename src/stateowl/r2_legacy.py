from __future__ import annotations
from .r2 import PROTOCOL, ROUTER_V1, R2Reader

class LegacyCompatibilityError(ValueError):
    def __init__(self,code):self.code=code;super().__init__(code)

_MAP={'CONFLICT':'EXPECTED_HEAD_MISMATCH','EXACT_SNAPSHOT_REQUIRED':'LINK_COMMIT_REQUIRED','INVALID_SOURCE':'JSON_DUPLICATE_KEY'}

def _raw(oid):
    return oid.split(':',2)[2] if oid.startswith('git:sha1:') else oid

def _source(src,repo,root_oid):
    origin=src.get('origin');repository=origin['target']['resource'] if origin else repo;oid=origin['snapshot']['id'] if origin else root_oid
    obj=src.get('object','');blob=_raw(obj) if obj else ''
    return {'repository':repository,'commit':_raw(oid),'path':src['path'],'blob':blob}

class R2LegacyReader:
    """0.1.0 router/API compatibility projected through the R2 reader."""
    def __init__(self,provider,*,authority='github.com'):self.provider=provider;self.authority=authority
    def read(self,repository,route,*,ref='refs/heads/main',router_path='.stateowl/router.json',expand=(),expected_head=None):
        if router_path!='.stateowl/router.json': raise LegacyCompatibilityError('ROUTER_PATH_UNSUPPORTED')
        target={'kind':'git','authority':self.authority,'resource':repository,'namespace':ref}
        at={'current':True}
        if expected_head is not None:at['assert_snapshot']={'id':'git:sha1:'+expected_head}
        req={'protocol':PROTOCOL,'op':'read','target':target,'at':at,'records':[{'key':route,'route':route,**({'expand':list(expand)} if expand else {})}],'resolver':ROUTER_V1}
        out=R2Reader(self.provider).read(req)
        if out.get('status')!='ok':raise LegacyCompatibilityError(_MAP.get(out['error']['code'],out['error']['code']))
        rec=out['records'][0];oid=out['snapshot']['id'];sources=out['routing']['sources']
        result={'route':route,'head':{'repository':repository,'ref':ref,'commit':_raw(oid)},'value':rec['value'],'sources':{'router':_source(sources[0],repository,oid),'record':_source(rec['source'],repository,oid)}}
        if rec.get('expanded'):
            result['expanded']={c['key']:{'value':c['value'],'source':_source(c['source'],repository,oid)} for c in rec['expanded']}
        return result
