import { Reader } from "../src/reader.js";
import { MemoryProvider, type MemoryWorld } from "../src/providers/memory.js";
import { canonicalJson } from "../src/encoding.js";
import { PROTOCOL, ROUTER_V1, type Capabilities, type ReadProvider, type Target } from "../src/types.js";

const A="git:sha1:"+"a".repeat(40);
const target:Target={kind:"git",authority:"github.com",resource:"fixture/project",namespace:"refs/heads/state"};
const scales=[0,10,100,1000];
const caps:Capabilities={protocol:PROTOCOL,operations:["read"],formats:["json","text","base64"],features:["routes","expand"],resolvers:[ROUTER_V1],limits:{request_bytes:65536,record_bytes:16384,mutation_bytes:32768,response_bytes:65536,records:32,expansions:16,changes:32,tag_hops:8,reconcile_commits:16,json_depth:64}};
const enc=(v:unknown)=>Buffer.from(JSON.stringify(v)+"\n").toString("base64");
const workObj={id:"work",status:"working",count:1,noise:"omit"};
const work={base64:enc(workObj),mode:"100644"};

function makeWorld(scale=0,growing=false):MemoryWorld{
  const routes:any={work:{path:"state/work.json",select:["id","status"]}};
  const files:any={"state/work.json":work};
  for(let i=0;i<scale;i++){files[`unrelated/${i}.json`]={base64:Buffer.from("{}\n").toString("base64"),mode:"100644"};if(growing)routes[`unused-${i}`]={path:`unrelated/${i}.json`,select:[]};}
  files[".stateowl/router.json"]={base64:enc({schema:"stateowl.router/v1",routes}),mode:"100644"};
  return {target,head:A,native:true,algorithm:"sha1",objects:{[A]:{type:"commit",parents:[],message:"base\n",files}}};
}
class Metered implements ReadProvider{
  bytes=0; constructor(public inner:MemoryProvider){}
  get calls(){return this.inner.calls}
  access(t:any,o:any){return this.inner.access(t,o)}
  resolve(t:any){return this.inner.resolve(t)}
  inspect(t:any,s:any){return this.inner.inspect(t,s)}
  async file(t:any,s:any,p:any){const f=await this.inner.file(t,s,p);this.bytes+=Buffer.from(f.base64,"base64").length;return f}
}
function req(mode:"exact"|"current",batch=false,routed=false):any{
  const records=batch?Array.from({length:5},(_,i)=>({key:`r${i}`,path:"state/work.json",format:"json",select:[i%2?"count":"status"]})):routed?[{key:"work",route:"work"}]:[{key:"work",path:"state/work.json",format:"json",select:["status"]}];
  const out:any={protocol:PROTOCOL,op:"read",target,at:mode==="exact"?{snapshot:{id:A}}:{current:true},records};if(routed)out.resolver=ROUTER_V1;return out;
}
async function runCase(name:string,w:MemoryWorld,r:any){const m=new Metered(new MemoryProvider(structuredClone(w)));const out=await new Reader(m,caps).read(r);const c=m.calls;return {case:name,mutable_ref_resolutions:c.resolve??0,provider_operations:Object.values(c).reduce((a,b)=>a+b,0),file_reads:c.file??0,model_visible_bytes:Buffer.byteLength(canonicalJson(out)),provider_returned_bytes:m.bytes};}
async function baseline(compact=false){const m=new Metered(new MemoryProvider(makeWorld()));await m.access(target,"read");await m.file(target,A,"state/work.json");const out=compact?Array.from({length:5},(_,i)=>i%2?{count:1}:{status:"working"}):{status:"working"};return {case:compact?"compact_batch_baseline":"direct_pinned_file_baseline",mutable_ref_resolutions:0,provider_operations:2,file_reads:1,model_visible_bytes:Buffer.byteLength(JSON.stringify(out)),provider_returned_bytes:m.bytes};}
const out:any[]=[await runCase("exact",makeWorld(),req("exact")),await runCase("current",makeWorld(),req("current")),await runCase("batch5",makeWorld(),req("current",true)),await baseline(),await baseline(true)];
for(const n of scales)out.push({...await runCase(`fixed_router_${n}`,makeWorld(n,false),req("current",false,true)),scale:n});
for(const n of scales)out.push({...await runCase(`growing_router_${n}`,makeWorld(n,true),req("current",false,true)),scale:n});
process.stdout.write(JSON.stringify(out));
