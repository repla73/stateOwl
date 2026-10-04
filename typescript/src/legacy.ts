import { parseStrictJson } from "./encoding.js";
import type { Json } from "./types.js";

type LegacyFile = { bytes: Uint8Array; blob: string };
export interface LegacyReadProvider {
  resolve(repository: string, ref: string): Promise<string>;
  file(repository: string, commit: string, path: string): Promise<LegacyFile>;
}
export type LegacyReadRequest = { repository: string; route: string; expected_head?: string; select?: string[]; expand?: string[] };

const isObj=(x:unknown):x is Record<string,unknown>=>!!x&&typeof x==="object"&&!Array.isArray(x);
const project=(o:Record<string,unknown>, keys:string[])=>Object.fromEntries(keys.filter(k=>Object.prototype.hasOwnProperty.call(o,k)).map(k=>[k,o[k]]));
const legacyError=(code:string):never=>{const e=new Error(code);e.name="LegacyStateOwlError";throw e;};

export class LegacyReader {
  constructor(private provider: LegacyReadProvider, private ref="refs/heads/main"){}
  async read(req:LegacyReadRequest):Promise<unknown>{
    const head=await this.provider.resolve(req.repository,this.ref);
    if(req.expected_head!==undefined&&req.expected_head!==head) legacyError("EXPECTED_HEAD_MISMATCH");
    const routerFile=await this.provider.file(req.repository,head,".stateowl/router.json");
    const router:Json=(()=>{try{return parseStrictJson(routerFile.bytes);}catch{return legacyError("JSON_DUPLICATE_KEY");}})();
    if(!isObj(router))legacyError("INVALID_ROUTER");
    const ro=router as Record<string,unknown>;
    if(ro.schema!=="stateowl.router/v1"||!isObj(ro.routes))legacyError("INVALID_ROUTER");
    const route=(ro.routes as Record<string,unknown>)[req.route];if(!isObj(route)||typeof route.path!=="string"||!Array.isArray(route.select))legacyError("ROUTE_NOT_FOUND");
    const routeObj=route as Record<string,unknown>;
    const recordFile=await this.provider.file(req.repository,head,routeObj.path as string);
    const record:Json=(()=>{try{return parseStrictJson(recordFile.bytes);}catch{return legacyError("INVALID_JSON");}})();
    if(!isObj(record))legacyError("INVALID_RECORD");
    const recObj=record as Record<string,unknown>;
    const select=req.select??(routeObj.select as string[]);
    const result:any={route:req.route,head:{repository:req.repository,ref:this.ref,commit:head},value:project(recObj,select),sources:{router:{repository:req.repository,commit:head,path:".stateowl/router.json",blob:routerFile.blob},record:{repository:req.repository,commit:head,path:routeObj.path,blob:recordFile.blob}}};
    if(req.expand?.length){const links=recObj.links;if(!isObj(links))legacyError("LINK_NOT_FOUND");const linkMap=links as Record<string,unknown>;result.expanded={};for(const name of req.expand){const link=linkMap[name];if(!isObj(link)||typeof link.path!=="string")legacyError("LINK_NOT_FOUND");const linkObj=link as Record<string,unknown>;const repository=typeof linkObj.repository==="string"?linkObj.repository:req.repository;if(repository!==req.repository&&typeof linkObj.commit!=="string")legacyError("LINK_COMMIT_REQUIRED");const commit=typeof linkObj.commit==="string"?linkObj.commit:head;const path=linkObj.path as string;const f=await this.provider.file(repository,commit,path);const format=typeof linkObj.format==="string"?linkObj.format:"json";let value:unknown;if(format==="text")value=new TextDecoder("utf-8",{fatal:true}).decode(f.bytes);else{const parsed=parseStrictJson(f.bytes);value=Array.isArray(linkObj.select)&&isObj(parsed)?project(parsed,linkObj.select as string[]):parsed;}result.expanded[name]={value,source:{repository,commit,path,blob:f.blob}};}}
    return result;
  }
}
