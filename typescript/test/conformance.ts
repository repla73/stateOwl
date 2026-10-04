import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import assert from "node:assert/strict";
import { MemoryProvider, Reader, type Capabilities } from "../src/index.js";

const root=resolve(process.cwd(),"..");
const fixtures=JSON.parse(readFileSync(resolve(root,"docs/protocol/fixtures.json"),"utf8"));
const cases=JSON.parse(readFileSync(resolve(root,"docs/protocol/read-cases.json"),"utf8"));
const assets=fixtures.assets as Record<string,unknown>;

function expand(x:any,stack:string[]=[]):any{
 if(Array.isArray(x))return x.map(v=>expand(v,stack));
 if(x&&typeof x==="object"){
  const ks=Object.keys(x);if(ks.length===1&&ks[0]==="$fixture") {const n=x.$fixture;if(typeof n!=="string"||!(n in assets)||stack.includes(n)||stack.length>=64)throw new Error(`bad fixture ${n}`);return expand(structuredClone(assets[n]),[...stack,n]);}
  const o:any={};for(const [k,v] of Object.entries(x))o[k]=expand(v,stack);return o;
 }
 return x;
}
function patch(base:any,p:any):any{
 if(p===null)return undefined;if(!p||typeof p!=="object"||Array.isArray(p))return structuredClone(p);
 const out=(base&&typeof base==="object"&&!Array.isArray(base))?structuredClone(base):{};
 for(const [k,v] of Object.entries(p)){if(v===null)delete out[k];else out[k]=patch(out[k],v);}return out;
}
function canonical(x:any):string {if(x===null||typeof x!=="object")return JSON.stringify(x);if(Array.isArray(x))return "["+x.map(canonical).join(",")+"]";return "{"+Object.keys(x).sort().map(k=>JSON.stringify(k)+":"+canonical(x[k])).join(",")+"}";}

let passed=0;const failed:any[]=[];
for(const c0 of cases){
 const c=expand(c0);let req=expand(fixtures.requests[c.request]);if(c.request_patch)req=patch(req,expand(c.request_patch));
 let world=expand(fixtures.defaults.world);if(c.world)world=patch(world,expand(fixtures.worlds[c.world]));if(c.world_patch)world=patch(world,expand(c.world_patch));
 let caps=expand(fixtures.defaults.capabilities) as Capabilities;if(c.cap_patch)caps=patch(caps,expand(c.cap_patch));
 const input=c.request_bytes?Buffer.from(c.request_bytes,"base64"):req;
 const provider=new MemoryProvider(world);const got=await new Reader(provider,caps).read(input as any);const expected=expand(c.expected);
 try{assert.equal(canonical(got),canonical(expected));if(c.trace){for(const [k,v] of Object.entries(c.trace)){if(k in provider.calls)assert.equal(provider.calls[k],v,`${k} calls`);}}passed++;}
 catch(e:any){failed.push({id:c.id,error:e.message,got,expected,calls:provider.calls});}
}
const result={protocol_read_cases:{passed,total:cases.length},failed};console.log(JSON.stringify(result,null,2));if(failed.length)process.exitCode=1;
