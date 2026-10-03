import { canonicalJson, canonicalBase64, parseStrictJson, sha256 } from "./encoding.js";
import { gitAlgorithm, gitBlobId, validateGitTarget } from "./git.js";
import { PROTOCOL, ROUTER_V1, ProtocolError, type Capabilities, type Format, type Json, type ReadProvider, type ReadRequest, type Selection, type Snapshot, type Source, type Target } from "./types.js";

const retry:Record<string,string>={
  INVALID_REQUEST:"after_correction",NOT_FOUND:"after_correction",EXACT_SNAPSHOT_REQUIRED:"after_correction",INVALID_SOURCE:"after_correction",NUMBER_UNREPRESENTABLE:"after_correction",LIMIT_EXCEEDED:"after_correction",VALIDATION_FAILED:"after_correction",
  UNAUTHENTICATED:"after_refresh",CONFLICT:"after_refresh",NAMESPACE_DISCONTINUITY:"after_refresh",TOKEN_INVALID:"after_refresh",RATE_LIMITED:"after_backoff",PROVIDER_UNAVAILABLE:"after_backoff",
  UNSUPPORTED_VERSION:"never",UNSUPPORTED_CAPABILITY:"never",FORBIDDEN:"never",NOT_FOUND_OR_FORBIDDEN:"never",SNAPSHOT_UNAVAILABLE:"never",INTEGRITY_MISMATCH:"never",NO_CHANGE:"never",HISTORY_UNAVAILABLE:"never"
};
const err=(code:string, op:"read"|"unknown"="read")=>({protocol:PROTOCOL,op,status:"error",error:{code,retry:retry[code]}});
const isObj=(x:unknown):x is Record<string,unknown>=>!!x&&typeof x==="object"&&!Array.isArray(x);
const keysExact=(o:Record<string,unknown>, allowed:string[])=>Object.keys(o).every(k=>allowed.includes(k));
const validPath=(p:unknown):p is string=>typeof p==="string"&&p.length>0&&!p.startsWith("/")&&!p.endsWith("/")&&!p.includes("\\")&&!/[\x00-\x1f\x7f]/.test(p)&&p.split("/").every(x=>x!==""&&x!=="."&&x!=="..");
const uniq=(a:unknown[], pred:(x:unknown)=>boolean)=>a.every(pred)&&new Set(a as unknown[]).size===a.length;
const sameTarget=(a:Target,b:Target)=>a.kind===b.kind&&a.authority===b.authority&&a.resource===b.resource&&a.namespace===b.namespace;

function validateSelection(s:unknown): asserts s is Selection {
  if(!isObj(s)||typeof s.key!=="string"||!s.key)throw new ProtocolError("INVALID_REQUEST");
  const hasPath="path" in s, hasRoute="route" in s; if(hasPath===hasRoute)throw new ProtocolError("INVALID_REQUEST");
  if(hasPath){if(!keysExact(s,["key","path","format","select","optional","expand"])||!validPath(s.path)||!(["json","text","base64"] as unknown[]).includes(s.format))throw new ProtocolError("INVALID_REQUEST");if("select" in s&&s.format!=="json")throw new ProtocolError("INVALID_REQUEST");}
  else {if(!keysExact(s,["key","route","select","optional","expand"])||typeof s.route!=="string"||!s.route)throw new ProtocolError("INVALID_REQUEST");}
  if("select" in s&&(!Array.isArray(s.select)||!uniq(s.select,x=>typeof x==="string")))throw new ProtocolError("INVALID_REQUEST");
  if("optional" in s&&typeof s.optional!=="boolean")throw new ProtocolError("INVALID_REQUEST");
  if("expand" in s&&(!Array.isArray(s.expand)||!uniq(s.expand,x=>typeof x==="string"&&x.length>0)))throw new ProtocolError("INVALID_REQUEST");
}
function validateRequest(r:unknown, bytes:number, cap:Capabilities): asserts r is ReadRequest {
  if(bytes>cap.limits.request_bytes)throw new ProtocolError("LIMIT_EXCEEDED");
  if(!isObj(r)||typeof r.protocol!=="string")throw new ProtocolError("INVALID_REQUEST");
  if(r.protocol!==PROTOCOL)throw new ProtocolError("UNSUPPORTED_VERSION");
  if(!keysExact(r,["protocol","op","target","at","records","resolver"])||r.op!=="read"||!isObj(r.target)||!keysExact(r.target,["kind","authority","resource","namespace"])||![r.target.kind,r.target.authority,r.target.resource,r.target.namespace].every(x=>typeof x==="string"&&x.length>0))throw new ProtocolError("INVALID_REQUEST");
  validateGitTarget(r.target as Target);
  if(!isObj(r.at)||!(keysExact(r.at,["current","assert_snapshot"])&&r.at.current===true || keysExact(r.at,["snapshot"])))throw new ProtocolError("INVALID_REQUEST");
  const snap=(r.at as Record<string,unknown>).snapshot, ass=(r.at as Record<string,unknown>).assert_snapshot;
  for(const x of [snap,ass])if(x!==undefined&&(!isObj(x)||!keysExact(x,["id"])||typeof x.id!=="string"||!x.id))throw new ProtocolError("INVALID_REQUEST");
  if(!Array.isArray(r.records)||r.records.length<1)throw new ProtocolError("INVALID_REQUEST");
  for(const s of r.records)validateSelection(s); if(new Set((r.records as Selection[]).map(s=>s.key)).size!==r.records.length)throw new ProtocolError("INVALID_REQUEST");
  const needsResolver=(r.records as Selection[]).some(s=>s.route!==undefined||(s.expand?.length??0)>0);
  if(needsResolver?(typeof r.resolver!=="string"||!r.resolver):("resolver" in r))throw new ProtocolError("INVALID_REQUEST");
  if(r.records.length>cap.limits.records)throw new ProtocolError("LIMIT_EXCEEDED");
  const expansions=(r.records as Selection[]).reduce((n,s)=>n+(s.expand?.length??0),0);if(expansions>cap.limits.expansions)throw new ProtocolError("LIMIT_EXCEEDED");
}

