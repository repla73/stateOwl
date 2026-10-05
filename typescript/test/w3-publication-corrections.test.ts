import test from "node:test";
import assert from "node:assert/strict";
import { Publisher, type AdmissionResult, type ProjectValidationBoundary, type PublicationAccess, type PublicationProvider, type PublicationTree, type PublishRequest } from "../src/publication.js";
import { GitHubPublicationProvider } from "../src/providers/github-publication.js";
import { PROTOCOL, ProtocolError, type Capabilities, type InspectResult, type Target } from "../src/types.js";

const A="git:sha1:"+"a".repeat(40), B="git:sha1:"+"b".repeat(40);
const target:Target={kind:"git",authority:"github.com",resource:"fixture/project",namespace:"refs/heads/state"};
const caps=(authority:"mechanical"|"project_validated"):Capabilities=>({
  protocol:PROTOCOL,operations:["publish"],formats:[],features:[],resolvers:[],
  limits:{request_bytes:65536,record_bytes:16384,mutation_bytes:32768,response_bytes:65536,records:32,expansions:16,changes:32,tag_hops:8,reconcile_commits:16,json_depth:64},
  publication:{continuity:"single_step_required",receipt_format:"stateowl.git-receipt/2",receipt_retention:"reachable_history",authority}
});
const request=(validation:string|null):PublishRequest=>({protocol:PROTOCOL,op:"publish",target,expected:{id:A},mode:"submit",validation,changes:[{path:"state/a",put:{encoding:"utf8",data:"new\n"}}]});

class TrustedFixture implements PublicationProvider,ProjectValidationBoundary {
  head=A; admitCalls=0; validateCalls=0; authorizeCalls=0; pathAuthorized=true;
  readonly old:PublicationTree={"state/a":{base64:Buffer.from("old\n").toString("base64"),mode:"100644"},"state/untouched":{base64:Buffer.from("keep\n").toString("base64"),mode:"100644"}};
  candidate?:PublicationTree; message?:string;
  constructor(public required:string|null,public validatorAvailable=true,public projectAuthorized=true){}
  async access():Promise<PublicationAccess>{return {validation:this.required,validator_available:this.validatorAvailable,project_authorized:this.projectAuthorized,continuity:"intact",auth_scope:"w3"};}
  async authorize(){this.authorizeCalls++;return this.pathAuthorized;}
  async validate(){this.validateCalls++;return true;}
  async resolve(){return this.head;}
  async inspect(_target:Target,snapshot:string):Promise<InspectResult>{if(snapshot===A)return {id:A,type:"commit",parents:[],message:"base\n"};if(snapshot===B)return {id:B,type:"commit",parents:[A],message:this.message};throw new ProtocolError("SNAPSHOT_UNAVAILABLE");}
  async tree(_target:Target,snapshot:string):Promise<PublicationTree>{if(snapshot===A)return structuredClone(this.old);if(snapshot===B&&this.candidate)return structuredClone(this.candidate);throw new ProtocolError("SNAPSHOT_UNAVAILABLE");}
  async admit(_target:Target,expected:string,candidate:PublicationTree,message:string):Promise<AdmissionResult>{this.admitCalls++;assert.equal(expected,A);this.candidate=structuredClone(candidate);this.message=message;this.head=B;return {status:"admitted",snapshot:B};}
}

test("F01: truncated GitHub tree is rejected rather than returned as complete state",async()=>{
  const treeSha="c".repeat(40);let blobReads=0;
  const rest=async(method:"GET"|"POST",path:string)=>{
    assert.equal(method,"GET");
    if(path.endsWith(`/git/commits/${"a".repeat(40)}`))return {tree:{sha:treeSha}};
    if(path.endsWith(`/git/trees/${treeSha}`))return {truncated:true,tree:[{path:"state",mode:"040000",type:"tree",sha:"d".repeat(40)}]};
    if(path.includes("/git/blobs/")){blobReads++;return {encoding:"base64",content:"a2VlcAo="};}
    throw Object.assign(new Error(path),{status:404});
  };
  const provider=new GitHubPublicationProvider(rest,async()=>{throw new Error("unexpected admission");},new Set(["fixture/project"]));
  await assert.rejects(()=>provider.tree(target,A),(e:any)=>e instanceof ProtocolError&&e.code==="INVALID_SOURCE");
  assert.equal(blobReads,0);
});

