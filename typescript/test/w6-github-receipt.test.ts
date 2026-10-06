import test from "node:test";
import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { Publisher, publicationIdentity, receiptMessage, parseReceipt, type AdmissionResult, type ProjectValidationBoundary, type PublicationAccess, type PublicationProvider, type PublicationTree, type PublishRequest } from "../src/publication.js";
import { GitHubPublicationProvider } from "../src/providers/github-publication.js";
import { PROTOCOL, ProtocolError, type Capabilities, type InspectResult, type Target } from "../src/types.js";

const ARAW="a".repeat(40), A=`git:sha1:${ARAW}`, BRAW="b".repeat(40), B=`git:sha1:${BRAW}`;
const target:Target={kind:"git",authority:"github.com",resource:"fixture/project",namespace:"refs/heads/state"};
const DATE="2026-10-06T00:00:00Z", actor={name:"stateOwl test",email:"stateowl@example.invalid",date:DATE};
const caps=(authority:"project_validated"|"mechanical"="project_validated"):Capabilities=>({protocol:PROTOCOL,operations:["publish"],formats:[],features:[],resolvers:[],limits:{request_bytes:65536,record_bytes:16384,mutation_bytes:32768,response_bytes:65536,records:32,expansions:16,changes:32,tag_hops:8,reconcile_commits:16,json_depth:64},publication:{continuity:"single_step_required",receipt_format:"stateowl.git-receipt/2",receipt_retention:"reachable_history",authority}});
const req=(mode:"submit"|"reconcile"="submit",data="new\n",validation:string|null=null):PublishRequest=>({protocol:PROTOCOL,op:"publish",target,expected:{id:A},mode,validation,changes:[{path:"state/a",put:{encoding:"utf8",data}}]});
const boundary=(required:string|null=null,validatorAvailable=true,projectAuthorized=true):ProjectValidationBoundary=>({
  async access(){return {validation:required,validator_available:validatorAvailable,project_authorized:projectAuthorized,continuity:"intact",auth_scope:"w6"};},
  async authorize(){return true;},
  async validate(){return true;}
});
const b64=(s:string)=>Buffer.from(s,"utf8").toString("base64");

function rawCommitSha(tree:string,parents:string[],message:string,tz="+0300"):string{
  const seconds=Math.trunc(Date.parse(DATE)/1000);
  let body=`tree ${tree}\n`;for(const parent of parents)body+=`parent ${parent}\n`;
  body+=`author ${actor.name} <${actor.email}> ${seconds} ${tz}\ncommitter ${actor.name} <${actor.email}> ${seconds} ${tz}\n\n${message}`;
  const bytes=Buffer.from(body,"utf8"),h=createHash("sha1");h.update(`commit ${bytes.byteLength}\0`);h.update(bytes);return h.digest("hex");
}
function commitMeta(tree:string,parents:string[],rawMessage:string,apiMessage=rawMessage,tz="+0300"):any{
  const sha=rawCommitSha(tree,parents,rawMessage,tz);
  return {sha,tree:{sha:tree},parents:parents.map(parent=>({sha:parent})),author:actor,committer:actor,message:apiMessage,verification:{verified:false,reason:"unsigned",signature:null,payload:null,verified_at:null}};
}

