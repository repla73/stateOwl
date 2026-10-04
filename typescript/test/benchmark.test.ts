import test from "node:test";import assert from "node:assert/strict";import {Reader,MemoryProvider,PROTOCOL,type Capabilities} from "../src/index.js";import {A,capabilities,target} from "./helpers.js";
const enc=(s:string)=>Buffer.from(s).toString("base64");
function make(unrelated:number){const files:any={"state/work.json":{base64:enc('{"status":"working"}\n'),mode:"100644"}};for(let i=0;i<unrelated;i++)files[`state/unrelated-${i}.json`]={base64:"e30K",mode:"100644"};return {target,head:A,native:true as const,algorithm:"sha1" as const,objects:{[A]:{type:"commit",parents:[],message:"base\n",files}}};}
const req=(current:boolean,batch=false)=>({protocol:PROTOCOL,op:"read",target,at:current?{current:true}:{snapshot:{id:A}},records:batch?[{key:"a",path:"state/work.json",format:"json",select:["status"]},{key:"b",path:"state/work.json",format:"json",select:["status"]}]:[{key:"a",path:"state/work.json",format:"json",select:["status"]}]});

test("benchmark regression: exact/current/batch instrumentation and unrelated-state invariance",async()=>{
 let p=new MemoryProvider(make(0)),out=await new Reader(p,structuredClone(capabilities) as Capabilities).read(req(false) as any);assert.equal(out.status,"ok");assert.equal(p.calls.resolve,0);assert.equal(p.calls.file,1);const baseline=Buffer.byteLength(JSON.stringify(out));
 p=new MemoryProvider(make(0));out=await new Reader(p,structuredClone(capabilities) as Capabilities).read(req(true,true) as any);assert.equal(out.status,"ok");assert.equal(p.calls.resolve,1);assert.equal(p.calls.file,1);
 p=new MemoryProvider(make(100000));out=await new Reader(p,structuredClone(capabilities) as Capabilities).read(req(false) as any);assert.equal(out.status,"ok");assert.equal(p.calls.resolve,0);assert.equal(p.calls.file,1);assert.equal(Buffer.byteLength(JSON.stringify(out)),baseline);
});