test("F01: incomplete old tree fails before any publication admission",async()=>{
  const treeSha="c".repeat(40);let posts=0,graphqlCalls=0;
  const rest=async(method:"GET"|"POST",path:string)=>{
    if(method==="POST"){posts++;throw new Error("unexpected POST");}
    if(path.endsWith(`/git/commits/${"a".repeat(40)}`))return {sha:"a".repeat(40),parents:[],message:"base\n",tree:{sha:treeSha}};
    if(path.endsWith(`/git/trees/${treeSha}`))return {truncated:true,tree:[]};
    throw Object.assign(new Error(path),{status:404});
  };
  const provider=new GitHubPublicationProvider(rest,async()=>{graphqlCalls++;throw new Error("unexpected GraphQL");},new Set(["fixture/project"]));
  const boundary:ProjectValidationBoundary={
    async access(){return {validation:null,validator_available:true,project_authorized:true,continuity:"intact",auth_scope:"w3"};},
    async authorize(){return true;},
    async validate(){throw new Error("unexpected validator");}
  };
  const out=await new Publisher(provider,boundary,caps("project_validated")).publish(request(null));
  assert.equal(out.outcome,"not_committed");assert.equal(out.error.code,"INVALID_SOURCE");assert.equal(posts,0);assert.equal(graphqlCalls,0);
});

test("F01: complete GitHub tree behavior is preserved",async()=>{
  const treeSha="c".repeat(40),blobA="d".repeat(40),blobB="e".repeat(40);
  const rest=async(method:"GET"|"POST",path:string)=>{
    assert.equal(method,"GET");
    if(path.endsWith(`/git/commits/${"a".repeat(40)}`))return {tree:{sha:treeSha}};
    if(path.endsWith(`/git/trees/${treeSha}`))return {truncated:false,tree:[{path:"state/a",mode:"100644",type:"blob",sha:blobA},{path:"state/untouched",mode:"100755",type:"blob",sha:blobB}]};
    if(path.endsWith(`/git/blobs/${blobA}`))return {encoding:"base64",content:Buffer.from("old\n").toString("base64")};
    if(path.endsWith(`/git/blobs/${blobB}`))return {encoding:"base64",content:Buffer.from("keep\n").toString("base64")};
    throw Object.assign(new Error(path),{status:404});
  };
  const provider=new GitHubPublicationProvider(rest,async()=>({}),new Set(["fixture/project"]));
  assert.deepEqual(await provider.tree(target,A),{
    "state/a":{base64:Buffer.from("old\n").toString("base64"),mode:"100644"},
    "state/untouched":{base64:Buffer.from("keep\n").toString("base64"),mode:"100755"}
  });
});

test("F02: project_validated authority permits trusted null validation",async()=>{
  const fixture=new TrustedFixture(null);
  const out=await new Publisher(fixture,fixture,caps("project_validated")).publish(request(null));
  assert.equal(out.outcome,"committed");assert.equal(fixture.validateCalls,0);assert.equal(fixture.admitCalls,1);assert.deepEqual(fixture.candidate?.["state/untouched"],fixture.old["state/untouched"]);
});

test("F02: mechanical authority still enforces a non-null trusted validation binding",async()=>{
  const binding="urn:test:validation:1",fixture=new TrustedFixture(binding);
  const out=await new Publisher(fixture,fixture,caps("mechanical")).publish(request(binding));
  assert.equal(out.outcome,"committed");assert.equal(fixture.validateCalls,1);assert.equal(fixture.admitCalls,1);
});

test("F02: pin, validator availability, and project authority remain independent pre-admission checks",async()=>{
  let fixture=new TrustedFixture("urn:test:required");let out=await new Publisher(fixture,fixture,caps("mechanical")).publish(request("urn:test:wrong"));assert.equal(out.error.code,"VALIDATION_FAILED");assert.equal(fixture.admitCalls,0);
  fixture=new TrustedFixture("urn:test:required",false,true);out=await new Publisher(fixture,fixture,caps("mechanical")).publish(request("urn:test:required"));assert.equal(out.error.code,"UNSUPPORTED_CAPABILITY");assert.equal(fixture.admitCalls,0);
  fixture=new TrustedFixture(null,true,false);out=await new Publisher(fixture,fixture,caps("project_validated")).publish(request(null));assert.equal(out.error.code,"FORBIDDEN");assert.equal(fixture.admitCalls,0);
  fixture=new TrustedFixture(null,true,true);fixture.pathAuthorized=false;out=await new Publisher(fixture,fixture,caps("project_validated")).publish(request(null));assert.equal(out.error.code,"FORBIDDEN");assert.equal(fixture.admitCalls,0);
});