function reconciliationWorld(rawMessage:string,apiMessage=rawMessage){
  const treeA="1".repeat(40),treeB="2".repeat(40),oldBlob="3".repeat(40),newBlob="4".repeat(40),keepBlob="5".repeat(40),meta=commitMeta(treeB,[ARAW],rawMessage,apiMessage);
  const rest=async(method:"GET"|"POST",path:string)=>{
    assert.equal(method,"GET");
    if(path.includes("/git/ref/heads%2Fstate"))return {object:{sha:meta.sha}};
    if(path.endsWith(`/git/commits/${ARAW}`))return {sha:ARAW,parents:[],message:"base",tree:{sha:treeA}};
    if(path.endsWith(`/git/commits/${meta.sha}`))return meta;
    if(path.endsWith(`/git/trees/${treeA}`))return {truncated:false,tree:[{path:"state/a",mode:"100644",type:"blob",sha:oldBlob},{path:"state/untouched",mode:"100644",type:"blob",sha:keepBlob}]};
    if(path.endsWith(`/git/trees/${treeB}`))return {truncated:false,tree:[{path:"state/a",mode:"100644",type:"blob",sha:newBlob},{path:"state/untouched",mode:"100644",type:"blob",sha:keepBlob}]};
    if(path.endsWith(`/git/blobs/${oldBlob}`))return {encoding:"base64",content:b64("old\n")};
    if(path.endsWith(`/git/blobs/${newBlob}`))return {encoding:"base64",content:b64("new\n")};
    if(path.endsWith(`/git/blobs/${keepBlob}`))return {encoding:"base64",content:b64("keep\n")};
    throw Object.assign(new Error(path),{status:404});
  };
  return {meta,provider:new GitHubPublicationProvider(rest,async()=>({}),new Set([target.resource]))};
}

test("normalized REST echo missing terminal LF is proven by exact commit OID through submit and post-admission verification",async()=>{
  const treeA="1".repeat(40),treeB="2".repeat(40),oldBlob="3".repeat(40),newBlob="4".repeat(40),keepBlob="5".repeat(40),request=req(),message=receiptMessage(publicationIdentity(request).identity),created=commitMeta(treeB,[ARAW],message,message.slice(0,-1),"+0300");
  let graphCalls=0;
  const rest=async(method:"GET"|"POST",path:string,body?:any)=>{
    if(method==="POST"){
      if(path.endsWith("/git/blobs"))return {sha:body.content===b64("new\n")?newBlob:keepBlob};
      if(path.endsWith("/git/trees"))return {sha:treeB};
      if(path.endsWith("/git/commits"))return {sha:created.sha};
    }
    if(path.endsWith(`/git/commits/${ARAW}`))return {sha:ARAW,parents:[],message:"base",tree:{sha:treeA}};
    if(path.endsWith(`/git/commits/${created.sha}`))return created;
    if(path.endsWith(`/git/trees/${treeA}`))return {truncated:false,tree:[{path:"state/a",mode:"100644",type:"blob",sha:oldBlob},{path:"state/untouched",mode:"100644",type:"blob",sha:keepBlob}]};
    if(path.endsWith(`/git/trees/${treeB}`))return {truncated:false,tree:[{path:"state/a",mode:"100644",type:"blob",sha:newBlob},{path:"state/untouched",mode:"100644",type:"blob",sha:keepBlob}]};
    if(path.endsWith(`/git/blobs/${oldBlob}`))return {encoding:"base64",content:b64("old\n")};
    if(path.endsWith(`/git/blobs/${newBlob}`))return {encoding:"base64",content:b64("new\n")};
    if(path.endsWith(`/git/blobs/${keepBlob}`))return {encoding:"base64",content:b64("keep\n")};
    if(path==="/repos/fixture/project")return {node_id:"R_repo"};
    if(path.includes("/git/ref/heads%2Fstate"))return {object:{sha:created.sha}};
    throw Object.assign(new Error(path),{status:404});
  };
  const graphql=async()=>{graphCalls++;return {data:{updateRefs:{clientMutationId:null}}};};
  const out=await new Publisher(new GitHubPublicationProvider(rest,graphql,new Set([target.resource])),boundary(),caps()).publish(request);
  assert.equal(out.outcome,"committed");assert.equal(out.snapshot.id,`git:sha1:${created.sha}`);assert.equal(graphCalls,1);
});

