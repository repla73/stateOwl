import { PROTOCOL, ROUTER_V1, type Capabilities, type Target } from "../src/types.js";
import type { MemoryWorld } from "../src/providers/memory.js";

export const A="git:sha1:"+"a".repeat(40), B="git:sha1:"+"b".repeat(40), T="git:sha1:"+"f".repeat(40), G="git:sha1:"+"1".repeat(40);
export const target:Target={kind:"git",authority:"github.com",resource:"fixture/project",namespace:"refs/heads/state"};
export const tagTarget:Target={...target,namespace:"refs/tags/release"};
export const capabilities:Capabilities={protocol:PROTOCOL,operations:["read"],formats:["json","text","base64"],features:["routes","expand"],resolvers:[ROUTER_V1],limits:{request_bytes:65536,record_bytes:16384,mutation_bytes:32768,response_bytes:65536,records:32,expansions:16,changes:32,tag_hops:8,reconcile_commits:16,json_depth:64}};
const enc=(s:string)=>Buffer.from(s,"utf8").toString("base64");
export const files={
 ".stateowl/router.json":{base64:enc('{"schema":"stateowl.router/v1","routes":{"work":{"path":"state/work.json","select":["id","status"]}}}\n'),mode:"100644"},
 "state/work.json":{base64:enc('{"id":"work","status":"working","count":1,"noise":"omit","links":{"detail":{"path":"state/detail.txt","format":"text"},"checks":{"path":"state/checks.json","select":["status"]}}}\n'),mode:"100644"},
 "state/detail.txt":{base64:enc("detail\n"),mode:"100644"},
 "state/checks.json":{base64:enc('{"status":"pass","other":1}\n'),mode:"100644"},
 "state/binary":{base64:"AP8=",mode:"100644"}
};
export function world():MemoryWorld{return {target,head:A,native:true,algorithm:"sha1",objects:{[A]:{type:"commit",parents:[],message:"base\n",files:structuredClone(files)}}};}
export const exact=(records:any[])=>({protocol:PROTOCOL,op:"read",target,at:{snapshot:{id:A}},records});
export const current=(records:any[])=>({protocol:PROTOCOL,op:"read",target,at:{current:true},records});
