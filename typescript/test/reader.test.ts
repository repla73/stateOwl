import test from "node:test";
import assert from "node:assert/strict";
import { MemoryProvider, Reader, PROTOCOL, ROUTER_V1 } from "../src/index.js";
import { A, G, T, capabilities, current, exact, files, tagTarget, target, world } from "./helpers.js";

const record={key:"work",path:"state/work.json",format:"json",select:["status","missing"]};

test("exact uses zero mutable resolutions; current uses one",async()=>{
 let p=new MemoryProvider(world()), r=new Reader(p,structuredClone(capabilities));
 let out=await r.read(exact([record]) as any); assert.equal(out.status,"ok"); assert.equal(p.calls.resolve,0); assert.deepEqual(out.records[0].value,{status:"working"});
 p=new MemoryProvider(world());r=new Reader(p,structuredClone(capabilities));out=await r.read(current([record]) as any);assert.equal(out.status,"ok");assert.equal(p.calls.resolve,1);
});

test("batch shares one file and one root resolution",async()=>{
 const p=new MemoryProvider(world()),r=new Reader(p,structuredClone(capabilities));
 const out=await r.read(current([{key:"a",path:"state/work.json",format:"json",select:["id"]},{key:"b",path:"state/work.json",format:"json",select:["count"]}]) as any);
 assert.equal(out.status,"ok");assert.equal(p.calls.resolve,1);assert.equal(p.calls.file,1);assert.deepEqual(out.records.map((x:any)=>x.value),[{id:"work"},{count:1}]);
});

test("route and ordered one-level expansions",async()=>{
 const p=new MemoryProvider(world()),r=new Reader(p,structuredClone(capabilities));
 const req={protocol:PROTOCOL,op:"read",target,at:{current:true},records:[{key:"work",route:"work",expand:["detail","checks"]}],resolver:ROUTER_V1};
 const out=await r.read(req as any);assert.equal(out.status,"ok");assert.deepEqual(out.records[0].value,{id:"work",status:"working"});assert.equal(out.records[0].expanded[0].value,"detail\n");assert.deepEqual(out.records[0].expanded[1].value,{status:"pass"});assert.deepEqual(out.routing.sources.map((x:any)=>x.path),[".stateowl/router.json","state/work.json"]);assert.equal(p.calls.file,4);
});

test("optional absence and concealed denial",async()=>{
 let w=world(),p=new MemoryProvider(w),r=new Reader(p,structuredClone(capabilities));let out=await r.read(exact([{key:"x",path:"missing",format:"json",optional:true}]) as any);assert.deepEqual(out.records,[{key:"x",status:"absent",path:"missing"}]);
 w=world();w.conceal_absence=true;p=new MemoryProvider(w);r=new Reader(p,structuredClone(capabilities));out=await r.read(exact([{key:"x",path:"missing",format:"json",optional:true}]) as any);assert.equal(out.error.code,"NOT_FOUND_OR_FORBIDDEN");
});

test("annotated and nested tags peel without re-resolve",async()=>{
 const w=world();w.target=tagTarget;w.head=T;w.objects[T]={type:"tag",target:G,target_type:"tag"};w.objects[G]={type:"tag",target:A,target_type:"commit"};
 const p=new MemoryProvider(w),r=new Reader(p,structuredClone(capabilities));const req=current([record]) as any;req.target=tagTarget;const out=await r.read(req);assert.equal(out.status,"ok");assert.equal(out.snapshot.id,A);assert.equal(p.calls.resolve,1);
});

test("opaque non-Git exact snapshot",async()=>{
 const t={kind:"fixture",authority:"stateowl.invalid",resource:"fixture/project",namespace:"state"};const w:any={target:t,head:"opaque/revision-7",native:false,objects:{"opaque/revision-7":{type:"commit",parents:[],files:{"state/work.json":files["state/work.json"]}}}};
 const p=new MemoryProvider(w),r=new Reader(p,structuredClone(capabilities));const req:any={protocol:PROTOCOL,op:"read",target:t,at:{snapshot:{id:"opaque/revision-7"}},records:[record]};const out=await r.read(req);assert.equal(out.status,"ok");assert.equal(out.snapshot.id,"opaque/revision-7");assert.equal(out.records[0].source.object,undefined);assert.equal(p.calls.resolve,0);
});

test("whole source validates before projection",async()=>{
 const w=world();w.objects[A]!.files!["state/work.json"]={base64:Buffer.from('{"status":"working","hidden":{"x":1,"x":2}}').toString("base64"),mode:"100644"};const out=await new Reader(new MemoryProvider(w),structuredClone(capabilities)).read(exact([record]) as any);assert.equal(out.error.code,"INVALID_SOURCE");
});
