import test from "node:test";
import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { createHash } from "node:crypto";
import { mkdtempSync, mkdirSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { Publisher, publicationIdentity, receiptMessage, type PublicationTree, type PublishRequest } from "../src/publication.js";
import { TrustedProjectValidationBoundary } from "../src/project-validation.js";
import { LocalGitPublicationProvider } from "../src/providers/local-git-publication.js";
import { GitHubPublicationProvider } from "../src/providers/github-publication.js";
import { PROTOCOL, type Capabilities, type Target } from "../src/types.js";

const caps=():Capabilities=>({protocol:PROTOCOL,operations:["publish"],formats:[],features:[],resolvers:[],limits:{request_bytes:65536,record_bytes:16384,mutation_bytes:32768,response_bytes:65536,records:32,expansions:16,changes:32,tag_hops:8,reconcile_commits:16,json_depth:64},publication:{continuity:"single_step_required",receipt_format:"stateowl.git-receipt/2",receipt_retention:"reachable_history",authority:"project_validated"}});
const git=(cwd:string,args:string[],opts:any={})=>execFileSync("git",["-C",cwd,...args],{encoding:"utf8",...opts});

test("Local-Git publisher builds objects without checking out or mutating the state branch",async()=>{
 const dir=mkdtempSync(join(tmpdir(),"stateowl-r3-local-"));
 try{
  git(dir,["init","-q"]);git(dir,["config","user.email","test@example.invalid"]);git(dir,["config","user.name","stateOwl test"]);mkdirSync(join(dir,"state"));
  writeFileSync(join(dir,"state/work.json"),'{"status":"working"}\n');writeFileSync(join(dir,"state/obsolete.txt"),"obsolete\n");writeFileSync(join(dir,"state/script"),"old\n");git(dir,["add","."]);git(dir,["update-index","--chmod=+x","state/script"]);git(dir,["commit","-qm","base"]);
  const base=String(git(dir,["rev-parse","HEAD"])).trim(),branch=String(git(dir,["branch","--show-current"])).trim();git(dir,["branch","state",base]);
  const target:Target={kind:"git",authority:"github.com",resource:"fixture/project",namespace:"refs/heads/state"};
  const validationId="urn:test:validator:1";const boundary=new TrustedProjectValidationBoundary({target,requiredValidation:validationId,projectAuthorized:true,continuity:"intact",authScope:"local-test",validators:new Map([[validationId,()=>true]])});
  const request:PublishRequest={protocol:PROTOCOL,op:"publish",target,expected:{id:`git:sha1:${base}`},mode:"submit",validation:validationId,changes:[{path:"state/work.json",put:{encoding:"utf8",data:'{"status":"ready"}\n'}},{path:"state/obsolete.txt",delete:true},{path:"state/new",put:{encoding:"utf8",data:""}}]};
  const provider=new LocalGitPublicationProvider(dir,target);const out=await new Publisher(provider,boundary,caps()).publish(request);assert.equal(out.outcome,"committed");
  assert.equal(String(git(dir,["branch","--show-current"])).trim(),branch);assert.equal(String(git(dir,["show","HEAD:state/work.json"])), '{"status":"working"}\n');
  const stateHead=String(git(dir,["rev-parse","state"])).trim();assert.equal(out.snapshot.id,`git:sha1:${stateHead}`);const modes=String(git(dir,["ls-tree","-r",stateHead])).split("\n");assert.ok(modes.some(x=>x.startsWith("100755 blob")&&x.endsWith("\tstate/script")));assert.ok(modes.some(x=>x.startsWith("100644 blob")&&x.endsWith("\tstate/new")));
  const meta=await provider.inspect(target,out.snapshot.id);assert.equal(meta.type,"commit");assert.equal((meta as any).message,receiptMessage(publicationIdentity(request).identity));assert.deepEqual((meta as any).parents,[`git:sha1:${base}`]);
 } finally {rmSync(dir,{recursive:true,force:true});}
});

test("GitHub publisher prebuilds exact objects then admits with updateRefs beforeOid CAS",async()=>{
 const expectedRaw="a".repeat(40),treeSha="c".repeat(40),blobSha="d".repeat(40),target:Target={kind:"git",authority:"github.com",resource:"fixture/project",namespace:"refs/heads/state"};
 const candidate:PublicationTree={"state/a":{base64:Buffer.from("a\n").toString("base64"),mode:"100644"},"state/run":{base64:Buffer.from("x\n").toString("base64"),mode:"100755"}};
 const posts:Array<{path:string;body:any}>=[];let graphVars:any;const message="stateOwl publication\n\nStateOwl-Receipt: e30=\n",who={name:"stateOwl test",email:"stateowl@example.invalid",date:"2026-10-06T00:00:00Z"},seconds=Math.trunc(Date.parse(who.date)/1000);
 const raw=Buffer.from(`tree ${treeSha}\nparent ${expectedRaw}\nauthor ${who.name} <${who.email}> ${seconds} +0000\ncommitter ${who.name} <${who.email}> ${seconds} +0000\n\n${message}`,"utf8"),hash=createHash("sha1");hash.update(`commit ${raw.byteLength}\0`);hash.update(raw);const candidateRaw=hash.digest("hex");
 const rest=async(method:"GET"|"POST",path:string,body?:any)=>{if(method==="POST"){posts.push({path,body});if(path.endsWith("/git/blobs"))return {sha:blobSha};if(path.endsWith("/git/trees"))return {sha:treeSha};if(path.endsWith("/git/commits"))return {sha:candidateRaw};}
   if(path===`/repos/fixture/project/git/commits/${candidateRaw}`)return {sha:candidateRaw,message:message.slice(0,-1),tree:{sha:treeSha},parents:[{sha:expectedRaw}],author:who,committer:who,verification:{verified:false,reason:"unsigned",signature:null,payload:null,verified_at:null}};if(path==="/repos/fixture/project")return {node_id:"R_repo"};if(path.includes("/git/ref/heads%2Fstate"))return {object:{sha:expectedRaw}};throw Object.assign(new Error(path),{status:404});};
 const graphql=async(_query:string,variables:any)=>{graphVars=variables;return {data:{updateRefs:{clientMutationId:null}}};};
 const provider=new GitHubPublicationProvider(rest,graphql,new Set(["fixture/project"]));const ack=await provider.admit(target,`git:sha1:${expectedRaw}`,candidate,message);assert.deepEqual(ack,{status:"admitted",snapshot:`git:sha1:${candidateRaw}`});
 const treePost=posts.find(x=>x.path.endsWith("/git/trees"))!;assert.equal(treePost.body.tree.length,2);assert.deepEqual(posts.find(x=>x.path.endsWith("/git/commits"))!.body,{message,tree:treeSha,parents:[expectedRaw]});
 assert.deepEqual(graphVars.input,{repositoryId:"R_repo",refUpdates:[{name:"refs/heads/state",beforeOid:expectedRaw,afterOid:candidateRaw,force:false}]});
});