test("genuinely missing-LF raw receipt is recovered exactly and rejected by unchanged parser",async()=>{
  const valid=receiptMessage(publicationIdentity(req()).identity),missing=valid.slice(0,-1),meta=commitMeta("2".repeat(40),[ARAW],missing,missing);
  const provider=new GitHubPublicationProvider(async(method,path)=>{assert.equal(method,"GET");if(path.endsWith(`/git/commits/${meta.sha}`))return meta;throw Object.assign(new Error(path),{status:404});},async()=>({}),new Set([target.resource]));
  const inspected:any=await provider.inspect(target,`git:sha1:${meta.sha}`);assert.equal(inspected.message,missing);assert.throws(()=>parseReceipt(inspected.message),(e:any)=>e instanceof ProtocolError&&e.code==="INVALID_SOURCE");
});

test("extra-LF raw receipt is recovered exactly and rejected by unchanged parser",async()=>{
  const valid=receiptMessage(publicationIdentity(req()).identity),extra=valid+"\n",meta=commitMeta("2".repeat(40),[ARAW],extra,valid);
  const provider=new GitHubPublicationProvider(async(method,path)=>{assert.equal(method,"GET");if(path.endsWith(`/git/commits/${meta.sha}`))return meta;throw Object.assign(new Error(path),{status:404});},async()=>({}),new Set([target.resource]));
  const inspected:any=await provider.inspect(target,`git:sha1:${meta.sha}`);assert.equal(inspected.message,extra);assert.throws(()=>parseReceipt(inspected.message),(e:any)=>e instanceof ProtocolError&&e.code==="INVALID_SOURCE");
});

test("candidate exact proof unavailable fails before guarded ref admission",async()=>{
  const tree="2".repeat(40),blob="4".repeat(40),message=receiptMessage(publicationIdentity(req()).identity);let graphCalls=0;
  const rest=async(method:"GET"|"POST",path:string)=>{
    if(method==="POST"){if(path.endsWith("/git/blobs"))return {sha:blob};if(path.endsWith("/git/trees"))return {sha:tree};if(path.endsWith("/git/commits"))return {sha:"b".repeat(40)};}
    if(path.endsWith(`/git/commits/${"b".repeat(40)}`))return {sha:"b".repeat(40),tree:{sha:tree},parents:[{sha:ARAW}],message:message.slice(0,-1)};
    throw Object.assign(new Error(path),{status:404});
  };
  const provider=new GitHubPublicationProvider(rest,async()=>{graphCalls++;return {};},new Set([target.resource]));
  await assert.rejects(()=>provider.admit(target,A,{"state/a":{base64:b64("new\n"),mode:"100644"}},message),(e:any)=>e instanceof ProtocolError&&e.code==="INTEGRITY_MISMATCH");assert.equal(graphCalls,0);
});

test("candidate parent or tree mismatch fails before guarded ref admission",async()=>{
  for(const mismatch of ["parent","tree"] as const){
    const intendedTree="2".repeat(40),actualTree=mismatch==="tree"?"6".repeat(40):intendedTree,actualParent=mismatch==="parent"?"c".repeat(40):ARAW,blob="4".repeat(40),message=receiptMessage(publicationIdentity(req()).identity),meta=commitMeta(actualTree,[actualParent],message,message.slice(0,-1));let graphCalls=0;
    const rest=async(method:"GET"|"POST",path:string)=>{if(method==="POST"){if(path.endsWith("/git/blobs"))return {sha:blob};if(path.endsWith("/git/trees"))return {sha:intendedTree};if(path.endsWith("/git/commits"))return {sha:meta.sha};}if(path.endsWith(`/git/commits/${meta.sha}`))return meta;throw Object.assign(new Error(path),{status:404});};
    const provider=new GitHubPublicationProvider(rest,async()=>{graphCalls++;return {};},new Set([target.resource]));
    await assert.rejects(()=>provider.admit(target,A,{"state/a":{base64:b64("new\n"),mode:"100644"}},message),(e:any)=>e instanceof ProtocolError&&e.code==="INTEGRITY_MISMATCH");assert.equal(graphCalls,0);
  }
});