export class Reader {
  constructor(private provider:ReadProvider, public capabilities:Capabilities){}
  async read(input:ReadRequest|string|Uint8Array):Promise<any>{
    let request:unknown, requestBytes:Uint8Array;
    try{
      if(typeof input==="string")requestBytes=Buffer.from(input,"utf8"); else if(input instanceof Uint8Array)requestBytes=input; else requestBytes=Buffer.from(JSON.stringify(input),"utf8");
      request=parseStrictJson(requestBytes,this.capabilities.limits.json_depth);
      validateRequest(request,requestBytes.byteLength,this.capabilities);
    }catch(e){
      const code=e instanceof ProtocolError?(e.code==="INVALID_SOURCE"?"INVALID_REQUEST":e.code):"INVALID_REQUEST";
      return err(code,"unknown");
    }
    const r=request as ReadRequest;
    try{
      if(!this.capabilities.operations.includes("read"))throw new ProtocolError("UNSUPPORTED_CAPABILITY");
      for(const s of r.records)if(s.format&&!this.capabilities.formats.includes(s.format))throw new ProtocolError("UNSUPPORTED_CAPABILITY");
      if(r.records.some(s=>s.route!==undefined)&&!this.capabilities.features.includes("routes"))throw new ProtocolError("UNSUPPORTED_CAPABILITY");
      if(r.records.some(s=>(s.expand?.length??0)>0)&&!this.capabilities.features.includes("expand"))throw new ProtocolError("UNSUPPORTED_CAPABILITY");
      if(r.resolver&&!this.capabilities.resolvers.includes(r.resolver))throw new ProtocolError("UNSUPPORTED_CAPABILITY");
      await this.provider.access(r.target,"read");
      let rootId:string;
      if("snapshot" in r.at) rootId=await this.exactCommit(r.target,r.at.snapshot.id,false);
      else {const raw=await this.provider.resolve(r.target); rootId=await this.exactCommit(r.target,raw,true);if(r.at.assert_snapshot&&r.at.assert_snapshot.id!==rootId)throw new ProtocolError("CONFLICT");}
      const root={id:rootId};
      const cache=new Map<string,Awaited<ReturnType<Reader["load"]>>>(); const routing:Source[]=[]; const routeCache:{value?:Record<string,unknown>,source?:Source}={};
      const loadCached=async(t:Target,snap:string,path:string)=>{const k=canonicalJson([t.kind,t.authority,t.resource,t.namespace,snap,path] as unknown as Json);if(!cache.has(k))cache.set(k,await this.load(t,snap,path));return cache.get(k)!};
      const records=[];
      for(const sel of r.records){
        let path:string,format:Format,select:string[]|undefined, parentRaw:Json|undefined;
        if(sel.route!==undefined){
          if(r.resolver!==ROUTER_V1)throw new ProtocolError("UNSUPPORTED_CAPABILITY");
          if(!routeCache.value){const rr=await loadCached(r.target,rootId,".stateowl/router.json"); if(rr.absent)throw new ProtocolError("NOT_FOUND"); const obj=this.router(rr.value!);routeCache.value=obj;routeCache.source=rr.source; routing.push(rr.source!);}
          const routes=routeCache.value.routes as Record<string,unknown>; if(!(sel.route in routes))throw new ProtocolError("NOT_FOUND"); const entry=routes[sel.route];
          if(!isObj(entry)||!keysExact(entry,["path","select"])||!validPath(entry.path)||!Array.isArray(entry.select)||!uniq(entry.select,x=>typeof x==="string"&&x.length>0))throw new ProtocolError("INVALID_SOURCE");
          path=entry.path;format="json";select=sel.select??(entry.select as string[]);
        }else {path=sel.path!;format=sel.format!;select=sel.select;}
        const loaded=await loadCached(r.target,rootId,path);
        if(loaded.absent){if(sel.optional){records.push({key:sel.key,status:"absent",path});continue;}throw new ProtocolError("NOT_FOUND");}
        parentRaw=loaded.value; if(format==="json"&&parentRaw===undefined) parentRaw=parseStrictJson(loaded.bytes,this.capabilities.limits.json_depth);
        if(sel.route!==undefined && (!isObj(parentRaw)))throw new ProtocolError("INVALID_SOURCE");
        const rec:any={key:sel.key,status:"found",format,value:this.represent(format,parentRaw,loaded.bytes)};rec.source=loaded.source;
        if(select!==undefined){if(format!=="json"||!isObj(parentRaw))throw new ProtocolError("INVALID_REQUEST"); const projected:Record<string,Json>={}; const missing:string[]=[];for(const k of select){if(Object.prototype.hasOwnProperty.call(parentRaw,k))projected[k]=parentRaw[k] as Json;else missing.push(k);}rec.value=projected;rec.select=select;rec.missing=missing;}
        if(sel.expand?.length){
          if(!routing.some(s=>s.path===loaded.source!.path&&(!s.origin||canonicalJson(s.origin as unknown as Json)===canonicalJson(loaded.source!.origin as unknown as Json))))routing.push(loaded.source!);
          if(!isObj(parentRaw))throw new ProtocolError("INVALID_SOURCE"); const links=parentRaw.links===undefined?{}:parentRaw.links;if(!isObj(links))throw new ProtocolError("INVALID_SOURCE"); const expanded=[];
          for(const name of sel.expand){if(!(name in links))throw new ProtocolError("NOT_FOUND");const l=links[name];if(!isObj(l)||!keysExact(l,["path","repository","commit","format","select"])||!validPath(l.path))throw new ProtocolError("INVALID_SOURCE");
            if("repository" in l&&(typeof l.repository!=="string"||!this.legacyRepo(l.repository)))throw new ProtocolError("INVALID_SOURCE");if("commit" in l&&(typeof l.commit!=="string"||!/^[0-9a-f]{40}$/.test(l.commit)))throw new ProtocolError("INVALID_SOURCE");
            const lf=(l.format??"json") as Format;if(!["json","text"].includes(lf))throw new ProtocolError("INVALID_SOURCE");if("select" in l&&(!Array.isArray(l.select)||!uniq(l.select,x=>typeof x==="string"&&x.length>0)||lf!=="json"))throw new ProtocolError("INVALID_SOURCE");
            let target=r.target,snapshot=rootId; const repo=(l.repository as string|undefined)??r.target.resource; if(repo!==r.target.resource){if(!l.commit)throw new ProtocolError("EXACT_SNAPSHOT_REQUIRED");target={...r.target,resource:repo};snapshot=`git:sha1:${l.commit}`;await this.provider.access(target,"read");await this.exactCommit(target,snapshot,false);} else if(l.commit){snapshot=`git:sha1:${l.commit}`;await this.exactCommit(target,snapshot,false);}
            const child=await loadCached(target,snapshot,l.path as string);if(child.absent)throw new ProtocolError("NOT_FOUND");let childValue=child.value;if(lf==="json"&&childValue===undefined)childValue=parseStrictJson(child.bytes,this.capabilities.limits.json_depth);const er:any={key:name,status:"found",format:lf,value:this.represent(lf,childValue,child.bytes),source:{...child.source}};
            if(!sameTarget(target,r.target)||snapshot!==rootId)er.source.origin={target,snapshot:{id:snapshot}};
            if(l.select!==undefined){if(!isObj(childValue))throw new ProtocolError("INVALID_SOURCE");const v:Record<string,Json>={},missing:string[]=[];for(const k of l.select as string[]){if(Object.prototype.hasOwnProperty.call(childValue,k))v[k]=childValue[k] as Json;else missing.push(k);}er.value=v;er.select=l.select;er.missing=missing;}
            expanded.push(er);
          } rec.expanded=expanded;
        }
        records.push(rec);
      }
      const response:any={protocol:PROTOCOL,op:"read",status:"ok",target:r.target,snapshot:root,records};if(r.resolver)response.routing={binding:r.resolver,sources:routing};
      const bytes=Buffer.byteLength(canonicalJson(response as Json),"utf8");if(bytes>this.capabilities.limits.response_bytes)throw new ProtocolError("LIMIT_EXCEEDED");return response;
    }catch(e){return err(e instanceof ProtocolError?e.code:"PROVIDER_UNAVAILABLE");}
  }
  private legacyRepo(x:string){const m=/^([A-Za-z0-9_.-]+)\/([A-Za-z0-9_.-]+)$/.exec(x);return !!m&&m[1]!=="."&&m[1]!==".."&&m[2]!=="."&&m[2]!=="..";}
  private router(v:Json):Record<string,unknown>{if(!isObj(v)||!keysExact(v,["schema","routes"])||v.schema!=="stateowl.router/v1"||!isObj(v.routes)||Object.keys(v.routes).length<1)throw new ProtocolError("INVALID_SOURCE");return v;}
  private represent(format:Format,v:Json|undefined,bytes:Uint8Array):Json|string {if(format==="base64")return Buffer.from(bytes).toString("base64");if(format==="text"){try{return new TextDecoder("utf-8",{fatal:true}).decode(bytes)}catch{throw new ProtocolError("INVALID_SOURCE")}}return v!;}
  private async exactCommit(target:Target,id:string,fromRef:boolean):Promise<string>{
    if(target.kind!=="git"){const o=await this.provider.inspect(target,id);if(o.type!=="commit")throw new ProtocolError("INVALID_SOURCE");return id;}
    gitAlgorithm(id); let cur=id, hops=0, expectedType:string|undefined; const seen=new Set<string>();
    while(true){if(seen.has(cur))throw new ProtocolError("INVALID_SOURCE");seen.add(cur);const o=await this.provider.inspect(target,cur);if(o.id!==cur)throw new ProtocolError("INTEGRITY_MISMATCH");if(expectedType!==undefined&&o.type!==expectedType)throw new ProtocolError("INTEGRITY_MISMATCH");expectedType=undefined;if(o.type==="commit")return cur;
      if(!fromRef||!target.namespace.startsWith("refs/tags/")||o.type!=="tag")throw new ProtocolError("INVALID_SOURCE");if(hops>=this.capabilities.limits.tag_hops)throw new ProtocolError("LIMIT_EXCEEDED");if(typeof o.target!=="string")throw new ProtocolError("INVALID_SOURCE");if(o.target_type!==undefined&&o.target_type!=="tag"&&o.target_type!=="commit")throw new ProtocolError("INTEGRITY_MISMATCH");expectedType=o.target_type;cur=o.target;gitAlgorithm(cur);hops++;}
  }
  private async load(target:Target,snapshot:string,path:string,_unused?:unknown):Promise<{absent:boolean;bytes:Uint8Array;value?:Json;source?:Source}>{
    let f;try{f=await this.provider.file(target,snapshot,path)}catch(e){if(e instanceof ProtocolError&&e.code==="NOT_FOUND")return {absent:true,bytes:new Uint8Array()};throw e;}
    const bytes=canonicalBase64(f.base64);if(bytes.byteLength>this.capabilities.limits.record_bytes)throw new ProtocolError("LIMIT_EXCEEDED");if(f.digest!==sha256(bytes))throw new ProtocolError("INTEGRITY_MISMATCH");
    if(f.object&&target.kind==="git"&&f.object!==gitBlobId(bytes,gitAlgorithm(snapshot)))throw new ProtocolError("INTEGRITY_MISMATCH");if(f.mode!=="100644"&&f.mode!=="100755")throw new ProtocolError("INVALID_SOURCE");
    const source:Source={path,digest:f.digest,integrity:f.integrity};if(f.object)source.object=f.object; let value:Json|undefined; // parse JSON lazily by caller format is intentionally avoided: router/JSON callers need complete validation.
    if(path.endsWith(".json")||path===".stateowl/router.json"){value=parseStrictJson(bytes,this.capabilities.limits.json_depth);}return {absent:false,bytes,value,source};
  }
}
