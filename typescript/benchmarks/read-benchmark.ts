import { mkdtempSync, rmSync, writeFileSync, mkdirSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { execFileSync } from "node:child_process";
import { performance } from "node:perf_hooks";
import { Reader } from "../src/reader.js";
import { MemoryProvider, type MemoryWorld } from "../src/providers/memory.js";
import { LocalGitProvider } from "../src/providers/local-git.js";
import { canonicalJson, parseStrictJson } from "../src/encoding.js";
import { PROTOCOL, ROUTER_V1, type Capabilities, type Json, type Target } from "../src/types.js";

const A="git:sha1:"+"a".repeat(40);
const target:Target={kind:"git",authority:"github.com",resource:"fixture/project",namespace:"refs/heads/state"};
const caps:Capabilities={protocol:PROTOCOL,operations:["read"],formats:["json","text","base64"],features:["routes","expand"],resolvers:[ROUTER_V1],limits:{request_bytes:1<<20,record_bytes:64<<20,mutation_bytes:1<<20,response_bytes:64<<20,records:64,expansions:32,changes:32,tag_hops:8,reconcile_commits:16,json_depth:64}};
const enc=(s:string)=>Buffer.from(s).toString("base64");
const work={base64:enc('{"id":"work","status":"working","count":1,"noise":"omit"}\n'),mode:"100644"};
const directReq=(current:boolean,records=1)=>({protocol:PROTOCOL,op:"read",target,at:current?{current:true}:{snapshot:{id:A}},records:Array.from({length:records},(_,i)=>({key:`r${i}`,path:"state/work.json",format:"json",select:[i%2?"count":"status"]}))});
function world(unrelated=0,routerEntries=0):MemoryWorld{
 const files:Record<string,{base64:string;mode:string}>={"state/work.json":work};
 for(let i=0;i<unrelated;i++)files[`unrelated/${i}.json`]={base64:"e30K",mode:"100644"};
 if(routerEntries>=0){const routes:any={work:{path:"state/work.json",select:["id","status"]}};for(let i=0;i<routerEntries;i++)routes[`unused-${i}`]={path:`unrelated/${i}.json`,select:[]};files[".stateowl/router.json"]={base64:enc(JSON.stringify({schema:"stateowl.router/v1",routes})+"\n"),mode:"100644"};}
 return {target,head:A,native:true,algorithm:"sha1",objects:{[A]:{type:"commit",parents:[],message:"base\n",files}}};
}
function bytes(v:unknown){return Buffer.byteLength(canonicalJson(v as Json));}
function calls(p:MemoryProvider){return Object.values(p.calls).reduce((a,b)=>a+b,0)}
async function runMemory(label:string,w:MemoryWorld,req:any,iterations=30){let total=0,last:any,pcalls:any;for(let i=0;i<iterations;i++){const p=new MemoryProvider(structuredClone(w));const r=new Reader(p,caps);const t=performance.now();last=await r.read(req);total+=performance.now()-t;pcalls=p.calls;}return {label,mean_ms:+(total/iterations).toFixed(4),provider_calls_total:Object.values(pcalls).reduce((a:any,b:any)=>a+b,0),provider_calls:pcalls,model_visible_bytes:bytes(last),token_approximation_4bytes:+(bytes(last)/4).toFixed(2)};}
async function directPinnedBaseline(){const p=new MemoryProvider(world());await p.access(target,"read");const t=performance.now();const f=await p.file(target,A,"state/work.json");const parsed=parseStrictJson(Buffer.from(f.base64,"base64")) as any;const result={status:parsed.status};return {label:"direct_pinned_file_baseline",mean_ms:+(performance.now()-t).toFixed(4),provider_calls_total:1,model_visible_bytes:Buffer.byteLength(JSON.stringify(result)),token_approximation_4bytes:+(Buffer.byteLength(JSON.stringify(result))/4).toFixed(2)};}
async function compactBatchBaseline(){const p=new MemoryProvider(world());await p.access(target,"read");const t=performance.now();const f=await p.file(target,A,"state/work.json");const parsed=parseStrictJson(Buffer.from(f.base64,"base64")) as any;const result=Array.from({length:5},(_,i)=>i%2?{count:parsed.count}:{status:parsed.status});return {label:"compact_batch_baseline_5",mean_ms:+(performance.now()-t).toFixed(4),provider_calls_total:1,model_visible_bytes:Buffer.byteLength(JSON.stringify(result)),token_approximation_4bytes:+(Buffer.byteLength(JSON.stringify(result))/4).toFixed(2)};}
function coldStart(){const t=performance.now();execFileSync(process.execPath,["-e",`import(${JSON.stringify(new URL("../src/index.js",import.meta.url).href)}).catch(()=>process.exit(1))`],{stdio:"ignore"});return +(performance.now()-t).toFixed(3)}
async function localReal(){const dir=mkdtempSync(join(tmpdir(),"stateowl-bench-"));try{execFileSync("git",["init","-q",dir]);execFileSync("git",["-C",dir,"config","user.email","bench@example.invalid"]);execFileSync("git",["-C",dir,"config","user.name","bench"]);mkdirSync(join(dir,"state"));writeFileSync(join(dir,"state/work.json"),Buffer.from(work.base64,"base64"));execFileSync("git",["-C",dir,"add","."]);execFileSync("git",["-C",dir,"commit","-qm","base"]);const sha=String(execFileSync("git",["-C",dir,"rev-parse","HEAD"],{encoding:"utf8"})).trim();execFileSync("git",["-C",dir,"branch","state",sha]);const t:Target={...target,resource:"local/fixture",namespace:"refs/heads/state"};const p=new LocalGitProvider(dir,t);const r=new Reader(p,caps);const snap={id:`git:sha1:${sha}`};const exact={protocol:PROTOCOL,op:"read",target:t,at:{snapshot:snap},records:[{key:"work",path:"state/work.json",format:"json",select:["status"]}]};const current={...exact,at:{current:true}};const one=async(req:any,n=20)=>{let d=0;for(let i=0;i<n;i++){const s=performance.now();await r.read(req);d+=performance.now()-s;}return +(d/n).toFixed(4)};return {exact_mean_ms:await one(exact),current_mean_ms:await one(current)};}finally{rmSync(dir,{recursive:true,force:true})}}

const results:any={basis:"05278c225eb302697e8b31406d06f98022ab7d3c",protocol:PROTOCOL,evidence_type:"mixed",environment:{node:process.version,platform:process.platform,arch:process.arch,token_metric:"serialized semantic response UTF-8 bytes / 4; approximation, not a model tokenizer"},cold_start_ms:coldStart(),paths:[],unrelated_state_scaling:[],router_metadata_scaling:[],local_real_git:await localReal()};
results.paths.push(await runMemory("exact_read",world(),directReq(false)));
results.paths.push(await runMemory("current_read",world(),directReq(true)));
results.paths.push(await runMemory("batch_5_same_file",world(),directReq(true,5)));
results.paths.push(await directPinnedBaseline());results.paths.push(await compactBatchBaseline());
for(const n of [0,100,10000,100000])results.unrelated_state_scaling.push({unrelated_records:n,...await runMemory(`exact_unrelated_${n}`,world(n),directReq(false),10)});
for(const n of [0,100,10000,100000]){const w=world(0,n);const req={protocol:PROTOCOL,op:"read",target,at:{current:true},records:[{key:"work",route:"work"}],resolver:ROUTER_V1};const routerBytes=Buffer.from(w.objects[A]!.files![".stateowl/router.json"]!.base64,"base64").length;results.router_metadata_scaling.push({extra_routes:n,router_bytes:routerBytes,...await runMemory(`route_growth_${n}`,w,req,5)});}
process.stdout.write(JSON.stringify(results,null,2)+"\n");
