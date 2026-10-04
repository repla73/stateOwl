import test from "node:test";
import assert from "node:assert/strict";
import { GitHubReadProvider, MemoryProvider, Reader, PROTOCOL, gitBlobId, validateGitTarget, type ReadProvider, type Target } from "../src/index.js";
import { A, G, T, capabilities, exact, files, tagTarget, target, world } from "./helpers.js";

const rec=(path:string,format:"json"|"text"|"base64")=>({key:"x",path,format});

test("F01 explicit representation controls parsing",async()=>{
  const w=world();w.objects[A]!.files!["state/malformed.json"]={base64:Buffer.from("{").toString("base64"),mode:"100644"};
  for(const [format,value] of [["text","{"],["base64","ew=="]] as const){const out=await new Reader(new MemoryProvider(structuredClone(w)),structuredClone(capabilities)).read(exact([rec("state/malformed.json",format)]) as any);assert.equal(out.status,"ok");assert.equal(out.records[0].value,value);}
  const bad=await new Reader(new MemoryProvider(structuredClone(w)),structuredClone(capabilities)).read(exact([rec("state/malformed.json","json")]) as any);assert.equal(bad.error.code,"INVALID_SOURCE");
});

test("F03 annotated tags verify advertised type before terminal classification",async()=>{
  const cases=[
    {name:"tag-commit",first:{type:"tag",target:A,target_type:"commit"},second:{type:"commit",parents:[],files},code:null},
    {name:"tag-tag-commit",first:{type:"tag",target:G,target_type:"tag"},second:{type:"tag",target:A,target_type:"commit"},third:{type:"commit",parents:[],files},code:null},
    {name:"tag-blob",first:{type:"tag",target:G,target_type:"blob"},second:{type:"blob"},code:"INVALID_SOURCE"},
    {name:"tag-tree",first:{type:"tag",target:G,target_type:"tree"},second:{type:"tree"},code:"INVALID_SOURCE"},
    {name:"advertised-blob-actual-commit",first:{type:"tag",target:G,target_type:"blob"},second:{type:"commit",parents:[],files},code:"INTEGRITY_MISMATCH"},
    {name:"advertised-commit-actual-blob",first:{type:"tag",target:G,target_type:"commit"},second:{type:"blob"},code:"INTEGRITY_MISMATCH"},
    {name:"unavailable-target",first:{type:"tag",target:G,target_type:"commit"},second:null,code:"SNAPSHOT_UNAVAILABLE"}
  ] as const;
  for(const c of cases){const w=world();w.target=tagTarget;w.head=T;w.objects[T]=c.first as any;if(c.second)w.objects[G]=c.second as any;if("third" in c&&c.third)w.objects[A]=c.third as any;const p=new MemoryProvider(w),r=new Reader(p,structuredClone(capabilities));const req:any={protocol:PROTOCOL,op:"read",target:tagTarget,at:{current:true},records:[{key:"w",path:"state/work.json",format:"json",select:["status"]}]};const out=await r.read(req);if(c.code)assert.equal(out.error.code,c.code,c.name);else assert.equal(out.status,"ok",c.name);assert.equal(p.calls.resolve,1,c.name);}
});

test("F03 GitHub distinguishes existing blob from unavailable",async()=>{
  const oid="b".repeat(40),t:Target={...target,namespace:"refs/heads/blob"},calls:string[]=[];
  const transport=async(path:string)=>{calls.push(path);if(path.includes("/git/ref/"))return {object:{sha:oid,type:"blob"}};if(path.includes("/git/blobs/"))return {sha:oid};throw Object.assign(new Error("missing"),{status:404});};
  const out=await new Reader(new GitHubReadProvider(transport,new Set([t.resource])),structuredClone(capabilities)).read({protocol:PROTOCOL,op:"read",target:t,at:{current:true},records:[{key:"x",path:"state/work.json",format:"json"}]} as any);
  assert.equal(out.error.code,"INVALID_SOURCE");assert.ok(calls.some(x=>x.includes("/git/blobs/")));
});

