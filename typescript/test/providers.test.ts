import test from "node:test";
import assert from "node:assert/strict";
import { mkdtempSync, rmSync, writeFileSync, mkdirSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { execFileSync } from "node:child_process";
import { LocalGitProvider, GitHubReadProvider, Reader, gitBlobId, type Target } from "../src/index.js";
import { capabilities } from "./helpers.js";

function git(cwd:string,args:string[],input?:string){return execFileSync("git",["-C",cwd,...args],{input,encoding:"utf8"});}

test("local Git exact/current reads do not change checked-out branch",async()=>{
 const dir=mkdtempSync(join(tmpdir(),"stateowl-ts-"));
 try{
  git(dir,["init","-q"]);git(dir,["config","user.email","test@example.invalid"]);git(dir,["config","user.name","stateOwl test"]);
  mkdirSync(join(dir,"state"));writeFileSync(join(dir,"state/work.json"),'{"status":"working"}\n');git(dir,["add","."]);git(dir,["commit","-qm","base"]);
  const branch=String(git(dir,["branch","--show-current"])).trim();git(dir,["branch","state"]);const oid=String(git(dir,["rev-parse","state"])).trim();
  const target:Target={kind:"git",authority:"github.com",resource:"fixture/project",namespace:"refs/heads/state"};const provider=new LocalGitProvider(dir,target);const reader=new Reader(provider,structuredClone(capabilities));
  let out=await reader.read({protocol:"stateowl/0.2-draft.3",op:"read",target,at:{snapshot:{id:`git:sha1:${oid}`}},records:[{key:"w",path:"state/work.json",format:"json",select:["status"]}]});assert.equal(out.status,"ok");assert.deepEqual(out.records[0].value,{status:"working"});
  out=await reader.read({protocol:"stateowl/0.2-draft.3",op:"read",target,at:{current:true},records:[{key:"w",path:"state/work.json",format:"json",select:["status"]}]});assert.equal(out.status,"ok");assert.equal(String(git(dir,["branch","--show-current"])).trim(),branch);
 } finally {rmSync(dir,{recursive:true,force:true});}
});

test("GitHub provider is read-only and maps REST reads",async()=>{
 const sha="a".repeat(40), content=Buffer.from('{"status":"working"}\n'), blob=gitBlobId(content,"sha1").slice("git:sha1:".length), target:Target={kind:"git",authority:"github.com",resource:"fixture/project",namespace:"refs/heads/state"};
 const calls:string[]=[];const transport=async(path:string)=>{calls.push(path);if(path.includes("/git/ref/"))return {object:{sha,type:"commit"}};if(path.includes("/git/commits/"))return {parents:[]};if(path.includes("/contents/"))return {type:"file",sha:blob,content:content.toString("base64")};throw Object.assign(new Error("not found"),{status:404});};
 const out=await new Reader(new GitHubReadProvider(transport,new Set(["fixture/project"])),structuredClone(capabilities)).read({protocol:"stateowl/0.2-draft.3",op:"read",target,at:{current:true},records:[{key:"w",path:"state/work.json",format:"json",select:["status"]}]});
 assert.equal(out.status,"ok");assert.ok(calls.every(x=>!/(POST|PATCH|PUT|DELETE)/.test(x)));assert.equal(calls.filter(x=>x.includes("/git/ref/")).length,1);
});