test("reconciliation accepts exact receipt despite normalized REST echo",async()=>{
  const request=req("reconcile"),message=receiptMessage(publicationIdentity(request).identity),w=reconciliationWorld(message,message.slice(0,-1));
  const out=await new Publisher(w.provider,boundary(),caps()).publish(request);assert.equal(out.outcome,"committed");assert.equal(out.snapshot.id,`git:sha1:${w.meta.sha}`);
});

test("reconciliation rejects missing-LF and extra-LF exact raw receipts",async()=>{
  const request=req("reconcile"),valid=receiptMessage(publicationIdentity(request).identity);
  for(const raw of [valid.slice(0,-1),valid+"\n"]){const api=raw.endsWith("\n")?raw.slice(0,-1):raw,w=reconciliationWorld(raw,api),out=await new Publisher(w.provider,boundary(),caps()).publish(request);assert.equal(out.outcome,"indeterminate");assert.equal(out.error.code,"INVALID_SOURCE");}
});

test("reconciliation excludes wrong exact receipt identity",async()=>{
  const request=req("reconcile"),other=req("reconcile","other\n"),message=receiptMessage(publicationIdentity(other).identity),w=reconciliationWorld(message,message.slice(0,-1));
  const out=await new Publisher(w.provider,boundary(),caps()).publish(request);assert.equal(out.outcome,"not_committed");assert.equal(out.error.code,"CONFLICT");
});

test("F01 truncated-tree protection remains fail-closed",async()=>{
  const tree="2".repeat(40),provider=new GitHubPublicationProvider(async(method,path)=>{assert.equal(method,"GET");if(path.endsWith(`/git/commits/${ARAW}`))return {tree:{sha:tree}};if(path.endsWith(`/git/trees/${tree}`))return {truncated:true,tree:[]};throw Object.assign(new Error(path),{status:404});},async()=>({}),new Set([target.resource]));
  await assert.rejects(()=>provider.tree(target,A),(e:any)=>e instanceof ProtocolError&&e.code==="INVALID_SOURCE");
});

class Fake implements PublicationProvider,ProjectValidationBoundary{
  head=A;candidate?:PublicationTree;message?:string;validateCalls=0;required:string|null;
  old:PublicationTree={"state/a":{base64:b64("old\n"),mode:"100644"}};
  constructor(required:string|null){this.required=required;}
  async access():Promise<PublicationAccess>{return {validation:this.required,validator_available:true,project_authorized:true,continuity:"intact",auth_scope:"f02"};}
  async authorize(){return true;} async validate(){this.validateCalls++;return true;} async resolve(){return this.head;}
  async inspect(_t:Target,s:string):Promise<InspectResult>{if(s===A)return {id:A,type:"commit",parents:[],message:"base"};if(s===B)return {id:B,type:"commit",parents:[A],message:this.message};throw new ProtocolError("SNAPSHOT_UNAVAILABLE");}
  async tree(_t:Target,s:string){if(s===A)return structuredClone(this.old);if(s===B&&this.candidate)return structuredClone(this.candidate);throw new ProtocolError("SNAPSHOT_UNAVAILABLE");}
  async admit(_t:Target,_e:string,c:PublicationTree,m:string):Promise<AdmissionResult>{this.candidate=structuredClone(c);this.message=m;this.head=B;return {status:"admitted",snapshot:B};}
}

test("F02 authority and validation remain independent",async()=>{
  let f=new Fake(null),out=await new Publisher(f,f,caps("project_validated")).publish(req("submit","new\n",null));assert.equal(out.outcome,"committed");assert.equal(f.validateCalls,0);
  const binding="urn:test:v1";f=new Fake(binding);out=await new Publisher(f,f,caps("mechanical")).publish(req("submit","new\n",binding));assert.equal(out.outcome,"committed");assert.equal(f.validateCalls,1);
});