test("F04 complete ref validation and pre-access rejection",async()=>{
  for(const ns of ["refs/heads/state","refs/heads/feature/x","refs/tags/v1.0.0"])assert.doesNotThrow(()=>validateGitTarget({...target,namespace:ns}));
  const invalid=["refs/heads/foo.lock","refs/heads/foo@{bar","refs/heads/.hidden","refs/heads/a..b","refs/heads/a//b","refs/heads/a.","refs/heads/a b","refs/heads/a~b","refs/heads/a^b","refs/heads/a:b","refs/heads/a?b","refs/heads/a*b","refs/heads/a[b","refs/heads/a\\b"];
  for(const namespace of invalid){assert.throws(()=>validateGitTarget({...target,namespace}),/INVALID_REQUEST/);const p=new MemoryProvider({...world(),target:{...target,namespace}});const out=await new Reader(p,structuredClone(capabilities)).read({...exact([{key:"x",path:"state/work.json",format:"json"}]),target:{...target,namespace}} as any);assert.equal(out.error.code,"INVALID_REQUEST");assert.deepEqual(p.calls,{access:0,resolve:0,inspect:0,file:0});}
});

test("F05 central provider validation",async()=>{
  let w=world();w.faults=[{method:"file",replace:{base64:files["state/work.json"]!.base64,mode:"100644",digest:"sha256:"+"0".repeat(64),integrity:"bogus"}}];let out=await new Reader(new MemoryProvider(w),structuredClone(capabilities)).read(exact([{key:"x",path:"state/work.json",format:"json"}]) as any);assert.equal(out.error.code,"INVALID_SOURCE");
  w=world();w.faults=[{method:"inspect",replace:{id:A,type:"commit",parents:[],message:"x".repeat(capabilities.limits.record_bytes)}}];out=await new Reader(new MemoryProvider(w),structuredClone(capabilities)).read(exact([{key:"x",path:"state/work.json",format:"json"}]) as any);assert.equal(out.error.code,"LIMIT_EXCEEDED");
  const nt:Target={kind:"fixture",authority:"stateowl.invalid",resource:"fixture/project",namespace:"state"};const nw:any={target:nt,head:"opaque:one",native:false,objects:{"opaque:one":{type:"commit",files:{"state/work.json":files["state/work.json"]}}},faults:[{method:"inspect",replace:{id:"opaque:other",type:"commit",parents:[]}}]};out=await new Reader(new MemoryProvider(nw),structuredClone(capabilities)).read({protocol:PROTOCOL,op:"read",target:nt,at:{snapshot:{id:"opaque:one"}},records:[{key:"x",path:"state/work.json",format:"json"}]} as any);assert.equal(out.error.code,"INTEGRITY_MISMATCH");
  w=world();w.faults=[{method:"inspect",replace:{id:A,type:"commit",parents:[],extra:true}}];out=await new Reader(new MemoryProvider(w),structuredClone(capabilities)).read(exact([{key:"x",path:"state/work.json",format:"json"}]) as any);assert.equal(out.error.code,"INVALID_SOURCE");
});

test("F06 GitHub contents paths encode each component exactly once",async()=>{
  const sha="a".repeat(40),bytes=Buffer.from("x"),blob=gitBlobId(bytes,"sha1").slice(9),vectors=["state/a?b#c","state/a%b","state/a b","state/雪.json","one/two?x/three#y/%25"];
  for(const path of vectors){const calls:string[]=[];const transport=async(p:string)=>{calls.push(p);if(p.includes("/git/commits/"))return {parents:[]};if(p.includes("/contents/"))return {type:"file",sha:blob,content:bytes.toString("base64")};throw Object.assign(new Error("missing"),{status:404});};const provider=new GitHubReadProvider(transport,new Set([target.resource]));const out=await new Reader(provider,structuredClone(capabilities)).read({protocol:PROTOCOL,op:"read",target,at:{snapshot:{id:"git:sha1:"+sha}},records:[{key:"x",path,format:"text"}]} as any);assert.equal(out.status,"ok",path);const expected="/repos/fixture/project/contents/"+path.split("/").map(encodeURIComponent).join("/")+"?ref="+sha;assert.ok(calls.includes(expected),`${path}: ${calls.join(",")}`);}
});

test("F07 at must be exactly one addressing form before provider access",async()=>{
  for(const at of [{},{current:true,snapshot:{id:A}},{snapshot:{id:A},assert_snapshot:{id:A}}]){const p=new MemoryProvider(world());const req:any={protocol:PROTOCOL,op:"read",target,at,records:[{key:"x",path:"state/work.json",format:"json"}]};const out=await new Reader(p,structuredClone(capabilities)).read(req);assert.equal(out.error.code,"INVALID_REQUEST");assert.deepEqual(p.calls,{access:0,resolve:0,inspect:0,file:0});}
});
